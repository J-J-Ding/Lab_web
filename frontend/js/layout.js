(() => {
 'use strict';
 const root=new URL('../',document.currentScript.src);
 async function load(){
  if(!document.querySelector('.site-footer')){
   try{const r=await fetch(new URL('data/footer-unified.html',root),{cache:'no-store'});if(r.ok){const slot=document.createElement('div');slot.innerHTML=await r.text();slot.querySelectorAll('a[href^="/"]').forEach(a=>a.href=new URL(a.getAttribute('href').slice(1),root));document.body.append(slot);}}catch(_){}
  }
  const main=document.querySelector('main');
  if(main&&location.pathname!=='/index.html'&&location.pathname!=='/'&&!main.querySelector('.breadcrumbs')){
   const nav=document.createElement('nav');nav.className='breadcrumbs';nav.setAttribute('aria-label','面包屑');const a=document.createElement('a');a.href=new URL('index.html',root);a.textContent='首页';nav.append(a,document.createTextNode(' / '+(document.querySelector('h1')?.textContent||document.title)));main.prepend(nav);
  }
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',load,{once:true});else load();
})();
