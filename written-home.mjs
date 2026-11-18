import {consultHomeAssistant} from './home-assistant.mjs';
import {memoryStore,memoryContext} from './voice-memory.mjs';

// Only the server can execute this lookup. No service calls, shell or arbitrary URL.
export async function answerWithHomeAssistant(question,sources,context,signal,generate,dependencies={}) {
 const consult=dependencies.consult||consultHomeAssistant;
 let memories=[];
 try { memories=await (dependencies.memories||memoryStore)('list',{space:context.space}); } catch {}
 const session={entities:new Set(),services:new Map(),memories,economy:true};
 const homeAssistant={lookupAllowed:true,readOnly:true,aliases:JSON.parse(memoryContext(memories,1800,160)),observations:[]};
 for(let step=0;step<4;step++) {
  signal?.throwIfAborted();
  homeAssistant.lookupAllowed=step<3;
  const result=await generate(question,sources,{...context,homeAssistant},signal);
  signal?.throwIfAborted();
  const lookup=result.homeAssistantLookup;
  if(!lookup?.requested) {delete result.homeAssistantLookup;return result;}
  if(!homeAssistant.lookupAllowed) return {answer:'Je n’ai pas pu identifier la mesure avec certitude dans Home Assistant. Quel est le nom exact du capteur ?',sourceIds:[],action:{type:'none',target:'',title:'',text:''}};
  // Explicit allowlist: model output cannot introduce writes or change credentials.
  const args={query:lookup.query,domain:lookup.domain,area:lookup.area,offset:lookup.offset,details:lookup.details};
  let observation;
  try {observation=await consult(args,session);} catch {observation={connected:false,error:'Consultation Home Assistant impossible.'};}
  signal?.throwIfAborted();
  homeAssistant.observations.push({request:args,result:observation});
 }
}
