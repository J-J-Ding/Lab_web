(() => {
 'use strict';const P=window.LabPublic;
 async function load(){return P.run(async current=>{
  const key=document.body.dataset.pageKey;
  if(key==='about'){
   const [about,home]=await Promise.allSettled([P.get('/api/public/pages/about/'),P.get('/api/public/home/')]);if(!current())return;
   const intro=P.node('section',undefined,'detail-section');intro.id='introduction';intro.append(P.node('h2','团队简介'));
   if(about.status==='fulfilled'){const row=about.value;if(row.detail.body)intro.append(P.node('p',row.detail.body,'section-copy'));else if(row.summary)intro.append(P.node('p',row.summary,'section-copy'));else intro.append(P.node('p','团队简介暂未填写。','empty-note'));window.renderPublicAssets(row.assets,intro);}
   else intro.append(P.node('p','暂无公开团队简介。','empty-note'));
   const research=P.node('section',undefined,'detail-section');research.id='research';research.append(P.node('h2','研究方向'));const tags=P.node('div',undefined,'research-tags');
   if(home.status==='fulfilled'&&home.value.research_areas.length)for(const area of home.value.research_areas)tags.append(P.node('span',area));else tags.append(P.node('p','暂无公开研究方向。','empty-note'));
   research.append(tags);P.content.append(intro,research);if(about.status==='rejected'&&home.status==='rejected')throw Error('公开服务暂不可用，请重试。');P.ready();
  }else{const row=await P.get('/api/public/pages/'+key+'/');if(!current())return;P.content.append(P.node('h2',row.title));if(row.detail.body)P.content.append(P.node('p',row.detail.body,'section-copy'));window.renderPublicAssets(row.assets,P.content);P.ready();}
 });}document.getElementById('public-retry').onclick=load;load();
})();
