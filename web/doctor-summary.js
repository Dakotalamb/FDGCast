'use strict';
(function(root){
 function doctorSummary(s,now=Date.now()/1000){
  const pc=s.pc_health||{},pcFresh=!!pc.available&&Number.isFinite(pc.sampled_at)&&now-pc.sampled_at<10&&now>=pc.sampled_at;
  const audio=s.audio_guard||{},native=!!s.native_connected,stats=!!s.obs_connected&&!!s.stats_connected,items=[];
  const add=(i,area)=>{if(i&&i.title)items.push({key:[area,i.code||i.title,i.source_uuid||''].join(':'),title:i.title,next:i.suggestion||'Open the audio checks below and check the selected source.',evidence:i.evidence||'',area});};
  if(s.optimizer?.pending_restore)add({code:'restore',title:'Your Windows settings still need restoring',suggestion:'Use Restore now in the streaming profile below.'},'profile');
  if(native)for(const o of [s.main_output,...(s.outputs||[])].filter(Boolean)){
   const t=o.transmission_state;
   if(['stalled','reconnecting','error'].includes(t))add({code:o.id,title:(o.name||'A destination')+(t==='reconnecting'?' is reconnecting':t==='stalled'?' has stopped sending data':' could not start'),suggestion:'Open Destinations and check this output before restarting it.',evidence:o.detail||o.error||''},'outputs');
  }
  if(native)for(const i of audio.issues||[])add(i,'audio');
  if(stats)for(const i of s.issues||[])add(i,'performance');
  if(pcFresh)for(const i of s.pc_issues||[])add(i,'pc');
  const unique=[...new Map(items.map(i=>[i.key,i])).values()];
  const gaps=[];if(!s.obs_connected)gaps.push('OBS connection');else if(!s.stats_connected)gaps.push('OBS readings');if(!native)gaps.push('OBS plugin');if(!pcFresh)gaps.push('PC readings');else for(const [label,n] of [['CPU',pc.cpu_percent],['GPU',pc.gpu?.busy_percent],['memory',pc.memory_percent]])if(!Number.isFinite(n))gaps.push(label+' readings');if(!native||['setup','unknown','disabled','paused','telemetry_gap'].includes(audio.state)||!audio.state)gaps.push('audio checks');
  const sending=native&&[s.main_output,...(s.outputs||[])].some(o=>o?.transmission_state==='sending');
  if(s.demo)return {tone:'neutral',title:'Demo — connect OBS for a real check',body:'These are examples, not readings from your stream.',items:[],gaps:[],pcFresh:false};
  if(unique.length)return {tone:'warning',title:unique.length===1?'One thing needs your attention':unique.length+' things need your attention',body:'Start with the first item below.',items:unique,gaps,pcFresh};
  if(gaps.length)return {tone:'neutral',title:'Some checks are unavailable',body:'Unable to check: '+gaps.join(', ')+'.',items:[],gaps,pcFresh};
  return {tone:sending?'good':'neutral',title:sending?'No problems detected':'Ready for your next stream',body:sending?'Local checks look okay. Check your platform preview for the viewer’s picture and sound.':'Start your stream when ready. Live delivery checks begin once it sends data.',items:[],gaps,pcFresh};
 }
 if(typeof module!=='undefined')module.exports={doctorSummary};
 root.doctorSummary=doctorSummary;
 root.renderDoctorSummary=function(s){
  const model=doctorSummary(s),get=id=>document.getElementById(id),make=(tag,value,cls)=>{const e=document.createElement(tag);e.textContent=value;if(cls)e.className=cls;return e;};
  get('doctorSummary').dataset.tone=model.tone;get('doctorTitle').textContent=model.title;get('doctorIntro').textContent=model.body;
  get('doctorCoverage').textContent=model.items.length&&model.gaps.length?'Also unable to check: '+model.gaps.join(', ')+'.':'';
  const guide=get('doctorConnect');guide.hidden=!s.demo&&!model.gaps.length;
  const connection=s.demo||!s.obs_connected||!s.native_connected||!s.stats_connected;
  const audioGap=model.gaps.includes('audio checks');
  guide.textContent=connection?'Check OBS connections':audioGap?'Set up audio checks':'Show PC check details';
  guide.onclick=()=>{
   if(connection){openTab('setup');return;}
   if(audioGap){get('doctorDetails').open=true;get('doctorAudio').open=true;get('audioForm').closest('details').open=true;get('doctorAudio').scrollIntoView({behavior:'smooth',block:'start'});}
   else{get('pcTechnical').open=true;get('pcTechnical').scrollIntoView({behavior:'smooth',block:'start'});}
  };
  get('doctorMore').textContent=model.items.length>3?'See all '+model.items.length+' items and detailed checks':'More checks, history & reports';
  const signature=JSON.stringify(model.items);if(get('doctorActions').dataset.signature!==signature){
   const opened=new Set([...get('doctorActions').querySelectorAll('details[open]')].map(e=>e.dataset.key));
   get('doctorActions').replaceChildren(...model.items.slice(0,3).map(i=>{
    const card=make('article','', 'doctor-action');card.append(make('h3',i.title),make('p',i.next));
    if(i.evidence){const d=document.createElement('details');d.dataset.key=i.key;d.open=opened.has(i.key);d.append(make('summary','Why am I seeing this?'),make('p',i.evidence));card.append(d);}
    const b=make('button',i.area==='outputs'?'Open Destinations':i.area==='profile'?'Review streaming profile':i.area==='audio'?'Open audio checks':'Show detailed readings');b.type='button';b.onclick=()=>{
     if(i.area==='outputs'){openTab('outputs');return;}
     const target=i.area==='profile'?'optimizerOptions':i.area==='pc'?'pcTechnical':'doctorDetails';get(target).open=true;
     if(i.area==='audio')get('doctorAudio').open=true;
     get(target).scrollIntoView({behavior:'smooth',block:'start'});
    };card.append(b);return card;
   }));get('doctorActions').dataset.signature=signature;
  }
 };
})(typeof globalThis!=='undefined'?globalThis:this);
