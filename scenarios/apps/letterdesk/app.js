import {data,avatar,icon,ready,failure,start,escape} from '/apps/runtime.js';
import {schemas} from './registry.js';
start();
document.querySelector('#shell').innerHTML=`<header class="topbar"><a class="brand" href="/apps/letterdesk/mail"><em>▱</em> letterdesk<span>MAIL, AT YOUR PACE</span></a><label class="search">${icon('search')}<input id="mail-query" placeholder="Find a letter, a person, a little detail" aria-label="Search mail"></label><span class="topbar-note">A little space to focus.</span><button class="button" id="mail-settings" aria-label="Toggle reading density" aria-pressed="false">☷</button><img class="avatar" src="${avatar(3)}" alt="Jules Moss"></header><aside class="sidebar"><button class="button primary" id="compose">${icon('compose')} A new letter</button><div id="folders"></div><p class="eyebrow">A LITTLE ORGANISATION</p><div class="mail-label"><span class="label-dot sage"></span> The garden project</div><div class="mail-label"><span class="label-dot terracotta"></span> Good company</div><div class="mail-label"><span class="label-dot lavender"></span> Something to read</div><div class="mail-storage"><div class="storage-line"></div><p>1.2 GB of 15 GB used</p><span>Room for a few more good things.</span></div><div class="account"><img class="avatar" src="${avatar(3)}" alt=""><span><b>Jules Moss</b><small>jules@letters.gauntlet.test</small></span></div></aside><main id="main" class="mail-main"><section class="mail-list-pane"><header class="mail-list-heading"><div><span class="eyebrow">YOUR LITTLE LETTERBOX</span><h1 id="folder-title">Inbox</h1></div><span id="folder-count"></span></header><div class="mail-tabs"><button id="all-mail" class="active">All letters</button><button id="unread-mail">Unread</button><span id="list-count"></span></div><div id="message-list" class="message-list"></div><div class="mail-list-footer">All caught up with the little details. ${icon('check')}</div></section><section id="reading-pane" class="reading-pane" aria-label="Reading pane"></section></main><dialog id="compose-dialog"><form id="compose-form"><div class="row between"><h2>A new letter</h2><button type="button" id="close-compose" aria-label="Close compose">×</button></div><label>To<input id="compose-to" type="email" required placeholder="Someone worth writing to"></label><label>Subject<input id="compose-subject" required placeholder="A little hello"></label><label class="sr-only" for="compose-body">Message</label><textarea id="compose-body" rows="9" placeholder="Take your time. Good words are worth it." required></textarea><div class="row between"><small>Saved only in this local session.</small><button class="button primary">Send locally ${icon('arrow')}</button></div></form></dialog><div id="mail-status" role="status" hidden></div>`;
let folders,messages,folder='inbox',selected=null,unread=false,query='',version=0;
const stars=new Set();
async function display(){
 const ticket=++version;gauntletApp.ready=false;
 const {list,letter,welcome}=await import('./letters.js');
 if(ticket!==version)return;
 let items=messages.filter(m=>folder==='starred'?stars.has(m.id):m.folder===folder);
 items=items.filter(m=>(!unread||m.unread)&&(m.subject+' '+m.author+' '+m.preview).toLowerCase().includes(query.toLowerCase()));
 document.querySelector('#folder-title').textContent=folders.find(f=>f.id===folder)?.name||folder;
 document.querySelector('#folder-count').textContent=items.filter(m=>m.unread).length+' unread';
 document.querySelector('#list-count').textContent=items.length+' letters';
 document.querySelector('#message-list').innerHTML=list(items,selected,stars,schemas);
 document.querySelector('#reading-pane').innerHTML=selected?letter(messages.find(m=>m.id===selected)):welcome();
 document.querySelectorAll('[data-folder]').forEach(button=>button.classList.toggle('active',button.dataset.folder===folder));
 document.querySelectorAll('[data-message]').forEach(button=>button.onclick=()=>{selected=button.dataset.message;messages.find(m=>m.id===selected).unread=false;display().catch(failure);});
 document.querySelectorAll('[data-star]').forEach(button=>button.onclick=e=>{e.stopPropagation();const id=button.dataset.star;stars.has(id)?stars.delete(id):stars.add(id);display().catch(failure);});
 const back=document.querySelector('#message-close');if(back)back.onclick=()=>{selected=null;display().catch(failure);};
 const archive=document.querySelector('#archive-message');if(archive)archive.onclick=()=>{messages.find(m=>m.id===selected).folder='archive';selected=null;display().catch(failure);};
 const reply=document.querySelector('#mail-reply');if(reply)reply.onsubmit=e=>{e.preventDefault();const status=document.querySelector('#reply-status');status.hidden=false;status.textContent='Your reply was saved locally. Thanks for making time.';reply.reset();};
 const attachment=document.querySelector('#attachment');if(attachment)attachment.onclick=()=>{document.querySelector('#attachment-preview').hidden=!document.querySelector('#attachment-preview').hidden;};
 await ready(selected?'message-'+selected:'folder-'+folder);
}
try{
 [folders,messages]=await Promise.all([data('folders'),data('messages')]);messages.filter(m=>m.starred).forEach(m=>stars.add(m.id));
 document.querySelector('#folders').innerHTML=folders.map((f,i)=>`<button id="folder-${f.id}" data-folder="${f.id}">${icon(['mail','star','arrow','folder'][i])}<span>${f.name}</span><small>${f.count}</small></button>`).join('');
 document.querySelectorAll('[data-folder]').forEach(button=>button.onclick=()=>{folder=button.dataset.folder;selected=null;display().catch(failure);});
 document.querySelector('#mail-query').oninput=e=>{query=e.target.value;display().catch(failure);};
 document.querySelector('#all-mail').onclick=()=>{unread=false;document.querySelector('#all-mail').classList.add('active');document.querySelector('#unread-mail').classList.remove('active');display().catch(failure);};
 document.querySelector('#unread-mail').onclick=()=>{unread=true;document.querySelector('#unread-mail').classList.add('active');document.querySelector('#all-mail').classList.remove('active');display().catch(failure);};
 document.querySelector('#compose').onclick=()=>document.querySelector('#compose-dialog').showModal();
 document.querySelector('#close-compose').onclick=()=>document.querySelector('#compose-dialog').close();
 document.querySelector('#compose-form').onsubmit=e=>{e.preventDefault();const subject=escape(document.querySelector('#compose-subject').value);messages.unshift({...messages[0],id:'local-'+messages.length,folder:'sent',author:'You',subject,body:['Hello,',escape(document.querySelector('#compose-body').value),'Jules'],preview:escape(document.querySelector('#compose-body').value),unread:false,time:'Now',attachment:false});document.querySelector('#compose-dialog').close();e.target.reset();folder='sent';selected=null;display().catch(failure);};
 document.querySelector('#mail-settings').onclick=e=>{document.body.classList.toggle('compact-mail');e.currentTarget.setAttribute('aria-pressed',String(document.body.classList.contains('compact-mail')));};
 await display();
}catch(error){failure(error);}
