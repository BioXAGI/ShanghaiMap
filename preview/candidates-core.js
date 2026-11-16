/* Owner-only candidate review. No network calls, publishing or credentials. */
(function(root){
'use strict';
const Links=typeof module==='object'&&module.exports?require('./sources.js'):root.SourceLinks;
const NOTEBOOK_KEY='preview-shanghai-food-map-v1',QUEUE_KEY='preview-shanghai-food-map-candidates-v1';
const EDIT_FIELDS=['name','branch','description','address','district','cuisine','dishes','videoUrl','videoTime','tiktokUrl','lat','lng'];
function text(v,max=2000){return typeof v==='string'?v.trim().slice(0,max):'';}
function https(v){try{const u=new URL(v);return u.protocol==='https:'&&!u.username&&!u.password&&!u.port&&v.length<=2000?u.href:'';}catch{return '';}}
function norm(v){return text(v).normalize('NFKC').toLocaleLowerCase().replace(/[\s·,，()（）]/g,'');}
function arr(v,max=30){return Array.isArray(v)?v.filter(x=>typeof x==='string').map(x=>text(x,200)).filter(Boolean).slice(0,max):[];}
function parseBatch(data){
 if(!data||data.schema_version!==1||!['live','manual','dry-run'].includes(data.mode)||!Array.isArray(data.candidates)||data.candidates.length>500)throw Error('Choose schema_version 1 discovery JSON, mode live, manual or dry-run, with up to 500 candidates.');
 const out=[],seen=new Set();let excluded=0;
 for(const raw of data.candidates){
  if(!raw||typeof raw!=='object'||!text(raw.id,120))throw Error('Every candidate needs an ID.');
  if(!['shanghai','上海'].includes(text(raw.city_candidate,40).toLowerCase())){excluded++;continue;}
  const id=text(raw.id,120),key='Shanghai:'+id;if(seen.has(key))throw Error('Duplicate candidate ID: '+id);seen.add(key);
  const provenance=[];const add=(label,url)=>{const safe=https(url);if(safe&&!provenance.some(p=>p.url===safe))provenance.push({label:text(label,100)||'Source',url:safe});};
  add('YouTube video',raw.video_url);for(const p of Array.isArray(raw.provenance)?raw.provenance:[])if(p&&typeof p==='object')add(p.label,p.url);
  for(const u of Array.isArray(raw.evidence_urls)?raw.evidence_urls:[])add('Web evidence',u);
  for(const u of Array.isArray(raw.comments?.comment_evidence_urls)?raw.comments.comment_evidence_urls:[])add('Comment clue (unverified)',u);
  const youtube=Links.youtube(raw.video_url,typeof raw.youtube_time==='string'?raw.youtube_time:'');
  const tiktok=Links.tiktok(raw.tiktok_url);
  const draft={name:text(raw.restaurant_name,120),branch:text(raw.branch,120),description:text(raw.description,1000),address:text(raw.address,240),district:text(raw.district,80),cuisine:text(raw.cuisine,80),dishes:arr(raw.dishes),videoUrl:youtube?.url.split('&t=')[0]||'',videoTime:youtube?text(raw.youtube_time,12):'',tiktokUrl:tiktok?.url||'',lat:Number.isFinite(raw.lat)?String(raw.lat):'',lng:Number.isFinite(raw.lng)?String(raw.lng):''};
  const synthetic=data.mode==='dry-run'||raw.synthetic===true||raw.mode==='dry-run';
  out.push({key,id,title:text(raw.title,500),excerpt:text(raw.description_excerpt,1000),publishedAt:text(raw.published_at,80),channel:text(raw.channel_title,200),generatedAt:text(raw.discovered_at||data.generated_at,80),mode:data.mode,synthetic,provenance:provenance.slice(0,30),commentCount:Number.isInteger(raw.comments?.relevant_comment_count_sampled)?Math.max(0,raw.comments.relevant_comment_count_sampled):0,proposedMatch:text(raw.existing_place_id,100),draft,status:'pending',targetId:'',localId:'',confirmed:false});
 }
 return {candidates:out,excluded};
}
function validNotebook(p){return p&&typeof p==='object'&&typeof p.id==='string'&&p.id.length<100&&typeof p.name==='string'&&p.name.trim()&&p.name.length<=120&&['Want to try','Visited','Favorite'].includes(p.status)&&['cuisine','address','district','notes','image'].every(k=>typeof p[k]==='string')&&(p.lat===null&&p.lng===null||Number.isFinite(p.lat)&&Number.isFinite(p.lng)&&Math.abs(p.lat)<=90&&Math.abs(p.lng)<=180);}
function readNotebook(storage){const raw=storage.getItem(NOTEBOOK_KEY);if(raw===null)throw Error('Open the preview notebook first to initialize it, then return here.');let p;try{p=JSON.parse(raw);}catch{throw Error('Notebook storage is unreadable. It has not been overwritten.');}if(!Array.isArray(p)||!p.every(validNotebook))throw Error('Notebook storage is invalid. It has not been overwritten.');return p;}
function toDraft(p){return {name:p.name||'',branch:p.branch||'',description:p.description||'',address:p.address||'',district:p.district||'',cuisine:p.cuisine||'',dishes:Array.isArray(p.dishes)?p.dishes:[],videoUrl:p.videoUrl||'',videoTime:p.videoTime||'',tiktokUrl:p.tiktokUrl||'',lat:p.lat===null?'':String(p.lat),lng:p.lng===null?'':String(p.lng)};}
function matches(draft,places){return places.map(p=>{let score=0;const n=norm(draft.name),a=norm(draft.address);if(n&&norm(p.name)===n)score+=5;else if(n&&(norm(p.name).includes(n)||n.includes(norm(p.name))))score+=2;if(a&&norm(p.address)===a)score+=6;return {place:p,score};}).filter(m=>m.score>0).sort((a,b)=>b.score-a.score).slice(0,6);}
function mergeDraft(candidate,existing){const result=toDraft(existing);for(const k of EDIT_FIELDS){const v=candidate[k];if(Array.isArray(v)?v.length:v!==''&&v!==undefined)result[k]=v;}return result;}
function buildPlace(entry,before){
 if(entry.status!=='pending')throw Error('This candidate already has a decision.');
 if(entry.synthetic||entry.mode==='dry-run')throw Error('Synthetic/dry-run candidates cannot be added or used to update the notebook.');
 if(!entry.confirmed)throw Error('Confirm the exact branch, address and any video association after reviewing evidence.');
 const d=entry.draft;if(!d||!text(d.name,120)||!text(d.address,240))throw Error('Enter a verified restaurant name and branch address.');
 if(d.name.length>120||d.address.length>240)throw Error('Name or address is too long.');
 if(d.videoUrl&&!Links.youtube(d.videoUrl,d.videoTime))throw Error('Enter a valid HTTPS YouTube video and start time.');
 if(Links.seconds(d.videoTime)===null)throw Error('Use seconds, mm:ss or hh:mm:ss for video time.');
 if(d.tiktokUrl&&!Links.tiktok(d.tiktokUrl))throw Error('Enter a valid HTTPS TikTok video or short link, or leave it blank.');
 if((d.lat==='')!==(d.lng===''))throw Error('Enter both coordinates or leave both blank.');
 const lat=d.lat===''?null:Number(d.lat),lng=d.lng===''?null:Number(d.lng);if(lat!==null&&(!Number.isFinite(lat)||!Number.isFinite(lng)||Math.abs(lat)>90||Math.abs(lng)>180))throw Error('Check the coordinates.');
 const p={...(before||{id:entry.localId,status:'Want to try',budget:'',notes:'',image:''}),name:d.name.trim(),branch:text(d.branch,120),description:text(d.description,1000),address:d.address.trim(),district:text(d.district,80),cuisine:text(d.cuisine,80),dishes:arr(d.dishes),videoUrl:d.videoUrl?Links.youtube(d.videoUrl,d.videoTime).url.split('&t=')[0]:'',videoTime:d.videoTime||'',tiktokUrl:d.tiktokUrl?Links.tiktok(d.tiktokUrl).url:'',lat,lng};
 if(!p.id||!validNotebook(p))throw Error('Invalid place data.');
 return p;
}
function preview(entry,places){const before=entry.targetId?places.find(p=>p.id===entry.targetId):null;if(entry.targetId&&!before)throw Error('Selected restaurant no longer exists. Reload the notebook.');return {before,after:buildPlace(entry,before)};}
function commit(entry,storage,expectedBefore){
 const latest=readNotebook(storage),before=entry.targetId?latest.find(p=>p.id===entry.targetId):null;
 if(entry.targetId&&JSON.stringify(before)!==JSON.stringify(expectedBefore))throw Error('This restaurant changed in another tab. Reload before updating.');
 const after=buildPlace(entry,before);
 if(!entry.targetId&&latest.some(p=>p.id===after.id||norm(p.name)===norm(after.name)&&norm(p.address)===norm(after.address)))throw Error('This restaurant is already in the notebook. Select it and review an Update instead.');
 const next=entry.targetId?latest.map(p=>p.id===entry.targetId?after:p):[after,...latest];
 storage.setItem(NOTEBOOK_KEY,JSON.stringify(next));
 return {before,after,action:entry.targetId?'updated':'added'};
}
function searchLinks(d){const q=['上海',d.name,d.branch,d.address].filter(Boolean).join(' ');return [{label:'Amap address search',url:'https://www.amap.com/search?query='+encodeURIComponent(q)},{label:'Web evidence search',url:'https://www.google.com/search?q='+encodeURIComponent(q)},{label:'YouTube search',url:'https://www.youtube.com/results?search_query='+encodeURIComponent(q+' 美食')}];}
function expired(entry,now=Date.now()){if(entry.mode!=='live')return false;const t=Date.parse(entry.generatedAt||entry.importedAt);return Number.isFinite(t)&&now-t>30*86400000;}
function restoreQueue(data){
 if(data?.format!=='shanghaimap-owner-review'||data.version!==1||!Array.isArray(data.entries)||data.entries.length>1000)throw Error('Invalid review backup.');
 const seen=new Set();return data.entries.map(raw=>{
  if(!raw||typeof raw.key!=='string'||seen.has(raw.key)||!['pending','added','updated','skipped'].includes(raw.status)||!['manual','live','dry-run'].includes(raw.mode)||!raw.draft||!EDIT_FIELDS.every(k=>k==='dishes'?Array.isArray(raw.draft[k])&&raw.draft[k].every(x=>typeof x==='string'):typeof raw.draft[k]==='string')||!Array.isArray(raw.provenance)||!raw.provenance.every(p=>p&&typeof p.label==='string'&&!!https(p.url)))throw Error('Invalid review backup entry.');
  seen.add(raw.key);const e={};for(const k of ['key','id','title','excerpt','publishedAt','channel','generatedAt','importedAt','decidedAt','proposedMatch','targetId','localId','status','mode'])e[k]=text(raw[k],k==='excerpt'?1000:500);
  e.synthetic=raw.mode==='dry-run'||!!raw.synthetic;e.confirmed=false;e.commentCount=Number.isInteger(raw.commentCount)?Math.max(0,raw.commentCount):0;e.provenance=raw.provenance.slice(0,30).map(p=>({label:text(p.label,100),url:https(p.url)}));e.draft={};for(const k of EDIT_FIELDS)e.draft[k]=k==='dishes'?arr(raw.draft[k]):text(raw.draft[k],2000);return e;
 });
}
const api={NOTEBOOK_KEY,QUEUE_KEY,EDIT_FIELDS,expired,restoreQueue,parseBatch,readNotebook,toDraft,matches,mergeDraft,buildPlace,preview,commit,searchLinks,https};if(typeof module==='object'&&module.exports)module.exports=api;root.CandidateReview=api;
})(typeof globalThis!=='undefined'?globalThis:this);
