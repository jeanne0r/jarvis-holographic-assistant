// One shared text engine for both channels. Audio never enters this context.
import {randomUUID} from 'node:crypto';
import {createJarvisTools} from './tools-server.mjs';
import {ANSWER_SCHEMA,CORE_INSTRUCTIONS} from './core-instructions.mjs';
import {usage} from './usage.mjs';
export const FAST_MODEL=process.env.JARVIS_GEMINI_TEXT_MODEL||'gemini-3.5-flash-lite';
const fail=message=>Error(message);
export async function fastAnswer(question,sources,context={},signal,dependencies={}){
 const fetchImpl=dependencies.fetch||fetch,meter=dependencies.meter||usage;
 const bridge=await (dependencies.tools||createJarvisTools)(context.space||'member1');
 const id=randomUUID();await meter('session',{id,model:FAST_MODEL});
 const schema={...ANSWER_SCHEMA,properties:{...ANSWER_SCHEMA.properties,toolCalls:{type:'array',items:{type:'object',properties:{name:{type:'string',enum:bridge.tools.map(t=>t.name)},arguments_json:{type:'string'}},required:['name','arguments_json'],additionalProperties:false}}},required:[...ANSWER_SCHEMA.required,'toolCalls']};
 const observations=[],effects=[];
 const excerpts=sources.slice(0,3).map(source=>({...source,body:typeof source.body==='string'?source.body.slice(0,1200):'',title:source.title?.slice(0,160)}));
 const compactContext={...context,history:Array.isArray(context.history)?context.history.slice(-12).map(message=>({...message,text:message.text.slice(0,1500)})):[]};
 const instruction=(dependencies.instruction||CORE_INSTRUCTIONS)+' Utilise le protocole JSON toolCalls pour demander les outils : name et arguments_json contenant un objet JSON conforme au schéma de l’outil. Ne prétends jamais avoir le résultat avant de recevoir observations. Aucun outil nécessaire : toolCalls vide. Pendant une consultation : answer vide et action none. Tu peux regrouper les consultations indépendantes ; ne pilote pas une cible avant d’avoir lu les résultats de sa consultation et des commandes disponibles. Si toolCallsAllowed=false, réponds avec les observations acquises ou demande une précision. Un échec de commande ne justifie jamais une répétition.';
 for(let step=0;step<6;step++){
  signal?.throwIfAborted();
  let metadata;
  try{
   const controller=new AbortController(),abort=()=>controller.abort();
   signal?.addEventListener('abort',abort,{once:true});const timeout=setTimeout(abort,20000);
   let data;
   try{
    const response=await fetchImpl(`https://generativelanguage.googleapis.com/v1beta/models/${FAST_MODEL}:generateContent`,{method:'POST',headers:{'content-type':'application/json','x-goog-api-key':process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY},body:JSON.stringify({systemInstruction:{parts:[{text:instruction}]},contents:[{role:'user',parts:[{text:JSON.stringify({question,sources:excerpts,context:compactContext,availableTools:bridge.tools,observations,toolCallsAllowed:step<5})}]}],generationConfig:{responseMimeType:'application/json',responseJsonSchema:schema,thinkingConfig:{thinkingLevel:'MINIMAL'},maxOutputTokens:2048}}),signal:controller.signal});
    if(!response.ok)throw fail('Le moteur Jarvis est momentanément indisponible.');
    const raw=await response.text();if(raw.length>1000000)throw fail('Réponse Jarvis trop volumineuse.');data=JSON.parse(raw);
   }finally{clearTimeout(timeout);signal?.removeEventListener('abort',abort);}
   const u=data.usageMetadata;
   if(u&&Number.isInteger(u.promptTokenCount)&&Number.isInteger(u.candidatesTokenCount))metadata={promptTokenCount:u.promptTokenCount,responseTokenCount:u.candidatesTokenCount,promptTokensDetails:[{modality:'TEXT',tokenCount:u.promptTokenCount}],responseTokensDetails:[{modality:'TEXT',tokenCount:u.candidatesTokenCount}],thoughtsTokenCount:u.thoughtsTokenCount||0};
   signal?.throwIfAborted();
   const text=data.candidates?.[0]?.content?.parts?.filter(p=>p.text&&!p.thought).map(p=>p.text).join('');
   let result;try{result=JSON.parse(text);}catch{throw fail('Jarvis n’a pas pu terminer sa réponse.');}
   if(typeof result.answer!=='string'||!Array.isArray(result.sourceIds)||!Array.isArray(result.toolCalls)||result.toolCalls.length>5)throw fail('Réponse Jarvis invalide.');
   if(!result.toolCalls.length){result.sourceIds=result.sourceIds.filter(sourceId=>sources.some(s=>s.id===sourceId));delete result.toolCalls;if(effects.length)result.effects=effects;return result;}
   if(step===5)throw fail('La demande nécessite une précision. Peux-tu nommer l’appareil exact ?');
   const handoff=await dependencies.preflight?.(result.toolCalls);if(handoff)return handoff;
   for(let index=0;index<result.toolCalls.length;index++){
    signal?.throwIfAborted();const call=result.toolCalls[index];let output;
    try{const args=JSON.parse(call.arguments_json);output=await bridge.call(call.name,args,`${step}:${index}`);}catch{output={error:'Consultation ou commande refusée/inaboutie. Pour une commande, résultat inconnu : ne pas répéter.'};}
    if(output?.clientAction)effects.push(output.clientAction);
    observations.push({name:call.name,arguments_json:call.arguments_json,result:output});
   }
  }finally{await meter('report',{sessionId:id,sequence:step+1,usage:metadata||{},incomplete:!metadata}).catch(()=>{});}
 }
 throw fail('Jarvis n’a pas pu terminer sa réponse.');
}
