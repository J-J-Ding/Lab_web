(function(){
  'use strict';
  const P=window.LabPublic;
  async function load(){return P.run(async current=>{
    const key=document.body.dataset.pageKey;
    const row=await P.get('/api/public/pages/'+key+'/');if(!current())return;
    P.content.append(P.node('h2',row.title),P.node('p',row.detail.body||'','public-body'));window.renderPublicAssets(row.assets,P.content);P.ready();
  });}
  document.getElementById('public-retry').addEventListener('click',load);load();
})();
