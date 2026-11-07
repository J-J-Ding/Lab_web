(() => {
 'use strict';const P=window.LabPublic;
 const labels={patent_number:'专利号',application_date:'申请日期',grant_date:'授权日期',abstract:'专利摘要',doi:'DOI',venue:'期刊/会议',publication_date:'发表日期',category:'分类',volume:'卷',issue:'期',pages:'页码',open_url:'公开链接',project_number:'项目编号',funder:'资助方',level:'级别',start_date:'开始日期',end_date:'结束日期',status:'项目状态',event_name:'赛事名称',award_name:'所获奖项',award_date:'获奖日期',starts_at:'开始时间',ends_at:'结束时间',location:'地点',event_date:'日期',isbn:'ISBN',publisher:'出版社',edition:'版次'};
 const enums={ACTIVE:'进行中',COMPLETED:'已结项',CANCELLED:'已取消',COMPETITION:'学科竞赛',HONOR:'荣誉奖励',RESOURCE:'学习资料',APPLIED:'申请中',GRANTED:'已授权',EXPIRED:'已失效'};
 function section(parent,title){const s=P.node('section',undefined,'detail-section');s.append(P.node('h2',title));parent.append(s);return s;}
 async function load(){return P.run(async current=>{
  const id=new URLSearchParams(location.search).get('id');if(!/^[0-9a-f-]{36}$/.test(id||''))throw Error('内容不存在或尚未公开');
  const data=await P.get('/api/public/content/'+id+'/');if(!current())return;document.title=data.title+' - 智能系统实验室';
  const card=P.node('article',undefined,'detail-article'),heading=P.node('header',undefined,'detail-heading');heading.append(P.node('h1',data.title));const meta=P.node('div',undefined,'detail-meta');meta.append(P.node('span',P.labels[data.kind]));if(data.date)meta.append(P.node('span',data.date));
  if(data.contributions?.length){const people=P.node('span');data.contributions.forEach((person,i)=>{if(i)people.append(document.createTextNode('、'));people.append(person.member_slug?P.link(person.name,'/member.html?slug='+encodeURIComponent(person.member_slug)):P.node('span',person.name));});meta.append(people);}heading.append(meta);card.append(heading);
  if(data.cover){const image=P.node('img',undefined,'detail-cover');image.src=data.cover.url;image.alt=data.title+'封面';image.onerror=()=>image.remove();card.append(image);}
  if(data.summary)section(card,'内容摘要').append(P.node('p',data.summary));
  if(data.rich_body)LabRich.render(data.rich_body,data.assets,section(card,'详细内容'));else if(data.detail.body)section(card,'详细内容').append(P.node('p',data.detail.body));
  const fields=Object.entries(data.detail).filter(([key,value])=>labels[key]&&value!==null&&value!==undefined&&value!=='');
  if(fields.length){const grid=P.node('dl',undefined,'detail-grid');for(const [key,value] of fields){const row=P.node('div');row.append(P.node('dt',labels[key]));const dd=P.node('dd');dd.append(key==='open_url'?P.link(value,value):document.createTextNode(enums[value]||String(value)));row.append(dd);grid.append(row);}section(card,'成果信息').append(grid);}
  if(data.projects.length){const box=section(card,'关联项目');for(const p of data.projects){const line=P.node('p');line.append(P.link(p.title,'/content.html?id='+p.id));box.append(line);}}
  const assets=(data.assets||[]).filter(a=>a.id!==data.cover?.id&&!LabRich.imageIDs(data.rich_body).has(a.id));if(assets.length)window.renderPublicAssets(assets,section(card,'图片与附件'));P.content.append(card);
  if(data.kind==='PROJECT'){
   const box=section(card,'项目成果');let page=1;async function outputs(){const rows=await P.get('/api/public/projects/'+id+'/outputs/?page='+page);if(!current())return;box.replaceChildren(P.node('h2','项目成果'));const grid=P.node('div',undefined,'public-card-grid');for(const row of rows.results)grid.append(renderPublicCard(row));if(!rows.count)grid.append(P.node('p','暂无公开成果','empty-note'));box.append(grid);for(const [text,url,delta] of [['上一页',rows.previous,-1],['下一页',rows.next,1]]){const b=P.node('button',text);b.disabled=!url;b.onclick=()=>{page+=delta;outputs().catch(e=>{box.textContent=e.message;});};box.append(b);}}await outputs();
  }P.ready();
 });}document.getElementById('public-retry').onclick=load;load();
})();
