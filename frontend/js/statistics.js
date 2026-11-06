(async()=>{
'use strict';const $=s=>document.querySelector(s),status=$('#stats-status'),box=$('#stats-data'),form=$('#stats-filter');let generation=0;
const node=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
const internal=document.body.dataset.internal==='true';
form.year_to.value=new Date().getFullYear();form.year_from.value=form.year_to.value-9;
async function load(){const ticket=++generation;box.replaceChildren();status.textContent='正在计算…';
try{
const query=new URLSearchParams(new FormData(form));const base=internal?'/api/admin/stats/overview/':'/api/public/stats/overview/';
const response=await fetch(base+'?'+query,{cache:'no-store',credentials:'same-origin'});if(!response.ok)throw Error(response.status===403?'请以管理账号登录后查看内部看板。':'统计暂不可用或年份范围无效。');const overview=await response.json();
const annual=internal?null:await fetch('/api/public/stats/annual/?'+query,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('年度统计暂不可用');return r.json();});if(ticket!==generation)return;
box.append(node('p','口径 '+overview.metric_version+' · '+new Date(overview.as_of).toLocaleString()));
if(internal){const data=overview.data;box.append(node('p',`内容对象 ${data.items} · 可管理档案 ${data.manageable_member_profiles}`),node('p',`审核样本 ${data.review.sample_size} · 中位数 ${data.review.median_seconds??'暂无'} 秒 · P95 ${data.review.p95_seconds??'暂无'} 秒`));const table=node('table');const head=node('tr');for(const text of ['工作稿状态','数量'])head.append(node('th',text));table.append(head);for(const row of data.working_states){const tr=node('tr');tr.append(node('td',row.working_revision__state||'无工作稿'),node('td',row.count));table.append(tr);}box.append(table);$('#stats-export').href='/api/admin/stats/export/?'+query;}
else{box.append(node('h2','当前公开成员 '+overview.data.members.total));for(const series of annual.data){const section=node('section');section.append(node('h2',series.kind+' · '+series.total+'项'),node('p',`未知年份 ${series.unknown_date} · 同比 ${series.growth_rate===null?'无可比基数':(series.growth_rate*100).toFixed(1)+'%'}`));const max=Math.max(1,...series.series.map(r=>r.count));const chart=node('div');chart.setAttribute('role','img');chart.setAttribute('aria-label',series.kind+'年度数量，等价数据见下表');for(const r of series.series){const line=node('div');line.className='stats-bar';line.append(node('span',r.year+'年'));const bar=node('span');bar.style.width=Math.max(1,r.count/max*65)+'%';bar.className='stats-fill';line.append(bar,node('span',r.count));chart.append(line);}section.append(chart);const table=node('table');const tr=node('tr');tr.append(node('th','年份'),node('th','数量'));table.append(tr);for(const r of series.series){const row=node('tr');row.append(node('td',r.year),node('td',r.count));table.append(row);}section.append(table);box.append(section);}}
status.textContent='统计已更新';
}catch(e){if(ticket===generation){box.replaceChildren();status.textContent=e.message;}}}
document.addEventListener('lab-auth-state',e=>{if(internal&&(e.detail.status!=='authenticated'||(!e.detail.user?.is_superuser&&!['ADMIN','TEACHER'].includes(e.detail.user?.role)))){generation++;box.replaceChildren();status.textContent='请以管理账号登录后查看内部看板。';}});
form.addEventListener('submit',e=>{e.preventDefault();load();});addEventListener('pagehide',()=>{generation++;box.replaceChildren();});addEventListener('pageshow',e=>{if(e.persisted)location.reload();});await load();
})();
