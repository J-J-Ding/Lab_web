/* V5 domain client: reuses LabAuth CSRF/session state, keeps no credentials. */
(() => {
  'use strict';
  const root = new URL('../', document.currentScript.src);
  let generation = 0, alive = true, user = null, capabilities = null;
  const $ = s => document.querySelector(s);
  class ApiError extends Error {
    constructor(status, data) {
      super('请求失败');
      this.status = status;
      this.data = data;
    }
  }
  function status(text, error = false) {
    const node = $('#business-status');
    if (node) {
      node.textContent = text;
      node.dataset.kind = error ? 'error' : 'info';
    }
  }
  function errorText(error) {
    if (error.status === 409) return '内容已变化或当前状态不允许此操作。请重新读取后核对，未保存输入仍保留。';
    if (error.status === 403) return '没有操作权限或安全验证已过期，请核对登录状态后重试。';
    if (error.status === 404) return '该记录不存在或你没有访问权限。';
    if (error.status === 413) return '文件超过服务器允许大小，请改用更小文件。';
    if (error.status === 429) return '操作过于频繁，请稍后重试。';
    if (!error.status) return '连接中断，操作结果未确认，请先重新读取再决定是否重试。';
    if (error.status >= 500) return '服务暂不可用，操作未能确认，请稍后重新读取。';
    const data = error.data?.fields || error.data || {
    }
    ;
    const entries = Object.entries(data).filter(([k]) => !['code', 'fields'].includes(k));
    return entries.map(([k, v]) => `${k === 'detail' ? '' : k + '：'}${typeof v === 'string' ? v : JSON.stringify(v)}`).join('；') || '请核对输入资料。';
  }
  function showError(error, form) {
    if (error.silent) return;
    status(errorText(error), true);
    const fields = error.data?.fields || error.data || {
    }
    ;
    let first;
    for (const name of Object.keys(fields)) {
      const field = form?.elements.namedItem(name);
      if (field && field.setAttribute) {
        field.setAttribute('aria-invalid', 'true');
        field.setAttribute('aria-describedby', 'business-status');
        first ||= field;
      }
    }
    if (first?.getClientRects().length) first.focus();
  }
  async function request(path, {
    method = 'GET', data, file
  }
  = {
  }
  ) {
    const url = new URL(path, location.origin);
    if (url.origin !== location.origin || !url.pathname.startsWith('/api/')) throw new ApiError(400);
    if (method !== 'GET') generation += 1;
    const version = generation, controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const headers = {
        Accept: 'application/json'
      }
      ;
      if (method !== 'GET') {
        await LabAuth.ensureCsrf();
        headers['X-CSRFToken'] = LabAuth.csrfToken();
      }
      if (data !== undefined) headers['Content-Type'] = 'application/json';
      const response = await fetch(url, {
        method, headers, credentials: 'same-origin', cache: 'no-store', signal: controller.signal, ...(file ? {
          body: file
        }
        : data !== undefined ? {
          body: JSON.stringify(data)
        }
        : {
        }
        )
      }
      );
      let body = null;
      if (response.status !== 204) {
        if (!response.headers.get('Content-Type')?.includes('application/json')) throw new ApiError(response.ok ? 503 : response.status);
        body = await response.json();
      }
      if (!alive || version !== generation) {
        const stale = new Error('Stale response');
        stale.silent = true;
        throw stale;
      }
      if (!response.ok) {
        if (response.status === 403) {
          await LabAuth.refreshUser(true);
          await LabAuth.ensureCsrf(true);
        }
        throw new ApiError(response.status, body);
      }
      return body;
    }
    catch (error) {
      if (error instanceof ApiError || error.silent) throw error;
      throw new ApiError(0);
    }
    finally {
      clearTimeout(timer);
    }
  }
  function node(tag, text, attrs = {
  }
  ) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    for (const [key,value] of Object.entries(attrs)) el.setAttribute(key,value);
    return el;
  }
  function disabled(button, value) {
    if (button) {
      button.dataset.forbidden = value ? 'true' : 'false';
      button.disabled = value;
    }
  }
  function bind(form, action) {
    if (!form) return;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (form.dataset.busy) return;
      form.querySelectorAll('[aria-invalid]').forEach(el => el.removeAttribute('aria-invalid'));
      if (!form.checkValidity()) {
        status('请检查必填字段及格式。', true);
        form.reportValidity();
        return;
      }
      form.dataset.busy = 'true';
      const button = event.submitter;
      if (button) button.disabled = true;
      try {
        await action(form, event.submitter);
      }
      catch (error) {
        showError(error, form);
      }
      finally {
        delete form.dataset.busy;
        if (button) button.disabled = button.dataset.forbidden === 'true';
      }
    }
    );
  }
  function button(label, action) {
    const el = node('button', label, {
      type:'button'
    }
    );
    el.addEventListener('click', async () => {
      if (el.disabled) return;
      el.disabled = true;
      try {
        await action(el);
      }
      catch (error) {
        showError(error);
      }
      finally {
        el.disabled = el.dataset.forbidden === 'true';
      }
    }
    );
    return el;
  }
  const manager = u => !!u && (u.is_superuser || ['ADMIN','TEACHER'].includes(u.role));
  async function boot(management = false) {
    try {
      await LabAuth.ensureCsrf();
      const result = await LabAuth.refreshUser(true);
      if (result.status !== 'authenticated') {
        if (result.status === 'anonymous') {if(location.pathname.endsWith('/ai-import.html'))status('请登录后使用AI辅助填写，可先阅读流程说明。',true);else location.replace(new URL('login.html',root));}
        else status('账号服务暂不可用，请刷新重试。',true);
        return null;
      }
      user = result.user;
      document.querySelectorAll('.work-nav a').forEach(a=>{
        const path=new URL(a.href).pathname;
        if(path==='/resume.html')a.remove();
        if(['/workspace.html','/statistics.html','/manage/statistics.html'].includes(path)&&!user.capabilities.can_edit_content)a.hidden=true;
      });
      try { capabilities=await request("/api/content/capabilities/"); } catch(error) { if(error.status===404){status("协同功能尚未部署，请稍后重试。",true);return null;}throw error; }
      if (management && !manager(user)) {
        status('无管理权限。',true);
        return null;
      }
      document.querySelectorAll('[data-manager-only]').forEach(el => {
        el.hidden = !manager(user);
      }
      );
      $('#business-content').hidden = false;
      status('');
      return user;
    }
    catch (error) {
      showError(error);
      return null;
    }
  }
  document.addEventListener('lab-auth-state', event => {
    const result = event.detail;
    if (user && result.status === 'authenticated' && result.user.id === user.id && (result.user.role !== user.role || result.user.is_superuser !== user.is_superuser)) {
      generation += 1;
      $('#business-content')?.replaceChildren();
      if ($('#business-content')) $('#business-content').hidden = true;
      status('权限已变化，请刷新页面重新读取。', true);
      return;
    }
    if (user && (result.status !== 'authenticated' || result.user.id !== user.id)) {
      generation += 1;
      $('#business-content')?.replaceChildren();
      if ($('#business-content')) $('#business-content').hidden = true;
      if (result.status === 'anonymous') {if(location.pathname.endsWith('/ai-import.html'))status('请登录后使用AI辅助填写，可先阅读流程说明。',true);else location.replace(new URL('login.html',root));}
      else if (result.status === 'authenticated') location.reload();
      else status('账号服务暂不可用，请刷新重试。',true);
    }
    else if (user && result.status === 'authenticated' && document.body.dataset.management === 'true' && !manager(result.user)) {
      generation += 1;
      $('#business-content').replaceChildren();
      $('#business-content').hidden = true;
      status('无管理权限。',true);
    }
  }
  );
  document.addEventListener('lab-auth-state',event=>{
    if(user&&event.detail.status==='authenticated'&&event.detail.user.id===user.id)user=event.detail.user;
  }
  );
  window.addEventListener('pagehide', () => {
    alive=false;
    generation+=1;
    $('#business-content')?.replaceChildren();
    if ($('#business-content')) $('#business-content').hidden=true;
  }
  );
  window.addEventListener('pageshow', event => {
    if (event.persisted) location.reload();
  }
  );
  window.addEventListener('focus', () => {
    if (user && alive) LabAuth.refreshUser(true);
  }
  );
  window.LabContent = Object.freeze({
    request, boot, status, showError, bind, button, node, disabled, manager, root, get capabilities(){return capabilities;}, get user(){
      return user;
    }
  }
  );
}
)();
