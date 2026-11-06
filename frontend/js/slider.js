/* Full-height first-screen carousel; logo slides are explicit local placeholders. */
(() => {
 'use strict';
 const placeholders=[{title:'探索智能边界，让科研与创新同行',url:'/about.html',image:{url:'/lab-logo.png'},placeholder:true},{title:'汇聚团队智慧，连接研究与实践',url:'/data/projects/index.html',image:{url:'/lab-logo.png'},placeholder:true}];
 window.mountTeamCarousel=(host,rows)=>{
  if(!host)return;if(!rows?.length&&host.querySelector('.home-slide--logo'))return;host._destroyCarousel?.();const slides=rows?.length?rows:placeholders;
  host.replaceChildren();host.className='home-slider';host.setAttribute('aria-label','实验室图片轮播');
  const stage=document.createElement('div'),tools=document.createElement('div');tools.className='slider-tools';let index=0,timer,paused=matchMedia('(prefers-reduced-motion:reduce)').matches;
  const make=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
  const prev=make('button','上一张'),next=make('button','下一张'),pause=make('button',paused?'播放':'暂停'),dots=make('div');dots.className='slider-dots';
  for(const [i,row] of slides.entries()){const dot=make('button');dot.setAttribute('aria-label','第'+(i+1)+'张：'+row.title);dot.onclick=()=>{index=i;render();restart();};dots.append(dot);}
  function render(){stage.replaceChildren();const row=slides[index],panel=make('div');panel.className='home-slide'+(row.placeholder?' home-slide--logo':'');const image=make('img');image.src=row.image.url;image.alt=row.placeholder?'智能系统实验室标识':row.title;image.decoding='async';const width=make('div');width.className='site-width';const caption=make('div');caption.className='slide-caption';caption.append(make('p','INTELLIGENT SYSTEMS LABORATORY'),make('h1',row.placeholder?row.title.replace('，','\n'):row.title));const a=make('a','了解实验室 →');a.href=row.url;caption.append(a);width.append(caption);panel.append(image,width);stage.append(panel);for(const [i,dot] of [...dots.children].entries())dot.setAttribute('aria-current',String(i===index));}
  function stop(){clearInterval(timer);}function restart(){stop();if(!paused&&slides.length>1&&!document.hidden)timer=setInterval(()=>{index=(index+1)%slides.length;render();},6000);}
  prev.onclick=()=>{index=(index-1+slides.length)%slides.length;render();restart();};next.onclick=()=>{index=(index+1)%slides.length;render();restart();};pause.onclick=()=>{paused=!paused;pause.textContent=paused?'播放':'暂停';restart();};
  tools.append(prev,dots,next,pause);host.append(stage,tools);tools.hidden=slides.length<2;
  const hover=()=>stop(),leave=()=>restart(),focusout=e=>{if(!host.contains(e.relatedTarget))restart();};host.addEventListener('mouseenter',hover);host.addEventListener('mouseleave',leave);host.addEventListener('focusin',hover);host.addEventListener('focusout',focusout);document.addEventListener('visibilitychange',restart);window.addEventListener('pagehide',stop);
  host._destroyCarousel=()=>{stop();host.removeEventListener('mouseenter',hover);host.removeEventListener('mouseleave',leave);host.removeEventListener('focusin',hover);host.removeEventListener('focusout',focusout);document.removeEventListener('visibilitychange',restart);window.removeEventListener('pagehide',stop);};render();restart();
 };
 document.addEventListener('DOMContentLoaded',()=>{const host=document.getElementById('home-visual');if(host)window.mountTeamCarousel(host,[]);});
})();
