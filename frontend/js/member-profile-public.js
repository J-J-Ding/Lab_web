(function(){
  'use strict';
  const P=window.LabPublic;
  async function load(){return P.run(async current=>{
    const slug=new URLSearchParams(location.search).get('slug');if(!slug)throw new Error('内容不存在或尚未公开');
    const data=await P.get('/api/public/members/'+encodeURIComponent(slug)+'/');if(!current())return;
    const card=P.node('article',undefined,'public-card');card.append(P.node('h1',data.display_name));
    card.append(P.node('p',(data.research_areas||[]).join(' · ')));
    if(data.public_contact_email)card.append(P.node('p','公开邮箱：'+data.public_contact_email));
    for(const education of data.highest_education?[{education_level:data.highest_education}]:(data.education||[]))card.append(P.node('p',education.education_level));
    if(data.enrollment_year)card.append(P.node('p',data.enrollment_year+'级'));
    if(data.avatar)window.renderPublicAssets([data.avatar],card);P.content.append(card);
    const outputs=P.node('section');P.content.append(outputs);let page=1;
    const show=async()=>{
      const rows=await P.get('/api/public/members/'+encodeURIComponent(slug)+`/achievements/?page=${page}`);if(!current())return;
      outputs.replaceChildren(P.node('h2','参与成果'));
      const grid=P.node('div',undefined,'public-card-grid');for(const row of rows.results)grid.append(window.renderPublicCard(row));outputs.append(grid);
      if(!rows.count)outputs.append(P.node('p','暂无公开成果'));
      for(const [text,ok,delta] of [['上一页',rows.previous,-1],['下一页',rows.next,1]]){const b=P.node('button',text);b.disabled=!ok;b.onclick=()=>{page+=delta;show().catch(e=>{outputs.textContent=e.message;});};outputs.append(b);}
    };await show();P.ready();
  });}
  document.getElementById('public-retry').addEventListener('click',load);load();
})();
