/* Session-aware website reader. No content or credentials are persisted. */
(() => {
 'use strict';if(window.LabSite)return;
 let epoch=0,key=null,pending,checked=0,state=null,authLoad;
 const clear=()=>{document.getElementById('home-visual')?._destroyCarousel?.();for(const selector of ['#public-content','#public-pagination','#stats-data','#home-news','#home-papers','#home-projects','#home-competitions','#home-members','#home-resources','#home-stats','#home-visual','#home-research','.search-results'])document.querySelectorAll(selector).forEach(el=>el.replaceChildren());};
 function changed(event){const s=event.detail,next=s.status+':'+(s.user?.id||'')+':'+(s.user?.role||'')+':'+!!s.user?.is_superuser;state=s;checked=Date.now();if(key!==null&&key!==next){epoch++;clear();document.dispatchEvent(new Event('site-access-changed'));}key=next;}
 document.addEventListener('lab-auth-state',changed);
 async function identity(){
  if(!window.LabAuth){authLoad||=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/js/auth.js?v=14-20261107-01';script.onload=resolve;script.onerror=reject;document.head.append(script);});await authLoad;}
  if(state&&Date.now()-checked<1000)return state;
  if(!pending)pending=LabAuth.refreshUser(true).finally(()=>pending=null);return pending;
 }
 async function get(path){
  const url=new URL(path,location.origin);if(url.origin!==location.origin||!/^\/api\/(public|site)\//.test(url.pathname))throw Error('无效资料地址');
  const session=await identity();if(session.status==='unavailable')throw Error('登录状态暂不可用，请重试。');
  url.pathname=url.pathname.replace('/api/public/','/api/site/');const version=epoch;
  const response=await fetch(url,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
  if(version!==epoch)throw Object.assign(Error('账号状态已变化'),{silent:true});
  if(!response.ok){if(response.status===403)LabAuth.refreshUser(true);throw Object.assign(Error(response.status===404?'内容不存在或当前账号不可查看':response.status===400?'查询条件无效，请检查输入':'资料暂不可用，请稍后重试'),{status:response.status});}
  const data=await response.json();if(version!==epoch)throw Object.assign(Error('账号状态已变化'),{silent:true});return data;
 }
 window.LabSite=Object.freeze({get,identity});
 window.addEventListener('focus',()=>{checked=0;identity().catch(clear);});
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){checked=0;identity().catch(clear);}});
 const poll=setInterval(()=>{if(document.visibilityState==='visible'){checked=0;identity().catch(clear);}},15000);
 window.addEventListener('pagehide',()=>{epoch++;clear();clearInterval(poll);});window.addEventListener('pageshow',e=>{if(e.persisted)location.reload();});
})();
