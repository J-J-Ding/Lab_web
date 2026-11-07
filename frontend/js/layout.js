(() => {
 'use strict';
 const root=new URL('../',document.currentScript.src);
 async function load(){
  if(!document.querySelector('.site-footer')){
   try{const r=await fetch(new URL('data/footer-unified.html',root),{cache:'no-store'});if(r.ok){const slot=document.createElement('div');slot.innerHTML=await r.text();slot.querySelectorAll('a[href^="/"]').forEach(a=>a.href=new URL(a.getAttribute('href').slice(1),root));document.body.append(slot);}}catch(_){}
  }
  document.querySelectorAll('[data-footer-year]').forEach(el=>el.textContent=new Date().getFullYear());
  const emailRow=document.querySelector('[data-footer-email]');
  if(emailRow){
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
   fetch(new URL('api/public/pages/contact/',root),{credentials:'omit',cache:'no-store',signal:controller.signal}).then(async response=>{
    if(!response.ok)return;const data=await response.json(),email=data.detail?.contact_email;
    if(typeof email==='string'&&email.includes('@')&&!/[\s<>]/.test(email)){const a=emailRow.querySelector('a');a.textContent=email;a.href='mailto:'+email;emailRow.hidden=false;}
   }).catch(()=>{}).finally(()=>clearTimeout(timer));
  }
  const main=document.querySelector('main');
  const groups=[
   [['/data/projects/index.html','科研项目'],['/data/papers/index.html','发表论文'],['/data/patents/index.html','专利成果'],['/data/publications/index.html','出版成果']],
   [['/data/competitions/index.html','学科竞赛'],['/data/competitions/index.html?category=HONOR','荣誉奖励']],
   [['/data/news/index.html','团队新闻'],['/data/activities/index.html','团队活动']],
   [['/resources.html','学习资料与下载'],['/data/blogs/index.html','技术博客']]
  ];
  const group=groups.find(items=>items.some(([href])=>new URL(href,location.origin).pathname===location.pathname));
  if(main&&group){const nav=document.createElement('nav');nav.className='section-tabs';nav.setAttribute('aria-label','栏目分类');for(const [href,text] of group){const a=document.createElement('a');a.href=href;a.textContent=text;const u=new URL(href,location.origin);if(u.pathname===location.pathname&&(u.searchParams.get('category')||'')===(new URLSearchParams(location.search).get('category')||''))a.setAttribute('aria-current','page');nav.append(a);}const intro=main.querySelector('.public-intro');if(intro)intro.after(nav);else main.prepend(nav);}
  for(const a of document.querySelectorAll('.work-nav a'))if(new URL(a.href).pathname===location.pathname)a.setAttribute('aria-current','page');

  if(main&&location.pathname!=='/index.html'&&location.pathname!=='/'&&!main.querySelector('.breadcrumbs')){
   const nav=document.createElement('nav');nav.className='breadcrumbs';nav.setAttribute('aria-label','面包屑');const a=document.createElement('a');a.href=new URL('index.html',root);a.textContent='首页';nav.append(a,document.createTextNode(' / '+(document.querySelector('h1')?.textContent||document.title)));main.prepend(nav);
  }
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',load,{once:true});else load();
})();
