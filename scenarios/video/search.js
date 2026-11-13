import {h,render,card} from './runtime.js';
export function show(data,query) {
  document.querySelector('#query').value = query;
  const view = (filter = 0) => {
    const selected = filter ? data.videos.filter(item=>item.image%3 === filter-1) : data.videos;
    render(document.querySelector('#search-page'),h('div',{},
      h('div',{class:'search-heading'},h('div',{},h('p',{class:'eyebrow'},'GOOD STORIES ARE WORTH FINDING'),h('h1',{},`A world of ${query}`)),h('span',{class:'muted'},`${selected.length} films to wander through`)),
      h('div',{class:'search-filters'},...['All films','Land & light','Made by hand','The long way home'].map((label,index)=>h('button',{class:'pill','aria-pressed':index === filter,'data-filter':index},label))),
      h('div',{class:'search-results'},...selected.map((item,index)=>card(item,index,true))),
      h('p',{class:'collection-note'},'Take the scenic route. There is always another story.')));
    document.querySelectorAll('[data-filter]').forEach(button=>button.onclick=()=>view(Number(button.dataset.filter)));
  };
  view();
}
