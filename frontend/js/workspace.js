(() => {
  'use strict';
  const C=LabContent,$=s=>document.querySelector(s), management=document.body.dataset.management==='true';
  async function list(path='/api/content/items/') {
    const data=await C.request(path),box=$('#content-list');
    box.replaceChildren();
    if (!data.results.length) box.append(C.node('p','暂无内容。'));
    for (const item of data.results) {
      const row=C.node('article',undefined,{
        class:'work-row'
      }
      ),r=item.working_revision||item.published_revision;
      const link=C.node('a',r?.title||'未命名内容',{
        href:new URL(`content-editor.html?id=${item.id}`,C.root).href
      }
      );
      row.append(C.node('h3'));
      row.lastChild.append(link);
      row.append(C.node('p',`${item.kind} · ${r?.state||'无活动版本'}${item.archived?' · 已归档':''}${!item.visible?' · 已撤下':''}`,{
        class:'work-note'
      }
      ));
      if(management) for (const [action,label] of [[item.archived?'unarchive':'archive',item.archived?'恢复编辑':'归档'],['unpublish','撤下公开版本']]) {
        if(action==='unpublish'&&(!item.published_revision||!item.visible))continue;
        const reason=C.node('input',undefined,{
          placeholder:'操作理由',maxlength:'2000','aria-label':`${label}理由`
        }
        );
        const b=C.button(label,async()=>{
          if(!reason.value.trim())throw {
            status:400,data:{
              detail:'请填写操作理由。'
            }
          }
          ;
          await C.request(`/api/content/items/${item.id}/${action}/`,{
            method:'POST',data:{
              lock_version:item.lock_version,reason:reason.value
            }
          }
          );
          await list(path);
          C.status('操作已记录。');
        }
        );
        row.append(reason,b);
      }
      box.append(row);
    }
    const pages=$('#content-pages');
    pages.replaceChildren();
    for(const [url,label]of [[data.previous,'上一页'],[data.next,'下一页']])if(url)pages.append(C.button(label,()=>list(url)));
  }
  async function participations(path='/api/content/participations/') {
    if(!$('#participations'))return;
    const data=await C.request(path),box=$('#participations');
    box.replaceChildren();
    if(!data.results.length)box.append(C.node('p','暂无已发布成果。'));
    for(const item of data.results){
      const row=C.node('article',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('h3',item.title));
      const reason=C.node('textarea',undefined,{
        maxlength:'2000','aria-label':`对${item.title}的纠错意见`
      }
      );
      row.append(reason,C.button('提交纠错意见',async()=>{
        await C.request(`/api/content/items/${item.id}/corrections/`,{
          method:'POST',data:{
            reason:reason.value
          }
        }
        );
        reason.value='';
        C.status('纠错申请已提交。');
      }
      ));
      box.append(row);
    }
    for(const [url,label]of [[data.previous,'上一页成果'],[data.next,'下一页成果']])if(url)box.append(C.button(label,()=>participations(url)));
  }
  async function confirmations(path='/api/content/confirmations/'){
    if(!$('#confirmations'))return;
    const data=await C.request(path),box=$('#confirmations');
    box.replaceChildren();
    if(!data.results.length)box.append(C.node('p','暂无待确认署名。'));
    for(const item of data.results){
      const row=C.node('article',undefined,{
        class:'work-row'
      }
      );
      row.append(C.node('h3',item.title),C.node('p',`${item.name} · ${item.role} · 顺序 ${item.position}`));
      const reason=C.node('input',undefined,{
        placeholder:'核对说明或争议理由',maxlength:'2000','aria-label':'署名核对说明'
      }
      );
      row.append(reason);
      for(const [decision,label]of [['CONFIRMED','确认参与'],['DISPUTED','提出署名争议']])row.append(C.button(label,async()=>{
        await C.request(`/api/content/contributions/${item.id}/confirm/`,{
          method:'POST',data:{
            decision,reason:reason.value
          }
        }
        );
        await confirmations();
        C.status('署名意见已记录。');
      }
      ));
      box.append(row);
    }
    for(const [url,label]of [[data.previous,'上一页署名'],[data.next,'下一页署名']])if(url)box.append(C.button(label,()=>confirmations(url)));
  }
  document.addEventListener('DOMContentLoaded',async()=>{
    if(!await C.boot(management))return;
    C.bind($('#list-filter'),async form=>list('/api/content/items/'+(form.elements.scope.value?'?scope='+form.elements.scope.value:'')));
    try{
      const capabilities=C.capabilities;
      document.querySelectorAll('[data-create-content]').forEach(a=>{
        a.hidden=!capabilities.can_submit;
      }
      );
      await list(management?'/api/content/items/':'/api/content/items/?scope=mine');
      await participations();
      await confirmations();
    }
    catch(error){
      C.showError(error);
    }
  }
  );
}
)();
