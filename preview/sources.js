/* Exact-host source validation shared by the visitor map and local notebook. */
(function(root){
  'use strict';
  function https(value){
    if(typeof value!=='string'||value.length>2000)return null;
    try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&!u.port?u:null;}catch{return null;}
  }
  function seconds(value){
    if(value===undefined||value==='')return 0;
    if(typeof value!=='string'||!/^\d+(?::[0-5]\d){0,2}$/.test(value))return null;
    const n=value.split(':').reduce((a,b)=>a*60+Number(b),0);
    return Number.isSafeInteger(n)&&n<=2147483647?n:null;
  }
  function timeLabel(n){return n>=3600?Math.floor(n/3600)+':'+String(Math.floor(n/60)%60).padStart(2,'0')+':'+String(n%60).padStart(2,'0'):Math.floor(n/60)+':'+String(n%60).padStart(2,'0');}
  function youtube(value,time=''){
    const u=https(value);if(!u)return null;
    let id='';
    if(['youtu.be','www.youtu.be'].includes(u.hostname))id=u.pathname.match(/^\/([\w-]{11})\/?$/)?.[1]||'';
    else if(['youtube.com','www.youtube.com','m.youtube.com'].includes(u.hostname))id=u.pathname==='/watch'?u.searchParams.get('v'):u.pathname.match(/^\/(?:embed|shorts|live)\/([\w-]{11})\/?$/)?.[1]||'';
    if(!/^[\w-]{11}$/.test(id||''))return null;
    const start=seconds(time);if(start===null)return null;
    return {platform:'YouTube',url:'https://www.youtube.com/watch?v='+id+(start?'&t='+start+'s':''),seconds:start,label:'YouTube'+(start?' · '+timeLabel(start):'')};
  }
  function tiktok(value){
    const u=https(value);if(!u)return null;
    const main=['tiktok.com','www.tiktok.com','m.tiktok.com'].includes(u.hostname);
    const video=main&&/^\/@[A-Za-z0-9_.]{1,24}\/video\/\d{10,25}\/?$/.test(u.pathname);
    const share=(main&&/^\/t\/[A-Za-z0-9]{5,40}\/?$/.test(u.pathname))||(['vm.tiktok.com','vt.tiktok.com'].includes(u.hostname)&&/^\/[A-Za-z0-9]{5,40}\/?$/.test(u.pathname));
    const mobile=u.hostname==='m.tiktok.com'&&/^\/v\/\d{10,25}\.html$/.test(u.pathname);
    return video||share||mobile?{platform:'TikTok',label:'TikTok',url:u.origin+u.pathname}:null;
  }
  const api={youtube,tiktok,seconds,timeLabel};
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.SourceLinks=api;
})(typeof globalThis!=='undefined'?globalThis:this);
