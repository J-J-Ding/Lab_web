(function(){
  'use strict';
  const C=window.LabContent,$=s=>document.querySelector(s);
  const names={MEMBER:'个人资料 / 简历',PAPER:'论文',PROJECT:'项目',AWARD:'竞赛 / 文本证书',ACTIVITY:'活动',NEWS:'新闻',BLOG:'博客',PUBLICATION:'出版刊物',LAB_PAGE:'实验室介绍'};
  const roles={PAPER:['AUTHOR'],PROJECT:['LEAD','PARTICIPANT'],AWARD:['WINNER','ADVISOR'],ACTIVITY:['ORGANIZER','PARTICIPANT'],NEWS:['AUTHOR'],BLOG:['AUTHOR'],PUBLICATION:['AUTHOR','EDITOR'],LAB_PAGE:[]};
  let job=null,quota=null,timer=null,backoff=2000,version=0,matches=[],candidateDirty=false;
  function stop(){clearTimeout(timer);timer=null;}
  function localError(message){return {status:400,data:{detail:message}};}
  function paths(fields){return [...Object.keys(fields).filter(k=>k!=='detail'),...Object.keys(fields.detail||{}).map(k=>'detail.'+k)];}
  async function loadQuota(){
    quota=await C.request('/api/ai/quota/');
    $('#ai-quota').textContent=(quota.enabled?'AI 已启用':'AI 暂未启用或价格配置未就绪')+` · ${quota.model} · 今日剩余 ${quota.user_remaining}/${quota.user_daily_limit} 次 · 已计量 ¥${quota.spent_cny} · 预留 ¥${quota.reserved_cny}`;
    for(const form of [$('#ai-upload-form'),$('#ai-summary-form')])form.querySelectorAll('input,select,textarea,button').forEach(el=>el.disabled=!quota.enabled);
    for(const select of [$('#ai-target'),$('#ai-summary-target')]){
      select.replaceChildren();
      for(const [key,name] of Object.entries(names)){const option=C.node('option',name,{value:key});option.disabled=key!=='MEMBER'&&!C.capabilities.can_submit;select.append(option);}
      select.value=C.capabilities.can_submit?'BLOG':'MEMBER';
    }
  }
  async function list(path='/api/ai/imports/'){
    const data=await C.request(path),box=$('#ai-jobs');box.replaceChildren();
    for(const item of data.results){const row=C.node('div',undefined,{class:'ai-job'});row.append(C.button(`${names[item.target_type]} · ${item.state} · ${item.id}`,()=>select(item.id)));box.append(row);}
    if(!data.results.length)box.append(C.node('p','暂无 AI 任务。'));
    const pagination=$('#ai-job-pages');pagination.replaceChildren();
    for(const [url,label]of [[data.previous,'上一页'],[data.next,'下一页']])if(url)pagination.append(C.button(label,()=>list(url)));
  }
  function schedule(){
    stop();if(!job||!['QUEUED','EXTRACTING','CALLING','VALIDATING'].includes(job.state))return;
    timer=setTimeout(async()=>{try{await refresh();}catch(error){C.showError(error);}},backoff);backoff=Math.min(backoff*2,15000);
  }
  async function select(id){
    stop();const ticket=++version;
    const result=await C.request('/api/ai/imports/'+encodeURIComponent(id)+'/');if(ticket!==version)return;
    job=result;backoff=2000;candidateDirty=false;$('#ai-applied-result').replaceChildren();render();schedule();
  }
  async function refresh(){
    if(!job)return;const id=job.id,ticket=version;
    const result=await C.request('/api/ai/imports/'+id+'/');if(ticket!==version||job?.id!==id)return;
    job=result;render();schedule();
  }
  function render(){
    if(!job)return;
    $('#ai-current').hidden=false;$('#ai-job-id').textContent=job.id;$('#ai-job-state').textContent=job.state;$('#ai-job-message').textContent=job.message;
    $('#ai-job-cost').textContent=`额度状态 ${job.usage.state} · 预留 ¥${job.usage.reserved_cny} · 按配置价格计量 ${job.usage.actual_cny===null?'待结算':'¥'+job.usage.actual_cny}`;
    $('#ai-consent-form').hidden=job.state!=='AWAITING_CONSENT';
    if(job.state==='AWAITING_CONSENT'&&document.activeElement!==$('#ai-preview'))$('#ai-preview').value=job.preview;
    const candidate=job.candidate,hasRecords=candidate&&Array.isArray(candidate.records)&&candidate.records.length>0;
    $('#ai-candidate-section').hidden=!hasRecords||!['READY','APPLIED'].includes(job.state);
    if(hasRecords){
      if(!candidateDirty)$('#ai-candidate').value=JSON.stringify(candidate,null,2);
      const old=$('#ai-record').value;$('#ai-record').replaceChildren();
      candidate.records.forEach((r,index)=>$('#ai-record').append(C.node('option',`${index+1}. ${r.fields.title||r.fields.display_name||'候选'}`,{value:String(index)})));
      if(candidate.records[Number(old)])$('#ai-record').value=old;
      $('#ai-save-candidate').disabled=Object.keys(job.applied||{}).length>0;
      renderRecord();
    }
  }
  function renderRecord(){
    if(!job?.candidate?.records)return;
    const index=Number($('#ai-record').value),record=job.candidate.records[index];if(!record)return;
    $('#ai-evidence').replaceChildren();
    for(const item of record.evidence||[])$('#ai-evidence').append(C.node('p',`${item.field} · 第${item.page}页\n${item.excerpt}`,{class:'ai-evidence'}));
    for(const note of [...(job.candidate.warnings||[]),...(record.warnings||[])])$('#ai-evidence').append(C.node('p',note,{class:'ai-warning'}));
    const box=$('#ai-field-options');box.replaceChildren();
    for(const path of paths(record.fields)){
      const label=C.node('label',undefined,{class:'ai-check'}),checkbox=C.node('input',undefined,{type:'checkbox',value:path,'data-ai-field':''});label.append(checkbox,document.createTextNode('确认字段 '+path));box.append(label);
      const value=path.startsWith('detail.')?record.fields.detail[path.split('.')[1]]:record.fields[path];
      box.append(C.node('div',typeof value==='string'?value:JSON.stringify(value),{class:'ai-field-value'}));
      if((record.uncertain_fields||[]).includes(path))box.append(C.node('p','此字段存在不确定或人工修改，请结合来源核对。',{class:'ai-warning'}));
    }
    const already=job.applied?.[String(index)];C.disabled($('#ai-apply'),!!already);$('#ai-confirm-fields').checked=false;
    if(already)showApplied(already);
    $('#ai-author-matches').replaceChildren();$('#ai-duplicates').replaceChildren();matches=[];
  }
  async function loadMatches(){
    if(!job?.candidate)return;const id=job.id,ticket=version;
    const data=await C.request(`/api/ai/imports/${id}/matches/`);if(ticket!==version||job.id!==id)return;
    const index=Number($('#ai-record').value),row=data.records.find(r=>r.record_index===index);matches=row?.authors||[];
    const box=$('#ai-author-matches');box.replaceChildren();
    const authors=job.candidate.records[index].fields.authors||[];
    authors.forEach((author,i)=>{
      const id='ai-author-'+i;box.append(C.node('label',`${i+1}. ${author.name}：人工匹配贡献者`,{for:id}));const select=C.node('select',undefined,{id,'data-author-index':String(i)});select.append(C.node('option','请选择，不会自动绑定',{value:''}));
      for(const option of (matches.find(m=>m.author_index===i)?.options||[]))select.append(C.node('option',`${option.name} · ${option.affiliation||''}`,{value:option.id}));box.append(select);
      const role=C.node('select',undefined,{'data-author-role':String(i),'aria-label':`第${i+1}位作者的贡献角色`});for(const value of roles[job.target_type]||[])role.append(C.node('option',value,{value}));box.append(role);
    });
    const duplicates=$('#ai-duplicates');duplicates.replaceChildren();
    for(const item of row?.duplicates||[]){const line=C.node('p','发现已有标识，请人工核对：');line.append(C.node('span',item.title));duplicates.append(line);}
  }
  function showApplied(result){
    const href=result.kind==='MEMBER'?'member-application.html':`content-editor.html?id=${encodeURIComponent(result.target_id)}`;
    const box=$('#ai-applied-result');box.replaceChildren(C.node('p','已保存为草稿，尚未公开。'),C.node('a','打开已保存草稿',{href:new URL(href,C.root).href}));
  }
  async function readTarget(){
    if(!job)return;
    if(job.target_type==='MEMBER'){
      const [overview,draft]=await Promise.all([C.request('/api/members/me/overview/'),C.request('/api/members/me/draft/')]);
      $('#ai-target-id').value=overview.profile_id||'';$('#ai-target-version').value=draft.draft?.lock_version??'';
      C.status(draft.draft?'已读取本人草稿版本。':'本人暂无活动草稿，可在应用时建立。');
    }else{
      const id=$('#ai-target-id').value.trim();if(!id)throw localError('请先填写目标内容 ID。');
      const item=await C.request(`/api/content/items/${encodeURIComponent(id)}/`);
      if(!item.can_edit||item.working_revision?.state!=='DRAFT')throw localError('目标没有可编辑草稿，请先在内容编辑页建立新版本。');
      $('#ai-target-version').value=item.lock_version;C.status('已读取目标草稿版本；应用前如有其他编辑会返回冲突。');
    }
  }
  document.addEventListener('DOMContentLoaded',async()=>{
    for(const form of [$('#ai-upload-form'),$('#ai-summary-form')])form.querySelectorAll('input,select,textarea,button').forEach(el=>el.disabled=true);
    if(!await C.boot())return;
    try{await loadQuota();await list();}catch(error){if(error.status===404)C.status('AI 后端尚未部署，请稍后重试。',true);else C.showError(error);}
    C.bind($('#ai-upload-form'),async()=>{
      const file=$('#ai-file').files[0];if(!file)throw localError('请选择 PDF 或 DOCX。');
      const upload=new FormData();upload.append('purpose','ai_source');upload.append('file',file);
      const asset=await C.request('/api/assets/',{method:'POST',file:upload});
      const created=await C.request('/api/ai/imports/',{method:'POST',data:{asset:asset.id,target_type:$('#ai-target').value,consent_version:'local-v1'}});
      $('#ai-file').value='';$('#ai-local-consent').checked=false;await select(created.id);await list();C.status('任务已排队进行本地解析，尚未发送文档内容给模型。');
    });
    C.bind($('#ai-summary-form'),async()=>{
      let fields;try{fields=JSON.parse($('#ai-verified').value);}catch(_){throw localError('请填写合法的字段 JSON。');}
      const created=await C.request('/api/ai/summaries/',{method:'POST',data:{target_type:$('#ai-summary-target').value,verified_fields:fields,consent_version:'deepseek-text-v1'}});await select(created.id);await list();
    });
    C.bind($('#ai-consent-form'),async()=>{
      const result=await C.request(`/api/ai/imports/${job.id}/consent/`,{method:'POST',data:{lock_version:job.lock_version,consent_version:'deepseek-text-v1',text_digest:job.text_digest,selected_text:$('#ai-preview').value}});
      version++;job=result;$('#ai-remote-consent').checked=false;backoff=2000;render();schedule();C.status('已授权选中文本，候选生成中。');
    });
    $('#ai-candidate').addEventListener('input',()=>candidateDirty=true);
    $('#ai-save-candidate').addEventListener('click',async()=>{try{
      let data;try{data=JSON.parse($('#ai-candidate').value);}catch(_){throw localError('候选 JSON 格式不正确。');}
      const result=await C.request(`/api/ai/imports/${job.id}/candidate/`,{method:'PATCH',data:{lock_version:job.lock_version,candidate:data}});version++;job=result;candidateDirty=false;render();C.status('候选修改已保存，请重新逐项确认。');
    }catch(error){C.showError(error);}});
    C.bind($('#ai-apply-form'),async()=>{
      if(candidateDirty)throw localError('请先保存候选修改，再确认应用。');
      const index=Number($('#ai-record').value),fields=[...document.querySelectorAll('[data-ai-field]:checked')].map(c=>c.value);
      const data={lock_version:job.lock_version,record_index:index,confirmed_fields:fields,confirm:$('#ai-confirm-fields').checked};
      const target=$('#ai-target-id').value.trim(),targetVersion=$('#ai-target-version').value;
      if(target)data.target_id=target;if(targetVersion!=='')data.target_lock_version=Number(targetVersion);
      if(fields.includes('authors')){
        data.contributor_matches=(job.candidate.records[index].fields.authors||[]).map((author,i)=>{
          const contributor=$(`[data-author-index="${i}"]`)?.value;if(!contributor)throw localError('请刷新匹配提示并人工选择每位作者。');
          return {index:i,contributor,contribution_role:$(`[data-author-role="${i}"]`).value,position:i+1,is_corresponding:false};
        });
      }
      const result=await C.request(`/api/ai/imports/${job.id}/apply/`,{method:'POST',data});await refresh();showApplied(result);await list();await loadQuota();C.status('已保存草稿；没有自动审核或发布。');
    });
    $('#ai-record').addEventListener('change',()=>{renderRecord();});
    for(const [id,action]of [['ai-refresh-list',list],['ai-refresh',refresh],['ai-refresh-matches',loadMatches],['ai-read-target',readTarget]])$('#'+id).addEventListener('click',()=>Promise.resolve(action()).catch(C.showError));
    $('#ai-cancel').addEventListener('click',async()=>{try{stop();job=await C.request(`/api/ai/imports/${job.id}/cancel/`,{method:'POST',data:{}});version++;render();await list();await loadQuota();}catch(error){C.showError(error);}});
    $('#ai-delete').addEventListener('click',async()=>{try{stop();await C.request(`/api/ai/imports/${job.id}/`,{method:'DELETE'});version++;job=null;$('#ai-current').hidden=true;$('#ai-candidate-section').hidden=true;await list();C.status('候选已移除，业务草稿保留；原件按清理策略处理。');}catch(error){C.showError(error);}});
  });
  addEventListener('pagehide',()=>{version++;stop();job=null;});
  document.addEventListener('lab-auth-state',()=>{if(!C.user){version++;stop();job=null;}});
})();
