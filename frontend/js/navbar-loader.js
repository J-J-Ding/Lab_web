/* Shared, code-owned navigation. No user content is inserted as HTML. */
(() => {
 'use strict';
 const root=new URL('../',document.currentScript.src);
 function script(path){return new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=new URL(path,root);s.onload=resolve;s.onerror=reject;document.head.append(s);});}
 async function load(){
  const target=document.getElementById('navbar-container');if(!target)return;
  try{
   const response=await fetch(new URL('data/navbar-unified.html',root),{cache:'no-store'});if(!response.ok)throw Error();
   target.innerHTML=await response.text();
   target.querySelectorAll('[href^="/"],[src^="/"]').forEach(el=>{for(const key of ['href','src'])if(el.getAttribute(key)?.startsWith('/'))el.setAttribute(key,new URL(el.getAttribute(key).slice(1),root));});
   const toggle=target.querySelector('.mobile-toggle'),menu=target.querySelector('.site-nav');
   toggle.addEventListener('click',()=>{const open=toggle.getAttribute('aria-expanded')!=='true';toggle.setAttribute('aria-expanded',String(open));menu.classList.toggle('is-open',open);});
   const groups=[...target.querySelectorAll('details')];
   groups.forEach(group=>{group.addEventListener('toggle',()=>{if(group.open)groups.filter(other=>other!==group).forEach(other=>other.open=false);});group.addEventListener('mouseenter',()=>{if(matchMedia('(min-width:1024px) and (hover:hover)').matches)group.open=true;});group.addEventListener('mouseleave',()=>{if(!group.contains(document.activeElement))group.open=false;});});
   target.addEventListener('keydown',e=>{if(e.key==='Escape'){groups.forEach(g=>g.open=false);toggle.setAttribute('aria-expanded','false');menu.classList.remove('is-open');}});
   for(const link of target.querySelectorAll('a'))if(new URL(link.href).pathname===location.pathname&&!new URL(link.href).search)link.setAttribute('aria-current','page');
   if(!window.LabAuth)await script('js/auth.js?v=10');
   LabAuth.initNavigation(target);await script('js/search.js?v=10');
  }catch(_){target.replaceChildren();const a=document.createElement('a');a.href=new URL('index.html',root);a.textContent='智能系统实验室 · 返回首页';target.append(a);}
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',load,{once:true});else load();
})();
