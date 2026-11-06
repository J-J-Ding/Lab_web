/* V10 structured forms. The server owns permissions, identifiers and revision state. */
(() => {
 'use strict';
 const C=window.LabContent,$=s=>document.querySelector(s),mode=document.body.dataset.v10Page;
 const N=(tag,text,attrs={})=>C.node(tag,text,attrs);
 let dirty=false,user;
 const labels={PAPER:'发表论文',PROJECT:'科研项目',AWARD:'竞赛与荣誉',NEWS:'团队新闻',ACTIVITY:'团队活动',BLOG:'文章与资源',PUBLICATION:'出版成果',LAB_PAGE:'团队介绍'};
 const schemas={
  PAPER:[['venue','期刊/会议'],['publication_date','发表日期','date'],['doi','DOI'],['category','论文分类'],['volume','卷'],['issue','期'],['pages','页码'],['open_url','公开链接','url']],
  PROJECT:[['project_number','项目编号'],['funder','资助方'],['level','项目级别'],['start_date','开始日期','date'],['end_date','结束日期','date'],['status','项目状态','select',[['ACTIVE','进行中'],['COMPLETED','已结项'],['CANCELLED','已取消']]],['funding_amount','经费金额（内部资料）','number']],
  AWARD:[['event_name','赛事名称'],['category','成果分类','select',[['COMPETITION','学科竞赛'],['HONOR','荣誉奖励']]],['level','级别'],['award_name','奖项'],['award_date','获奖日期','date']],
  NEWS:[['event_date','新闻日期','date'],['category','分类'],['body','新闻正文','textarea']],
  ACTIVITY:[['starts_at','开始时间','datetime-local'],['ends_at','结束时间','datetime-local'],['location','活动地点'],['body','活动正文','textarea']],
  BLOG:[['event_date','日期','date'],['category','分类','select',[['','技术文章'],['RESOURCE','学习资料与下载']]],['body','正文','textarea']],
  PUBLICATION:[['isbn','ISBN'],['publisher','出版社'],['publication_date','出版日期','date'],['edition','版次']],
  LAB_PAGE:[['page_key','页面','select',[['about','团队简介'],['contact','联系我们']]],['body','正文','textarea']]
 };
 function field(parent,name,label,type='text',value='',required=false,options){
  const wrap=N('div'),id='v10-'+name.replace(/[^a-z0-9_-]/gi,'-'),l=N('label',label+' ',{for:id});
  l.append(N('span',required?'*':'选填',{class:required?'required':'optional'}));
  const input=N(type==='textarea'?'textarea':type==='select'?'select':'input',undefined,{name,id});
  if(type!=='textarea'&&type!=='select')input.type=type;
  if(type==='select')for(const [v,text] of options||[]){const o=N('option',text,{value:v});input.append(o);}
  if(type==='number'){input.min='0';input.step='any';}
  if(type!=='select'||value!==undefined&&value!==null&&value!=='')input.value=value??'';input.required=required;
  if(type==='text')input.maxLength=1000;
  wrap.append(l,input);parent.append(wrap);return input;
 }
 function check(parent,name,label,value=false){const l=N('label',undefined,{class:'check'}),input=N('input',undefined,{type:'checkbox',name});input.checked=value;l.append(input,document.createTextNode(label));parent.append(l);return input;}
 function formValue(form,name){return form.elements.namedItem(name)?.value||'';}
 function link(text,href){const a=N('a',text,{href});return a;}
 function markSaved(text='已保存，修改立即生效。'){dirty=false;C.status(text);}
 function bind(form,action){form?.addEventListener('input',()=>dirty=true);C.bind(form,action);}
 async function upload(input,purpose,status){
  const file=input.files[0];if(!file)throw {status:400,data:{detail:'请先选择文件。'}};
  const body=new FormData();body.append('file',file);body.append('purpose',purpose);status.textContent='正在上传 '+file.name+'…';
  try{const asset=await C.request('/api/assets/',{method:'POST',file:body});status.textContent='已上传：'+file.name+'，请保存表单。';dirty=true;return {...asset,name:file.name};}
  catch(e){status.textContent='上传未成功，请重试，原表单内容已保留。';throw e;}
 }
 function ownURL(path){return '/api/members/'+(new URLSearchParams(location.search).get('member')||'me')+'/'+path+'/';}
 function renderHistory(box,rows,restore){
  box.replaceChildren();if(!rows.length){box.append(N('p','暂无修改记录'));return;}
  for(const row of rows){const article=N('article');article.append(N('h3',row.title||row.display_name||'资料修改'),N('p',new Date(row.created_at).toLocaleString()));article.append(C.button('恢复这次记录',async()=>{if(dirty&&!confirm('恢复将替换表单中未保存的内容，是否继续？'))return;await restore(row);markSaved('已恢复为一条新的修改记录。');}));box.append(article);}
 }
 async function profile(){
  const endpoint=ownURL('profile');let data=await C.request(endpoint),avatar=data.avatar_asset||null;
  const f=$('#business-profile-form'),box=$('#profile-fields');
  $('#identity-summary').textContent=(data.display_name||'请完善你的姓名')+' · '+user.identity;
  function render(){
   box.replaceChildren();
   field(box,'display_name','姓名','text',data.display_name);field(box,'bio','个人简介','textarea',data.bio);
   field(box,'research_areas','研究方向（用逗号分隔）','text',(data.research_areas||[]).join('，'));
   field(box,'public_contact_email','公开联系邮箱','email',data.public_contact_email);
   check(box,'public_contact_enabled','允许展示上述公开联系邮箱',data.public_contact_enabled);
   if('phone' in data)field(box,'phone','私人联系电话（不公开）','tel',data.phone);
   if('internal_contact' in data)field(box,'internal_contact','私人联系信息（不公开）','text',data.internal_contact);
   const file=field(box,'avatar_file','头像','file');file.accept='.png,.jpg,.jpeg,.webp';
   const status=N('p',avatar?'已保存头像，可上传替换。':'未设置头像',{class:'v10-file-status',role:'status'});box.append(C.button('上传头像',async()=>{const a=await upload(file,'avatar',status);avatar=a.id;}),status);
   const privacy=$('#privacy-fields');privacy.replaceChildren();
   for(const [key,label] of Object.entries({public_visible:'在官网展示个人主页与姓名',contact_visible:'公开已启用的联系邮箱',education_visible:'公开标记为公开的教育经历',alumni_visible:'公开已授权的毕业去向'}))check(privacy,key,label,data[key]);
   if(user.role==='CUSTOMER'&&!user.is_superuser&&!new URLSearchParams(location.search).has('member')){privacy.hidden=true;$('#privacy-note').textContent='Customer 资料和简历默认私有，不会在官网展示。Teacher / Student 身份由 Root 授予。';}
   else $('#privacy-note').textContent='只展示你选择公开的内容。Teacher 编辑其他成员时不能替其扩大公开范围。';
   $('#education-rows').replaceChildren();for(const row of data.education||[])educationRow(row);
  }
  function educationRow(row={}){
   const wrap=N('fieldset');wrap.append(N('legend','教育经历'));
   for(const [key,label,type] of [['school','学校','text'],['major','专业','text'],['degree','学历/学位','text'],['start_date','开始日期','date'],['end_date','结束日期','date']])field(wrap,key,label,type,row[key]);
   check(wrap,'is_public','允许公开这条经历',row.is_public);wrap.append(C.button('移除这条经历',()=>{wrap.remove();dirty=true;}));$('#education-rows').append(wrap);
  }
  $('#add-education').onclick=()=>{educationRow();dirty=true;};render();
  bind(f,async()=>{
   const payload={lock_version:data.lock_version,avatar_asset:avatar,education:[],research_areas:formValue(f,'research_areas').split(/[,，]/).map(v=>v.trim()).filter(Boolean)};
   for(const key of ['display_name','bio','public_contact_email','phone','internal_contact'])if(f.elements[key])payload[key]=formValue(f,key);
   payload.public_contact_enabled=f.elements.public_contact_enabled.checked;
   for(const key of ['public_visible','contact_visible','education_visible','alumni_visible'])if(!$('#privacy-fields').hidden)payload[key]=f.elements[key].checked;
   for(const [index,row] of [...$('#education-rows').children].entries()){
    const values={};for(const key of ['school','major','degree','start_date','end_date'])values[key]=row.querySelector('[name='+key+']').value;
    if(!Object.values(values).some(Boolean))continue;
    payload.education.push({...values,start_date:values.start_date||null,end_date:values.end_date||null,is_public:row.querySelector('[name=is_public]').checked,position:index+1});
   }
   data=await C.request(endpoint,{method:'PATCH',data:payload});render();markSaved();$('#identity-summary').textContent=(data.display_name||'姓名待完善')+' · '+user.identity;
  });
  $('#profile-history').onclick=async()=>{try{const rows=await C.request(ownURL('history'));renderHistory($('#history-list'),rows.results,async row=>{data=await C.request(ownURL('restore'),{method:'POST',data:{lock_version:data.lock_version,source_revision:row.id}});avatar=data.avatar_asset;render();});}catch(e){C.showError(e);}};
  const editingOther=new URLSearchParams(location.search).has('member');$('#security').hidden=editingOther;
  if(!editingOther){$('#account-email').value=user.email||'';bind($('#account-email-form'),async form=>{await C.request('/api/auth/me/',{method:'PATCH',data:{email:formValue(form,'email')}});markSaved('联系邮箱已保存。');});}
 }
 async function workspace(){
  if(!user.capabilities.can_edit_content){C.status('Customer 可在个人资料和简历页填写信息，团队内容由 Teacher / Student 编辑。');$('#business-content').hidden=true;return;}
  const form=$('#workspace-filter');form.elements.mine.checked=new URLSearchParams(location.search).get('mine')==='1';let page=1;
  async function load(){
   const query=new URLSearchParams({page});for(const key of ['kind','q'])if(formValue(form,key))query.set(key,formValue(form,key));if(form.elements.mine.checked)query.set('mine','1');
   const data=await C.request('/api/content/items/?'+query),box=$('#workspace-list');box.replaceChildren();
   for(const row of data.results){const article=N('article'),r=row.revision;article.append(N('h3',r?.title||'历史工作稿'),N('p',labels[row.kind]+' · '+(row.visibility_scope==='TEAM'?'团队可见':'公开网站')+(row.visible?'':' · 已撤下')));if(row.can_edit)article.append(link('编辑内容 →','/content-editor.html?id='+encodeURIComponent(row.id)));else if(row.visibility_scope==='PUBLIC'&&row.visible)article.append(link('查看公开详情 →','/content.html?id='+encodeURIComponent(row.id)));else article.append(C.button('查看团队内容',()=>{const details=N('div');if(r?.summary)details.append(N('p',r.summary));for(const [key,value] of Object.entries(r?.detail||{}))if(value!==null&&value!==''&&value!==undefined)details.append(N('p',(schemas[row.kind]?.find(f=>f[0]===key)?.[1]||key)+'：'+value));article.append(details);}));box.append(article);}
   if(!data.count)box.append(N('p','暂无符合条件的内容。','empty-note'));
   $('#workspace-pages').replaceChildren();for(const [text,exists,delta] of [['上一页',data.previous,-1],['下一页',data.next,1]]){const b=C.button(text,async()=>{page+=delta;await load();});b.disabled=!exists;$('#workspace-pages').append(b);}
   C.status('共 '+data.count+' 条内容');
  }
  bind(form,async()=>{page=1;await load();});await load();
 }
 async function editor(){
  if(!user.capabilities.can_edit_content){$('#business-content').hidden=true;C.status('仅 Teacher / Student 可以编辑团队内容。',true);return;}
  const params=new URLSearchParams(location.search),id=params.get('id'),form=$('#direct-content-form');let item=id?await C.request('/api/content/items/'+encodeURIComponent(id)+'/'):null,authors=[],ordered=false,attachments=[],directory=[];
  if(item&&!item.can_edit){$('#business-content').hidden=true;C.status('你可以查看该内容，但没有编辑授权。',true);return;}
  const source=item?.revision;
  if(item){form.elements.kind.value=item.kind;form.elements.kind.disabled=true;form.elements.title.value=source?.title||'';form.elements.summary.value=source?.summary||'';form.elements.visibility_scope.value=item.visibility_scope;form.elements.featured.checked=item.featured;authors=[...item.authors];attachments=(source?.assets||[]).map(id=>({id,name:'已保存附件'}));$('#content-history').hidden=false;}
  else if(params.get('kind')&&schemas[params.get('kind')])form.elements.kind.value=params.get('kind');
  function details(values={}){const box=$('#detail-fields');box.replaceChildren();for(const [key,label,type='text',options] of schemas[form.elements.kind.value]){let value=values[key];if(type==='datetime-local'&&value){const d=new Date(value);value=new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);}field(box,'detail_'+key,label,type,value,false,options);}$('#author-fieldset').hidden=form.elements.kind.value==='LAB_PAGE';}
  details(source?.detail);form.elements.kind.onchange=()=>{details();authors=[];renderAuthors();dirty=true;};
  async function loadDirectory(q=''){const data=await C.request('/api/members/directory/?page_size=100&q='+encodeURIComponent(q));directory=data.results;const select=$('#author-choice');select.replaceChildren(N('option','选择团队成员',{value:''}));for(const p of directory){const o=N('option',(p.display_name||'姓名待完善')+' · '+p.identity,{value:String(p.user_id)});o.disabled=!p.selectable;select.append(o);}const grants=$('#grant-user');grants.replaceChildren(...[...select.options].map(o=>o.cloneNode(true)));}
  let timer;$('#member-search').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>loadDirectory($('#member-search').value).catch(C.showError),250);});await loadDirectory();
  function renderAuthors(){const box=$('#author-selected');box.replaceChildren();for(const [index,p] of authors.entries()){const row=N('div',undefined,{class:'member-chip'});row.append(N('strong',p.display_name));for(const [text,delta] of [['上移',-1],['下移',1]]){const b=C.button(text,()=>{const next=index+delta;[authors[index],authors[next]]=[authors[next],authors[index]];ordered=true;dirty=true;renderAuthors();});b.disabled=index+delta<0||index+delta>=authors.length;row.append(b);}row.append(C.button('移除',()=>{authors=authors.filter(a=>a.user_id!==p.user_id);dirty=true;renderAuthors();}));box.append(row);}}
  $('#add-author').onclick=()=>{const id=Number($('#author-choice').value),person=directory.find(p=>p.user_id===id);if(person?.selectable&&!authors.some(a=>a.user_id===id)){authors.push(person);dirty=true;renderAuthors();}};renderAuthors();
  if((source?.contributions||[]).length>authors.length)$('#legacy-author-note').textContent='包含历史署名，系统将保留其历史信息；新增关联只接受注册团队成员。';
  function renderAttachments(){const box=$('#attachment-list');box.replaceChildren();for(const a of attachments){const row=N('div',undefined,{class:'member-chip'});row.append(N('strong',a.name),C.button('移除',()=>{attachments=attachments.filter(v=>v!==a);dirty=true;renderAttachments();}));box.append(row);}}
  $('#upload-content').onclick=async()=>{try{const input=$('#content-file'),purpose=input.files[0]?.type.startsWith('image/')?'image':'attachment';const asset=await upload(input,purpose,$('#content-file-status'));attachments.push(asset);renderAttachments();}catch(e){C.showError(e);}};renderAttachments();
  const projects=await C.request('/api/content/items/?kind=PROJECT&page_size=100');for(const p of projects.results){if(p.id===id)continue;const option=N('option',p.revision?.title||'项目',{value:p.id});option.selected=(source?.project_links||[]).includes(p.id);$('#project-choice').append(option);}
  bind(form,async()=>{
   const detail={};for(const [key,,type='text'] of schemas[form.elements.kind.value]){const value=formValue(form,'detail_'+key);detail[key]=type==='date'||type==='datetime-local'||type==='number'?(value?(type==='datetime-local'?new Date(value).toISOString():type==='number'?value:value):null):value;}
   const payload={title:formValue(form,'title'),summary:formValue(form,'summary'),detail,visibility_scope:formValue(form,'visibility_scope'),authors:authors.map(p=>p.user_id),authors_ordered:ordered,assets:attachments.map(a=>a.id),project_links:[...$('#project-choice').selectedOptions].map(o=>o.value)};
   if(user.capabilities.can_manage_team)payload.featured=form.elements.featured.checked;
   if(item)payload.lock_version=item.lock_version;else payload.kind=form.elements.kind.value;
   item=await C.request(item?'/api/content/items/'+item.id+'/':'/api/content/items/',{method:item?'PATCH':'POST',data:payload});markSaved();
   if(!id){location.replace('/content-editor.html?id='+encodeURIComponent(item.id));return;}
  });
  $('#content-history').onclick=async()=>{try{const data=await C.request('/api/content/items/'+item.id+'/history/');renderHistory($('#history-list'),data.results,async row=>{item=await C.request('/api/content/items/'+item.id+'/restore/',{method:'POST',data:{lock_version:item.lock_version,source_revision:row.id}});dirty=false;location.reload();});}catch(e){C.showError(e);}};
  $('#grant-section').hidden=!item||!user.capabilities.can_manage_team;
  bind($('#grant-form'),async f=>{if(!item)throw {status:400,data:{detail:'先保存内容。'}};item=await C.request('/api/content/items/'+item.id+'/grants/',{method:'POST',data:{lock_version:item.lock_version,user_id:Number(formValue(f,'user_id')),revoke:f.elements.revoke.checked,can_edit:true}});markSaved('协作权限已更新。');});
 }
 async function resume(){
  let current=null,asset=null;const form=$('#resume-form');
  function reset(){current=null;asset=null;form.reset();$('#resume-file-status').textContent='未选择简历文件。';dirty=false;}
  async function load(){const data=await C.request('/api/members/me/resumes/'),box=$('#resume-list');box.replaceChildren();for(const r of data.results){const article=N('article');article.append(N('h3',r.title));if(r.intention)article.append(N('p',r.intention));article.append(C.button('编辑简历',()=>{current=r;asset=r.asset;for(const key of ['title','intention','introduction'])form.elements[key].value=r[key]||'';$('#resume-file-status').textContent=r.asset?'已保存简历文件，可上传替换。':'未设置简历文件。';dirty=false;form.scrollIntoView({behavior:'smooth',block:'start'});}));if(r.download_url)article.append(link(' 下载简历文件',r.download_url));box.append(article);}if(!data.count)box.append(N('p','还没有简历，可以在下方新建。'));}
  $('#resume-new').onclick=reset;$('#upload-resume').onclick=async()=>{try{asset=(await upload($('#resume-file'),'resume',$('#resume-file-status'))).id;}catch(e){C.showError(e);}};
  bind(form,async()=>{const payload={title:formValue(form,'title'),intention:formValue(form,'intention'),introduction:formValue(form,'introduction'),asset};if(current)payload.lock_version=current.lock_version;current=await C.request('/api/members/me/resumes/'+(current?current.id+'/':''),{method:current?'PATCH':'POST',data:payload});markSaved('简历已私密保存。');await load();});await load();
 }
 async function management(){
  if(!user.capabilities.can_manage_team){$('#business-content').hidden=true;C.status('仅 Teacher / Root 可以管理团队业务资料。',true);return;}
  async function directory(q=''){
   const data=await C.request('/api/members/directory/?page_size=100&q='+encodeURIComponent(q));$('#directory-list').replaceChildren();for(const p of data.results){const article=N('article');article.append(N('h3',p.display_name||'姓名待完善'),N('p',p.identity),link('编辑业务资料 →','/profile.html?member='+encodeURIComponent(p.profile_id)));$('#directory-list').append(article);}
   if(!data.count)$('#directory-list').append(N('p','暂无团队成员，身份由 Root 授予。'));
  }
  bind($('#directory-filter'),async f=>directory(formValue(f,'q')));await directory();
  if(!user.capabilities.can_manage_accounts)return;
  $('#root-accounts').hidden=false;let page=1;
  async function accounts(){const data=await C.request('/api/admin/users/?page='+page),box=$('#account-list');box.replaceChildren();for(const account of data.results){
   const article=N('article'),form=N('form',undefined,{class:'v10-form'});article.append(N('h3',account.display_name||'姓名待完善'),N('p','登录名：'+account.username+' · '+account.identity));
   field(form,'role','业务身份','select',account.role,false,[['CUSTOMER','Customer'],['STUDENT','Student'],['TEACHER','Teacher']]);check(form,'is_active','账号可登录',account.is_active);form.append(N('button','保存身份与状态',{type:'submit'}));
   bind(form,async f=>{await C.request('/api/admin/users/'+account.id+'/',{method:'PATCH',data:{role:formValue(f,'role'),is_active:f.elements.is_active.checked}});markSaved('账号状态已更新。');await accounts();});
   const reset=N('form',undefined,{class:'v10-form'});field(reset,'new_password','重置密码','password','',true);reset.append(N('button','为此账号重置密码',{type:'submit',class:'secondary'}));bind(reset,async f=>{await C.request('/api/admin/users/'+account.id+'/reset-password/',{method:'POST',data:{new_password:formValue(f,'new_password')}});f.reset();markSaved('目标账号密码已重置。');});article.append(form,reset);box.append(article);
  }$('#account-pages').replaceChildren();for(const [text,exists,delta] of [['上一页',data.previous,-1],['下一页',data.next,1]]){const b=C.button(text,async()=>{page+=delta;await accounts();});b.disabled=!exists;$('#account-pages').append(b);}}
  bind($('#root-create-form'),async f=>{await C.request('/api/admin/users/',{method:'POST',data:{username:formValue(f,'username'),password:formValue(f,'password'),role:formValue(f,'role')}});f.reset();markSaved('账号已创建。');await accounts();});await accounts();
 }
 async function start(){
  user=await C.boot();if(!user)return;
  document.querySelectorAll('[data-team-only]').forEach(el=>el.hidden=!user.capabilities.can_edit_content);
  document.querySelectorAll('[data-manager-only]').forEach(el=>el.hidden=!user.capabilities.can_manage_team);
  try{
   await ({profile,workspace,editor,resume,management}[mode])();
   const params=new URLSearchParams(location.search),job=params.get('ai_job');
   if(job&&['profile','editor'].includes(mode)){
    const candidate=await C.request('/api/ai/imports/'+encodeURIComponent(job)+'/');
    const records=candidate.candidate?.records||candidate.records||candidate.data?.records||[];
    const fields=records[Number(params.get('ai_record')||0)]?.fields;
    if(!fields)throw {status:400,data:{detail:'候选不可用，请返回 AI 页面重新选择。'}};
    const selected=(params.get('ai_fields')||'').split(',');
    for(const key of selected){
     if(key==='authors')continue;
     if(key==='detail'){for(const [name,value] of Object.entries(fields.detail||{})){const el=document.querySelector('[name="detail_'+name+'"]');if(el)el.value=value??'';}}
     else {const el=document.querySelector('[name="'+key+'"]');if(el)el.value=Array.isArray(fields[key])?fields[key].join('，'):fields[key]??'';}
    }
    dirty=true;C.status('候选已填入表单，请核对、选择关联成员与公开范围后保存。');
   }
  }catch(e){C.showError(e);}
 }
 addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});start();
})();
