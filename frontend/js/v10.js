/* V10 structured forms. The server owns permissions, identifiers and revision state. */
(() => {
 'use strict';
 const C=window.LabContent,$=s=>document.querySelector(s),mode=document.body.dataset.v10Page;
 const N=(tag,text,attrs={})=>C.node(tag,text,attrs);
 let updateProfileNav=()=>{};
 let dirty=false,profileDirty=false,user,fieldSerial=0,fillProfileCandidate=null;
 const labels={PATENT:'专利',PAPER:'发表论文',PROJECT:'科研项目',AWARD:'竞赛与荣誉',NEWS:'团队新闻',ACTIVITY:'团队活动',BLOG:'文章与资源',PUBLICATION:'出版成果',LAB_PAGE:'团队介绍'};
 const schemas={
  PATENT:[["patent_number","专利号"],["application_date","申请日期","date"],["grant_date","授权日期","date"],["status","专利状态","select",[["APPLIED","申请中"],["GRANTED","已授权"],["EXPIRED","已失效"]]],["abstract","专利摘要","textarea"]],
  PAPER:[['venue','期刊/会议'],['publication_date','发表日期','date'],['doi','DOI'],['category','论文分类'],['volume','卷'],['issue','期'],['pages','页码'],['open_url','公开链接','url']],
  PROJECT:[['project_number','项目编号'],['funder','资助方'],['level','项目级别'],['start_date','开始日期','date'],['end_date','结束日期','date'],['status','项目状态','select',[['ACTIVE','进行中'],['COMPLETED','已结项'],['CANCELLED','已取消']]],['funding_amount','经费金额（内部资料）','number']],
  AWARD:[['event_name','赛事名称'],['category','成果分类','select',[['COMPETITION','学科竞赛'],['HONOR','荣誉奖励']]],['level','级别'],['award_name','奖项'],['award_date','获奖日期','date']],
  NEWS:[['event_date','新闻日期','date'],['category','分类'],['body','新闻正文','textarea']],
  ACTIVITY:[['starts_at','开始时间','datetime-local'],['ends_at','结束时间','datetime-local'],['location','活动地点'],['body','活动正文','textarea']],
  BLOG:[['event_date','日期','date'],['category','分类','select',[['','技术文章'],['RESOURCE','学习资料与下载']]],['body','正文','textarea']],
  PUBLICATION:[['isbn','ISBN'],['publisher','出版社'],['publication_date','出版日期','date'],['edition','版次']],
  LAB_PAGE:[['contact_email','招聘联系邮箱（仅联系页面使用）','email'],['page_key','页面','select',[['about','团队简介'],['contact','联系我们']]],['body','正文','textarea']]
 };
 function field(parent,name,label,type='text',value='',required=false,options){
  const wrap=N('div'),id='v10-'+(++fieldSerial)+'-'+name.replace(/[^a-z0-9_-]/gi,'-'),l=N('label',label+' ',{for:id});
  if(required)l.append(N('span','*',{class:'required'}));
  const input=N(type==='textarea'?'textarea':type==='select'?'select':'input',undefined,{name,id});
  if(type!=='textarea'&&type!=='select')input.type=type;
  if(type==='select'){for(const [v,text] of options||[]){input.append(N('option',text,{value:v}));}if(value!==null&&value!==undefined&&value!==''&&![...input.options].some(o=>o.value===String(value)))input.append(N('option','原值：'+value,{value}));}
  if(type==='password'){input.minLength=6;input.maxLength=128;input.pattern='(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9]{6,128}';input.title='6至128位英文字母与数字，且两者都包含';}
  if(type==='number'){input.min='0';input.step='any';}
  if(type!=='select'||value!==undefined&&value!==null&&value!=='')input.value=value??'';input.required=required;
  if(type==='text')input.maxLength=1000;
  wrap.append(l,input);parent.append(wrap);return input;
 }
 function check(parent,name,label,value=false){const l=N('label',undefined,{class:'check'}),input=N('input',undefined,{type:'checkbox',name});input.checked=value;l.append(input,document.createTextNode(label));parent.append(l);return input;}
 function formValue(form,name){return form.elements.namedItem(name)?.value||'';}
 function link(text,href){const a=N('a',text,{href});return a;}
 function displayValue(key,value){
  if(key==='research_areas')return value.join('、');
  if(key==='education')return value.map(e=>[e.start_date,e.end_date,e.school,e.major,e.degree].filter(Boolean).join(' · ')).join('；');
  if(key==='alumni')return [value.graduation_year,value.degree,value.organization].filter(Boolean).join(' · ');
  if(key==='cv_private')return [value.gender,value.native_region?.names?.join(' · '),value.skills,value.political_status,value.education_note,...[...(value.internships||[]),...(value.practice||[])].map(e=>[e.period||[e.start_date,e.end_date].filter(Boolean).join(' — '),e.organization,e.role,e.description].filter(Boolean).join(' · '))].filter(Boolean).join('；');
  return String(value??'');
 }
 function markSaved(text='已保存，修改立即生效。'){dirty=false;C.status(text);}
 function bind(form,action){form?.addEventListener('input',()=>dirty=true);C.bind(form,action);}
 async function upload(input,purpose,status){
  const file=input.files[0];if(!file)throw {status:400,data:{detail:'请先选择文件。'}};
  const limit=(['avatar','image'].includes(purpose)?5:purpose==='proof'?10:20)*1024*1024;
  if(!file.size||file.size>limit){status.textContent='文件须大于0且不超过'+(limit/1024/1024)+' MiB，当前文件为'+(file.size/1024/1024).toFixed(2)+' MiB。';throw {status:400,data:{detail:status.textContent}};}
  const body=new FormData();body.append('file',file);body.append('purpose',purpose);status.textContent='正在上传并校验 '+file.name+'（'+(file.size/1024/1024).toFixed(2)+' MiB，最多等待60秒）…';
  try{const asset=await C.request('/api/assets/',{method:'POST',file:body});status.textContent='已上传：'+file.name+'，请保存表单。';dirty=true;return {...asset,name:file.name};}
  catch(e){status.textContent=C.errorText(e)+' 原表单内容已保留。';throw e;}
 }
 function ownURL(path){return '/api/members/'+(new URLSearchParams(location.search).get('member')||'me')+'/'+path+'/';}
 function renderHistory(box,rows,restore){
  box.replaceChildren();if(!rows.length){box.append(N('p','暂无修改记录'));return;}
  for(const row of rows){const article=N('article');article.append(N('h3',row.title||row.display_name||'资料修改'),N('p',new Date(row.created_at).toLocaleString()));article.append(C.button('恢复这次记录',async()=>{if(dirty&&!confirm('恢复将替换表单中未保存的内容，是否继续？'))return;await restore(row);markSaved('已恢复为一条新的修改记录。');}));box.append(article);}
 }
 async function profile(){
  const options=await C.request('/api/site/profile-options/');
  const choices=values=>[['','请选择'],...values.map(v=>[v,v])];
  const years=[['','请选择年份'],...Array.from({length:new Date().getFullYear()+11-1900},(_,i)=>{const y=new Date().getFullYear()+10-i;return [String(y),String(y)+'年'];})];
  const endpoint=ownURL('profile');let data=await C.request(endpoint),avatar=data.avatar_asset||null;
  const f=$('#business-profile-form'),box=$('#profile-fields');f.addEventListener('input',()=>profileDirty=true);
  $('#identity-summary').textContent=(data.display_name||'请完善你的姓名')+' · '+user.identity;
  function render(){
   box.replaceChildren();
   field(box,'display_name','姓名','text',data.display_name);field(box,'public_member_status','成员状态','select',data.public_member_status||'ACTIVE',false,[['ACTIVE','在读/在岗'],['ALUMNI','已毕业'],['LEFT','已离开']]);field(box,'bio','个人简介','textarea',data.bio);
   $('#research-fields').replaceChildren();field($('#research-fields'),'research_areas','研究方向（用逗号分隔）','text',(data.research_areas||[]).join('，'));
   field(box,'public_contact_email','邮箱','email',data.public_contact_email,true);field(box,'highest_education','最高学历','select',data.highest_education,false,choices(['本科','硕士研究生','博士研究生']));field(box,'enrollment_year','年级 / 入学年份','select',data.enrollment_year,false,years);
   if('phone' in data)field(box,'phone','联系电话','tel',data.phone,true);
   if('internal_contact' in data)field(box,'internal_contact','其他联系信息','text',data.internal_contact);
   if('cv_private' in data){
    const cv=data.cv_private||{};field(box,'cv_skills','技能简介','textarea',cv.skills);field(box,'cv_political_status','政治面貌','select',cv.political_status,true,choices(options.political_status));field(box,'cv_gender','性别','select',cv.gender,true,choices(options.gender));renderRegion(box,cv.native_region||{});
    for(const [key,label] of [['internships','实习经历'],['practice','实践经历']]){
     const section=N('section',undefined,{id:'cv-'+key});section.append(N('h3',label+''));const rows=N('div');section.append(rows);
     function add(entry={}){const row=N('fieldset');for(const [name,title,type] of [['organization','单位 / 组织','text'],['role','岗位 / 职务','text'],['start_date','开始日期','date'],['end_date','结束日期（进行中可留空）','date'],['description','工作内容及成果','textarea']])field(row,name,title,type,entry[name]);if(entry.period){const legacy=field(row,'period','历史时间','hidden',entry.period);row.append(N('p','历史时间：'+entry.period,{class:'v10-caption'}));}row.append(C.button('移除此条',()=>{row.remove();dirty=true;profileDirty=true;}));rows.append(row);}
     for(const entry of cv[key]||[])add(entry);section.append(C.button('添加'+label,()=>{add();dirty=true;profileDirty=true;}));box.append(section);
    }
   }
   const file=field(box,'avatar_file','头像','file');file.accept='.png,.jpg,.jpeg,.webp';
   const status=N('p',avatar?'已保存头像，可上传替换。':'未设置头像',{class:'v10-file-status',role:'status'});box.append(C.button('上传头像',async()=>{const a=await upload(file,'avatar',status);avatar=a.id;profileDirty=true;}),status);
   $('#education-rows').replaceChildren();for(const row of data.education||[])educationRow(row);
   renderAlumni(data.alumni);syncAlumni();
   f.elements.public_member_status.onchange=syncAlumni;

  }
  function syncAlumni(){
   const visible=formValue(f,'public_member_status')==='ALUMNI';$('#alumni-fields').hidden=!visible;const permission=f.elements.alumni_visible?.closest('label');if(permission)permission.hidden=!visible;
   document.querySelectorAll('a[href="#alumni-fields"]').forEach(a=>a.hidden=!visible);
   $('#alumni-fields').querySelectorAll('input,select,textarea').forEach(el=>el.disabled=!visible);updateProfileNav();
  }
  function renderRegion(parent,saved){
   const section=N('div',undefined,{class:'region-fields',role:'group','aria-label':'籍贯'});section.append(N('label','籍贯',{class:'region-title'}));
   const provinces=options.regions.provinces;
   const province=field(section,'native_province','省 / 地区','select',saved.province,false,[['','请选择'],...provinces.map(r=>[r.code,r.name]),['OVERSEAS','境外']]);
   const city=field(section,'native_city','市 / 地区','select','',false,[]),district=field(section,'native_district','区县','select','',false,[]),country=field(section,'native_country','国家 / 地区','select',saved.country,false,[['','请选择'],...Object.entries(options.countries)]),note=field(section,'native_note','地区补充说明','text',saved.note);
   function populate(select,rows,value=''){select.replaceChildren(N('option','请选择',{value:''}));for(const r of rows)select.append(N('option',r.name,{value:r.code}));select.value=value;select.closest('div').hidden=!rows.length;}
   function cities(initial=false){const overseas=province.value==='OVERSEAS';country.closest('div').hidden=!overseas;note.closest('div').hidden=!overseas;if(!overseas){country.value='';note.value='';}const rows=provinces.find(p=>p.code===province.value)?.children||[];populate(city,rows,initial?saved.city:'');districts(initial);}
   function districts(initial=false){const rows=provinces.find(p=>p.code===province.value)?.children?.find(c=>c.code===city.value)?.children||[];populate(district,rows,initial?saved.district:'');}
   province.onchange=()=>cities();city.onchange=()=>districts();cities(true);parent.append(section);
  }
  function educationRow(row={}){
   const wrap=N('fieldset');wrap.append(N('legend','教育经历'));
   for(const [key,label,type] of [['school','学校','text'],['major','专业','text'],['education_level','学历','select'],['degree','学位','select'],['start_date','开始日期','date'],['end_date','结束日期','date']])field(wrap,key,label,type,row[key],false,key==='education_level'?choices(options.education_level):key==='degree'?choices(options.degree):undefined);
   wrap.append(C.button('移除这条经历',()=>{wrap.remove();dirty=true;profileDirty=true;}));$('#education-rows').append(wrap);
  }
  function renderAlumni(alumni){
   let box=$('#alumni-fields');if(!box){box=N('fieldset',undefined,{id:'alumni-fields'});$('#education').after(box);}box.replaceChildren(N('h2','毕业去向'));
   field(box,'graduation_year','毕业年份','select',alumni?.graduation_year,false,years);field(box,'alumni_degree','学位','select',alumni?.degree,false,choices(options.degree));field(box,'destination_type','去向类型','select',alumni?.destination_type||'OTHER',false,[['OTHER','其他'],['WORK','工作'],['STUDY','继续深造']]);field(box,'organization','去向单位','text',alumni?.organization);
  }
  fillProfileCandidate=(fields,selected)=>{
   if(selected.includes('education')&&Array.isArray(fields.education)){$('#education-rows').replaceChildren();for(const row of fields.education)educationRow(row);}
   if(selected.includes('alumni'))renderAlumni(fields.alumni);
  };
  $('#add-education').onclick=()=>{educationRow();dirty=true;profileDirty=true;};render();
  bind(f,async()=>{
   const payload={lock_version:data.lock_version,avatar_asset:avatar,education:[],research_areas:formValue(f,'research_areas').split(/[,，]/).map(v=>v.trim()).filter(Boolean)};
   for(const key of ['display_name','bio','public_member_status','highest_education','public_contact_email','phone','internal_contact'])if(f.elements[key])payload[key]=formValue(f,key);
   const year=formValue(f,'graduation_year');if(formValue(f,'public_member_status')==='ALUMNI')payload.alumni=year?{graduation_year:Number(year),degree:formValue(f,'alumni_degree'),destination_type:formValue(f,'destination_type'),organization:formValue(f,'organization'),is_public:false}:null;
   if('cv_private' in data){payload.cv_private={skills:formValue(f,'cv_skills'),political_status:formValue(f,'cv_political_status'),gender:formValue(f,'cv_gender'),native_region:{province:formValue(f,'native_province'),city:formValue(f,'native_city'),district:formValue(f,'native_district'),country:formValue(f,'native_country'),note:formValue(f,'native_note')}};for(const key of ['internships','practice'])payload.cv_private[key]=[...document.querySelectorAll('#cv-'+key+' fieldset')].map(row=>Object.fromEntries([...row.querySelectorAll('input,textarea')].map(input=>[input.name,input.type==='date'?(input.value||null):input.value])));}
   payload.enrollment_year=formValue(f,'enrollment_year')?Number(formValue(f,'enrollment_year')):null;
   for(const [index,row] of [...$('#education-rows').children].entries()){
    const values={};for(const key of ['school','education_level','major','degree','start_date','end_date'])values[key]=row.querySelector('[name='+key+']').value;
    if(!Object.values(values).some(Boolean))continue;
    payload.education.push({...values,start_date:values.start_date||null,end_date:values.end_date||null,is_public:false,position:index+1});
   }
   data=await C.request(endpoint,{method:'PATCH',data:payload});render();await LabAuth.refreshUser(true);profileDirty=false;markSaved();$('#identity-summary').textContent=(data.display_name||'姓名待完善')+' · '+user.identity;
  });
  $('#profile-history').onclick=async()=>{try{const rows=await C.request(ownURL('history'));renderHistory($('#history-list'),rows.results,async row=>{data=await C.request(ownURL('restore'),{method:'POST',data:{lock_version:data.lock_version,source_revision:row.id}});avatar=data.avatar_asset;render();});}catch(e){C.showError(e);}};
  const editingOther=new URLSearchParams(location.search).has('member');$('#security').hidden=editingOther;$('#resume-section').hidden=editingOther;if(!editingOther){await resume();if(['TEACHER','STUDENT'].includes(user.role)&&!user.is_superuser)await teamCV();}
  setupProfileNav();
 }
 async function teamCV(){
  if(!$('.v10-sidebar a[href="#team-cv"]'))$('.v10-sidebar a[href="#resume-section"]').before(link('生成简历Word','#team-cv'));
  const section=N('section',undefined,{class:'work-card',id:'team-cv'});$('#resume-section').before(section);section.append(N('h2','生成个人简历Word'),N('p','根据已保存的个人资料与本人参与的当前成果生成；先保存资料再预览。内部成果需逐项选择并确认，文件可能包含内部信息。'));
  const preview=N('div'),controls=N('div');section.append(C.button('预览 / 刷新简历内容',load),link('下载空白模板','/api/members/me/cv-template.docx'),preview,controls);
  async function load(){const cv=await C.request('/api/members/me/cv-data/');preview.replaceChildren(N('h3',cv.profile.display_name||'姓名待填写'));controls.replaceChildren();
   const profile=cv.profile;for(const key of ['bio','research_areas','education','cv_private'])if(profile[key])preview.append(N('p',({bio:'个人介绍',research_areas:'研究方向',education:'教育经历',cv_private:'简历补充资料'})[key]+'：'+displayValue(key,profile[key])));
   if(cv.missing_fields.length)preview.append(N('p','待完善：'+cv.missing_fields.join('、')));
   const list=N('div');const ordered=[...cv.achievements];
   function render(){list.replaceChildren();for(const [index,item] of ordered.entries()){const row=N('div',undefined,{class:'member-chip'});const checked=item.selected??item.visibility_scope==='PUBLIC';const input=check(row,'cv-item',item.title+' · 第'+item.position+'署名 · '+item.role+(item.visibility_scope==='TEAM'?' · 内部内容':''),checked);input.value=item.id;input.onchange=()=>item.selected=input.checked;
    for(const [label,delta] of [['上移',-1],['下移',1]]){const b=C.button(label,()=>{[ordered[index],ordered[index+delta]]=[ordered[index+delta],ordered[index]];render();});b.disabled=index+delta<0||index+delta>=ordered.length;row.append(b);}const duty=field(row,'cv-duty-'+item.id,'本人职责','textarea',item.duty??profile.cv_private?.responsibilities?.[item.id]??'');duty.oninput=()=>item.duty=duty.value;list.append(row);}}
   render();preview.append(list);
   controls.append(C.button('保存本人参与职责',async()=>{if(dirty&&!confirm('此操作将重新载入页面，请先保存表单中其他改动；仍要继续吗？'))return;const responsibilities=Object.fromEntries(ordered.map(item=>[item.id,item.duty??profile.cv_private?.responsibilities?.[item.id]??'']));await C.request('/api/members/me/profile/',{method:'PATCH',data:{lock_version:profile.lock_version,cv_private:{responsibilities}}});dirty=false;location.reload();}));const sections=N('fieldset');sections.append(N('legend','显示章节'));for(const label of ['教育经历','实习经历','项目经历','论文','专利','学科竞赛','实践经历','荣誉奖项'])check(sections,'cv-section',label,true).value=label;controls.append(sections);const team=check(controls,'include_team','我确认选入的内部成果可以用于本次简历',false);
   controls.append(C.button('一键生成Word',async()=>{
    const ids=[...list.querySelectorAll('input:checked')].map(i=>i.value);await LabAuth.ensureCsrf();const response=await fetch('/api/members/me/cv.docx',{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRFToken':LabAuth.csrfToken()},body:JSON.stringify({item_ids:ids,sections:[...sections.querySelectorAll('input:checked')].map(i=>i.value),include_team:team.checked,template_version:cv.template_version})});if(!response.ok)throw {status:response.status,data:await response.json()};const url=URL.createObjectURL(await response.blob()),a=link('下载',url);a.download='个人简历.docx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);C.status('Word已生成，请核对下载文件。');
   }));
  }
 }
 function setupProfileNav(){
  const sidebar=$('.v10-sidebar');let lockedUntil=0,ticking=false;
  function entries(){return [...sidebar.querySelectorAll('a[href^="#"]')].map(a=>({a,target:document.getElementById(a.hash.slice(1))})).filter(row=>row.target&&row.target.getClientRects().length);}
  function select(id){sidebar.querySelectorAll('a').forEach(a=>a.setAttribute('aria-current',String(a.hash==='#'+id)));}
  function update(){for(const a of sidebar.querySelectorAll('a')){const target=document.getElementById(a.hash.slice(1));a.hidden=!target||!target.getClientRects().length;}if(sidebar.querySelector('[aria-current=true]')?.hidden)lockedUntil=0;if(performance.now()<lockedUntil)return;const rows=entries();let selected=rows[0];for(const row of rows)if(row.target.getBoundingClientRect().top<=110)selected=row;if(scrollY+innerHeight>=document.documentElement.scrollHeight-3)selected=rows.at(-1);if(selected)select(selected.target.id);}
  sidebar.addEventListener('click',e=>{const a=e.target.closest('a');if(!a)return;const target=document.getElementById(a.hash.slice(1));if(!target?.getClientRects().length)return;e.preventDefault();lockedUntil=performance.now()+900;select(target.id);history.replaceState({},'',location.pathname+location.search+a.hash);target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});});
  window.addEventListener('scroll',()=>{if(!ticking){ticking=true;requestAnimationFrame(()=>{ticking=false;update();});}},{passive:true});window.addEventListener('resize',update);updateProfileNav=update;update();if(location.hash){const target=document.getElementById(location.hash.slice(1));if(target?.getClientRects().length){select(target.id);lockedUntil=performance.now()+900;target.scrollIntoView();}}
 }
 async function workspace(){
  if(!user.capabilities.can_edit_content){C.status('Customer 可在个人资料中填写信息，团队内容由 Teacher / Student 编辑。');$('#business-content').hidden=true;return;}
  const form=$('#workspace-filter');field(form,'scope','内容目录','select','normal',false,[['normal','正常内容'],['deleted','已删除']]);form.classList.add('list-toolbar');const reset=N('button','重置',{type:'reset'});form.append(form.querySelector('button[type=submit]'),reset);const initial=new URLSearchParams(location.search);form.elements.mine.checked=initial.get('mine')==='1';form.elements.kind.value=initial.get('kind')||'';form.elements.q.value=initial.get('q')||'';form.elements.scope.value=initial.get('scope')||'normal';let page=Math.max(1,Number(initial.get('page'))||1);let loadTicket=0;
  async function load(){
   const ticket=++loadTicket;const query=new URLSearchParams({page});for(const key of ['kind','q','scope'])if(formValue(form,key))query.set(key,formValue(form,key));if(form.elements.mine.checked)query.set('mine','1');
   history.replaceState({},'',location.pathname+'?'+query);const data=await C.request('/api/content/items/?'+query);if(ticket!==loadTicket)return;const box=$('#workspace-list');box.replaceChildren();
   for(const row of data.results){const article=N('article'),r=row.revision;if(row.cover_asset){const img=N('img',undefined,{src:'/api/assets/'+row.cover_asset+'/download/',alt:'内容封面',class:'record-thumbnail',loading:'lazy'});article.append(img);}article.append(N('h3',r?.title||'历史工作稿'));if(r?.summary)article.append(N('p',r.summary));article.append(N('p',labels[row.kind]+' · '+(row.visibility_scope==='TEAM'?'团队可见':'公开网站')+(row.visible?'':' · 已撤下')));if(row.can_edit&&!row.deleted)article.append(link('编辑内容 →','/content-editor.html?id='+encodeURIComponent(row.id)));else if(row.visibility_scope==='PUBLIC'&&row.visible)article.append(link('查看公开详情 →','/content.html?id='+encodeURIComponent(row.id)));else article.append(C.button('查看团队内容',()=>{const details=N('div');if(r?.summary)details.append(N('p',r.summary));for(const [key,value] of Object.entries(r?.detail||{}))if(value!==null&&value!==''&&value!==undefined)details.append(N('p',(schemas[row.kind]?.find(f=>f[0]===key)?.[1]||key)+'：'+value));article.append(details);}));if(row.can_edit){if(row.deleted)article.append(C.button('恢复内容',async()=>{await C.request('/api/content/items/'+row.id+'/undelete/',{method:'POST',data:{lock_version:row.lock_version}});await load();C.status('已恢复至正常目录，默认不公开；请核对后编辑保存。');}));else article.append(C.button('移入已删除',async()=>{if(!confirm('将此内容移入已删除目录？公开页面和附件引用将撤下，历史记录保留。'))return;await C.request('/api/content/items/'+row.id+'/delete/',{method:'POST',data:{lock_version:row.lock_version}});await load();}));}box.append(article);}
   if(!data.count)box.append(N('p','暂无符合条件的内容。',{class:'empty-note'}));
   $('#workspace-pages').replaceChildren();for(const [text,exists,delta] of [['上一页',data.previous,-1],['下一页',data.next,1]]){const b=C.button(text,async()=>{page+=delta;await load();});b.disabled=!exists;$('#workspace-pages').append(b);}
   C.status('共 '+data.count+' 条内容');
  }
  let timer,composing=false;
  async function apply(){clearTimeout(timer);page=1;const expected=loadTicket+1;try{await load();}catch(e){if(expected===loadTicket)C.showError(e);}}
  for(const element of form.querySelectorAll('select,input[type=checkbox]'))element.addEventListener('change',apply);
  const search=form.elements.q;search.addEventListener('compositionstart',()=>{composing=true;clearTimeout(timer);loadTicket++;});search.addEventListener('compositionend',()=>{composing=false;clearTimeout(timer);timer=setTimeout(apply,300);});search.addEventListener('input',()=>{clearTimeout(timer);loadTicket++;if(!composing){if(!search.value)apply();else timer=setTimeout(apply,300);}});
  form.onreset=()=>{clearTimeout(timer);loadTicket++;setTimeout(apply,0);};form.onsubmit=e=>{e.preventDefault();apply();};await load();

 }
 async function editor(){
  if(!user.capabilities.can_edit_content){$('#business-content').hidden=true;C.status('仅 Teacher / Student 可以编辑团队内容。',true);return;}
  const params=new URLSearchParams(location.search),id=params.get('id'),form=$('#direct-content-form');let item=id?await C.request('/api/content/items/'+encodeURIComponent(id)+'/'):null,authors=[],ordered=false,attachments=[],directory=[],cover=null;
  if(item&&(item.deleted||!item.can_edit)){$('#business-content').hidden=true;C.status('你可以查看该内容，但没有编辑授权。',true);return;}
  const source=item?.revision;
  if(item){form.elements.kind.value=item.kind;form.elements.kind.disabled=true;form.elements.title.value=source?.title||'';form.elements.summary.value=source?.summary||'';form.elements.visibility_scope.value=item.visibility_scope;form.elements.featured.checked=item.featured;authors=[...item.authors];attachments=(source?.assets||[]).map(id=>source.asset_details?.find(a=>a.id===id)||({id,name:'已保存附件'}));cover=item.cover_asset||null;$('#content-history').hidden=false;}
  else if(params.get('kind')&&schemas[params.get('kind')])form.elements.kind.value=params.get('kind');
  function details(values={}){const box=$('#detail-fields');box.replaceChildren();for(const [key,label,type='text',options] of schemas[form.elements.kind.value]){let value=values[key];if(type==='datetime-local'&&value){const d=new Date(value);value=new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);}field(box,'detail_'+key,label,type,value,false,options);}$('#author-fieldset').hidden=form.elements.kind.value==='LAB_PAGE';}
  details(source?.detail||{page_key:params.get('page_key')||'about'});
  if(!item&&params.get('page_key')==='contact'){
   const pages=await C.request('/api/content/items/?kind=LAB_PAGE&page_size=100');const existing=pages.results.find(p=>p.revision?.detail?.page_key==='contact');if(existing){location.replace('/content-editor.html?id='+existing.id);return;}form.elements.title.value='联系我们';
  }form.elements.kind.onchange=()=>{details();authors=[];renderAuthors();dirty=true;};
  async function loadDirectory(q=''){const data=await C.request('/api/members/directory/?page_size=100&q='+encodeURIComponent(q));directory=data.results;const select=$('#author-choice');select.replaceChildren(N('option','选择团队成员',{value:''}));for(const p of directory){const o=N('option',(p.display_name||'姓名待完善')+' · '+p.identity,{value:String(p.user_id)});o.disabled=!p.selectable;select.append(o);}const grants=$('#grant-user');grants.replaceChildren(...[...select.options].map(o=>o.cloneNode(true)));}
  let timer;$('#member-search').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>loadDirectory($('#member-search').value).catch(C.showError),250);});await loadDirectory();
  function renderAuthors(){const box=$('#author-selected');box.replaceChildren();for(const [index,p] of authors.entries()){const row=N('div',undefined,{class:'member-chip'});row.append(N('strong',p.display_name));for(const [text,delta] of [['上移',-1],['下移',1]]){const b=C.button(text,()=>{const next=index+delta;[authors[index],authors[next]]=[authors[next],authors[index]];ordered=true;dirty=true;renderAuthors();});b.disabled=index+delta<0||index+delta>=authors.length;row.append(b);}row.append(C.button('移除',()=>{authors=authors.filter(a=>a.user_id!==p.user_id);dirty=true;renderAuthors();}));box.append(row);}}
  $('#add-author').onclick=()=>{const id=Number($('#author-choice').value),person=directory.find(p=>p.user_id===id);if(person?.selectable&&!authors.some(a=>a.user_id===id)){authors.push(person);dirty=true;renderAuthors();}};renderAuthors();
  if((source?.contributions||[]).length>authors.length)$('#legacy-author-note').textContent='包含历史署名，系统将保留其历史信息；新增关联只接受注册团队成员。';
  const coverBox=N('section',undefined,{class:'cover-uploader'}),preview=N('div'),coverControls=N('div');
  coverControls.append(N('h2','封面图'),N('p','用于列表、首页和详情展示',{class:'v10-caption'}));
  const coverInput=N('input',undefined,{type:'file',id:'cover-file',accept:'.png,.jpg,.jpeg,.webp','aria-label':'选择封面图片'}),coverStatus=N('p',undefined,{class:'v10-file-status',role:'status'});
  function showCover(){preview.replaceChildren();if(cover){const img=N('img',undefined,{src:'/api/assets/'+cover+'/download/',alt:'当前封面预览'});preview.append(img);}else preview.append(N('div','未设置封面',{class:'cover-placeholder'}));}
  coverControls.append(coverInput,C.button('上传封面',async()=>{const asset=await upload(coverInput,'image',coverStatus);attachments.push(asset);cover=asset.id;showCover();renderAttachments();}),C.button('移除封面',()=>{cover=null;dirty=true;showCover();}),coverStatus);coverBox.append(preview,coverControls);$('#detail-fields').after(coverBox);showCover();
  function renderAttachments(){const box=$('#attachment-list');box.replaceChildren();for(const a of attachments){const row=N('div',undefined,{class:'member-chip'});row.append(N('strong',a.name),C.button('移除',()=>{attachments=attachments.filter(v=>v!==a);if(cover===a.id){cover=null;showCover();}dirty=true;renderAttachments();}));box.append(row);}}
  $('#upload-content').onclick=async()=>{try{const input=$('#content-file'),purpose=input.files[0]?.type.startsWith('image/')?'image':'attachment';const asset=await upload(input,purpose,$('#content-file-status'));attachments.push(asset);renderAttachments();}catch(e){C.showError(e);}};renderAttachments();
  const projects=await C.request('/api/content/items/?kind=PROJECT&page_size=100');for(const p of projects.results){if(p.id===id)continue;const option=N('option',p.revision?.title||'项目',{value:p.id});option.selected=(source?.project_links||[]).includes(p.id);$('#project-choice').append(option);}
  bind(form,async()=>{
   const detail={};for(const [key,,type='text'] of schemas[form.elements.kind.value]){const value=formValue(form,'detail_'+key);detail[key]=type==='date'||type==='datetime-local'||type==='number'?(value?(type==='datetime-local'?new Date(value).toISOString():type==='number'?value:value):null):value;}
   const payload={title:formValue(form,'title'),summary:formValue(form,'summary'),detail,visibility_scope:formValue(form,'visibility_scope'),authors:authors.map(p=>p.user_id),authors_ordered:ordered,assets:attachments.map(a=>a.id),cover_asset:cover,project_links:[...$('#project-choice').selectedOptions].map(o=>o.value)};
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
  let current=null,asset=null;
  const form=$('#resume-form'),customer=user.role==='CUSTOMER'&&!user.is_superuser,previewBox=$('#resume-preview');
  $('#resume-primary').hidden=!customer;
  $('#resume-file').before(N('p','支持 PDF、DOCX，单个文件不超过 20 MiB（20,971,520 字节）；PDF 限 1–100 页，不支持加密文件。',{class:'v10-caption'}));
  const submissions=N('div',undefined,{id:'resume-submissions',class:'v10-list'});previewBox.after(submissions);
  if(customer)form.before(N('p','投递后，团队老师和Root可以查看本次简历和随投递提交的个人资料。请先保存资料并核对共享预览。',{id:'resume-submit-note',class:'v10-caption'}));
  function status(text,error=false){$('#resume-status').textContent=text;$('#resume-status').dataset.kind=error?'error':'info';C.status(text,error);}
  async function loadSubmissions(){
   if(!customer)return;
   const rows=await C.request('/api/members/me/resume-submissions/');submissions.replaceChildren(N('h3','我的投递记录'));
   for(const row of rows.results){const article=N('article');article.append(N('p',row.title+' · '+(row.state==='SUBMITTED'?'已投递':'已撤回')));
    if(row.state==='SUBMITTED')article.append(C.button('撤回投递',async()=>{if(!confirm('撤回后老师将不能继续查看本次投递，是否继续？'))return;await C.request('/api/members/me/resume-submissions/'+row.id+'/withdraw/',{method:'POST',data:{}});await loadSubmissions();status('已撤回投递，老师无法继续访问本次资料。');}));submissions.append(article);
   }
  }
  async function preview(r){
   if(profileDirty){status('请先保存个人资料，再预览投递；未保存输入已保留。',true);return;}
   if(!r.asset){status('请先上传有效简历文件并保存，再进行投递。',true);return;}
   const saved=await C.request('/api/members/me/profile/');
   if(!saved.display_name?.trim()){status('请先保存个人资料中的姓名，再进行投递。',true);return;}
   previewBox.replaceChildren();const preview=N('section',undefined,{class:'work-card'});preview.append(N('h3','本次共享资料预览'));
   for(const [key,label] of Object.entries({display_name:'姓名',highest_education:'最高学历',public_contact_email:'邮箱',bio:'个人介绍',phone:'联系电话',internal_contact:'私人联系信息',education:'教育经历',research_areas:'研究方向',cv_private:'简历补充资料'})){const value=saved[key];if(value&&(!Array.isArray(value)||value.length))preview.append(N('p',label+'：'+displayValue(key,value)));}
   if(saved.public_member_status==='ALUMNI'&&saved.alumni)preview.append(N('p','毕业去向：'+displayValue('alumni',saved.alumni)));
   preview.append(N('p','简历：'+r.title+'。确认后，团队老师和Root可查看以上已保存资料及本次文件。'));
   preview.append(C.button('确认共享并投递',async()=>{
    if(profileDirty){status('请先保存个人资料并重新预览，再确认投递。',true);return;}
    await C.request('/api/members/me/resume-submissions/',{method:'POST',data:{resume_id:r.id,consent:true}});previewBox.replaceChildren();status('已投递，团队老师可在站内通知查看。');await loadSubmissions();
   }),C.button('取消',()=>previewBox.replaceChildren()));previewBox.append(preview);status('简历已保存，请核对共享资料后确认投递。');preview.scrollIntoView({behavior:'smooth',block:'center'});
  }
  function reset(){current=null;asset=null;form.reset();previewBox.replaceChildren();$('#resume-file-status').textContent='请上传文件后保存，上传成功不代表已投递。';dirty=profileDirty;status('正在新建简历。');}
  async function load(){
   const data=await C.request('/api/members/me/resumes/'),box=$('#resume-list');box.replaceChildren();
   for(const r of data.results){const article=N('article');article.append(N('h3',r.title));
    article.append(C.button('编辑简历',()=>{current=r;asset=r.asset;for(const key of ['title','introduction'])form.elements[key].value=r[key]||'';$('#resume-file-status').textContent=r.asset?'已保存简历文件，可上传替换。':'未设置简历文件。';dirty=profileDirty;previewBox.replaceChildren();form.scrollIntoView({behavior:'smooth',block:'start'});}));
    if(r.download_url)article.append(link('下载简历文件',r.download_url));if(customer)article.append(C.button('预览并投递简历',()=>preview(r)));box.append(article);
   }
   if(!data.count)box.append(N('p','尚无已保存简历；上传后可在下方直接保存并预览投递。',{class:'v10-caption'}));
  }
  $('#resume-new').onclick=reset;
  $('#upload-resume').onclick=async()=>{const button=$('#upload-resume');button.disabled=true;try{asset=(await upload($('#resume-file'),'resume',$('#resume-file-status'))).id;previewBox.replaceChildren();status('文件已上传，尚未投递。');}catch(e){C.showError(e);status($('#business-status').textContent,true);}finally{button.disabled=false;}};
  form.addEventListener('input',()=>previewBox.replaceChildren());
  bind(form,async(_,submitter)=>{
   const submitting=submitter?.id==='resume-primary';
   if(submitting&&profileDirty){status('请先保存个人资料，再预览投递；未保存输入已保留。',true);return;}
   if(submitting&&!asset){status('请先上传有效简历文件，再保存并预览投递。',true);return;}
   const payload={title:formValue(form,'title'),introduction:formValue(form,'introduction'),asset};if(current)payload.lock_version=current.lock_version;
   try{current=await C.request('/api/members/me/resumes/'+(current?current.id+'/':''),{method:current?'PATCH':'POST',data:payload});dirty=profileDirty;status('简历已保存，尚未投递。');await load();if(submitting)await preview(current);}
   catch(e){C.showError(e);status($('#business-status').textContent,true);}
  });await load();await loadSubmissions();
 }
 async function management(){
  if(!user.capabilities.can_manage_team){$('#business-content').hidden=true;C.status('仅 Teacher / Root 可以管理团队业务资料。',true);return;}
  $('#business-content').prepend(link('编辑联系信息','/content-editor.html?kind=LAB_PAGE&page_key=contact'));
  let directoryTicket=0;
  async function directory(q=''){
   const ticket=++directoryTicket;const data=await C.request('/api/members/directory/?page_size=100&q='+encodeURIComponent(q));if(ticket!==directoryTicket)return;$('#directory-list').replaceChildren();for(const p of data.results){const article=N('article');article.append(N('h3',p.display_name||'姓名待完善'),N('p',p.identity),link('编辑业务资料 →','/profile.html?member='+encodeURIComponent(p.profile_id)));$('#directory-list').append(article);}
   if(!data.count)$('#directory-list').append(N('p','暂无团队成员，身份由 Root 授予。'));
  }
  bind($('#directory-filter'),async f=>directory(formValue(f,'q')));await directory();
  if(!user.capabilities.can_manage_accounts)return;
  $('#root-accounts').hidden=false;let page=1,accountQuery='',accountTicket=0,searchTimer,searchComposing=false;
  const search=N('form',undefined,{class:'account-search',role:'search'}),searchInput=field(search,'account_q','搜索账号 / 姓名','search');searchInput.maxLength=100;searchInput.placeholder='输入用户名或姓名';search.append(N('button','搜索',{type:'submit'}));$('#account-list').before(search);
  function searchAccounts(){clearTimeout(searchTimer);accountQuery=searchInput.value.trim();page=1;accounts().catch(C.showError);}
  search.onsubmit=e=>{e.preventDefault();searchAccounts();};searchInput.oncompositionstart=()=>searchComposing=true;searchInput.oncompositionend=()=>{searchComposing=false;searchAccounts();};searchInput.oninput=()=>{if(!searchComposing){clearTimeout(searchTimer);accountTicket++;searchTimer=setTimeout(searchAccounts,300);}};
  async function accounts(){
   const ticket=++accountTicket,data=await C.request('/api/admin/users/?page='+page+'&q='+encodeURIComponent(accountQuery)),box=$('#account-list');if(ticket!==accountTicket)return;
   box.replaceChildren(N('p','共 '+data.count+' 个账号',{class:'v10-caption',role:'status'}));
   const scroll=N('div',undefined,{class:'account-table-scroll'}),table=N('table',undefined,{class:'account-table'}),head=N('thead'),headRow=N('tr'),body=N('tbody');
   for(const title of ['用户名','姓名','账号身份与状态','重置密码'])headRow.append(N('th',title,{scope:'col'}));head.append(headRow);table.append(head,body);scroll.append(table);box.append(scroll);
   for(const account of data.results){
    const row=N('tr'),username=N('td',account.username),name=N('td',account.display_name||'姓名待完善'),identity=N('td'),password=N('td'),form=N('form',undefined,{class:'v10-form account-role-form'});
    if(account.is_superuser)form.append(N('strong','Root',{class:'account-root-badge'}));
    field(form,'role','业务身份','select',account.role,false,[['CUSTOMER','Customer'],['STUDENT','Student'],['TEACHER','Teacher']]);check(form,'is_active','账号可登录',account.is_active);form.append(N('button','保存身份与状态',{type:'submit'}));
    bind(form,async f=>{await C.request('/api/admin/users/'+account.id+'/',{method:'PATCH',data:{role:formValue(f,'role'),is_active:f.elements.is_active.checked}});markSaved('账号状态已更新。');await accounts();});identity.append(form);
    const reset=N('form',undefined,{class:'v10-form account-password-form'}),input=field(reset,'new_password','新密码','password','',true);input.autocomplete='new-password';reset.append(N('button','重置密码',{type:'submit',class:'secondary'}));
    bind(reset,async f=>{await C.request('/api/admin/users/'+account.id+'/reset-password/',{method:'POST',data:{new_password:formValue(f,'new_password')}});f.reset();markSaved('目标账号密码已重置。');});password.append(reset);row.append(username,name,identity,password);body.append(row);
   }
   if(!data.count){const row=N('tr');row.append(N('td','没有匹配的账号',{colspan:'4'}));body.append(row);}
   $('#account-pages').replaceChildren();for(const [text,exists,delta] of [['上一页',data.previous,-1],['下一页',data.next,1]]){const button=C.button(text,async()=>{page+=delta;await accounts();});button.disabled=!exists;$('#account-pages').append(button);}
  }
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
    if(mode==='profile'&&fillProfileCandidate)fillProfileCandidate(fields,selected);
    for(const key of selected){
     if(['authors','education','alumni'].includes(key))continue;
     if(key.startsWith('detail.')){const name=key.slice(7);if(schemas[document.querySelector('[name=kind]')?.value]?.some(row=>row[0]===name)){const el=document.querySelector('[name=detail_'+name+']');if(el)el.value=fields.detail?.[name]??'';}continue;}
     if(key==='detail'){for(const [name,value] of Object.entries(fields.detail||{})){const el=document.querySelector('[name="detail_'+name+'"]');if(el)el.value=value??'';}}
     else {const el=document.querySelector('[name="'+key+'"]');if(el)el.value=Array.isArray(fields[key])?fields[key].join('，'):fields[key]??'';}
    }
    dirty=true;C.status('候选已填入表单，请核对、选择关联成员与公开范围后保存。');
   }
  }catch(e){C.showError(e);}
 }
 addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});start();
})();
