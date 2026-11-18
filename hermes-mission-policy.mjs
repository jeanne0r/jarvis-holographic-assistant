// Server-only capability compilation. A user's text never supplies tools or context.
import {HERMES_OBJECTIVE} from './hermes-voice-tools.mjs';
import {missionIntent} from './hybrid-mission-admission.mjs';
export const missionCapabilities=Object.freeze({
 template:'doselab-current',data:'synthetic-only',maxCharacters:2000,
 tools:Object.freeze(['memory.search','report']),
 budget:Object.freeze({tokens:0,cost_micros:0,local_tokens:98304,seconds:240,attempts:1}),
 physical:false,shell:false,personalContext:false,remoteFallback:false,skillPublication:false,
});
export function missionObjective(data,{admissionEnabled=false,textEnabled=false}={}){
 if(!admissionEnabled||!data||typeof data!=='object'||Array.isArray(data))return null;
 if(Object.keys(data).join()==='template'&&data.template===missionCapabilities.template)return HERMES_OBJECTIVE;
 if(textEnabled&&Object.keys(data).join()==='objective'&&typeof data.objective==='string'&&data.objective.trim().length>=1&&data.objective.length<=2000)
  return 'Demande explicite utilisateur (données et outils synthétiques seulement) : '+data.objective;
 return null;
}
export function missionDefinition(objective){
 if(typeof objective!=='string'||!objective||objective.length>2200)throw Error('Bounded server objective required');
 return {objective,trigger:'jarvis-experimental',priority:1,memory_context:[],plan:['retrieve','report'],allowed_tools:[...missionCapabilities.tools],budget:{...missionCapabilities.budget}};
}
// Conservative preview; does not admit a task, fetch context, grant a role or call AI.
export function requestDisposition(text,identity){
 if(typeof text!=='string'||!text.trim()||text.length>2000)return {route:'clarify',reason:'Demande explicite limitée requise.'};
 if(!identity||identity.kind!=='human')return {route:'denied',reason:'Identité humaine vérifiée requise.'};
 if(/(?:allume|éteins|active|désactive|démarre|arrête|actionne|commande)\b.*(?:pompe|chauffage|mineur|s19|s9|jacuzzi|home assistant)/iu.test(text))
  return {route:'approval_required',available:false,reason:'Action physique hors du périmètre Hermes.'};
 const intent=missionIntent(text);
 if(intent){
  if(!identity.roles?.includes('missions.create'))return {route:'denied',reason:'Création de mission non autorisée.'};
  return intent==='unsupported'?{route:'clarify',reason:'Décris une mission et les données explicitement autorisées.'}:{route:'hermes',template:intent,data:'synthetic-only'};
 }
 if(/(?:modifie|corrige|développe|compile|teste)\b.*(?:code|dépôt|logiciel|programme)/iu.test(text))return identity.roles?.includes('development')?{route:'codex',approvalRequired:true}:{route:'denied',reason:'Développement non autorisé.'};
 return {route:'conversation'};
}
