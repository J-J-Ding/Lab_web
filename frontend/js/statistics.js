(async()=>{
'use strict';const $=s=>document.querySelector(s),status=$('#stats-status'),box=$('#stats-data'),form=$('#stats-filter');let generation=0;
const node=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
const internal=document.body.dataset.internal==='true';
form.year_to.value=new Date().getFullYear();form.year_from.value=form.year_to.value-9;
async function load(){const ticket=++generation;box.replaceChildren();status.textContent='正在计算…';
try{
const query=new URLSearchParams(new FormData(form));const base=internal?'/api/admin/stats/overview/':'/api/public/stats/overview/';
const response=await fetch(base+'?'+query,{cache:'no-store',credentials:'same-origin'});if(!response.ok)throw Error(response.status===403?'请以管理账号登录后查看内部看板。':'统计暂不可用或年份范围无效。');const overview=await response.json();
const annual=await fetch('/api/public/stats/annual/?'+query,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('年度统计暂不可用');return r.json();});if(ticket!==generation)return;
box.append(node('p','口径 '+overview.metric_version+' · '+new Date(overview.as_of).toLocaleString()));
if(internal){const data=overview.data;box.append(node('p',`内容对象 ${data.items} · 可管理档案 ${data.manageable_member_profiles}`),node('p',`历史审核记录（旧流程，当前无需审核）· 样本 ${data.review.sample_size} · 中位数 ${data.review.median_seconds??'暂无'} 秒 · P95 ${data.review.p95_seconds??'暂无'} 秒`));const table=node('table');const head=node('tr');for(const text of ['工作稿状态','数量'])head.append(node('th',text));table.append(head);for(const row of data.working_states){const tr=node('tr');tr.append(node('td',row.working_revision__state||'无工作稿'),node('td',row.count));table.append(tr);}box.append(table);$('#stats-export').href='/api/admin/stats/export/?'+query;}
{
 box.append(node('h2',internal?'当前公开科研成果（公开口径）':'当前公开成员 '+overview.data.members.total));
 const grid=node('div');grid.className='stats-grid';const extra=node('details');extra.append(node('summary','新闻、活动与文章资源补充统计'));
 const names={PAPER:'发表论文',PROJECT:'科研项目',COMPETITION:'学科竞赛',HONOR:'荣誉奖励',PATENT:'专利',PUBLICATION:'出版成果',NEWS:'团队新闻',ACTIVITY:'团队活动',BLOG:'文章与资源'};
 const rows=annual.data.flatMap(row=>row.kind==='AWARD'?(row.categories||[{...row,kind:'COMPETITION'}]):[row]);
 function card(series){const section=node('section');section.className='stats-card';section.append(node('h2',(names[series.kind]||series.kind)+' · '+series.total+'项'),node('p','未知年份 '+series.unknown_date));const max=Math.max(1,...series.series.map(r=>r.count));const chart=node('div');chart.className='stats-columns';chart.setAttribute('role','img');chart.setAttribute('aria-label',(names[series.kind]||series.kind)+'年度数量，等价数据见折叠表格');
  for(const r of series.series){const column=node('div');column.className='stats-column';const bar=node('span');bar.className='stats-fill';bar.style.height=(r.count/max*145)+'px';column.append(node('span',r.count),bar,node('span',r.year));chart.append(column);}section.append(chart);
  const details=node('details');details.append(node('summary','查看年度数据表'));const table=node('table');const head=node('tr');head.append(node('th','年份'),node('th','数量'));table.append(head);for(const r of series.series){const tr=node('tr');tr.append(node('td',r.year),node('td',r.count));table.append(tr);}details.append(table);section.append(details);return section;
 }
 for(const kind of ['PAPER','PROJECT','COMPETITION','HONOR','PATENT','PUBLICATION']){const row=rows.find(r=>r.kind===kind);if(row)grid.append(card(row));}
 for(const row of rows.filter(r=>['NEWS','ACTIVITY','BLOG'].includes(r.kind)))extra.append(card(row));box.append(grid,extra);
}
status.textContent='统计已更新';
}catch(e){if(ticket===generation){box.replaceChildren();status.textContent=e.message;}}}
document.addEventListener('lab-auth-state',e=>{if(internal&&(e.detail.status!=='authenticated'||(!e.detail.user?.is_superuser&&!['ADMIN','TEACHER'].includes(e.detail.user?.role)))){generation++;box.replaceChildren();status.textContent='请以管理账号登录后查看内部看板。';}});
form.addEventListener('submit',e=>{e.preventDefault();load();});addEventListener('pagehide',()=>{generation++;box.replaceChildren();});addEventListener('pageshow',e=>{if(e.persisted)location.reload();});await load();
})();
