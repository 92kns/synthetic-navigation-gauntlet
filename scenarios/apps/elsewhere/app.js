import {data,image,avatar,icon,ready,failure,start,routeLinks} from '/apps/runtime.js';
import {schemas} from './registry.js';
start();
document.querySelector('#shell').innerHTML=`<header class="topbar"><a class="brand" href="/apps/elsewhere/search"><em>↗</em> elsewhere<span class="brand-dot">.</span></a><nav><a href="/apps/elsewhere/results">Find a stay</a><a href="/apps/elsewhere/search">A little inspiration</a></nav><button class="button" id="saved-toggle" data-toggle aria-pressed="false">${icon('heart')} Saved places</button><img class="avatar" src="${avatar(4)}" alt="Your profile"></header><main id="main"><div id="travel-content"></div></main><footer class="row between"><a class="brand" href="/apps/elsewhere/search">elsewhere.</a><span>A little less ordinary. A little more you.</span><span>Thoughtful stays, independently found.</span></footer>`;
let stays,version=0;
async function navigate(){
 const ticket=++version;gauntletApp.ready=false;
 const page=location.pathname.split('/').pop();
 const params=new URLSearchParams(location.search),id=params.get('id')||'0';
 const {view}=await import('./views.js');
 const item=page==='stay'||page==='booking'?await data('item-'+id):null;
 if(ticket!==version)return;
 document.querySelector('#travel-content').innerHTML=view(page,stays,item,params,schemas);
 const search=document.querySelector('#stay-search');
 if(search)search.onsubmit=e=>{e.preventDefault();const query=new FormData(search);history.pushState({},'',`/apps/elsewhere/results?place=${encodeURIComponent(query.get('place'))}&nights=${query.get('nights')}&guests=${query.get('guests')}`);navigate().catch(failure);};
 const filter=document.querySelector('#breakfast-filter');
 if(filter)filter.onclick=()=>{const next=new URL(location.href);next.searchParams.set('breakfast',params.get('breakfast')==='1'?'0':'1');history.pushState({},'',next);navigate().catch(failure);};
 const sort=document.querySelector('#stay-sort');
 if(sort)sort.onchange=()=>{const next=new URL(location.href);next.searchParams.set('sort',sort.value);history.replaceState({},'',next);navigate().catch(failure);};
 const booking=document.querySelector('#booking-form');
 if(booking)booking.onsubmit=e=>{e.preventDefault();document.querySelector('#booking-confirmation').hidden=false;document.querySelector('#confirm-booking').disabled=true;document.querySelector('#confirm-booking').textContent='Reserved locally';};
 await ready(page==='results'&&params.get('breakfast')==='1'?'filtered':page);
}
try{stays=await data('stays');routeLinks(()=>navigate().catch(failure));await navigate();}catch(error){failure(error);}
