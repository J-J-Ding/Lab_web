(() => {
 'use strict';
 const $=id=>document.getElementById(id);
 const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 function cards(id,rows,label,member=false){
  const box=$(id);box.replaceChildren();
  if(!rows.length){box.append(node('p','暂无公开内容','empty-note'));return;}
  for(const row of rows){
   const article=node('article',undefined,'home-card'),a=node('a');a.href=member?'/member.html?slug='+encodeURIComponent(row.slug):'/content.html?id='+encodeURIComponent(row.id);
   const image=member?row.avatar:row.cover;
   if(image?.url&&/^\/api\/(public|site)\/assets\//.test(image.url)){const img=node('img');img.src=image.url;img.alt=member?row.display_name:row.title;img.loading='lazy';if(member)img.className='home-member-photo';a.append(img);}
   a.append(node('span',label,'kind-tag'),node('h3',member?row.display_name:row.title));article.append(a);
   const text=member?'':row.summary;if(text)article.append(node('p',text.slice(0,100)+(text.length>100?'…':'')));
   if(member){const description=[...(row.highest_education?[{education_level:row.highest_education}]:(row.education||[])).map(e=>e.education_level),...(row.research_areas||[]),row.enrollment_year?row.enrollment_year+'级':'',row.public_contact_email].filter(Boolean);if(description.length)article.append(node('p',description.join(' · ')));}
   if(row.date)article.append(node('time',row.date));box.append(article);
  }
 }
 async function load(){
  $('home-status').textContent='正在读取团队公开数据…';$('home-retry').hidden=true;
  try{
   const data=await LabSite.get('/api/public/home/');
   window.mountTeamCarousel?.($('home-visual'),data.slides);
   for(const [key,label] of Object.entries({news:'团队新闻',papers:'发表论文',projects:'科研项目',competitions:'竞赛成果',resources:'学习资料'}))cards('home-'+key,data[key],label);
   cards('home-members',data.members,'团队成员',true);
   $('home-research').replaceChildren(...data.research_areas.map(text=>node('span',text)));
   $('home-research').closest('.intro-panel').hidden=!data.research_areas.length;
   $('home-stats').replaceChildren();for(const [key,label] of Object.entries({members:'团队成员',papers:'发表论文',projects:'科研项目',competitions:'竞赛成果'})){const box=node('div');const number=node('strong','0');number.dataset.target=String(data.stats[key]);box.append(number,node('span',label));$('home-stats').append(box);}
   animateStats();$('home-status').textContent='';
  }catch(error){if(error.silent)return;$('home-status').textContent='公开数据暂不可用，请重试。页面导航仍可正常使用。';$('home-retry').hidden=false;}
 }
 let animationTicket=0;
 function animateStats(){const ticket=++animationTicket,box=$('home-stats'),reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;const numbers=[...box.querySelectorAll('strong')];
  const start=()=>{box.classList.add('is-visible');const begin=performance.now();function frame(now){if(ticket!==animationTicket)return;const ratio=reduced?1:Math.min(1,(now-begin)/1100),eased=1-Math.pow(1-ratio,3);for(const n of numbers)n.textContent=String(Math.round(Number(n.dataset.target)*eased));if(ratio<1)requestAnimationFrame(frame);}requestAnimationFrame(frame);};
  if(reduced)start();else {box.classList.remove('is-visible');const observer=new IntersectionObserver(rows=>{if(rows.some(r=>r.isIntersecting)){observer.disconnect();if(ticket===animationTicket)start();}},{threshold:.15});observer.observe(box);}
 }
 document.addEventListener('site-access-changed',()=>{animationTicket++;window.mountTeamCarousel?.($('home-visual'),[]);load();});
 $('home-retry').addEventListener('click',load);load();
})();
