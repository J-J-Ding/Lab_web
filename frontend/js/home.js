(() => {
 'use strict';
 const $=id=>document.getElementById(id);
 const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 function cards(id,rows,label,member=false){
  const box=$(id);box.replaceChildren();
  if(!rows.length){box.append(node('p','暂无公开内容','empty-note'));return;}
  for(const row of rows){
   const article=node('article',undefined,'home-card'),a=node('a');a.href=member?'/member.html?slug='+encodeURIComponent(row.slug):'/content.html?id='+encodeURIComponent(row.id);
   const image=member?row.avatar:(row.assets||[]).find(a=>a.mime_type.startsWith('image/'));
   if(image?.url?.startsWith('/api/public/assets/')){const img=node('img');img.src=image.url;img.alt='';img.loading='lazy';a.append(img);}
   a.append(node('span',label,'kind-tag'),node('h3',member?row.display_name:row.title));article.append(a);
   const text=member?row.bio:row.summary;if(text)article.append(node('p',text.slice(0,100)+(text.length>100?'…':'')));
   if(row.date)article.append(node('time',row.date));box.append(article);
  }
 }
 async function load(){
  $('home-status').textContent='正在读取团队公开数据…';$('home-retry').hidden=true;
  try{
   const response=await fetch('/api/public/home/',{credentials:'omit',cache:'no-store',headers:{Accept:'application/json'}});if(!response.ok)throw Error();const data=await response.json();
   for(const [key,label] of Object.entries({news:'团队新闻',papers:'发表论文',projects:'科研项目',competitions:'竞赛成果',resources:'学习资料'}))cards('home-'+key,data[key],label);
   cards('home-members',data.members,'团队成员',true);
   $('home-research').replaceChildren(...data.research_areas.map(text=>node('span',text)));
   if(!data.research_areas.length)$('home-research').append(node('p','研究领域由团队成员资料自动汇集。','v10-caption'));
   $('home-stats').replaceChildren();for(const [key,label] of Object.entries({members:'公开成员',papers:'发表论文',projects:'累计项目',competitions:'竞赛成果'})){const box=node('div');box.append(node('strong',data.stats[key]),node('span',label));$('home-stats').append(box);}
   $('home-status').textContent='';
  }catch(_){$('home-status').textContent='公开数据暂不可用，请重试。页面导航仍可正常使用。';$('home-retry').hidden=false;}
 }
 $('home-retry').addEventListener('click',load);load();
})();
