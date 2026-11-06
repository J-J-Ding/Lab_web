(function(){
  'use strict';
  const P=window.LabPublic;
  async function load(){return P.run(async current=>{
    const result=await P.get('/api/public/legacy/?path='+encodeURIComponent(location.pathname));
    if(!current())return;
    const url=new URL(result.url,location.origin);
    if(url.origin!==location.origin||!['/content.html','/member.html'].includes(url.pathname))throw new Error('兼容链接无效');
    location.replace(url.href);
  });}
  document.getElementById('public-retry').addEventListener('click',load);load();
})();
