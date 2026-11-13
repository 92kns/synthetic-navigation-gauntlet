import {routeWork} from '/apps/route-work.js';
import {api,h,render} from './runtime.js';
import './registry.js';
let generation = 0;
let pending;
window.fieldframe = {ready:false,commentsReady:false};
const fail = error => {
  const node = document.querySelector('#error');
  node.hidden = false;
  node.textContent = error.message;
};
async function route(push = false, url = location.href) {
  const token = ++generation;
  const target = new URL(url,location.href);
  pending?.abort();
  const controller = new AbortController();
  pending = controller;
  window.fieldframe.ready = false;
  window.fieldframe.commentsReady = false;
  if (push) {
    history.replaceState({scroll:scrollY},'',location.href);
    history.pushState({scroll:0},'',target);
  }
  const search = target.pathname === '/video/search';
  const id = target.searchParams.get('v') || 'film-0';
  const query = target.searchParams.get('q') || 'outdoors';
  const [module, data] = await Promise.all([
    search ? import('./search.js') : import('./watch.js'),
    search ? api('search.json') : Promise.all([api(`${id}.json`),...['related','transcript','channel','playback','captions'].map(part=>api(`${part}-${id}.json`))]).then(parts=>Object.assign({},...parts)),
  ]);
  if (token !== generation) return;
  document.querySelector('#watch-layout').hidden = search;
  document.querySelector('#search-page').hidden = !search;
  if (!search) render(document.querySelector('#search-page'),h('div',{}));
  module.show(data,search ? query : id);
  window.fieldframe.view = search ? 'search' : id;
  document.title = `${search ? 'Search · '+query : data.video.title} | Fieldframe`;
  scrollTo(0,history.state?.scroll || 0);
  await routeWork('video', search ? 'search' : id);
  await navGauntlet.rendered();
  if (token !== generation) return;
  window.fieldframe.ready = true;
  if (!search) {
    const comments = await import('./comments.js');
    if (token === generation) await comments.load(id,controller.signal);
  }
}
document.addEventListener('click',event=>{
  const link = event.target.closest('a');
  if (link && !event.ctrlKey && !event.metaKey && !event.shiftKey && event.button === 0 && link.pathname.startsWith('/video/') && link.origin === location.origin) {
    event.preventDefault();
    route(true,link.href).catch(fail);
  }
  const save = event.target.closest('[data-save]');
  if (save) save.textContent = save.textContent === '＋' ? '✓' : '＋';
  const subscribe = event.target.closest('[data-subscribe]');
  if (subscribe) subscribe.textContent = subscribe.textContent === 'Follow' ? 'Following' : 'Follow';
  const like = event.target.closest('[data-like]');
  if (like) like.setAttribute('aria-pressed',like.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
});
document.querySelector('#search-form').addEventListener('submit',event=>{
  event.preventDefault();
  route(true,`/video/search?q=${encodeURIComponent(document.querySelector('#query').value)}`).catch(fail);
});
document.querySelector('#history-back').onclick = () => history.back();
document.querySelector('#menu').onclick = event => {
  const closed = document.body.classList.toggle('sidebar-closed');
  event.currentTarget.setAttribute('aria-expanded',!closed);
};
document.querySelector('#play').onclick = event => {
  const active = document.querySelector('#player-shell').classList.toggle('previewing');
  event.currentTarget.setAttribute('aria-pressed',active);
  document.querySelector('#play-state').textContent = active ? 'Poster preview · no audio' : 'Preview paused';
};
document.querySelector('#fullscreen').onclick = () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.querySelector('#player-shell').requestFullscreen();
};
addEventListener('popstate',()=>route().catch(fail));
route().catch(fail);
