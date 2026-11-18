// A host-only request binding, never configured by HTTP/model arguments.
import {createHash} from 'node:crypto';
export const trustedHybridAdmissions=new WeakMap();
const accepted=new Set([
 'jarvis demande a hermes de verifier la configuration doselab',
 'demande a hermes de verifier la configuration doselab',
 'jarvis demande a hermes de verifier la configuration doselab x4',
 'demande a hermes de verifier la configuration doselab x4',
]);
export function missionIntent(question){
 const text=question.normalize('NFKC').normalize('NFD').replace(/\p{M}/gu,'').toLowerCase().trim().replace(/[.!?]+$/,'').replace(/\s+/g,' ').replace(/^jarvis, /,'jarvis ');
 if(accepted.has(text))return 'doselab-current';
 // Unsupported Hermes instructions must never fall through to the broad Codex worker.
 return /herm[eèéê]s/iu.test(question.normalize('NFKC'))?'unsupported':null;
}
export function hybridAdmission({identity,space,enabled,create,audit}){
 return async data=>{
  const intent=missionIntent(data.question);
  if(!intent)return null; // zero bridge/model calls for ordinary conversation
  const response=(status,answer,extra={})=>({status,body:{answer,speech:answer,sources:[],sourceIds:[],action:null,...extra}});
  if(intent==='unsupported')return response(422,'Seule la demande synthétique « demande à Hermes de vérifier la configuration DoseLab » est autorisée.');
  if(!identity.roles.includes('missions.create')||!identity.spaces.includes(space))return response(403,'Création de mission Hermes non autorisée.');
  if(!enabled())return response(503,'Hermes est désactivé. Aucune mission créée et aucun repli automatique.');
  // Existing voice and written clients already issue a stable archive id/turn.
  // Missing/ambiguous identifiers require an explicit new request, never a blind retry.
  if(!/^[A-Za-z0-9_-]{1,128}$/.test(data.archive?.id||'')||!Number.isSafeInteger(data.archive?.turn)||data.archive.turn<0)return response(409,'Identifiant de demande stable requis. Aucune mission créée.');
  const key=createHash('sha256').update(JSON.stringify(['hybrid-doselab-v1',identity.subject,space,data.archive.id,data.archive.turn])).digest('hex');
  try{
   await audit({event:'hybrid_mission_admission',subject:identity.subject,space,template:intent,request_key:key});
   const mission=await create(key);
   return response(202,'La mission synthétique DoseLab est enregistrée. Tu peux continuer la conversation et suivre son résultat dans le panneau des missions.',{mission,execution:{engine:'hermes-admission',routing:'hybrid',asynchronous:true}});
  }catch{return response(503,'Admission Hermes indisponible ou incertaine. Consulte le panneau ; aucun repli vers Codex ni nouvelle mission automatique.');}
 };
}
export async function handleHybridAdmission(req,data){
 const handler=trustedHybridAdmissions.get(req);
 return handler?handler(data):null;
}
