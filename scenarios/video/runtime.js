export const h = (tag, props = {}, ...children) => ({tag, props, children: children.flat(Infinity).filter(child => child !== null)});
function create(vnode) {
  if (typeof vnode !== 'object') return document.createTextNode(String(vnode));
  const node = document.createElement(vnode.tag);
  updateProps(node, {}, vnode.props);
  for (const child of vnode.children) node.append(create(child));
  return node;
}
function updateProps(node, old, next) {
  for (const key of new Set([...Object.keys(old), ...Object.keys(next)])) {
    if (old[key] === next[key]) continue;
    if (next[key] === undefined) node.removeAttribute(key);
    else node.setAttribute(key, next[key]);
  }
}
function patch(parent, node, before, after) {
  if (typeof before !== typeof after || typeof after === 'object' && before.tag !== after.tag) {
    parent.replaceChild(create(after), node);
  } else if (typeof after !== 'object') {
    if (before !== after) node.textContent = String(after);
  } else {
    updateProps(node, before.props, after.props);
    const children = [...node.childNodes];
    after.children.forEach((child, index) => {
      if (index < before.children.length) patch(node, children[index], before.children[index], child);
      else node.append(create(child));
    });
    for (let index = after.children.length; index < children.length; index++) children[index].remove();
  }
}
const roots = new WeakMap();
export function render(root, tree) {
  const previous = roots.get(root);
  if (previous) patch(root, root.firstChild, previous, tree);
  else root.replaceChildren(create(tree));
  roots.set(root, tree);
}
export const media = path => `${location.origin.replace(/\/\/video(?=--|\.)/, '//frames')}/video/images/${path}`;
export const api = async path => {
  const response = await fetch(`${location.origin.replace(/\/\/video(?=--|\.)/, '//api')}/video/data/${path}`, {cache:'no-store'});
  if (!response.ok) throw new Error(`Film data unavailable: ${response.status}`);
  return response.json();
};
export function card(video, index, search = false) {
  const href = `/video/watch?v=${video.id}`;
  return h('article', {class:'video-card'},
    h('a', {class:'thumb-link',href, 'data-route':'', id:`${search ? 'result' : 'related'}-${index}`},
      h('img', {class:'thumb',src:media(`thumb-${video.image}.png`),width:480,height:270,loading:index < (search ? 4 : 16) ? 'eager' : 'lazy',alt:video.scene}),
      h('span',{class:'time-badge'},video.duration)),
    h('div',{class:`card-copy ff-tone-${video.image}`},h('h3',{},h('a',{href,'data-route':''},video.title)),
      h('p',{},...(search ? [h('img',{class:'avatar',src:media(`avatar-${video.image%8}.png`),width:64,height:64,loading:'lazy',alt:''})] : []),video.channel),
      h('p',{},h('span',{},video.views), ' · ', h('span',{},video.age)),
      ...(search ? [h('p',{class:'search-description'},video.description)] : []),
      h('div',{class:'card-tags'},h('span',{},video.category),h('span',{},'Original film'))),
    h('button',{class:'card-menu','aria-label':`Save ${video.title}`,'data-save':''},'＋'));
}
