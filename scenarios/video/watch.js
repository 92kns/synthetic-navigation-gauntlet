import {h,render,media,card} from './runtime.js';
import './watch-registry.js';
export function show(data,id) {
  const video = data.video;
  document.querySelector('#poster').src = media(`poster-${video.image%4}.png`);
  document.querySelector('#poster').alt = video.scene;
  document.querySelector('#poster-title').textContent = video.shortTitle;
  document.querySelector('#duration').textContent = `/ ${data.playback.duration}`;
  const transcript = data.transcript.map(cue=>h('p',{},h('time',{},cue.time),h('span',{},cue.text)));
  render(document.querySelector('#watch-info'),h('div',{},
    h('p',{class:'eyebrow'},`${video.category.toUpperCase()} / FIELD NOTES ${String(video.image+1).padStart(2,'0')}`),
    h('h1',{id:'watch-title'},video.title),
    h('div',{class:'channel-row'},h('img',{class:'avatar',src:media(`avatar-${video.image%8}.png`),width:64,height:64,alt:''}),
      h('div',{class:'channel-detail'},h('span',{class:'channel-name'},video.channel),h('span',{class:'muted'},data.channel.followers)),
      h('button',{class:'subscribe','data-subscribe':''},'Follow'),
      h('div',{class:'actions'},h('button',{class:'pill','data-like':'','aria-pressed':'false'},'♡ 2.4K'),h('button',{class:'pill','data-save':''},'＋ Save'))),
    h('div',{class:'description'},h('strong',{},`${video.views} · ${video.age}`),h('p',{},video.description),
      h('details',{},h('summary',{},`Read the field notes & transcript · ${data.captions.language}`),h('div',{class:'transcript'},...transcript)))),
  );
  render(document.querySelector('#related-list'),h('div',{},...data.related.map((item,index)=>card(item,index))));
  render(document.querySelector('#comments'),h('div',{},h('h2',{},'Conversation'),h('p',{class:'muted'},'Gathering field notes…')));
  document.querySelector('#player-shell').dataset.video = id;
}
