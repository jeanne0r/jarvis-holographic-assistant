// Optional Gemini tool; admission/lookup only, never an agent loop or audio code.
let service=null;
export const HERMES_TEMPLATE='doselab-current';
export const HERMES_OBJECTIVE='DoseLab X4 synthétique : retrouve la configuration actuelle des quatre cellules de pesée et explique les modifications historiques avec leurs sources exactes.';
export const missionTool={name:'mission_hermes',description:'Enregistre une mission autonome synthétique DoseLab, ou consulte son état/résultat. N’attends jamais sa fin. Aucun équipement, donnée personnelle ni approbation.',parameters:{type:'OBJECT',properties:{action:{type:'STRING',enum:['create','status','result']},mission_id:{type:'STRING'}},required:['action']}};
export function configureHermesVoice(value){service=value}
export function hermesTools(identity){return service&&(!service.enabled||service.enabled())&&identity?.roles?.includes('missions.read')?[missionTool]:[]}
export async function hermesVoice(args,session,callId){
 if(!service||!session.identity)throw Error('Hermes disabled');
 if(!args||Object.keys(args).some(k=>!['action','mission_id'].includes(k)))throw Error('Mission fields denied');
 return service({identity:session.identity,space:session.space,args,callId,sessionId:session.id});
}
export function legacyToolPermission(name){
 if(name==='piloter_home_assistant')return 'physical';
 if(name==='evolution_jarvis')return 'development';
 if(name==='memoire_jarvis')return 'memory.write';
 if(name==='chercher_souvenirs')return 'memory.read';
 if(['consulter_home_assistant','commandes_home_assistant'].includes(name))return 'home.read';
 return 'capabilities';
}
