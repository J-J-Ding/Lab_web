/* Public responses are never cached or persisted; every request rechecks revocation. */
(function () {
  'use strict';
  const labels = {PATENT:'专利成果',PAPER:'发表论文',PROJECT:'课题项目',AWARD:'学科竞赛',PUBLICATION:'出版刊物',ACTIVITY:'团队活动',NEWS:'新闻动态',BLOG:'技术博客',MEMBER:'团队成员',GRADUATE:'成员去向'};
  const status = document.getElementById('public-status');
  const content = document.getElementById('public-content');
  let generation = 0;
  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = String(text ?? '');
    if (className) element.className = className;
    return element;
  }
  function link(text, href) {
    const anchor = node('a', text);
    const url = new URL(href, location.origin);
    if (!['http:','https:'].includes(url.protocol)) return node('span', text);
    anchor.href = url.href;
    if (url.origin !== location.origin) {anchor.rel='noopener noreferrer'; anchor.target='_blank';}
    return anchor;
  }
  async function get(path) {
    if (!path.startsWith('/api/public/')) throw new Error('无效的公开资源路径');
    let response;
    try {response = await fetch(path,{credentials:'omit',cache:'no-store',headers:{Accept:'application/json'}});}
    catch (_) {throw new Error('公开服务暂不可用，请稍后重试');}
    if (!response.ok) throw Object.assign(new Error(response.status===404?'内容不存在或尚未公开':response.status===400?'查询条件无效，请检查输入':'公开服务暂不可用，请稍后重试'),{status:response.status});
    try {return await response.json();} catch (_) {throw new Error('公开服务暂不可用，请稍后重试');}
  }
  async function run(action) {
    const version=++generation;
    content.replaceChildren(); status.textContent='正在加载公开资料…';
    document.getElementById('public-retry').hidden=true;
    try {
      await action(() => version === generation);
    } catch (error) {
      if (version !== generation) return;
      content.replaceChildren(); status.textContent=error.message;
      document.getElementById('public-retry').hidden=false;
    }
  }
  function ready(count) {status.textContent=count===0?'共 0 项符合条件的公开资料':count===undefined?'已加载公开资料':`共 ${count} 项公开资料`;}
  window.LabPublic={get,node,link,run,ready,labels,status,content};
  addEventListener('pagehide',()=>{generation++;content.replaceChildren();});
  addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
})();
