(() => {
  'use strict';
  const C=LabContent,$=s=>document.querySelector(s);
  let item=null,contributors=[],links=[],attachments=[],projectChoices=[],dirty=false;
  const types={
    BLOG:[['body','正文','textarea',true],['category','分类']],NEWS:[['body','正文','textarea',true],['event_date','事件日期','date'],['category','分类']],PAPER:[['doi','DOI'],['venue','期刊或会议','text',true],['publication_date','发表日期','date',true],['category','论文类别'],['volume','卷'],['issue','期'],['pages','页码'],['open_url','开放访问链接','url']],PROJECT:[['project_number','项目编号'],['funder','资助方','text',true],['level','项目级别'],['start_date','开始日期','date',true],['end_date','结束日期','date'],['status','项目状态','status'],['funding_amount','内部经费','number']],AWARD:[['event_name','竞赛或奖励名称','text',true],['award_name','奖项','text',true],['award_date','获奖日期','date',true],['category','类别','award'],['level','奖励级别']],ACTIVITY:[['starts_at','开始时间','datetime-local',true],['ends_at','结束时间','datetime-local'],['location','地点'],['body','活动正文','textarea',true]],PUBLICATION:[['isbn','ISBN'],['publisher','出版社','text',true],['publication_date','出版日期','date',true],['edition','版次']],LAB_PAGE:[['page_key','固定页面','page'],['body','介绍正文','textarea',true]]
  }
  ;
  const roles={
    PAPER:['AUTHOR'],PROJECT:['LEAD','PARTICIPANT'],AWARD:['WINNER','ADVISOR'],ACTIVITY:['ORGANIZER','PARTICIPANT'],PUBLICATION:['AUTHOR','EDITOR'],BLOG:['AUTHOR'],NEWS:['AUTHOR'],LAB_PAGE:[]
  }
  ;
  function localDateTime(value){
    const d=new Date(value),pad=x=>String(x).padStart(2,'0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
  function detailFields(kind,values={
  }
  ){
    const box=$('#type-fields');
    box.replaceChildren();
    for(const [name,label,type='text',required=false]of types[kind]){
      const id='detail-'+name;
      box.append(C.node('label',label,{
        for:id
      }
      ));
      let input;
      if(['status','award','page'].includes(type)){
        input=C.node('select',undefined,{
          id,name
        }
        );
        const options={
          status:['ACTIVE','COMPLETED','CANCELLED'],award:['COMPETITION','HONOR'],page:['home','about']
        }
        [type];
        for(const option of options)input.append(C.node('option',option,{
          value:option
        }
        ));
      }
      else input=C.node(type==='textarea'?'textarea':'input',undefined,{
        id,name,...(type!=='textarea'?{
          type
        }
        :{
        }
        ),maxlength:type==='textarea'?'50000':'1000'
      }
      );
      input.required=required;
      if(values[name]!=null)input.value=type==='datetime-local'?localDateTime(values[name]):values[name];
      box.append(input);
    }
  }
  function contributionRows(){
    const box=$('#contribution-list');
    box.replaceChildren();
    const kind=$('#kind').value;
    links.forEach((link,index)=>{
      const row=C.node('div',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('strong',link.name||contributors.find(c=>c.id===link.contributor)?.display_name||'贡献者'));
      const role=C.node('select',undefined,{
        'aria-label':`贡献者 ${index+1} 的职责`
      }
      );
      for(const r of roles[kind])role.append(C.node('option',r,{
        value:r
      }
      ));
      role.value=link.contribution_role;
      role.onchange=()=>{
        link.contribution_role=role.value;
      }
      ;
      const position=C.node('input',undefined,{
        type:'number',min:'1',max:'100','aria-label':`贡献者 ${index+1} 的顺序`
      }
      );
      position.value=link.position;
      position.oninput=()=>{
        link.position=Number(position.value);
      }
      ;
      const label=C.node('label','通信作者');
      const check=C.node('input',undefined,{
        type:'checkbox'
      }
      );
      check.checked=link.is_corresponding;
      check.onchange=()=>{
        link.is_corresponding=check.checked;
      }
      ;
      label.prepend(check);
      row.append(role,position,label,C.node('span',link.confirmation_status||'待确认',{
        class:'work-badge'
      }
      ),C.button('移除此署名',()=>{
        dirty=true;links.splice(index,1);
        contributionRows();
      }
      ));
      box.append(row);
    }
    );
  }
  function preview(box,revision){
    box.replaceChildren();
    if(!revision){
      box.append(C.node('p','暂无版本。'));
      return;
    }
    box.append(C.node('h3',revision.title),C.node('p',`${revision.state} · 第 ${revision.number} 版`),C.node('p',revision.summary||''));
    const dl=C.node('dl');
    for(const [key,value]of Object.entries(revision.detail||{
    }
    )){
      if(value===null||value==='')continue;
      const label=(types[item?.kind||$('#kind').value].find(x=>x[0]===key)||[key,key])[1];
      dl.append(C.node('dt',label),C.node('dd',String(value)));
    }
    box.append(dl);
    for(const c of revision.contributions||[])box.append(C.node('p',`${c.name} · ${c.contribution_role} · ${c.position} · ${c.confirmation_status}`));
  }
  function attachmentRows(){
    const box=$('#attachment-list');box.replaceChildren();
    const editable=!item||(item.can_edit&&item.working_revision?.state==='DRAFT'&&!item.archived);
    for(const id of attachments){const row=C.node('p','附件 '+id+' ');row.append(C.node('a','下载附件',{href:`/api/assets/${encodeURIComponent(id)}/download/`,target:'_blank',rel:'noopener noreferrer'}));if(editable){const b=C.button('移除此附件',()=>{attachments=attachments.filter(x=>x!==id);dirty=true;attachmentRows();});row.append(b);}box.append(row);}
  }
  function permissions(){
    $('#content-form').hidden=false;
    const r=item?.working_revision,editable=!item||(item.can_edit&&r?.state==='DRAFT'&&!item.archived);
    C.disabled($('#save-content'),!editable);
    C.disabled($('#upload-attachment'),!editable);
    attachmentRows();
    C.disabled($('#submit-content'),!item||!editable);
    C.disabled($('#discard-content'),!item||!editable);
    C.disabled($('#withdraw-content'),!item||r?.state!=='SUBMITTED'||!item.can_edit);
    C.disabled($('#clone-content'),!item||!!r||item.archived||!item.can_edit);
    C.disabled($('#approve-content'),!item?.can_review);
    C.disabled($('#reject-content'),!item?.can_review);
    $('#grant-card').hidden=!item||!(C.manager(C.user)||item.created_by===C.user.id);
    $('#external-card').hidden=!editable;
    $('#review-eligibility').textContent=item?.can_review?'请核对字段、来源和关联署名后审核。':'当前版本暂不可审核，请检查是否已提交、已处理、已归档或发布基线变化。';
    $('#content-form').querySelectorAll('input,textarea,select').forEach(input=>{
      input.disabled=!editable;
    }
    );
    $('#kind').disabled=!!item;
    $('#contributor-box').querySelectorAll('button').forEach(b=>C.disabled(b,!editable));
  }
  async function load(){
    const id=new URLSearchParams(location.search).get('id');
    if(!id){
      detailFields($('#kind').value);
      permissions();
      return;
    }
    $('#content-form').hidden=true;
    item=await C.request(`/api/content/items/${encodeURIComponent(id)}/`);
    const r=item.working_revision||item.published_revision;
    attachments=r?.assets||[];
    $('#kind').value=item.kind;
    $('#title').value=r?.title||'';
    $('#summary').value=r?.summary||'';
    detailFields(item.kind,r?.detail||{
    }
    );
    links=(r?.contributions||[]).map(x=>({
      ...x
    }
    ));
    contributionRows();
    $('#project-links').replaceChildren();
    for(const p of projectChoices)$('#project-links').append(C.node('option',p.title,{
      value:p.id
    }
    ));
    for(const id of r?.project_links||[]){
      let option=[...$('#project-links').options].find(o=>o.value===id);
      if(!option){
        option=C.node('option','现有关联项目（信息未对你公开）',{
          value:id
        }
        );
        $('#project-links').append(option);
      }
      option.selected=true;
    }
    $('#item-state').textContent=`当前版本 ${r?.number||'—'} · ${r?.state||'无活动版本'}${item.archived?' · 已归档':''}${!item.visible?' · 未公开':''}`;
    preview($('#published-preview'),item.published_revision);
    preview($('#working-preview'),item.working_revision);
    $('#grant-list').replaceChildren(...item.grants.map(g=>C.node('p',`账号 ${g.user_id} · ${g.revoked?'已撤销':g.can_edit?'可编辑':'只读'}`)));
    const history=await C.request(`/api/content/items/${item.id}/history/`);
    $('#history-list').replaceChildren();
    for(const rev of history.results){
      const row=C.node('div',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('p',`第 ${rev.number} 版 · ${rev.state} · ${rev.title}`));
      if(rev.decision)row.append(C.node('p',`${rev.decision.decision}：${rev.decision.reason}`));
      $('#history-list').append(row);
    }
    await moderationHistory();
    $('#proxy-confirmations').replaceChildren();
    if(C.manager(C.user)&&item.working_revision)for(const link of item.working_revision.contributions){
      const row=C.node('div',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('p',`${link.name} · ${link.confirmation_status}${link.confirmation_note?' · '+link.confirmation_note:''}`),C.button('记录证据代确认',async()=>{
        if(dirty)throw {status:400,data:{detail:'请先保存草稿，再确认署名；未保存输入已保留。'}};
        const reason=$('#review-reason').value.trim();
        if(!reason)throw{
          status:400,data:{
            detail:'请先填写核验理由。'
          }
        }
        ;
        await C.request(`/api/review/contributions/${link.id}/confirm/`,{
          method:'POST',data:{
            decision:'CONFIRMED',reason
          }
        }
        );
        await load();
        C.status('已追加代确认记录，仍需另一位审核者审核发布。');
      }
      ));
      $('#proxy-confirmations').append(row);
    }
    dirty=false;
    permissions();
  }
  async function moderationHistory(path){
    const data=await C.request(path||`/api/content/items/${item.id}/moderation-history/`);
    const box=$('#moderation-history');box.replaceChildren();
    for(const event of data.results)box.append(C.node('p',`${event.action}：${event.reason}`));
    for(const [url,label]of [[data.previous,'上一页管理记录'],[data.next,'下一页管理记录']])if(url)box.append(C.button(label,()=>moderationHistory(url)));
  }
  async function save(){
    const editingForm=$('#content-form');editingForm.inert=true;editingForm.setAttribute('aria-busy','true');
    try {
    const detail={
    }
    ;
    for(const [name,,type='text']of types[$('#kind').value]){
      const value=$('#detail-'+name).value;
      detail[name]=value===''&&['date','datetime-local','number'].includes(type)?null:type==='datetime-local'&&value?new Date(value).toISOString():value;
    }
    const data={
      title:$('#title').value,summary:$('#summary').value,detail,contributions:links.map(({
        contributor,contribution_role,position,is_corresponding
      }
      )=>({
        contributor,contribution_role,position,is_corresponding
      }
      ))
    }
    ;
    let result;
    if(item)result=await C.request(`/api/content/revisions/${item.working_revision.id}/`,{
      method:'PATCH',data:{
        ...data,assets:attachments,lock_version:item.lock_version,project_links:[...$('#project-links').selectedOptions].map(o=>o.value)
      }
    }
    );
    else result=await C.request('/api/content/items/',{
      method:'POST',data:{
        ...data,kind:$('#kind').value
      }
    }
    );
    if(!item && (attachments.length || $('#project-links').selectedOptions.length))result=await C.request(`/api/content/revisions/${result.working_revision.id}/`,{method:'PATCH',data:{lock_version:result.lock_version,assets:attachments,project_links:[...$('#project-links').selectedOptions].map(o=>o.value)}});
    history.replaceState(null,'',`?id=${result.id}`);
    await load();
    C.status('草稿已保存，尚未公开。');
    } finally {editingForm.inert=false;editingForm.removeAttribute('aria-busy');}
  }
  async function action(name){
    if(name==='submit'&&dirty)throw {status:400,data:{detail:'请先保存草稿，再提交审核；未保存输入已保留。'}};
    const path=name==='clone'?`/api/content/items/${item.id}/revisions/`:`/api/content/revisions/${item.working_revision.id}/${name}/`;
    await C.request(path,{
      method:'POST',data:{
        lock_version:item.lock_version
      }
    }
    );
    await load();
    C.status(name==='submit'?'已提交审核，公开版本保持原样。':name==='withdraw'?'已撤回投稿。':name==='discard'?'草稿已放弃并保留历史，可创建新版本。':'已创建新版本，请核对后保存。');
  }
  async function decision(value){
    const reason=$('#review-reason').value.trim();
    if(!reason)throw{
      status:400,data:{
        detail:'请填写审核意见。'
      }
    }
    ;
    await C.request(`/api/review/revisions/${item.working_revision.id}/decision/`,{
      method:'POST',data:{
        lock_version:item.lock_version,decision:value,reason
      }
    }
    );
    await load();
    C.status(value==='APPROVE'?'审核通过，发布版本已更新。':'已驳回并保留原公开版本。');
  }
  document.addEventListener('DOMContentLoaded',async()=>{
    if(!await C.boot())return;
    try{
      const capabilities=C.capabilities;
      if(!capabilities.can_submit&&!new URLSearchParams(location.search).get('id')){
        $('#external-card').hidden=true;
        $('#grant-card').hidden=true;
        C.status('请先完成成员身份审核，再创建内容。',true);
        return;
      }
      projectChoices=(await C.request('/api/content/projects/?page_size=100')).results;
      const data=await C.request('/api/content/contributors/?page_size=100');
      contributors=data.results;
      for(const c of contributors)$('#contributor-choice').append(C.node('option',c.display_name,{
        value:c.id
      }
      ));
      $('#kind').onchange=()=>{
        links=[];
        detailFields($('#kind').value);
        contributionRows();
      }
      ;
      $('#add-contributor').onclick=()=>{
        const selected=contributors.find(c=>c.id===$('#contributor-choice').value);
        if(!selected)return;
        dirty=true;links.push({
          contributor:selected.id,name:selected.display_name,contribution_role:roles[$('#kind').value][0]||'AUTHOR',position:links.length+1,is_corresponding:false
        }
        );
        contributionRows();
      }
      ;
      $('#content-form').addEventListener('input',()=>{dirty=true;});
      $('#content-form').addEventListener('change',()=>{dirty=true;});
      C.bind($('#content-form'),save);
      for(const name of ['submit','withdraw','discard','clone'])$('#'+name+'-content').addEventListener('click',async()=>{
        try{
          await action(name);
        }
        catch(error){
          C.showError(error);
        }
      }
      );
      $('#approve-content').onclick=async()=>{
        try{
          await decision('APPROVE');
        }
        catch(error){
          C.showError(error);
        }
      }
      ;
      $('#reject-content').onclick=async()=>{
        try{
          await decision('REJECT');
        }
        catch(error){
          C.showError(error);
        }
      }
      ;
      C.bind($('#external-form'),async form=>{
        const result=await C.request('/api/content/contributors/',{
          method:'POST',data:{
            display_name:form.elements.display_name.value,external_affiliation:form.elements.external_affiliation.value
          }
        }
        );
        contributors.push(result);
        $('#contributor-choice').append(C.node('option',result.display_name,{
          value:result.id
        }
        ));
        $('#contributor-choice').value=result.id;
        form.reset();
        C.status('外部合作者已建立，可选择后加入署名。');
      }
      );
      C.bind($('#grant-form'),async form=>{
        if(dirty)throw {status:400,data:{detail:'请先保存草稿，再调整协作授权；未保存输入已保留。'}};
        await C.request(`/api/content/items/${item.id}/grants/`,{
          method:'POST',data:{
            lock_version:item.lock_version,user_id:Number(form.elements.user_id.value),can_edit:$('#grant-edit').checked,revoke:$('#grant-revoke').checked
          }
        }
        );
        await load();
        C.status('协作授权已更新。');
      }
      );
      $('#upload-attachment').addEventListener('click',async()=>{
        const button=$('#upload-attachment');button.disabled=true;
        try{
          const file=$('#attachment-file').files[0];if(!file)throw {status:400,data:{detail:'请先选择附件。'}};
          const form=new FormData();form.append('file',file);form.append('purpose',file.type.startsWith('image/')?'image':'attachment');
          const result=await C.request('/api/assets/',{method:'POST',file:form});attachments.push(result.id);dirty=true;attachmentRows();$('#attachment-file').value='';C.status('附件已上传，请保存草稿。');
        }catch(error){C.showError(error);}finally{button.disabled=false;}
      });
      await load();
    }
    catch(error){
      C.showError(error);
    }
  }
  );
}
)();
