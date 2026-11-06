/* Public-photo carousel. No fabricated slides or independent copies of private images. */
(() => {
 'use strict';window.mountTeamCarousel=(host,slides)=>{
  if(!slides?.length)return;host.replaceChildren();host.className='home-slider';host.setAttribute('aria-label','团队风貌照片轮播');
  const stage=document.createElement('div'),tools=document.createElement('div');tools.className='slider-tools';let index=0,timer,paused=matchMedia('(prefers-reduced-motion:reduce)').matches;
  const make=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
  const prev=make('button','上一张'),next=make('button','下一张'),pause=make('button',paused?'播放':'暂停'),dots=make('div');dots.className='slider-dots';
  for(const [i,row]of slides.entries()){const dot=make('button');dot.setAttribute('aria-label','第'+(i+1)+'张：'+row.title);dot.onclick=()=>{index=i;render();restart();};dots.append(dot);}
  function render(){stage.replaceChildren();const row=slides[index],panel=make('div');panel.className='home-slide';const image=make('img');image.src=row.image.url;image.alt=row.title;image.decoding='async';const width=make('div');width.className='site-width';const caption=make('div');caption.className='slide-caption';caption.append(make('p','团队风貌 · 科研与生活'),make('h1',row.title));const a=make('a','了解更多 →');a.href=row.url;caption.append(a);width.append(caption);panel.append(image,width);stage.append(panel);for(const [i,dot]of [...dots.children].entries())dot.setAttribute('aria-current',String(i===index));}
  function stop(){clearInterval(timer);}function restart(){stop();if(!paused&&slides.length>1&&!document.hidden)timer=setInterval(()=>{index=(index+1)%slides.length;render();},6000);}
  prev.onclick=()=>{index=(index-1+slides.length)%slides.length;render();restart();};next.onclick=()=>{index=(index+1)%slides.length;render();restart();};pause.onclick=()=>{paused=!paused;pause.textContent=paused?'播放':'暂停';restart();};
  tools.append(prev,dots,next,pause);host.append(stage,tools);if(slides.length===1)tools.hidden=true;
  host.addEventListener('mouseenter',stop);host.addEventListener('mouseleave',restart);host.addEventListener('focusin',stop);host.addEventListener('focusout',e=>{if(!host.contains(e.relatedTarget))restart();});host.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'){e.preventDefault();prev.click();}if(e.key==='ArrowRight'){e.preventDefault();next.click();}});document.addEventListener('visibilitychange',restart);addEventListener('pagehide',stop);render();restart();
 };
})();
