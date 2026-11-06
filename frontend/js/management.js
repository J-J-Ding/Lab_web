(() => {
  'use strict';
  const C=LabContent,$=s=>document.querySelector(s);
  let selected=null;
  function pager(box,data,load){
    if(!box)return;
    box.replaceChildren();
    for(const [url,label]of [[data.previous,'上一页'],[data.next,'下一页']])if(url)box.append(C.button(label,()=>load(url)));
  }
  async function users(path='/api/admin/users/'){
    const data=await C.request(path),box=$('#users-list');
    box.replaceChildren();
    for(const user of data.results){
      const row=C.node('article',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('p',`${user.id} · ${user.username} · ${user.is_superuser?'ROOT':user.role} · ${user.is_active?'启用':'禁用'}`),C.button('编辑 '+user.username,()=>{
        selected=user;
        $('#user-form-title').textContent='编辑用户 '+user.username;
        for(const key of ['username','first_name','last_name','email','role'])$('#user-form').elements[key].value=user[key]||'';
        $('#user-name').disabled=true;
        $('#user-role').disabled=user.id===C.user.id&&!C.user.is_superuser;
        $('#user-active').checked=user.is_active;
        $('#user-password').required=false;
        $('#user-password').disabled=true;
        $('#user-password').value='';
        $('#reset-user').value=user.id;
        $('#user-form-title').scrollIntoView({
          block:'start'
        }
        );
      }
      ));
      box.append(row);
    }
    pager($('#users-pages'),data,users);
  }
  function comparison(box,title,data){
    if(!data)return;
    box.append(C.node('h3',title));
    const dl=C.node('dl');
    for(const [key,label]of [['display_name','姓名'],['bio','简介'],['slug','主页标识'],['member_kind','档案类型'],['public_contact_email','拟公开邮箱']])dl.append(C.node('dt',label),C.node('dd',data[key]||'未填写'));
    box.append(dl);
  }
  async function applications(path='/api/review/member-applications/'){
    const data=await C.request(path),box=$('#member-application-tasks');
    box.replaceChildren();
    if(!data.results.length)box.append(C.node('p','暂无待审身份申请。'));
    for(const app of data.results){
      const row=C.node('article',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('h3',`${app.applicant_username} · ${app.application_kind}`),C.node('p',app.statement));
      if(app.proof_asset)row.append(C.node('a','下载私有证明',{
        href:`/api/assets/${app.proof_asset}/download/`
      }
      ));
      const compare=C.node('div',undefined,{
        class:'work-grid'
      }
      );
      const left=C.node('div'),right=C.node('div');
      comparison(left,'申请者原草稿',app.claim_comparison.applicant_draft);
      comparison(right,'目标档案',app.claim_comparison.target_draft);
      compare.append(left,right);
      row.append(compare);
      const choice=C.node('input',undefined,{
        type:'checkbox'
      }
      ),label=C.node('label','将申请者原公开资料字段复制到目标草稿（不覆盖已发布版本）');
      label.prepend(choice);
      row.append(label);
      const reason=C.node('textarea',undefined,{
        maxlength:'2000','aria-label':`${app.applicant_username}的审核意见`
      }
      );
      row.append(reason);
      for(const [decision,title]of [['APPROVE','通过身份申请'],['REJECT','驳回身份申请']]){
        const b=C.button(title,async()=>{
          await C.request(`/api/review/member-applications/${app.id}/decision/`,{
            method:'POST',data:{
              decision,reason:reason.value,lock_version:app.lock_version,use_applicant_fields:choice.checked
            }
          }
          );
          await applications(path);
          await catalog();
          C.status('身份申请已处理。教师身份未自动获得管理权限。');
        }
        );
        C.disabled(b,!app.can_review);
        row.append(b);
      }
      box.append(row);
    }
    pager($('#member-task-pages'),data,applications);
  }
  async function catalog(path='/api/admin/members/'){
    const data=await C.request(path),box=$('#member-catalog');
    box.replaceChildren();
    for(const p of data.results){
      const row=C.node('article',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('p',`${p.draft?.display_name||'未命名成员'} · ${p.membership_status} · ${p.user_id?'账号 '+p.user_id:'未绑定'}`));
      if(!p.user_id)row.append(C.button('选择待绑定档案',()=>{
        $('#bind-profile').value=p.id;
      }
      ));
      box.append(row);
    }
    pager($('#catalog-pages'),data,catalog);
  }
  document.addEventListener('DOMContentLoaded',async()=>{
    const user=await C.boot(true);
    if(!user)return;
    try{
      if($('#users-list')){
        if(user.is_superuser)$('#user-role').append(C.node('option','ADMIN',{
          value:'ADMIN'
        }
        ));
        C.bind($('#user-form'),async form=>{
          const data={
          }
          ;
          for(const key of ['first_name','last_name','email','role'])if(!(key==='role'&&selected?.id===user.id&&!user.is_superuser))data[key]=form.elements[key].value;
          data.is_active=$('#user-active').checked;
          if(!selected){
            data.username=form.elements.username.value;
            data.password=form.elements.password.value;
          }
          await C.request(selected?`/api/admin/users/${selected.id}/`:'/api/admin/users/',{
            method:selected?'PATCH':'POST',data
          }
          );
          $('#user-password').value='';
          await users();
          C.status('用户已保存，权限由后端验证。');
        }
        );
        $('#user-create-mode').onclick=()=>{
          selected=null;
          $('#user-form').reset();
          $('#user-name').disabled=false;
          $('#user-role').disabled=false;
          $('#user-password').disabled=false;
          $('#user-password').required=true;
          $('#user-form-title').textContent='创建用户';
        }
        ;
        C.bind($('#reset-password-form'),async form=>{
          await C.request(`/api/admin/users/${Number(form.elements.user_id.value)}/reset-password/`,{
            method:'POST',data:{
              new_password:form.elements.new_password.value
            }
          }
          );
          form.elements.new_password.value='';
          C.status('密码已重置，目标旧会话全部失效。');
        }
        );
        await users();
      }
      if($('#member-application-tasks')){
        C.bind($('#catalog-form'),async form=>{
          await C.request('/api/admin/members/',{
            method:'POST',data:{
              display_name:form.elements.display_name.value,member_kind:form.elements.member_kind.value
            }
          }
          );
          form.reset();
          await catalog();
          C.status('未绑定档案已建立，尚未公开。');
        }
        );
        C.bind($('#bind-form'),async form=>{
          await C.request(`/api/admin/members/${form.elements.profile_id.value.trim()}/bind/`,{
            method:'POST',data:{
              user_id:Number(form.elements.user_id.value)
            }
          }
          );
          await catalog();
          C.status('账号已绑定；角色和发布状态未自动改变。');
        }
        );
        await applications();
        await catalog();
      }
    }
    catch(error){
      C.showError(error);
    }
  }
  );
}
)();
