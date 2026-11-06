(function(){
  'use strict';
  const P=window.LabPublic, kind=document.body.dataset.publicKind;
  const form=document.getElementById('public-search'), controls=document.getElementById('public-pagination');
  let page=1;
  async function load(){return P.run(async current=>{
    controls.replaceChildren();
    const query=new URLSearchParams({page:String(page)}), term=form.elements.q.value.trim();
    if(term && term.length<2){P.status.textContent='搜索至少输入 2 个字符';return;}
    const members=kind==='MEMBER'||kind==='GRADUATE';
    if(!members)query.set('kind',kind);
    const incoming=new URLSearchParams(location.search);
    if(kind==='MEMBER'&&['TEACHER','STUDENT'].includes(incoming.get('member_kind')))query.set('member_kind',incoming.get('member_kind'));
    if(document.body.dataset.resource)query.set('category','RESOURCE');
    else if(kind==='AWARD'&&incoming.get('category'))query.set('category',incoming.get('category'));
    if(term && kind!=='GRADUATE')query.set('q',term);
    if(form.elements.year.value)query.set('year',form.elements.year.value);
    let endpoint=kind==='MEMBER'?'members':kind==='GRADUATE'?'graduates':'content';
    const data=await P.get(`/api/public/${endpoint}/?${query}`);if(!current())return;
    for(const item of data.results){
      const card=P.node('article',undefined,'public-card');
      const title=P.node('h2');title.append(P.link(item.display_name||item.title,members?'/member.html?slug='+encodeURIComponent(item.slug):'/content.html?id='+encodeURIComponent(item.id)));card.append(title);
      if(members){card.append(P.node('p',item.bio));if(item.alumni)card.append(P.node('p',`${item.alumni.graduation_year} · ${item.alumni.organization}`));}
      else {if(item.date)card.append(P.node('p',item.date,'public-meta'));if(item.summary)card.append(P.node('p',item.summary));}
      P.content.append(card);
    }
    P.ready(data.count);
    for(const [label,enabled,delta] of [['上一页',!!data.previous,-1],['下一页',!!data.next,1]]){
      const button=P.node('button',label);button.disabled=!enabled;button.type='button';button.addEventListener('click',()=>{page+=delta;load();});controls.append(button);
    }
    controls.append(P.node('span',`第 ${page} 页`));
  });}
  if(kind==='GRADUATE'){form.elements.q.disabled=true;form.elements.q.placeholder='按年份筛选毕业去向';}
  form.addEventListener('submit',event=>{event.preventDefault();page=1;load();});
  document.getElementById('public-retry').addEventListener('click',load);
  load();
})();
