(() => {
 'use strict';const P=window.LabPublic,kind=document.body.dataset.publicKind,form=document.getElementById('public-search'),controls=document.getElementById('public-pagination');
 const memberPage=kind==='MEMBER'||kind==='GRADUATE';let ticket=0;
 const yearInput=form.elements.year,yearLabel=yearInput.closest('label');
 const reset=P.node('button','重置');reset.type='reset';form.append(reset);form.elements.q.placeholder=memberPage?'搜索姓名或研究简介':'搜索标题、摘要或正文';
 const tabs=P.node('nav',undefined,'section-tabs');tabs.setAttribute('aria-label','栏目分类');
 if(memberPage){form.before(tabs);}
 function state(){const p=new URLSearchParams(location.search);return {p,tab:kind==='GRADUATE'?'graduates':p.get('tab')||p.get('member_kind')||'all',q:p.get('q')||'',year:p.get('year')||'',page:Math.max(1,Number(p.get('page'))||1)};}
 function update(values){const p=new URLSearchParams(location.search);for(const [key,value] of Object.entries(values)){if(value)p.set(key,String(value));else p.delete(key);}history.pushState({},'',location.pathname+(p.size?'?'+p:''));load();}
 function renderTabs(s){tabs.replaceChildren();for(const [key,label] of [['all','全部成员'],['TEACHER','老师'],['STUDENT','同学'],['graduates','已毕业']]){const a=P.link(label,'/data/members/index.html'+(key==='all'?'':'?tab='+key));if(s.tab===key)a.setAttribute('aria-current','page');if(kind==='MEMBER')a.onclick=e=>{e.preventDefault();update({tab:key==='all'?'':key,member_kind:'',page:'',year:''});};tabs.append(a);}}
 async function load(){const s=state(),current=++ticket;form.elements.q.value=s.q;yearInput.value=s.year;
  const graduates=memberPage&&s.tab==='graduates';yearLabel.hidden=memberPage&&!graduates;
  if(memberPage){renderTabs(s);yearLabel.firstChild.textContent='毕业年份';}
  P.content.className='public-card-grid';
  return P.run(async valid=>{
   controls.replaceChildren();const query=new URLSearchParams({page:String(s.page)});
   if(s.q)query.set('q',s.q);if(s.year&&(!memberPage||graduates))query.set('year',s.year);
   let endpoint=memberPage?(graduates?'graduates':'members'):'content';
   if(!memberPage)query.set('kind',kind);
   if(memberPage&&!graduates){query.set('status','ACTIVE');if(['TEACHER','STUDENT'].includes(s.tab))query.set('member_kind',s.tab);}
   if(document.body.dataset.resource)query.set('category','RESOURCE');else if(kind==='AWARD')query.set('category',s.p.get('category')||'COMPETITION');else if(s.p.get('category'))query.set('category',s.p.get('category'));
   const data=await P.get('/api/public/'+endpoint+'/?'+query);if(!valid()||ticket!==current)return;
   for(const row of data.results)P.content.append(window.renderPublicCard(row,{member:memberPage}));
   if(!data.count)P.content.append(P.node('p','没有符合当前条件的公开内容，可调整条件或点击重置。','empty-note'));P.ready(data.count);
   for(const [text,enabled,page] of [['上一页',data.previous,s.page-1],['下一页',data.next,s.page+1]]){const b=P.node('button',text);b.type='button';b.disabled=!enabled;b.onclick=()=>update({page});controls.append(b);}controls.append(P.node('span','第 '+s.page+' 页'));
  });
 }
 form.onsubmit=e=>{e.preventDefault();update({q:form.elements.q.value.trim(),year:yearInput.value,page:''});};
 form.onreset=e=>{e.preventDefault();update({q:'',year:'',page:''});};window.addEventListener('popstate',load);document.getElementById('public-retry').onclick=load;load();
})();
