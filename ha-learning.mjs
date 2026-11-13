import {spawn} from 'node:child_process';
import {haTermsMatch} from './ha-search.mjs';
export function haLearning(action,data={}){return new Promise((resolve,reject)=>{
 const p=spawn('python3',[new URL('./ha-learning.py',import.meta.url).pathname,action],{stdio:['pipe','pipe','ignore']});let out='';const timer=setTimeout(()=>p.kill(),4000);
 p.stdout.on('data',b=>out+=b);p.stdin.on('error',()=>{});p.on('error',()=>{clearTimeout(timer);reject(Error('Repères HA indisponibles.'))});p.on('close',code=>{clearTimeout(timer);try{if(code!==0)throw Error();resolve(JSON.parse(out))}catch{reject(Error('Repères HA indisponibles.'))}});p.stdin.end(JSON.stringify(data));
})}
const normalize=s=>String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').trim();
export async function learnedHints(question,space,store=haLearning){
 const text=normalize(question),rows=await store('list',{space});
 return rows.filter(r=>haTermsMatch(normalize(r.query).split(' ').filter(Boolean),text)).slice(0,4).map(({key,query,filters,entities})=>({key,query,filters,entities,kind:'repere automatique provisoire : vérifier avec les outils HA actuels, pas une valeur ni une autorisation'}));
}
export function learningRows(observations,selected){
 const ids=new Set(Array.isArray(selected)?selected:[]),rows=[];
 for(const o of observations){
  if(!o.args?.query||/^\w+\.[\w_]+$/.test(o.args.query)||!o.result?.connected)continue;
  const states=o.result.states||[],chosen=states.filter(s=>ids.has(s.entity_id)&&!['unknown','unavailable'].includes(s.state));
  if(!chosen.length||chosen.length>5)continue;
  rows.push({query:o.args.query,filters:Object.fromEntries(Object.entries(o.args).filter(([k,v])=>['domain','device_class','area','protocol'].includes(k)&&v)),entities:chosen.map(({entity_id,name,unit,device_class})=>({entity_id,name,unit,device_class}))});
 }
 return rows.slice(-8);
}
export function haObservation(item){
 if(item.tool!=='consulter_home_assistant'||item.status!=='completed')return null;
 try{const result=JSON.parse(item.result?.content?.find(c=>c.type==='text')?.text||'null');if(!result?.connected)return null;return {args:item.arguments,result}}catch{return null}
}

export function invalidatedHints(hints,observations){
 return hints.filter(h=>h.entities.some(e=>observations.some(o=>{
  const current=o.result?.states?.find(s=>s.entity_id===e.entity_id);
  return o.args?.query===e.entity_id&&o.result?.connected&&o.result?.matched===0||current&&['name','unit','device_class'].some(k=>String(current[k]||'')!==String(e[k]||''));
 }))).map(h=>h.key);
}

export function explicitAliasHints(question,rows){
 const text=normalize(question);return rows.filter(r=>/^[a-z_]+\.[a-z0-9_]+$/.test(r.entity_id||'')&&r.label&&haTermsMatch(normalize(r.label).split(' ').filter(Boolean),text)).slice(0,4).map(r=>({query:r.label,entities:[{entity_id:r.entity_id,name:r.label}],kind:'alias explicitement mémorisé par la personne : prioritaire sur les repères automatiques, valeur actuelle à relire dans HA'}));
}
