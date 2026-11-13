import {routeWork} from '/apps/route-work.js';
export {h, render} from '/video/runtime.js';
export const app = document.body.dataset.app;
export const origin = host => location.origin.replace(/\/\/[^.]+(?=\.gauntlet\.test)/, `//${host}${location.hostname.includes('--') ? '--'+location.hostname.split('--')[1].split('.')[0] : ''}`);
export const image = (name, number=0, density=1) => `${origin(app+'-media')}/apps/images/${name}-${number}${density>1?'@2x':''}.png`;
export const avatar = number => `${origin(app+'-media')}/apps/images/avatar-${number%12}.png`;
export async function data(name) {
 const response = await fetch(`${origin(app+'-api')}/apps/${app}/data/${name}.json`, {cache:'no-store'});
 if (!response.ok) throw new Error(`Unable to load ${name}: ${response.status}`);
 return response.json();
}
export const icon = name => `<svg class="icon" aria-hidden="true"><use href="/apps/icons.svg#${name}"/></svg>`;
export function routeLinks(navigate) {
 document.addEventListener('click', event => {
  const link = event.target.closest('a[data-go]');
  if (!link || event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault(); history.pushState({}, '', link.href); navigate();
 });
 addEventListener('popstate', navigate);
}
export function actions() {
 document.addEventListener('click', event => {
  const button = event.target.closest('[data-toggle]');
  if (button) {const on=button.getAttribute('aria-pressed')!=='true';button.setAttribute('aria-pressed',String(on));button.classList.toggle('selected',on);}
  if (event.target.closest('[data-back]')) {event.preventDefault();history.back();}
 });
}
export async function ready(view) {
 await routeWork(app, view);
 window.gauntletApp.view=view;window.gauntletApp.ready=true;
 if(app!=='letterdesk')scrollTo(0,0);
 document.querySelector('#error').hidden=true;
 await navGauntlet.rendered();
}
export function failure(error) {document.querySelector('#error').hidden=false;document.querySelector('#error').textContent=error.message;console.error(error);}
export const start = () => {window.gauntletApp={ready:false,view:''};actions();};
export const paragraph = 'Small changes make a place feel different. We met the people making room for a more thoughtful everyday, and asked what they would carry forward. Here are their notes from a week of trying, learning and starting again.';

export const escape = value => value.replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;");
