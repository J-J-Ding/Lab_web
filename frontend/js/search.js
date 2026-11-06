(() => {
 'use strict';const input=document.getElementById('globalSearch'),form=document.getElementById('global-search-form');if(!input||!form)return;
 const results=document.createElement('div');results.className='search-results';results.setAttribute('role','status');results.hidden=true;form.append(results);
 let timer,ticket=0;const node=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
 async function search(){const q=input.value.trim(),version=++ticket;results.replaceChildren();if(!q){results.hidden=true;return;}results.hidden=false;results.textContent='正在搜索…';
  try{const query=new URLSearchParams({q,page_size:'5'}),[content,members]=await Promise.all(['/api/public/content/','/api/public/members/'].map(path=>LabSite.get(path+'?'+query)));if(ticket!==version)return;results.replaceChildren();
   for(const [label,data,isMember] of [['科研与动态',content,false],['团队成员',members,true]]){if(!data.count)continue;results.append(node('strong',label+' · '+data.count));for(const row of data.results){const a=node('a',row.title||row.display_name);a.href=isMember?'/member.html?slug='+encodeURIComponent(row.slug):'/content.html?id='+row.id;results.append(a);}}
   if(!content.count&&!members.count)results.append(node('p','没有找到匹配的公开内容或成员。'));
  }catch(_){if(ticket===version)results.textContent='搜索暂不可用，请稍后重试。';}
 }
 document.addEventListener('site-access-changed',()=>{ticket++;results.hidden=true;results.replaceChildren();});
 input.addEventListener('input',()=>{clearTimeout(timer);ticket++;timer=setTimeout(search,250);if(!input.value.trim()){results.hidden=true;results.replaceChildren();}});
 form.addEventListener('submit',e=>{e.preventDefault();clearTimeout(timer);search();});input.addEventListener('keydown',e=>{if(e.key==='Escape'){ticket++;results.hidden=true;}});document.addEventListener('click',e=>{if(!form.contains(e.target))results.hidden=true;});
})();
