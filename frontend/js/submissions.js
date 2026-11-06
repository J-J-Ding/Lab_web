(async()=>{
 'use strict';const C=window.LabContent,N=C.node;
 function format(key,value){
  if(key==='education')return value.map(e=>[e.start_date,e.end_date,e.school,e.major,e.degree].filter(Boolean).join(' · ')).join('；');
  if(key==='research_areas')return value.join('、');
  if(key==='alumni')return [value.graduation_year,value.degree,value.organization].filter(Boolean).join(' · ');
  if(key==='cv_private')return [value.gender,value.native_region?.names?.join(' · '),value.skills,value.political_status,value.education_note,...[...(value.internships||[]),...(value.practice||[])].map(e=>[e.period||[e.start_date,e.end_date].filter(Boolean).join(' — '),e.organization,e.role,e.description].filter(Boolean).join(' · '))].filter(Boolean).join('；');
  if(key==='public_member_status')return {ACTIVE:'在读 / 在岗',ALUMNI:'已毕业',LEFT:'已离开'}[value]||value;
  return String(value??'');
 }
 const user=await C.boot();if(!user)return;
 if(!C.manager(user)){C.status('仅老师和Root可查看投递收件箱。',true);document.getElementById('business-content').hidden=true;return;}
 const mode=document.body.dataset.submissionPage;
 try{
  if(mode==='detail'){
   const id=new URLSearchParams(location.search).get('id');if(!id)throw {status:400,data:{detail:'缺少投递编号。'}};
   const row=await C.request('/api/members/resume-inbox/'+encodeURIComponent(id)+'/'),box=document.getElementById('submission-detail');
   box.append(N('h2',row.title),N('p',row.state==='WITHDRAWN'?'已撤回（Root审计查看）':'已投递'),N('p','提交时间：'+new Date(row.created_at).toLocaleString()));
   const labels={display_name:'姓名',public_contact_email:'邮箱',bio:'个人介绍',phone:'联系电话',internal_contact:'私人联系信息',education:'教育经历',research_areas:'研究方向',cv_private:'简历补充资料',public_member_status:'成员状态',alumni:'毕业去向'};
   box.append(N('h3','随投递提交的个人资料'));
   for(const [key,label] of Object.entries(labels)){const value=row.profile[key];if(value&&(!Array.isArray(value)||value.length))box.append(N('p',label+'：'+format(key,value)));}
   for(const [key,label] of [['introduction','简历介绍']])if(row.resume[key])box.append(N('p',label+'：'+row.resume[key]));
   box.append(N('a','预览PDF简历（Word请下载）',{href:'/api/members/resume-inbox/'+row.id+'/preview/',target:'_blank',rel:'noopener'}));
   box.append(N('a','查看 / 下载投递简历',{href:row.download_url}));
   const notice=new URLSearchParams(location.search).get('notice');if(notice){await C.request('/api/members/notifications/'+encodeURIComponent(notice)+'/read/',{method:'POST',data:{}});document.dispatchEvent(new Event('lab-notifications-updated'));}
   C.status('资料为投递时快照；访客后续修改不会改写本次内容。');
  }else{
   let page=1;
   async function notices(){const rows=await C.request('/api/members/notifications/?page='+page),box=document.getElementById('notification-list');box.replaceChildren(N('p','未读通知 '+rows.unread_count));
    for(const n of rows.results){const article=N('article');article.append(N('p',(n.withdrawn?'投递已撤回':n.display_name+' 投递了简历')+' · '+new Date(n.created_at).toLocaleString()+(n.read_at?' · 已读':' · 未读')));
     if(n.url)article.append(N('a','查看投递资料',{href:n.url}));if(!n.read_at)article.append(C.button('标记已读',async()=>{await C.request('/api/members/notifications/'+n.id+'/read/',{method:'POST',data:{}});await notices();document.dispatchEvent(new Event('lab-notifications-updated'));}));box.append(article);}
    if(!rows.count)box.append(N('p','暂无投递消息。'));const pages=document.getElementById('notice-pages');pages.replaceChildren();for(const [text,url,delta] of [['上一页',rows.previous,-1],['下一页',rows.next,1]]){const button=C.button(text,async()=>{page+=delta;await notices();});button.disabled=!url;pages.append(button);}
   }await notices();
   let inboxPage=1;const inbox=document.getElementById('inbox-list');
   async function loadInbox(){const rows=await C.request('/api/members/resume-inbox/?page='+inboxPage);inbox.replaceChildren();
    for(const row of rows.results){const article=N('article');article.append(N('h3',row.display_name),N('p',row.title+' · '+(row.state==='WITHDRAWN'?'已撤回':'已投递')),N('a','查看投递',{href:'/submission.html?id='+row.id}));inbox.append(article);}if(!rows.count)inbox.append(N('p','暂无有效投递。'));
    for(const [text,url,delta] of [['上一页',rows.previous,-1],['下一页',rows.next,1]]){const button=C.button(text,async()=>{inboxPage+=delta;await loadInbox();});button.disabled=!url;inbox.append(button);}
   }await loadInbox();
   C.status('点击投递查看访客资料与本次简历。');
  }
 }catch(e){C.showError(e);}
})();
