'use strict';
const $=id=>document.getElementById(id);
let places=[],map=null,markers=[];
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
function external(text,url,cls='button'){const a=node('a',text,cls);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
function action(text,fn,cls=''){const b=node('button',text,cls);b.type='button';b.onclick=fn;return b;}
function sources(p){return [SourceLinks.youtube(p.youtubeUrl,p.youtubeTime),SourceLinks.tiktok(p.tiktokUrl)].filter(Boolean);}
function district(p){return (p.district||'').split(' · ')[0];}
function publicPlace(p){
  // Read only the explicit public catalog. Never load discovery/review or notebook storage.
  if(!p||typeof p.id!=='string'||typeof p.name!=='string'||!p.name.trim()||p.verified===false||p.synthetic||['draft','rejected','needs_human_review','pending'].includes(p.status))return null;
  const text=k=>typeof p[k]==='string'?p[k]:'';
  return {id:p.id,name:p.name,description:text('description'),address:text('address'),district:text('district'),cuisine:text('cuisine'),dishes:Array.isArray(p.dishes)?p.dishes.filter(d=>typeof d==='string'&&!/(待确认|待核实|unverified)/i.test(d)):[],lat:Number.isFinite(p.lat)&&Math.abs(p.lat)<=90?p.lat:null,lng:Number.isFinite(p.lng)&&Math.abs(p.lng)<=180?p.lng:null,approximate:!!p.approximate,youtubeUrl:text('youtubeUrl'),youtubeTime:text('youtubeTime'),tiktokUrl:text('tiktokUrl'),relatedVideos:Array.isArray(p.relatedVideos)?p.relatedVideos.slice(0,3).flatMap(v=>{const s=SourceLinks.youtube(v?.url);return s&&typeof v.label==='string'?[{url:s.url,label:v.label.slice(0,80)}]:[];}):[]};
}
function filtered(){const q=$('search').value.trim().toLocaleLowerCase();return places.filter(p=>(!$('district').value||district(p)===$('district').value)&&[p.name,p.description,p.address,p.district,p.cuisine,...p.dishes].join(' ').toLocaleLowerCase().includes(q));}
function render(){
 const shown=filtered();$('total').textContent=places.length;$('resultCount').textContent=shown.length+' 家餐厅';$('results').replaceChildren();
 if(!shown.length){const empty=node('div',undefined,'empty');empty.append(node('h2','暂时没有匹配的餐厅'),node('p','换个菜名或街区试试。'),action('清除筛选',clear));$('results').append(empty);}
 shown.forEach((p,i)=>{
  const card=node('article',undefined,'card');card.dataset.placeId=p.id;
  const top=node('div',undefined,'card-heading'),title=node('div'),h=node('h2');h.append(action(p.name,()=>openDetails(p.id),'card-title'));title.append(h,node('p',p.district,'area'));top.append(node('span',String(i+1),'number'),title);card.append(top,node('p',p.description,'description'));
  if(p.dishes.length)card.append(node('p',p.dishes.slice(0,3).join(' · '),'dishes'));
  const actions=node('div',undefined,'actions');actions.append(action('查看详情',()=>openDetails(p.id)));for(const s of sources(p))actions.append(external(s.label+' ↗',s.url));card.append(actions);
  if(!sources(p).length)card.append(node('p','暂无视频链接','source-missing'));$('results').append(card);
 });
 if(map){markers.forEach(m=>m.remove());markers=[];shown.forEach((p,i)=>{
  if(p.lat===null||p.lng===null)return;
  const popup=node('div');popup.append(node('h3',p.name),node('p',p.description),node('p',p.address,'popup-address'));if(p.dishes.length)popup.append(node('p',p.dishes.join(' · '),'dishes'));
  const actions=node('div',undefined,'popup-actions');actions.append(action('查看详情',()=>openDetails(p.id)));for(const s of sources(p))actions.append(external(s.label+' ↗',s.url));popup.append(actions);
  const m=L.marker([p.lat,p.lng],{title:p.name,icon:L.divIcon({className:'',html:'<div class="marker">'+(i+1)+'</div>',iconSize:[28,28],iconAnchor:[14,14]})}).addTo(map).bindPopup(popup).bindTooltip(node('span',p.name));m.placeId=p.id;markers.push(m);
 });}
}
function openDetails(id){
 const p=places.find(p=>p.id===id);if(!p)return;
 const body=$('detailBody');body.replaceChildren();const title=node('h2',p.name,'detail-title');title.id='detailTitle';body.append(title,node('p',p.description,'detail-description'));
 const section=(label)=>{const el=node('section',undefined,'detail-section');el.append(node('h3',label));body.append(el);return el;};
 const location=section('地址');location.append(node('p',p.address||'暂无详细地址'));if(p.approximate)location.append(node('p','地图针为近似位置，请以实际门店为准。','help'));
 const actions=node('div',undefined,'detail-actions');if(map&&p.lat!==null&&p.lng!==null)actions.append(action('在地图上定位',()=>{$('details').close();map.setView([p.lat,p.lng],16);$('map').scrollIntoView({block:'center',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});markers.find(m=>m.placeId===id)?.openPopup();}));actions.append(external('打开地址 ↗','https://www.amap.com/search?query='+encodeURIComponent(p.address||p.name)));location.append(actions);
 const food=section('特色菜');food.append(node('p',p.dishes.length?p.dishes.join(' · '):'暂无菜品信息','detail-dishes'));
 const videos=section('视频来源'),links=sources(p);if(!links.length)videos.append(node('p','暂无视频链接','help'));
 for(const s of links){const row=node('div',undefined,'source-item');row.append(external('在 '+s.platform+' 观看'+(s.seconds?' · '+SourceLinks.timeLabel(s.seconds):'')+' ↗',s.url,'button source-button'),external(s.url,s.url,'source-url'));videos.append(row);}
 for(const v of p.relatedVideos)videos.append(external(v.label+' · YouTube ↗',v.url,'source-url'));
 if(!$('details').open)$('details').showModal();
}
function clear(){$('search').value='';$('district').value='';render();}
$('clear').onclick=clear;$('search').addEventListener('input',render);$('district').addEventListener('change',render);$('closeDetails').onclick=()=>$('details').close();
if(window.L){
 map=L.map('map').setView([31.2304,121.4737],12);
 const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
 tiles.on('tileerror',()=>{$('mapStatus').hidden=false;$('mapStatus').textContent='部分地图未能加载，餐厅详情与地址链接仍可使用。';});
}else{$('map').replaceChildren(node('div','地图暂时无法加载。仍可浏览下方餐厅，在详情中打开地址。','map-fallback'));}
async function load(){
 try{const response=await fetch('data/places.json');if(!response.ok)throw Error();const data=await response.json();if(!Array.isArray(data.places))throw Error();places=data.places.map(publicPlace).filter(Boolean);const seen=new Set();places=places.filter(p=>!seen.has(p.id)&&seen.add(p.id));
 [...new Set(places.map(district).filter(Boolean))].sort().forEach(d=>$('district').add(new Option(d,d)));render();
 if(map&&markers.length)map.fitBounds(L.featureGroup(markers).getBounds(),{padding:[35,35],maxZoom:14});
 }catch{$('total').textContent='—';$('resultCount').textContent='餐厅信息暂时无法加载';const el=node('div',undefined,'empty');el.append(node('h2','还没加载好'),node('p','请检查连接后重试。'),action('重新加载',()=>location.reload()));$('results').replaceChildren(el);}
}
load();
