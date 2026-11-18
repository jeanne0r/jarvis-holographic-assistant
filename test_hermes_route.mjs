// 18.11 route 3 (browser side): panel delegate + conversation hand-off, with a fake panel session.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const panel=readFileSync(new URL('./ops/hermes-ui/hermes-embedded.js',import.meta.url),'utf8');
const delegateSrc=panel.slice(panel.indexOf('globalThis.JarvisHermesDelegate='));
const appPatch=JSON.parse(readFileSync(new URL('./ops/hermes-ui/route/app.patch.json',import.meta.url),'utf8'));
const handoffSrc=appPatch[0][1].slice(0,appPatch[0][1].indexOf('window.jarvisAsk='));
function world({identity,missions}){
 const posted=[],events=[],messages=[],remembered=[];
 const auth={identity:()=>identity,request:async(path,opts={})=>{
  if(opts.method==='POST'){posted.push({path,key:opts.headers['idempotency-key'],body:JSON.parse(opts.body)});return {mission_id:'m1234567-aaaa'}}
  const m=/^hermes\/missions\/([^/?]+)(\/results)?\?space=user$/.exec(path);assert(m,path);
  if(m[2])return missions.results;return missions.states.length>1?missions.states.shift():missions.states[0];
 }};
 const ctx={globalThis:null,crypto:globalThis.crypto,TextEncoder,setTimeout:(f)=>setTimeout(f,0),CustomEvent:class{constructor(t,o){this.type=t;this.detail=o?.detail}},Event:class{constructor(t){this.type=t}},
  document:{dispatchEvent:e=>events.push(e)},currentSpace:'user',
  message:(who,text)=>{const line={textContent:text};messages.push(line);return {lastChild:line}},remember:(r,t)=>remembered.push(t)};
 ctx.globalThis=ctx;ctx.JarvisHermesAuth=auth;vm.createContext(ctx);vm.runInContext(delegateSrc+'\n'+handoffSrc,ctx);
 return {ctx,posted,events,messages,remembered};
}
const identity={roles:['missions.create','missions.read'],spaces:['user']};
{ // completed: one POST with the question, stable key from the voice turn, result in the conversation, spoken summary
 const w=world({identity,missions:{states:[{state:'queued'},{state:'running'},{state:'completed'}],results:{events:[
  {kind:'report_quality',data:JSON.stringify({measurements_read:3})},
  {kind:'completed',data:JSON.stringify({output:'| a | b |\n|---|---|\nOui, recalibrer : écart `ha://sensor.vsv/history/24h@x` de -0,4 ml.'})}]}}});
 await vm.runInContext('hermesHandoff',w.ctx)('Dois-je recalibrer le VSV ?',{space:'user',archive:{id:'voice-1',turn:3}});
 assert.equal(w.posted.length,1);assert.deepEqual(w.posted[0].body,{objective:'Dois-je recalibrer le VSV ?'});assert.equal(w.posted[0].key,'jarvis-route-voice-1-3');
 assert.match(w.messages.at(-1).textContent,/Résultat de Hermes.*3 lectures réelles/);assert.match(w.remembered[0],/recalibrer/);
 const spoken=w.events.find(e=>e.type==='jarvis:hermes-result').detail.speech;assert.match(spoken,/^L’analyse de Hermes est prête\. Oui, recalibrer/);assert(!/\||ha:\/\//.test(spoken));
}
{ // failed: no replay, reason given, pointer to the panel
 const w=world({identity,missions:{states:[{state:'failed'}],results:{events:[{kind:'failed',data:JSON.stringify({reason:'GPU indisponible.'})}]}}});
 await vm.runInContext('hermesHandoff',w.ctx)('Analyse la PAC sur 30 jours',{space:'user',archive:null});
 assert.equal(w.posted.length,1);assert.match(w.messages.at(-1).textContent,/a échoué\. GPU indisponible\. Détails dans le panneau/);assert.match(w.posted[0].key,/^jarvis-route-[0-9a-f-]{36}$/);
}
{ // not connected to the missions panel: nothing posted, clear instruction
 const w=world({identity:null,missions:{states:[{}],results:{}}});
 await vm.runInContext('hermesHandoff',w.ctx)('Analyse',{space:'user',archive:null});
 assert.equal(w.posted.length,0);assert.match(w.messages[0].textContent,/connecte-toi au panneau Missions/);assert.equal(w.remembered.length,0);
}
console.log('hermes route (browser): ok');
