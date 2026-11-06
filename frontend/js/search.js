/* Navbar search queries only approved API data; never scrapes/caches old HTML. */
(function(){
  'use strict';
  const input=document.getElementById('globalSearch');if(!input)return;
  const results=document.createElement('div');results.className='search-results';results.setAttribute('role','status');results.style.cssText='position:absolute;background:white;color:#24354b;max-width:90vw;max-height:60vh;overflow:auto;z-index:1000;padding:12px;box-shadow:0 4px 16px #0002';results.hidden=true;input.parentNode.append(results);
  let timer,version=0;
  input.addEventListener('input',()=>{
    clearTimeout(timer);const current=++version;results.replaceChildren();results.hidden=true;
    const q=input.value.trim();if(q.length<2)return;
    timer=setTimeout(async()=>{
      try{
        const r=await fetch('/api/public/content/?q='+encodeURIComponent(q)+'&page_size=10',{cache:'no-store',credentials:'omit'});
        if(!r.ok)throw new Error();const data=await r.json();if(current!==version)return;
        results.replaceChildren();results.hidden=false;
        for(const row of data.results){const line=document.createElement('p'),a=document.createElement('a');a.textContent=row.title;a.href='/content.html?id='+encodeURIComponent(row.id);line.append(a);results.append(line);}
        if(!data.count)results.textContent='暂无匹配的公开内容';
      }catch(_){if(current===version){results.textContent='公开搜索暂不可用';results.hidden=false;}}
    },250);
  });
  if(input.value.trim())input.dispatchEvent(new Event('input'));
  input.addEventListener('keydown',e=>{if(e.key==='Escape'){version++;results.hidden=true;}});
  addEventListener('pagehide',()=>{version++;results.replaceChildren();});
})();
