(function(){
  'use strict';
  window.renderPublicAssets=function(assets,parent){
    const P=window.LabPublic;
    for(const asset of assets||[]){
      if(!/^\/api\/public\/assets\/[0-9a-f-]+\/$/.test(asset.url))continue;
      if(asset.mime_type.startsWith('image/')){
        const image=P.node('img');image.src=asset.url;image.alt='已审核公开图片';image.loading='lazy';
        image.addEventListener('error',()=>image.remove());parent.append(image);
      }else parent.append(P.link('下载公开附件',asset.url));
    }
  };
})();
