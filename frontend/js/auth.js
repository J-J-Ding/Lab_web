/* Native same-origin account client. Credentials remain in browser-managed Cookies. */
(() => {
  'use strict';
  if (window.LabAuth) return;
  const root = new URL('../', document.currentScript.src);
  let state = { status: 'loading', user: null };
  let pendingUser = null;
  let csrfPending = null;
  let csrfReady = false;
  let epoch = 0;
  let initialized = false;
  let profileDirty = false;
  let renderedUserId = null;
  let suspended = false;
  // Ephemeral notifications only: no credentials or user data are shared or stored.
  const channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel('lab-web-account') : null;
  const $ = (selector) => document.querySelector(selector);
  const pageType = () => document.body?.dataset.authPage;
  const pageURL = (name) => new URL(name, root).href;
  const cookie = () => {
    const entry = document.cookie.split(';').map(x => x.trim()).find(x => x.startsWith('csrftoken='));
    return entry ? decodeURIComponent(entry.slice('csrftoken='.length)) : '';
  };
  class ApiError extends Error {
    constructor(status, data, retry) { super('Account request failed'); this.status = status; this.data = data; this.retry = retry; }
  }
  async function request(path, { method = 'GET', data } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const headers = { Accept: 'application/json' };
      if (data !== undefined) headers['Content-Type'] = 'application/json';
      if (method !== 'GET') {
        await ensureCsrf();
        headers['X-CSRFToken'] = cookie();
        if (!headers['X-CSRFToken']) throw new ApiError(403);
      }
      const response = await fetch(`/api/auth/${path}`, {
        method, headers, credentials: 'same-origin', cache: 'no-store',
        signal: controller.signal, ...(data !== undefined ? { body: JSON.stringify(data) } : {}),
      });
      let body = null;
      if (response.status !== 204) {
        if (!response.headers.get('Content-Type')?.includes('application/json')) throw new ApiError(503);
        try { body = await response.json(); } catch { throw new ApiError(503); }
      }
      if (!response.ok) throw new ApiError(response.status, body, response.headers.get('Retry-After'));
      return body;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(0);
    } finally { clearTimeout(timer); }
  }
  async function ensureCsrf(force = false) {
    if (cookie() && !force) { csrfReady = true; return; }
    if (csrfPending) return csrfPending;
    csrfPending = request('csrf/').then(() => {
      if (!cookie()) throw new ApiError(403);
      csrfReady = true;
    }).finally(() => { csrfPending = null; });
    return csrfPending;
  }
  function message(id, text, kind = 'info') {
    const element = document.getElementById(id);
    if (element) { element.textContent = text; element.dataset.kind = kind; }
  }
  function clearPasswords() {
    document.querySelectorAll('input[type="password"]').forEach(input => { input.value = ''; });
  }
  function hideProfile(clear = false) {
    if (pageType() !== 'profile') return;
    $('#profile-content').hidden = true;
    $('#profile-summary').hidden = true;
    document.querySelectorAll('#profile-content button').forEach(button => { button.disabled = true; });
    if (clear) {
      $('#profile-form').reset();
      profileDirty = false; renderedUserId = null;
      document.querySelectorAll('[data-user-name],[data-user-role]').forEach(element => { element.textContent = ''; });
      clearPasswords();
    }
  }
  function renderNavigation() {
    document.querySelectorAll('[data-auth-nav]').forEach(nav => {
      nav.querySelector('[data-auth-anonymous]').hidden = !['anonymous', 'unavailable'].includes(state.status);
      nav.querySelector('[data-auth-member]').hidden = state.status !== 'authenticated';
      const status = nav.querySelector('[data-auth-loading]');
      status.hidden = !['loading', 'unavailable'].includes(state.status);
      status.textContent = state.status === 'unavailable' ? '账号服务暂不可用' : '账号加载中…';
    });
  }
  function publish(status, user = null) {
    state = { status, user };
    renderNavigation();
    document.querySelectorAll('[data-auth-manager]').forEach(el => { el.hidden = !(status === 'authenticated' && (user.is_superuser || ['ADMIN','TEACHER'].includes(user.role))); });
    document.dispatchEvent(new CustomEvent('lab-auth-state', {detail: {status, user}}));
    if (pageType() !== 'profile' || suspended) return;
    if (status === 'anonymous') {
      hideProfile(true);
      location.replace(pageURL('login.html'));
    } else if (status === 'unavailable') {
      hideProfile(true);
      message('auth-status', '账号服务暂不可用，请稍后重试。', 'error');
      $('[data-auth-retry]').hidden = false;
    } else if (status === 'authenticated' && csrfReady) {
      $('[data-user-name]').textContent = user.username;
      const labels = { ADMIN: '管理员', TEACHER: '教师', STUDENT: '学生', CUSTOMER: '访客' };
      $('[data-user-role]').textContent = user.is_superuser ? 'ROOT（超级管理员）' : `${user.role}（${labels[user.role] || '未知身份'}）`;
      if (!profileDirty || renderedUserId !== user.id) {
        for (const field of ['first_name', 'last_name', 'email']) $('#profile-form').elements[field].value = user[field] || '';
        profileDirty = false;
      }
      renderedUserId = user.id;
      $('#profile-content').hidden = false;
      $('#profile-summary').hidden = false;
      document.querySelectorAll('#profile-content button').forEach(button => { button.disabled = Boolean(button.closest('form').dataset.busy); });
      message('auth-status', '');
      $('[data-auth-retry]').hidden = true;
    }
  }
  function invalidateUser() { epoch += 1; pendingUser = null; }
  function refreshUser(force = false) {
    if (pendingUser) return pendingUser;
    if (!force && state.status !== 'loading') return Promise.resolve(state);
    const version = epoch;
    const operation = request('me/').then(user => {
      if (version === epoch) publish('authenticated', user);
      return state;
    }).catch(error => {
      if (version === epoch) publish(error.status === 403 ? 'anonymous' : 'unavailable');
      return state;
    }).finally(() => { if (pendingUser === operation) pendingUser = null; });
    pendingUser = operation;
    return operation;
  }
  function errorText(error) {
    if (error.status === 403) return '安全验证已过期，请刷新后重试。';
    if (error.status === 429) return `登录尝试过于频繁，请在 ${Number(error.retry) || 60} 秒后重试。`;
    if (error.status === 0) return '网络连接中断，操作结果尚未确认。请重新查询后再试。';
    if (error.status >= 500 || error.status === 404) return '账号服务暂不可用，请稍后重试。';
    const labels = { username: '用户名', password: '密码', old_password: '旧密码', new_password: '新密码', email: '电子邮箱', first_name: '名字', last_name: '姓氏' };
    const translate = text => ({
      'Username already exists.': '用户名已存在，请使用其他用户名。',
      'Invalid username or password.': '用户名或密码错误，或账号不可用。',
      'Incorrect password.': '旧密码不正确。',
    }[text] || text);
    const parts = [];
    if (error.data && typeof error.data === 'object') {
      for (const [key, value] of Object.entries(error.data)) {
        if (!labels[key] && key !== 'detail' && key !== 'non_field_errors') continue;
        const values = Array.isArray(value) ? value : [value];
        for (const text of values) if (typeof text === 'string') parts.push(`${labels[key] ? labels[key] + '：' : ''}${translate(text)}`);
      }
    }
    return parts.join('\n') || '输入信息有误，请检查后重试。';
  }
  function markField(form, fieldName, statusId) {
    const input = form?.elements.namedItem(fieldName);
    if (!input || input.type === 'hidden') return null;
    input.setAttribute('aria-invalid', 'true');
    const ids = new Set((input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
    ids.add(statusId); input.setAttribute('aria-describedby', [...ids].join(' '));
    return input;
  }
  async function showError(id, error) {
    if (error.status === 403) {
      if (pageType() === 'profile') await refreshUser(true);
      try { await ensureCsrf(true); } catch { /* No automatic replay of writes. */ }
    }
    message(id, errorText(error), 'error');
    if (error.status === 400 && error.data) {
      const form = document.getElementById(id)?.closest('section')?.querySelector('form');
      let first = null;
      for (const key of Object.keys(error.data)) {
        const name = id === 'password-status' && key === 'password' ? 'new_password' : key;
        const input = markField(form, name, id);
        first ||= input;
      }
      if (first?.getClientRects().length) first.focus();
    }
  }
  function bindForm(id, statusId, action) {
    const form = document.getElementById(id);
    if (!form) return;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (form.dataset.busy) return;
      message(statusId, '');
      form.querySelectorAll('input').forEach(input => {
        input.removeAttribute('aria-invalid');
        const ids = (input.getAttribute('aria-describedby') || '').split(/\s+/).filter(id => id && id !== statusId);
        if (ids.length) input.setAttribute('aria-describedby', ids.join(' '));
        else input.removeAttribute('aria-describedby');
      });
      if (!form.checkValidity()) {
        message(statusId, '请检查必填项、格式和密码长度（至少 8 个字符）。', 'error');
        form.querySelectorAll(':invalid').forEach(input => markField(form, input.name, statusId));
        form.reportValidity(); return;
      }
      form.dataset.busy = 'true';
      const button = form.querySelector('[type="submit"]');
      const title = button.textContent;
      button.disabled = true; button.textContent = '正在提交…';
      try { await action(form); }
      catch (error) { await showError(statusId, error); }
      finally {
        delete form.dataset.busy;
        button.disabled = pageType() === 'profile' && state.status !== 'authenticated';
        button.textContent = title;
      }
    });
  }
  async function logout(button) {
    if (button.disabled) return;
    button.disabled = true;
    try {
      await request('logout/', { method: 'POST', data: {} });
      invalidateUser(); clearPasswords(); hideProfile(true);
      channel?.postMessage('session-changed');
      publish('anonymous');
      await refreshUser(true);
    } catch (error) {
      invalidateUser();
      await refreshUser(true);
      const status = button.closest('[data-auth-nav]').querySelector('[data-auth-loading]');
      status.hidden = false; status.textContent = '退出未完成，请重试';
      if (pageType() === 'profile') message('auth-status', errorText(error), 'error');
    } finally { button.disabled = false; }
  }
  function initNavigation(container) {
    container.querySelectorAll('[data-auth-logout]').forEach(button => {
      if (!button.dataset.bound) { button.dataset.bound = 'true'; button.addEventListener('click', () => logout(button)); }
    });
    renderNavigation();
    refreshUser();
  }
  async function bootstrap() {
    if (!pageType()) return;
    try {
      await ensureCsrf();
      document.querySelectorAll('#register-form button,#login-form button').forEach(button => { button.disabled = false; });
      await refreshUser(true);
      if (pageType() !== 'profile') {
        message('auth-status', '');
        $('[data-auth-retry]').hidden = true;
      }
    } catch (error) {
      hideProfile(true);
      message('auth-status', errorText(error), 'error');
      $('[data-auth-retry]').hidden = false;
    }
  }
  function initialize() {
    if (initialized) return;
    initialized = true;
    bindForm('register-form', 'register-status', async form => {
      if (form.elements.password.value !== form.elements.confirm_password.value) { message('register-status', '两次输入的密码不一致。', 'error'); return; }
      await request('register/', { method: 'POST', data: { username: form.elements.username.value, password: form.elements.password.value } });
      clearPasswords(); form.hidden = true;
      message('register-status', '注册成功，初始身份为 CUSTOMER（访客）。请前往登录。', 'success');
      $('#registered-login').hidden = false;
    });
    bindForm('login-form', 'login-status', async form => {
      await request('login/', { method: 'POST', data: { username: form.elements.username.value, password: form.elements.password.value } });
      clearPasswords(); invalidateUser();
      channel?.postMessage('session-changed');
      const result = await refreshUser(true);
      if (result.status !== 'authenticated') throw new ApiError(503);
      location.assign(pageURL('profile.html'));
    });
    bindForm('profile-form', 'profile-status', async form => {
      const data = {};
      for (const key of ['first_name', 'last_name', 'email']) data[key] = form.elements[key].value;
      await request('me/', { method: 'PATCH', data });
      profileDirty = false; invalidateUser();
      await refreshUser(true);
      if (state.status === 'authenticated') message('profile-status', '资料已保存。', 'success');
    });
    bindForm('password-form', 'password-status', async form => {
      if (form.elements.new_password.value !== form.elements.confirm_new_password.value) { message('password-status', '两次输入的新密码不一致。', 'error'); return; }
      await request('change-password/', { method: 'POST', data: { old_password: form.elements.old_password.value, new_password: form.elements.new_password.value } });
      clearPasswords(); invalidateUser(); await refreshUser(true);
      if (state.status === 'authenticated') message('password-status', '密码已修改，其他旧会话已失效。', 'success');
    });
    $('#profile-form')?.addEventListener('input', () => { profileDirty = true; });
    $('[data-auth-retry]')?.addEventListener('click', () => { invalidateUser(); bootstrap(); });
    if (pageType() === 'login' && new URLSearchParams(location.search).get('registered') === '1') message('login-status', '注册成功，请登录。', 'success');
    bootstrap();
  }
  function revalidateProfile() {
    if (!suspended && pageType() === 'profile' && document.visibilityState === 'visible') {
      hideProfile(); refreshUser(true);
    }
  }
  if (channel) channel.onmessage = event => {
    if (event.data !== 'session-changed') return;
    invalidateUser();
    hideProfile(true);
    refreshUser(true);
  };
  window.LabAuth = Object.freeze({ initNavigation, ensureCsrf, csrfToken: cookie, refreshUser });
  window.addEventListener('pagehide', () => { suspended = true; invalidateUser(); clearPasswords(); hideProfile(true); });
  window.addEventListener('pageshow', event => { suspended = false; if (event.persisted) { invalidateUser(); revalidateProfile(); } });
  window.addEventListener('focus', revalidateProfile);
  document.addEventListener('visibilitychange', revalidateProfile);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true });
  else initialize();
})();
