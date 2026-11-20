(function(){
  'use strict';
  const P=window.LabPublic;
  async function load(){return P.run(async current=>{
    const slug=new URLSearchParams(location.search).get('slug');if(!slug)throw new Error('内容不存在或尚未公开');
    const base='/api/public/members/'+encodeURIComponent(slug)+'/';
    const data=await P.get(base);if(!current())return;
    const layout=P.node('div',undefined,'member-profile-layout');
    const sidebar=P.node('aside',undefined,'member-profile-sidebar');
    const portrait=P.node('div',undefined,'member-profile-portrait');
    const fallback=()=>portrait.replaceChildren(P.node('span',(data.display_name||'团队').slice(0,1),'member-portrait-initial'));
    if(data.avatar&&/^\/api\/(?:public|site)\/assets\/[0-9a-f-]+\/$/.test(data.avatar.url)){
      const img=P.node('img');img.src=data.avatar.url;img.alt=data.display_name;img.onerror=fallback;portrait.append(img);
    }else fallback();
    sidebar.append(portrait,P.node('h2',data.display_name));
    const facts=P.node('dl',undefined,'member-profile-facts');
    function fact(label,value){if(value)facts.append(P.node('dt',label),P.node('dd',value));}
    fact('最高学历',data.highest_education||(data.education||[]).map(e=>e.education_level).filter(Boolean).join(' · '));
    fact('年级',data.enrollment_year?data.enrollment_year+'级':'');
    fact('研究方向',(data.research_areas||[]).join('、'));
    if(data.public_contact_email){const dd=P.node('dd');dd.append(P.link(data.public_contact_email,'mailto:'+data.public_contact_email));facts.append(P.node('dt','邮箱'),dd);}
    sidebar.append(facts);
    const outputs=P.node('section',undefined,'member-profile-outputs');outputs.append(P.node('h2','参与成果'));
    const loading=P.node('p','正在加载关联成果…','member-output-status');outputs.append(loading);
    layout.append(sidebar,outputs);P.content.append(layout);
    const groups=new Map(),seenRows=new Set(),seenPages=new Set();
    const order=['PROJECT','PAPER','PATENT','AWARD','PUBLICATION','NEWS','ACTIVITY','BLOG'];
    const names={PROJECT:'科研项目',PAPER:'论文',PATENT:'专利',AWARD:'竞赛与荣誉',PUBLICATION:'著作',NEWS:'新闻',ACTIVITY:'活动',BLOG:'技术博客'};
    let next=base+'achievements/?page_size=100';
    while(next){
      const url=new URL(next,location.origin);
      if(url.origin!==location.origin||url.pathname!==base+'achievements/'||seenPages.has(url.href))throw new Error('成果分页地址无效，请重试。');
      seenPages.add(url.href);const rows=await P.get(url.pathname+url.search);if(!current())return;
      for(const row of rows.results){
        if(seenRows.has(row.id))continue;seenRows.add(row.id);
        if(!groups.has(row.kind))groups.set(row.kind,[]);groups.get(row.kind).push(row);
      }
      next=rows.next;
    }
    loading.remove();
    for(const kind of [...order,...[...groups.keys()].filter(k=>!order.includes(k))]){
      if(!groups.has(kind))continue;
      const section=P.node('section',undefined,'member-output-group');const rows=groups.get(kind);
      section.append(P.node('h3',(names[kind]||P.labels[kind]||'其他成果')+' · '+rows.length));
      const list=P.node('ul');for(const row of rows){const li=P.node('li');li.append(P.link(row.title,'/content.html?id='+encodeURIComponent(row.id)));if(row.date){const date=P.node('time',row.date);li.append(date);}list.append(li);}section.append(list);outputs.append(section);
    }
    if(!seenRows.size)outputs.append(P.node('p','暂无可展示的关联成果','empty-note'));
    P.ready();
  });}
  document.getElementById('public-retry').addEventListener('click',load);load();
})();
