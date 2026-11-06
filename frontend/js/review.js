(() => {
  'use strict';
  const C=LabContent,$=s=>document.querySelector(s);
  function pagination(box,data,load){
    box.replaceChildren();
    for(const [path,label]of [[data.previous,'上一页'],[data.next,'下一页']])if(path)box.append(C.button(label,()=>load(path)));
  }
  async function content(path='/api/review/tasks/'){
    const data=await C.request(path),box=$('#review-tasks');
    box.replaceChildren();
    if(!data.results.length)box.append(C.node('p','暂无待审内容。'));
    for(const task of data.results){
      const row=C.node('article',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('a',task.title,{
        href:new URL(`content-editor.html?id=${task.item_id}`,C.root).href
      }
      ),C.node('p',task.can_review?'可审核':'当前版本暂不可审核',{
        class:'work-note'
      }
      ));
      box.append(row);
    }
    pagination($('#review-pages'),data,content);
  }
  async function profiles(path='/api/review/member-revisions/'){
    const data=await C.request(path),box=$('#profile-review-tasks');
    box.replaceChildren();
    if(!data.results.length)box.append(C.node('p','暂无待审成员公开资料。'));
    for(const profile of data.results){
      const row=C.node('article',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('h3',profile.display_name),C.node('p',`${profile.member_kind} · ${profile.slug}`),C.node('p',profile.bio),C.node('p',profile.public_contact_enabled?`拟公开邮箱：${profile.public_contact_email}`:'未选择公开邮箱'),C.node('p','研究方向：'+profile.research_areas.join('、')));
      for(const e of profile.education)row.append(C.node('p',`${e.school} · ${e.major} · ${e.degree}${e.is_public?' · 可公开':' · 不公开'}`));
      if(profile.alumni)row.append(C.node('p',`毕业去向：${profile.alumni.graduation_year} · ${profile.alumni.organization}${profile.alumni.is_public?' · 可公开':' · 不公开'}`));
      const permissions=profile.public_consent||{
      }
      ;
      row.append(C.node('p',`授权公开：${permissions.public_visible?'主页 ':''}${permissions.contact_visible?'邮箱 ':''}${permissions.education_visible?'教育经历 ':''}${permissions.alumni_visible?'毕业去向':''}${!Object.values(permissions).some(Boolean)?'无（仅内部版本）':''}`));
      if(profile.avatar_download_url)row.append(C.node('a','查看待审头像',{
        href:profile.avatar_download_url
      }
      ));
      const reason=C.node('textarea',undefined,{
        maxlength:'2000','aria-label':`${profile.display_name}的资料审核意见`
      }
      );
      row.append(reason);
      for(const [decision,label]of [['APPROVE','通过公开资料'],['REJECT','驳回公开资料']]){
        const b=C.button(label,async()=>{
          await C.request(`/api/review/member-revisions/${profile.id}/decision/`,{
            method:'POST',data:{
              decision,reason:reason.value,lock_version:profile.lock_version
            }
          }
          );
          await profiles();
          C.status('公开资料审核已记录。');
        }
        );
        C.disabled(b,!profile.can_review);
        row.append(b);
      }
      if(!profile.can_review)row.append(C.node('p',profile.review_block_reason==='self_authored'?'当前版本暂不可审核。':'授权或基线已变更，请申请者撤回并重新提交。'));
      box.append(row);
    }
    pagination($('#profile-review-pages'),data,profiles);
  }
  async function corrections(path='/api/review/corrections/'){
    const data=await C.request(path),box=$('#correction-tasks');
    box.replaceChildren();
    if(!data.results.length)box.append(C.node('p','暂无待处理纠错申请。'));
    for(const item of data.results){
      const row=C.node('article',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('p',item.reason),C.node('a','查看相关内容',{
        href:new URL(`content-editor.html?id=${item.item_id}`,C.root).href
      }
      ));
      const reply=C.node('textarea',undefined,{
        maxlength:'2000','aria-label':'纠错处理意见'
      }
      );
      row.append(reply,C.button('记录处理结果',async()=>{
        await C.request(`/api/review/corrections/${item.id}/resolve/`,{
          method:'POST',data:{
            reason:reply.value
          }
        }
        );
        await corrections();
        C.status('纠错处理已记录；如需修改成果，请另建版本审核。');
      }
      ));
      box.append(row);
    }
    for(const [url,label]of [[data.previous,'上一页纠错'],[data.next,'下一页纠错']])if(url)box.append(C.button(label,()=>corrections(url)));
  }
  document.addEventListener('DOMContentLoaded',async()=>{
    if(!await C.boot(true))return;
    try{
      await content();
      await profiles();
      await corrections();
    }
    catch(error){
      C.showError(error);
    }
  }
  );
}
)();
