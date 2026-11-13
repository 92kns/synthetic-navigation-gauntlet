import {h,render,media,api} from './runtime.js';
const message = item => h('div',{},h('h3',{},item.author,h('time',{},item.age)),h('p',{},item.text),h('div',{class:'comment-actions'},h('button',{'data-like':'','aria-pressed':'false'},`♡ ${item.likes}`),h('span',{},'Field note')));
export async function load(id,signal) {
  const data = await api(`comments-${id}.json`);
  if (signal.aborted) return;
  render(document.querySelector('#comments'),h('div',{},
    h('div',{class:'comment-heading'},h('h2',{},`${data.comments.length} field notes`),h('span',{class:'muted'},'From the community')),
    ...data.comments.map((item,index)=>h('article',{class:'comment'},
      h('img',{class:'avatar',src:media(`avatar-${index%8}.png`),width:64,height:64,loading:'lazy',alt:''}),
      h('div',{class:'comment-body'},message(item),h('details',{},h('summary',{},'1 reply'),h('div',{class:'comment-replies'},message(item.reply))))))));
  window.fieldframe.commentsReady = true;
}
