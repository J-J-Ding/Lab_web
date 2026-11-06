(() => {
 'use strict';
 const safe=asset=>asset&&/^\/api\/(?:public|site)\/assets\/[0-9a-f-]+\/$/.test(asset.url);
 window.renderPublicAssets=function(assets,parent){
  const P=window.LabPublic;
  for(const asset of assets||[]){if(!safe(asset))continue;
   if(asset.mime_type.startsWith('image/')){const image=P.node('img');image.src=asset.url;image.alt='内容图片';image.loading='lazy';image.addEventListener('error',()=>image.remove());parent.append(image);}
   else parent.append(P.link('下载附件',asset.url));
  }
 };
 window.renderPublicCard=function(row,{member=false}={}){
  const P=window.LabPublic,article=P.node('article',undefined,member?'member-teaser':'content-teaser');
  const href=member?'/member.html?slug='+encodeURIComponent(row.slug):'/content.html?id='+encodeURIComponent(row.id),image=member?row.avatar:row.cover;
  if(member){const portrait=safe(image)?P.node('img'):P.node('span',(row.display_name||'团队').slice(0,1),'member-initial');portrait.classList.add('member-avatar');if(safe(image)){portrait.src=image.url;portrait.alt=row.display_name;portrait.loading='lazy';}article.append(portrait);}
  else if(safe(image)){const a=P.link('',href);a.className='teaser-image';const img=P.node('img');img.src=image.url;img.alt=row.title+'封面';img.loading='lazy';img.onerror=()=>a.remove();a.append(img);article.append(a);}
  const body=P.node('div',undefined,'teaser-body');
  body.append(P.node('span',member?(row.public_member_status==='ALUMNI'?'已毕业':row.member_kind==='TEACHER'?'老师':'同学'):(P.labels[row.kind]||'科研成果'),'teaser-type'));
  const title=P.node('h2');title.append(P.link(row.display_name||row.title,href));body.append(title);
  const summary=member?'':row.summary;if(summary)body.append(P.node('p',summary.length>150?summary.slice(0,150)+'…':summary));
  if(member&&row.research_areas?.length)body.append(P.node('p',row.research_areas.join(' · '),'teaser-meta'));
  if(row.date)body.append(P.node('p',row.date,'teaser-meta'));
  if(member){const levels=(row.highest_education?[{education_level:row.highest_education}]:(row.education||[])).map(e=>e.education_level).filter(Boolean);if(levels.length)body.append(P.node('p',levels.join(' · '),'teaser-meta'));if(row.enrollment_year)body.append(P.node('p',row.enrollment_year+'级','teaser-meta'));if(row.public_contact_email)body.append(P.node('p',row.public_contact_email,'teaser-meta'));}
  if(!member){const names=(row.contributions||[]).map(c=>c.name);if(names.length)body.append(P.node('p',names.join('、'),'teaser-meta'));}
  article.append(body);return article;
 };
})();
