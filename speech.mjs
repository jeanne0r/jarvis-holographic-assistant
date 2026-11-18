// Speech transport only. No conversation history, tools or answer generation.
import {randomUUID} from 'node:crypto';
import {usage} from './usage.mjs';
import {JARVIS_VOICE,JARVIS_DELIVERY} from './persona.mjs';
import {coreInfo} from './core-settings.mjs';
import {sseEvents} from './sse.mjs';
export const TRANSCRIBE_MODEL='gemini-3.5-transcribe';
export const SPEAK_MODEL='gemini-3.8-flash-lite-tts';
const sessions=new Map();
const key=()=>process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY;
const fail=(status,message)=>Object.assign(Error(message),{status});
export function speechStatus(){return {configured:Boolean(key()),...coreInfo(),speechOnly:true,transcriptionModel:TRANSCRIBE_MODEL,synthesisModel:SPEAK_MODEL,memoryAccess:true,voice:JARVIS_VOICE,maxSeconds:3600};}
export function speechSession(space){
 if(!key())throw fail(503,'La clé Gemini du serveur est nécessaire pour la voix.');
 for(const [id,s] of sessions)if(s.expires<Date.now())sessions.delete(id);
 if(sessions.size>=100)throw fail(429,'Trop de sessions vocales ouvertes. Réessaie dans un instant.');
 const session={id:randomUUID(),space,expires:Date.now()+3600000,inflight:0};sessions.set(session.id,session);
 return {...speechStatus(),sessionId:session.id};
}
function sessionFor(id,space){const s=sessions.get(id);if(!s||s.space!==space||s.expires<Date.now())throw fail(403,'Session vocale expirée. Rouvre le micro.');return s;}
export function validateSpeechWave(buffer){
 // Only the canonical mono PCM16 / 16kHz WAV produced by our microphone worklet.
 if(!Buffer.isBuffer(buffer)||buffer.length<6444||buffer.length>1920044||buffer.toString('ascii',0,4)!=='RIFF'||buffer.readUInt32LE(4)!==buffer.length-8||buffer.toString('ascii',8,16)!=='WAVEfmt '||buffer.readUInt32LE(16)!==16||buffer.readUInt16LE(20)!==1||buffer.readUInt16LE(22)!==1||buffer.readUInt32LE(24)!==16000||buffer.readUInt32LE(28)!==32000||buffer.readUInt16LE(32)!==2||buffer.readUInt16LE(34)!==16||buffer.toString('ascii',36,40)!=='data'||buffer.readUInt32LE(40)!==buffer.length-44||(buffer.length-44)%2)throw fail(400,'Audio invalide. Reprends ta phrase.');
 return buffer;
}
async function interaction(model,payload,{fetchImpl=fetch,meter=usage}={}){
 const sessionId=randomUUID();await meter('session',{id:sessionId,model});
 let report;
 try{
  const response=await fetchImpl('https://generativelanguage.googleapis.com/v1beta/interactions',{method:'POST',headers:{'content-type':'application/json','x-goog-api-key':key()},body:JSON.stringify({model,...payload,store:false}),signal:AbortSignal.timeout(45000)});
  if(!response.ok)throw fail(503,response.status===429?'La voix Google est momentanément occupée. Réessaie dans un instant.':'Le service vocal Google est indisponible.');
  const chunks=[];let size=0;
  for await(const chunk of response.body){size+=chunk.length;if(size>10*1024*1024)throw fail(502,'Réponse audio trop volumineuse.');chunks.push(chunk);}
  const data=JSON.parse(Buffer.concat(chunks).toString());
  const u=data.usage;
  if(u&&Number.isInteger(u.total_input_tokens)&&Number.isInteger(u.total_output_tokens))report={promptTokenCount:u.total_input_tokens,responseTokenCount:u.total_output_tokens,promptTokensDetails:[{modality:model===TRANSCRIBE_MODEL?'AUDIO':'TEXT',tokenCount:u.total_input_tokens}],responseTokensDetails:[{modality:model===TRANSCRIBE_MODEL?'TEXT':'AUDIO',tokenCount:u.total_output_tokens}],thoughtsTokenCount:u.total_thought_tokens||0};
  return data;
 }catch(error){if(error.status)throw error;throw fail(503,'Le service vocal Google est indisponible.');}
 finally{
  // Finish metering even if the browser interrupted playback/disconnected.
  await meter('report',{sessionId,sequence:1,usage:report||{},incomplete:!report}).catch(()=>{});
 }
}
async function run(id,space,operation){const s=sessionFor(id,space);if(s.inflight>=2)throw fail(429,'Une phrase est encore en cours de traitement.');s.inflight++;try{return await operation();}finally{s.inflight--;}}
export async function transcribeSpeech(id,space,buffer,dependencies){
 validateSpeechWave(buffer);
 return run(id,space,async()=>{
  const data=await interaction(TRANSCRIBE_MODEL,{input:[{type:'audio',mime_type:'audio/wav',data:buffer.toString('base64')}],generation_config:{transcription_config:{language_codes:['fr-FR'],custom_vocabulary:['Jarvis','Home Assistant','Qdrant'],mode:{type:'verbatim'}}}},dependencies);
  const text=(data.steps||[]).filter(s=>s.type==='model_output').flatMap(s=>s.content||[]).filter(c=>c.type==='text').map(c=>c.text||'').join(' ').trim();
  if(text.length>2000)throw fail(400,'Ta phrase est trop longue. Peux-tu la raccourcir ?');
  return {text,engine:coreInfo().engine};
 });
}
export async function speakSpeech(id,space,text,dependencies){
 if(typeof text!=='string'||!text.trim()||text.length>4000)throw fail(400,'Texte vocal invalide.');
 return run(id,space,async()=>{
  const data=await interaction(SPEAK_MODEL,{input:[{type:'user_input',content:[{type:'text',text,annotations:[{type:'speech_metadata',style:JARVIS_DELIVERY+' Français.'}]}]}],response_format:{type:'audio'},generation_config:{speech_config:[{voice:JARVIS_VOICE}]}},dependencies);
  const parts=(data.steps||[]).filter(s=>s.type==='model_output').flatMap(s=>s.content||[]).filter(c=>c.type==='audio');
  const audio=parts.at(-1);
  if(!audio?.data||audio.mime_type!=='audio/wav')throw fail(502,'La lecture vocale est indisponible ; la réponse reste affichée.');
  return Buffer.from(audio.data,'base64');
 });
}
export async function streamSpeech(id,space,text,onAudio,dependencies={}){
 if(typeof text!=='string'||!text.trim()||text.length>4000)throw fail(400,'Texte vocal invalide.');
 return run(id,space,async()=>{
  const meter=dependencies.meter||usage,fetchImpl=dependencies.fetchImpl||fetch,sessionId=randomUUID();
  const controller=new AbortController(),abort=()=>controller.abort();dependencies.signal?.addEventListener('abort',abort,{once:true});if(dependencies.signal?.aborted)abort();const timer=setTimeout(abort,45000);
  await meter('session',{id:sessionId,model:SPEAK_MODEL});let report,bytes=0;
  try{
   const response=await fetchImpl('https://generativelanguage.googleapis.com/v1beta/interactions',{method:'POST',headers:{'content-type':'application/json','x-goog-api-key':key()},signal:controller.signal,body:JSON.stringify({model:SPEAK_MODEL,input:[{type:'user_input',content:[{type:'text',text,annotations:[{type:'speech_metadata',style:JARVIS_DELIVERY+' Français.'}]}]}],response_format:{type:'audio',mime_type:'audio/l16',sample_rate:24000},generation_config:{speech_config:[{voice:JARVIS_VOICE}]},stream:true,store:false})});
   if(!response.ok)throw fail(503,'Lecture vocale momentanément indisponible.');
   for await(const event of sseEvents(response.body)){
    if(event.event_type==='step.delta'&&event.delta?.type==='audio'&&event.delta.data){
     const audio=Buffer.from(event.delta.data,'base64');bytes+=audio.length;if(bytes>10*1024*1024)throw fail(502,'Réponse vocale trop longue.');onAudio(audio);
    }
    if(event.event_type==='interaction.completed'){
     const u=event.interaction?.usage;
     if(u&&Number.isInteger(u.total_input_tokens)&&Number.isInteger(u.total_output_tokens))report={promptTokenCount:u.total_input_tokens,responseTokenCount:u.total_output_tokens,promptTokensDetails:[{modality:'TEXT',tokenCount:u.total_input_tokens}],responseTokensDetails:[{modality:'AUDIO',tokenCount:u.total_output_tokens}],thoughtsTokenCount:u.total_thought_tokens||0};
    }
    if(event.event_type==='error'||event.error)throw fail(503,'La lecture vocale a été interrompue.');
   }
   if(!bytes)throw fail(502,'Aucun son reçu pour cette réponse.');
  }finally{clearTimeout(timer);dependencies.signal?.removeEventListener('abort',abort);await meter('report',{sessionId,sequence:1,usage:report||{},incomplete:!report}).catch(()=>{});}
 });
}
