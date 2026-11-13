import {h,render,avatar} from '/apps/runtime.js';
import {schemas} from './route-registry.js';
export function channel(c,base){
 render(document.querySelector('#channel-main'),h('div',{class:'channel-copy kilncast-tone-'+(schemas.length+base.length)%300},
  h('div',{class:'row channel-header'},h('img',{class:'avatar',src:avatar(c.avatar),alt:''}),h('div',{},h('h1',{},c.title),h('a',{href:'/apps/kilncast/channel?id='+c.id,'data-go':''},c.name)),h('button',{class:'button primary','data-toggle':'','aria-pressed':'false'},'♡ Follow'),h('button',{class:'button','data-back':'',id:'live-back'},'Previous studio')),
  h('div',{class:'row'},h('span',{class:'chip'},c.category),h('span',{class:'muted'},c.viewers+' curious people watching')),
  h('div',{class:'about-studio'},h('h2',{},'A work in progress. You are invited.'),h('p',{},c.description),h('div',{class:'schedule'},c.schedule.map(s=>h('div',{},h('b',{},s.day),h('span',{},s.time+' · '+s.topic)))))));
}
