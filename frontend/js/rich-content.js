/* Versioned document renderer: only local asset URLs and explicit DOM nodes. */
(() => {
 'use strict';
 const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
 const assetURL=url=>typeof url==='string'&&/^\/api\/(?:(?:public|site)\/assets\/[0-9a-f-]+\/|assets\/[0-9a-f-]+\/download\/)$/.test(url);
 function safeLink(href){try{if(typeof href!=='string'||/[\s\x00-\x1f]/.test(href))return false;const u=new URL(href);return ['http:','https:','mailto:'].includes(u.protocol)&&!u.username&&!u.password;}catch{return false;}}
 function textDocument(text){return {version:1,type:'doc',content:String(text||'').split(/\r?\n/).map(line=>({type:'paragraph',...(line?{content:[{type:'text',text:line}]}:{})}))};}
 function imageIDs(doc){const ids=new Set();function walk(n){if(n?.type==='image'&&uuid.test(n.attrs?.asset_id))ids.add(n.attrs.asset_id);for(const child of n?.content||[])walk(child);}walk(doc);return ids;}
 function render(doc,assets,parent){
  const box=document.createElement('div');box.className='rich-document';const available=new Map((assets||[]).map(a=>[a.id,a]));let count=0;
  function node(n,depth=0){if(!n||depth>12||++count>10000)return document.createTextNode('');const a=n.attrs||{};let el;
   if(n.type==='text'){el=document.createTextNode(n.text||'');for(const mark of n.marks||[]){const tag={bold:'strong',italic:'em',underline:'u',strike:'s',link:'a'}[mark.type];if(!tag)continue;if(tag==='a'&&!safeLink(mark.attrs?.href))continue;const wrap=document.createElement(tag);if(tag==='a'){wrap.href=mark.attrs.href;wrap.rel='noopener noreferrer nofollow';wrap.target='_blank';}wrap.append(el);el=wrap;}return el;}
   if(n.type==='image'){const asset=available.get(a.asset_id);el=document.createElement('figure');el.className='rich-figure';if(!assetURL(asset?.url||asset?.download_url)||!asset?.mime_type?.startsWith('image/'))return el;el.style.width=([25,50,75,100].includes(a.width)?a.width:100)+'%';el.dataset.align=['left','center','right'].includes(a.align)?a.align:'center';const img=document.createElement('img');img.src=asset.url||asset.download_url;img.alt=a.caption||'正文图片';img.loading='lazy';img.onerror=()=>{img.replaceWith(document.createTextNode('图片暂不可用'));};el.append(img);if(a.caption){const caption=document.createElement('figcaption');caption.textContent=a.caption;el.append(caption);}return el;}
   const tag={doc:'div',paragraph:'p',heading:a.level===3?'h3':'h2',bulletList:'ul',orderedList:'ol',listItem:'li',blockquote:'blockquote',table:'table',tableRow:'tr',tableCell:'td',tableHeader:'th',hardBreak:'br',horizontalRule:'hr'}[n.type];if(!tag)return document.createTextNode('');el=document.createElement(tag);if(['p','h2','h3'].includes(tag)&&['left','center','right','justify'].includes(a.textAlign))el.style.textAlign=a.textAlign;if(['td','th'].includes(tag)&&['left','center','right','justify'].includes(a.align))el.style.textAlign=a.align;if(tag==='ol'&&Number.isInteger(a.start))el.start=a.start;if(tag==='ol'&&['1','a','A','i','I'].includes(a.type))el.type=a.type;for(const c of n.content||[])el.append(node(c,depth+1));if(tag==='table'){const scroll=document.createElement('div');scroll.className='rich-table-scroll';scroll.append(el);return scroll;}return el;
  }
  box.append(node(doc));parent.append(box);return box;
 }
 window.LabRich={render,textDocument,imageIDs,safeLink,assetURL,mount:(parent,options)=>window.LabEditor.mount(parent,options)};
})();
