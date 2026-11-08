/* Full-height carousel with dot navigation and crossfading slides. */
(() => {
 'use strict';
 const placeholders=[{title:'探索智能边界，让科研与创新同行',url:'/about.html',image:{url:'/lab-logo.png'},placeholder:true},{title:'汇聚团队智慧，连接研究与实践',url:'/data/projects/index.html',image:{url:'/lab-logo.png'},placeholder:true}];
 window.mountTeamCarousel=(host,rows)=>{
  if(!host)return;if(!rows?.length&&host.querySelector('.home-slide--logo'))return;
  host._destroyCarousel?.();const slides=rows?.length?rows:placeholders;
  host.replaceChildren();host.className='home-slider';host.setAttribute('aria-label','实验室图片轮播');
  const make=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
  const stage=make('div'),tools=make('div'),dots=make('div');stage.className='slider-stage';tools.className='slider-tools';dots.className='slider-dots';let index=0,timer,focused=false;
  const motion=matchMedia('(prefers-reduced-motion:reduce)');
  const panels=slides.map(row=>{
   const panel=make('div');panel.className='home-slide'+(row.placeholder?' home-slide--logo':'');
   const image=make('img');image.src=row.image.url;image.alt=row.placeholder?'智能系统实验室标识':row.title;image.decoding='async';
   const width=make('div');width.className='site-width';const caption=make('div');caption.className='slide-caption';if(row.subtitle||row.placeholder)caption.append(make('p',row.subtitle||'INTELLIGENT SYSTEMS LABORATORY'));if(row.title)caption.append(make('h1',row.placeholder?row.title.replace('，','\n'):row.title));const a=make('a','了解实验室 →');a.href='#lab-overview';a.addEventListener('click',event=>{if(event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;const overview=document.getElementById('lab-overview');if(!overview)return;event.preventDefault();history.replaceState(history.state,'',location.pathname+location.search+'#lab-overview');overview.scrollIntoView({behavior:motion.matches?'instant':'smooth',block:'start'});overview.focus({preventScroll:true});});caption.append(a);width.append(caption);panel.append(image,width);stage.append(panel);return panel;
  });
  function render(){for(const [i,panel] of panels.entries()){const active=i===index;panel.classList.toggle('is-active',active);panel.inert=!active;panel.setAttribute('aria-hidden',String(!active));dots.children[i].setAttribute('aria-current',String(active));}}
  function stop(){clearInterval(timer);}
  function restart(){stop();if(!motion.matches&&!focused&&slides.length>1&&!document.hidden)timer=setInterval(()=>{index=(index+1)%slides.length;render();},5000);}
  for(const [i,row] of slides.entries()){const dot=make('button');dot.type='button';dot.setAttribute('aria-label','第'+(i+1)+'张：'+row.title);dot.onclick=()=>{index=i;render();restart();};dots.append(dot);}
  tools.append(dots);host.append(stage,tools);tools.hidden=slides.length<2;
  const focusin=event=>{focused=!!event.target.closest('.slide-caption');restart();},focusout=event=>{if(!host.contains(event.relatedTarget)){focused=false;restart();}};
  host.addEventListener('focusin',focusin);host.addEventListener('focusout',focusout);document.addEventListener('visibilitychange',restart);window.addEventListener('pagehide',stop);motion.addEventListener('change',restart);
  host._destroyCarousel=()=>{stop();host.removeEventListener('focusin',focusin);host.removeEventListener('focusout',focusout);document.removeEventListener('visibilitychange',restart);window.removeEventListener('pagehide',stop);motion.removeEventListener('change',restart);};render();restart();
 };
 document.addEventListener('DOMContentLoaded',()=>{const host=document.getElementById('home-visual');if(host)window.mountTeamCarousel(host,[]);});
})();
