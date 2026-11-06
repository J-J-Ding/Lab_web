(() => {
  'use strict';
  const C=LabContent,$=s=>document.querySelector(s);
  let draft=null,overview=null,avatar=null,pendingProof=null,dirty=false;
  function education(entry={
  }
  ){
    const row=C.node('div',undefined,{
      class:'work-row','data-education':''
    }
    );
    const id='edu-'+Math.random().toString(36).slice(2);
    for(const [key,label,type]of [['school','学校','text'],['major','专业','text'],['degree','学位','text'],['start_date','入学日期','date'],['end_date','结束日期','date']]){
      const input=C.node('input',undefined,{
        id:id+key,type,'data-key':key,maxlength:'200'
      }
      );
      input.value=entry[key]||'';
      row.append(C.node('label',label,{
        for:id+key
      }
      ),input);
    }
    const check=C.node('input',undefined,{
      type:'checkbox','data-key':'is_public'
    }
    );
    check.checked=!!entry.is_public;
    const label=C.node('label','可公开此经历');
    label.prepend(check);
    row.append(label,C.button('移除教育经历',()=>{dirty=true;row.remove();}));
    $('#education-list').append(row);
  }
  function render(){
    const editable=draft?.state==='DRAFT';
    $('#member-form').hidden=!draft;
    $('#publish-member-form').querySelectorAll('input').forEach(x=>{x.disabled=!editable;});
    $('#member-state').textContent=draft?`资料第 ${draft.number} 版 · ${draft.state} · 档案类型 ${draft.member_kind} · 成员状态 ${overview?.membership_status||'PENDING'}`:'尚未建立成员资料草稿。';
    $('#member-form').querySelectorAll('input,textarea,button').forEach(x=>{
      x.disabled=!editable;
    }
    );
    C.disabled($('#save-member'),!editable);
    C.disabled($('#submit-member'),!editable||!['ACTIVE','ALUMNI'].includes(overview?.membership_status));
    C.disabled($('#withdraw-member'),draft?.state!=='SUBMITTED');
    $('#avatar-form').querySelector('button').disabled=!editable;
    C.disabled($('#initialize-profile'),!!draft);
  }
  function populate(){
    dirty=false;
    if(!draft){
      render();
      return;
    }
    for(const key of ['display_name','slug','bio','public_contact_email'])$('#member-form').elements[key].value=draft[key]||'';
    $('#contact-enabled').checked=draft.public_contact_enabled;
    $('#research-areas').value=draft.research_areas.join('，');
    $('#education-list').replaceChildren();
    for(const e of draft.education)education(e);
    const a=draft.alumni;
    $('#has-alumni').checked=!!a;
    $('#graduation-year').value=a?.graduation_year||'';
    $('#alumni-degree').value=a?.degree||'';
    $('#destination-type').value=a?.destination_type||'WORK';
    $('#organization').value=a?.organization||'';
    $('#alumni-public').checked=!!a?.is_public;
    avatar=draft.avatar_asset;
    for(const key of ['public_visible','contact_visible','education_visible','alumni_visible'])$('#publish-member-form').elements[key].checked=!!draft.publication_consent?.[key];
    render();
  }
  async function applications(path='/api/members/applications/'){
    const data=await C.request(path),box=$('#application-list');
    box.replaceChildren();
    if(!data.results.length)box.append(C.node('p','暂无申请记录。'));
    for(const a of data.results){
      const row=C.node('article',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('p',`${a.application_kind} · ${a.state}`));
      if(a.review_note)row.append(C.node('p',a.review_note));
      if(['DRAFT','SUBMITTED'].includes(a.state))row.append(C.button('撤回身份申请',async()=>{
        await C.request(`/api/members/applications/${a.id}/withdraw/`,{
          method:'POST',data:{
            lock_version:a.lock_version
          }
        }
        );
        await applications();
        C.status('申请已撤回。');
      }
      ));
      box.append(row);
    }
    for(const [url,label]of [[data.previous,'上一页申请'],[data.next,'下一页申请']])if(url)box.append(C.button(label,()=>applications(url)));
  }
  async function load(){
    const result=await C.request('/api/members/me/draft/');
    draft=result.draft;
    overview=await C.request('/api/members/me/overview/');
    populate();
    await applications();
  }
  function values(){
    const form=$('#member-form');
    const educationData=[...$('#education-list').children].map((row,index)=>{
      const data={
        position:index+1
      }
      ;
      row.querySelectorAll('[data-key]').forEach(input=>{
        data[input.dataset.key]=input.type==='checkbox'?input.checked:input.value||(['start_date','end_date'].includes(input.dataset.key)?null:'');
      }
      );
      return data;
    }
    );
    let alumni=null;
    if($('#has-alumni').checked)alumni={
      graduation_year:Number($('#graduation-year').value),degree:$('#alumni-degree').value,destination_type:$('#destination-type').value,organization:$('#organization').value,is_public:$('#alumni-public').checked
    }
    ;
    return {
      lock_version:draft.lock_version,display_name:form.elements.display_name.value,slug:form.elements.slug.value,bio:form.elements.bio.value,public_contact_email:form.elements.public_contact_email.value,public_contact_enabled:$('#contact-enabled').checked,research_areas:$('#research-areas').value.split(/[,，]/).map(x=>x.trim()).filter(Boolean),education:educationData,alumni,avatar_asset:avatar
    }
    ;
  }
  document.addEventListener('DOMContentLoaded',async()=>{
    if(!await C.boot())return;
    $('#initialize-profile').onclick=async()=>{
      try{
        draft=await C.request('/api/members/me/draft/',{
          method:'POST',data:{
          }
        }
        );
        overview=await C.request('/api/members/me/overview/');
        populate();
        C.status('资料草稿已准备，保存不会直接公开。');
      }
      catch(error){
        C.showError(error);
      }
    }
    ;
    $('#add-education').onclick=()=>{
      dirty=true;education();
      render();
    }
    ;
    $('#member-form').addEventListener('input',()=>{dirty=true;});
    $('#member-form').addEventListener('change',()=>{dirty=true;});
    C.bind($('#member-form'),async()=>{
      const editingForm=$('#member-form');editingForm.inert=true;editingForm.setAttribute('aria-busy','true');
      try {
      draft=await C.request('/api/members/me/draft/',{
        method:'PATCH',data:values()
      }
      );
      populate();
      C.status('成员草稿已保存，尚未公开。');
      } finally {editingForm.inert=false;editingForm.removeAttribute('aria-busy');}
    }
    );
    C.bind($('#avatar-form'),async()=>{
      if(!draft||draft.state!=='DRAFT')return;
      const file=$('#avatar-file').files[0],form=new FormData();
      form.append('purpose','avatar');
      form.append('file',file);
      const asset=await C.request('/api/assets/',{
        method:'POST',file:form
      }
      );
      draft=await C.request('/api/members/me/draft/',{
        method:'PATCH',data:{
          lock_version:draft.lock_version,avatar_asset:asset.id
        }
      }
      );
      avatar=asset.id;
      $('#avatar-result').textContent='头像已安全保存，公开展示仍需资料审核。';
      $('#avatar-file').value='';
      render();
      C.status('头像已保存；其他尚未保存的表单输入保持不变。');
    }
    );
    C.bind($('#publish-member-form'),async form=>{
      if(dirty)throw {status:400,data:{detail:'请先保存成员草稿，再提交审核；未保存输入已保留。'}};
      const data={
        lock_version:draft.lock_version
      }
      ;
      for(const key of ['public_visible','contact_visible','education_visible','alumni_visible'])data[key]=form.elements[key].checked;
      draft=await C.request('/api/members/me/draft/submit/',{
        method:'POST',data
      }
      );
      render();
      C.status('公开资料已提交审核，原公开版本保持不变。');
    }
    );
    $('#withdraw-member').onclick=async()=>{
      try{
        await C.request('/api/members/me/draft/withdraw/',{
          method:'POST',data:{
            lock_version:draft.lock_version
          }
        }
        );
        await load();
        C.status('资料已撤回，可重建草稿修改。');
      }
      catch(error){
        C.showError(error);
      }
    }
    ;
    $('#proof-file').onchange=()=>{
      pendingProof=null;
    }
    ;
    C.bind($('#application-form'),async form=>{
      const file=$('#proof-file').files[0];
      if(file&&!pendingProof){
        const upload=new FormData();
        upload.append('purpose','proof');
        upload.append('file',file);
        pendingProof=(await C.request('/api/assets/',{
          method:'POST',file:upload
        }
        )).id;
      }
      await C.request('/api/members/applications/',{
        method:'POST',data:{
          application_kind:form.elements.application_kind.value,statement:form.elements.statement.value,target_profile:form.elements.target_profile.value.trim()||null,proof_asset:pendingProof
        }
      }
      );
      form.reset();
      pendingProof=null;
      await applications();
      C.status('身份申请已提交。教师身份不会自动获得管理权限。');
    }
    );
    for(const [scope,label]of [['public','停止公开成员主页'],['contact','停止公开联系邮箱'],['education','停止公开教育经历'],['alumni','停止公开毕业去向']])$('#privacy-buttons').append(C.button(label,async()=>{
      const restricted=await C.request('/api/members/me/privacy/restrict/',{
        method:'POST',data:{
          scopes:[scope]
        }
      }
      );
      if(draft){draft.lock_version=restricted.lock_version;draft.consent_current=false;}
      overview=await C.request('/api/members/me/overview/');render();
      C.status('隐私范围已立即收紧，未保存输入已保留；恢复公开需重新授权审核。');
    }
    ));
    try{
      await load();
    }
    catch(error){
      C.showError(error);
    }
  }
  );
}
)();
