import {h,render,data,image,avatar,icon,routeLinks,ready,failure,start} from '/apps/runtime.js';
import {schemas} from './registry.js';
start();
const shell=document.querySelector('#shell');
shell.innerHTML=`<header class="topbar"><a class="brand" href="/apps/kilncast/home"><em>◧</em> kilncast<span class="brand-dot">●</span></a><nav><a href="/apps/kilncast/home">Discover</a><a href="/apps/kilncast/channel?id=0" data-go>Following</a></nav><label class="search">${icon('search')}<input id="channel-search" placeholder="Find your next rabbit hole" aria-label="Search channels"></label><button class="button" data-toggle aria-pressed="false">${icon('bell')}</button><img class="avatar" src="${avatar(3)}" alt="Your profile"></header><aside class="sidebar"><p class="eyebrow">Your corner of live</p><a class="active" href="/apps/kilncast/channel?id=0" data-go>${icon('play')} Live now</a><p class="eyebrow">Followed channels</p><div id="channels"></div><div class="sidebar-note"><b>Make something.<br>Meet someone.</b><p>A place for curious hands<br>and open studios.</p></div></aside><main id="main" class="content"><div class="stream-grid"><section><div id="player-shell" class="player"><img id="poster" width="1280" height="720" alt="A warmly lit maker studio"><span class="live-badge">● LIVE</span><div class="player-type"><span>OPEN STUDIO / 006</span><strong id="player-caption">A little room<br>to make things.</strong><small>LIVE STUDIO PREVIEW · NO VIDEO STREAM</small></div><button id="preview" class="preview" aria-label="Toggle studio preview" aria-pressed="false">${icon('play')}</button><div class="player-bar"><span>Studio preview</span><button id="fullscreen" aria-label="Fullscreen">⛶</button></div></div><div id="channel-main"></div></section><aside class="chat-panel"><div class="chat-title">${icon('chat')} Studio chat <span>●</span></div><div class="chat-note">Pull up a chair. Be kind, stay curious.</div><div id="chat" class="chat-messages" role="log" aria-label="Studio chat"></div><form id="chat-form"><label class="sr-only" for="chat-text">Your message</label><input id="chat-text" maxlength="220" placeholder="Say something kind…" required><div class="row between"><small class="muted">Community guidelines</small><button class="button primary">Chat</button></div></form></aside></div><section><div class="section-title"><h2>More open doors</h2><span class="muted">Find a new favourite</span></div><div id="recommendations" class="stream-cards"></div></section></main>`;
let channels,chat,version=0;
async function navigate(){
 const ticket=++version;gauntletApp.ready=false;
 const id=new URLSearchParams(location.search).get('id')||'0';
 const [channel,module]=await Promise.all([data('item-'+id),import('./channel.js')]);
 if(ticket!==version)return;
 module.channel(channel,schemas);
 document.querySelector('#poster').src=image('studio',channel.image);
 document.querySelector('#player-shell').dataset.channel=id;
 document.querySelector('#player-caption').textContent=channel.title;
 render(document.querySelector('#chat'),h('div',{},chat.slice(Number(id)%9,Number(id)%9+48).map(c=>h('p',{class:'chat-line tone-'+c.color},h('b',{},c.author),h('span',{},c.text)))));
 await ready('channel-'+id);
 requestAnimationFrame(()=>requestAnimationFrame(()=>{
  if(ticket!==version)return;
  const entry=document.createElement('p');entry.className='chat-line';entry.textContent='Studio host: Welcome in. We are glad you are here.';document.querySelector('#chat').append(entry);gauntletApp.chatUpdated=true;
 }));
}
try {
 [channels,chat]=await Promise.all([data('channels'),data('chat')]);
 const list=items=>items.slice(0,12).map((c,i)=>`<a id="channel-${i}" data-go href="/apps/kilncast/channel?id=${c.id}"><img class="avatar" src="${avatar(c.avatar)}" alt=""><span>${c.name}<small>${c.category}</small></span><span class="online-dot">●</span></a>`).join('');
 document.querySelector('#channels').innerHTML=list(channels);
 document.querySelector('#channel-search').addEventListener('input',e=>{document.querySelector('#channels').innerHTML=list(channels.filter(c=>(c.name+' '+c.category).toLowerCase().includes(e.target.value.toLowerCase())));});
 document.querySelector('#recommendations').innerHTML=channels.slice(1).map((c,i)=>`<article class="stream-card"><a data-go href="/apps/kilncast/channel?id=${c.id}"><div class="stream-thumb"><img src="${image('studio',c.image)}" srcset="${image('studio',c.image,2)} 2x" width="480" height="270" loading="${i<4?'eager':'lazy'}" alt="Maker studio"><span class="live-badge">LIVE</span><span class="viewer-count">${c.viewers} watching</span></div><h3>${c.title}</h3></a><p>${c.name}</p><span class="chip">${c.category}</span></article>`).join('');
 routeLinks(()=>navigate().catch(failure));
 document.querySelector('#preview').onclick=e=>{const button=e.currentTarget;button.setAttribute('aria-pressed',String(button.getAttribute('aria-pressed')!=='true'));document.querySelector('#player-shell').classList.toggle('preview-active');};
 document.querySelector('#fullscreen').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.querySelector('#player-shell').requestFullscreen();
 document.querySelector('#chat-form').onsubmit=e=>{e.preventDefault();const input=document.querySelector('#chat-text');const line=document.createElement('p');line.className='chat-line';line.textContent='You: '+input.value;document.querySelector('#chat').append(line);input.value='';line.scrollIntoView({block:'nearest'});};
 await navigate();
}catch(error){failure(error);}
