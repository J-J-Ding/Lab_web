(function(){
  'use strict';
  const P=window.LabPublic;
  async function load(){return P.run(async current=>{
    const id=new URLSearchParams(location.search).get('id');
    if(!/^[0-9a-f-]{36}$/.test(id||''))throw new Error('内容不存在或尚未公开');
    const data=await P.get(`/api/public/content/${id}/`);if(!current())return;
    document.title=data.title+' - 智能系统实验室';
    const card=P.node('article',undefined,'public-card');card.append(P.node('h1',data.title),P.node('p',data.date,'public-meta'),P.node('p',data.summary));
    const people=P.node('p');for(const person of data.contributions){people.append(person.member_slug?P.link(person.name,'/member.html?slug='+encodeURIComponent(person.member_slug)):P.node('span',person.name),P.node('span',' · '));}card.append(people);
    const labels={body:'正文',doi:'DOI',venue:'期刊/会议',publication_date:'发布日期',category:'分类',volume:'卷',issue:'期',pages:'页码',open_url:'公开链接',project_number:'项目编号',funder:'资助方',level:'级别',start_date:'开始日期',end_date:'结束日期',status:'项目状态',event_name:'赛事',award_name:'奖项',award_date:'获奖日期',starts_at:'开始时间',ends_at:'结束时间',location:'地点',event_date:'日期',isbn:'ISBN',publisher:'出版社',edition:'版次'};
    for(const [key,value] of Object.entries(data.detail))if(value && labels[key]){
      card.append(P.node('h2',labels[key]));card.append(key==='open_url'?P.link(value,value):P.node('p',value,'public-body'));
    }
    for(const project of data.projects)card.append(P.link(project.title,'/content.html?id='+project.id));
    window.renderPublicAssets(data.assets,card);P.content.append(card);
    if(data.kind==='PROJECT'){
      let page=1;
      const output=P.node('section');P.content.append(output);
      const show=async()=>{
        const rows=await P.get(`/api/public/projects/${id}/outputs/?page=${page}`);if(!current())return;
        output.replaceChildren(P.node('h2','项目成果'));
        for(const row of rows.results){const line=P.node('p');line.append(P.link(row.title,'/content.html?id='+row.id));output.append(line);}
        if(!rows.count)output.append(P.node('p','暂无公开成果'));
        for(const [text,ok,delta] of [['上一页',rows.previous,-1],['下一页',rows.next,1]]){const b=P.node('button',text);b.disabled=!ok;b.onclick=()=>{page+=delta;show().catch(e=>{output.textContent=e.message;});};output.append(b);}
      };await show();
    }
    P.ready();
  });}
  document.getElementById('public-retry').addEventListener('click',load);load();
})();
