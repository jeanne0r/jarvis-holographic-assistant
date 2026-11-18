import {haTermsMatch} from './ha-search.mjs';
import {haLearning} from './ha-learning.mjs';
import {spawn} from 'node:child_process';
export function memoryStore(action,data={}) {
 return new Promise((resolve,reject)=>{
  const child=spawn('python3',[new URL('./voice-memory.py',import.meta.url).pathname,action],{stdio:['pipe','pipe','ignore']});let output='';
  child.stdout.on('data',chunk=>output+=chunk);
  child.on('error',()=>reject(Error('Mémoire persistante indisponible.')));child.stdin.on('error',()=>{});
  child.on('close',()=>{try{const r=JSON.parse(output);r.ok?resolve(r.data):reject(Error(r.error));}catch{reject(Error('Mémoire persistante indisponible.'));}});
  child.stdin.end(JSON.stringify(data));
 });
}
export const voiceMemoryTool={name:'memoire_jarvis',description:'Mémoire persistante, retrouvée après rechargement et nouvelle session. Enregistrer les faits explicitement demandés ; les corrections directes sont gérées par le moteur et réutilisées automatiquement. Pour les autres faits, enregistrer seulement ce que la personne demande explicitement de retenir (noms d’appareils, habitudes, préférences), jamais les valeurs temporaires, secrets ou transcriptions complètes. Consulter pour retrouver, y compris les repères automatiques provisoires de recherche HA ; oublier pour supprimer (clé ha-lookup:... pour ces repères). Une association entity_id exige une entité déjà consultée. Annoncer mémorisé uniquement après saved:true.',parameters:{type:'OBJECT',properties:{action:{type:'STRING',enum:['consulter','memoriser','oublier']},key:{type:'STRING',description:'Nom du fait ; vide pour lister, puis offset pour la suite.'},fact:{type:'STRING',description:'Fait ou préférence demandé explicitement, 800 caractères max.'},entity_id:{type:'STRING',description:'Facultatif : association avec une entité HA exacte déjà consultée.'},area:{type:'STRING',description:'Facultatif : pièce apprise explicitement.'},shared:{type:'BOOLEAN',description:'true pour un nouveau souvenir explicitement partagé avec la maison, ou pour corriger/oublier un souvenir commun identifié ; sinon espace actif.'} ,offset:{type:'INTEGER',description:'Pagination de consultation, 0 par défaut.'}},required:['action','key']}};
export async function voiceMemory(args,session){
 if(!args||!['consulter','memoriser','oublier'].includes(args.action)||typeof args.key!=='string')throw Error('Requête mémoire invalide.');
 if(args.shared!==undefined&&typeof args.shared!=='boolean')throw Error('Espace de mémoire invalide.');
 const space=args.shared?'commun':session.space;
 if(session.identity&&!session.identity.spaces.includes(space))throw Error('Espace mémoire non autorisé.');
 if(args.action==='oublier'&&args.key.startsWith('ha-lookup:'))return haLearning('forget',{space,key:args.key});
 if(args.action==='consulter'){
  const rows=await memoryStore('list',{space:session.space,include_common:!session.identity||session.identity.spaces.includes('commun')});
  const words=text=>text.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').split(' ').filter(t=>t&&!['de','du','des','le','la','les','l','d'].includes(t));
  if(args.offset!==undefined&&(!Number.isInteger(args.offset)||args.offset<0||args.offset>128))throw Error('Pagination invalide.');
  const terms=words(args.key),found=rows.filter(r=>{const text=words(r.label+' '+r.fact).join(' ');return terms.every(t=>text.includes(t));});
  let automaticLookupHints=[];try{automaticLookupHints=(await haLearning('list',{space:session.space})).filter(r=>!args.key||haTermsMatch(words(r.query),words(args.key).join(' '))||haTermsMatch(words(args.key),words(r.query).join(' '))).slice(0,5)}catch{}
  const offset=args.offset||0;return {automaticLookupHints,memories:found.slice(offset,offset+5),nextOffset:offset+5<found.length?offset+5:null,total:found.length};
 }
 if(args.entity_id&&!session.entities.has(args.entity_id))throw Error('Consulte d’abord cette entité Home Assistant avant de mémoriser son nom.');
 const result=await memoryStore(args.action==='memoriser'?'save':'forget',{...args,space});
 session.memories=await memoryStore('list',{space:session.space,include_common:!session.identity||session.identity.spaces.includes('commun')});
 return result;
}
export function memoryContext(memories,budget=12000,factLimit=800){
 const selected=[];let chars=0;
 for(const r of memories){const row={key:r.key,fact:r.fact.slice(0,factLimit),entity_id:r.entity_id,area:r.area,space:r.space};const size=JSON.stringify(row).length;if(chars+size>budget-2)continue;selected.push(row);chars+=size;}
 return JSON.stringify(selected);
}
