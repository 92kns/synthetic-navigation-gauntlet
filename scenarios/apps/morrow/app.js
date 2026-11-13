import {data,image,avatar,icon,ready,failure,start,escape,routeLinks} from '/apps/runtime.js';
import {schemas} from './registry.js';
start();
document.querySelector('#shell').innerHTML=`<header class="topbar"><a class="brand" data-go href="/apps/morrow/feed"><em>m</em> morrow<span>●</span></a><label class="search">${icon('search')}<input id="people-search" placeholder="A person, a place, a little inspiration" aria-label="Search people"></label><nav><a class="current" data-go href="/apps/morrow/feed">${icon('home')}</a><a data-go href="/apps/morrow/profile?id=0">${icon('people')}</a><button data-toggle aria-pressed="false" aria-label="Notifications">${icon('bell')}</button></nav><a data-go href="/apps/morrow/profile?id=3"><img class="avatar" src="${avatar(3)}" alt="Your profile"></a></header><aside class="sidebar"><a data-go href="/apps/morrow/profile?id=3"><img class="avatar" src="${avatar(3)}" alt=""><span>Jules Moss<small>Your little corner</small></span></a><hr class="divider"><a class="active" data-go href="/apps/morrow/feed">${icon('home')} The everyday</a><a data-go href="/apps/morrow/profile?id=0">${icon('people')} Good company</a><a data-go href="/apps/morrow/feed?saved=1">${icon('heart')} Saved moments</a><p class="eyebrow">Your circles</p>${['Growing together','The makers table','Slow weekends'].map((n,i)=>`<a data-go href="/apps/morrow/feed?circle=${i}"><span class="circle-icon circle-${i}">${['✿','▧','↗'][i]}</span>${n}</a>`).join('')}<p class="sidebar-note">Life is made of<br><em>little things.</em></p></aside><main id="main" class="content"><div class="social-layout"><section id="social-content"></section><aside class="social-rail"><div class="day-note"><span class="eyebrow">A MOMENT FOR YOU</span><h2>Make room<br>for a little<br>wonder.</h2><span class="day-flower">✳</span><p>Wednesday, 4 November</p></div><div class="section-title"><h2>Good company</h2><span class="muted">People to know</span></div><div id="suggestions"></div><div class="gathering card"><span class="eyebrow">SOMETHING TO LOOK FORWARD TO</span><h3>The long table</h3><p>Sunday · 11:00<br>At the community garden</p><button class="button" data-toggle aria-pressed="false">I'll be there ${icon('arrow')}</button></div><p class="social-footer">Small moments. Real connections.<br>Morrow studio · 2026</p></aside></div></main>`;
let posts,profiles,version=0;
const saved=new Set();
async function navigate(){
 const ticket=++version;gauntletApp.ready=false;
 const params=new URLSearchParams(location.search),id=params.get('id')||'0';
 const page=location.pathname.split('/').pop();
 const {feed,post,profile}=await import('./views.js');
 let selected;
 if(page==='post')selected=id==='local'?posts.find(p=>p.id===id):await data('item-'+id);
 if(ticket!==version)return;
 const list=params.get('saved')?posts.filter(p=>saved.has(p.id)):params.has('circle')?posts.filter(p=>Number(p.id)%3===Number(params.get('circle'))):posts;
 document.querySelector('#social-content').innerHTML=page==='post'?post(selected):page==='profile'?profile(profiles[Number(id)%12],posts):feed(list,schemas);
 document.querySelectorAll('[data-save-post]').forEach(button=>{const id=button.dataset.savePost;button.setAttribute('aria-pressed',String(saved.has(id)));button.onclick=()=>{saved.has(id)?saved.delete(id):saved.add(id);button.setAttribute('aria-pressed',String(saved.has(id)));};});
 document.querySelectorAll('[data-like]').forEach(button=>button.onclick=()=>{const node=button.querySelector('span');const active=button.getAttribute('aria-pressed')==='true';node.textContent=Number(node.textContent)+(active?-1:1);button.setAttribute('aria-pressed',String(!active));});
 const compose=document.querySelector('#compose-form');
 if(compose)compose.onsubmit=e=>{e.preventDefault();const text=document.querySelector('#compose-text');posts.unshift({...posts[3],id:'local',author:'Jules Moss',text:escape(text.value),likes:0,comments:[]});navigate().catch(failure);};
 const reply=document.querySelector('#social-reply');
 if(reply)reply.onsubmit=e=>{e.preventDefault();const node=document.createElement('p');node.className='social-comment';node.textContent='You: '+document.querySelector('#reply-text').value;document.querySelector('#social-comments').prepend(node);reply.reset();};
 await ready(page==='feed'?'feed':page+'-'+id);
}
try{
 [posts,profiles]=await Promise.all([data('posts'),data('profiles')]);
 const suggestions=items=>items.slice(0,6).map(p=>`<div class="person"><a data-go href="/apps/morrow/profile?id=${p.id}"><img class="avatar" src="${avatar(Number(p.id))}" alt=""><span><b>${p.name}</b><small>${p.followers} kindred spirits</small></span></a><button data-toggle aria-pressed="false" aria-label="Follow ${p.name}">+</button></div>`).join('');
 document.querySelector('#suggestions').innerHTML=suggestions(profiles);
 document.querySelector('#people-search').oninput=e=>{document.querySelector('#suggestions').innerHTML=suggestions(profiles.filter(p=>p.name.toLowerCase().includes(e.target.value.toLowerCase())));};
 routeLinks(()=>navigate().catch(failure));await navigate();
}catch(error){failure(error);}
