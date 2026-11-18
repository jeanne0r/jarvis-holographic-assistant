// Real spoken-audio benchmark; same ephemeral connection, VAD and tools as UI.
// Synthetic microphone audio stays in RAM. No device control or memory writes.
import {readFileSync,writeFileSync} from 'node:fs';
import vm from 'node:vm';
import WebSocket from '/home/user/gateway/node_modules/ws/wrapper.mjs';
import {speechSession,streamSpeech} from './speech.mjs';
import {usage} from './usage.mjs';
for(const path of ['/home/user/gateway/.env','/home/user/workspace/_secrets/.env']){
 try{for(const line of readFileSync(path,'utf8').split('\n')){const m=line.match(/^(GEMINI_API_KEY|GOOGLE_API_KEY)=(.*)$/);if(m)process.env[m[1]]=m[2].replace(/^['"]|['"]$/g,'');}}catch{}
}
vm.runInThisContext(readFileSync(new URL('./public/voice-gate.js',import.meta.url),'utf8'));
const base='http://127.0.0.1:8787';
const post=async(path,data)=>{const r=await fetch(base+'/api/jarvis/'+path,{method:'POST',headers:{origin:base,'content-type':'application/json'},body:JSON.stringify(data)});const v=await r.json();if(!r.ok)throw Error(v.error||`HTTP ${r.status}`);return v;};
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const now=()=>performance.now();
async function spoken(text){
 const s=speechSession('user'),chunks=[];await streamSpeech(s.sessionId,'user',text,chunk=>chunks.push(chunk));
 const raw=Buffer.concat(chunks),n=raw.length/2,source=new Int16Array(n);for(let i=0;i<n;i++)source[i]=raw.readInt16LE(i*2);
 let end=n;while(end>0&&Math.abs(source[end-1])<115)end--;
 let begin=0;while(begin<end&&Math.abs(source[begin])<115)begin++;begin=Math.max(0,begin-2400);end=Math.min(n,end+480);
 const out=new Int16Array(Math.ceil((end-begin)*16000/24000));for(let i=0;i<out.length;i++){const x=begin+i*1.5,j=Math.floor(x),f=x-j;out[i]=Math.round(source[j]*(1-f)+(source[Math.min(j+1,n-1)]||0)*f);}
 return out;
}
async function benchmark(label,audio,repeat){
 const opened=now();const session=await post('live/session?space=user',{});
 const result={label,repeat,sessionId:session.usageSessionId,tools:[],inputDurationMs:Math.round(audio.length/16),usageReports:0};
 let ws,readyAt=0,speechEndedAt=0,firstAudio=0,firstAudible=0,firstTranscript=0,finished=false,gotAnswer=false,reports=Promise.resolve(),ttsSamples=0;
 return await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>finish(Error('Benchmark timeout')),45000);
  const send=data=>{if(!finished&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(data));};
  async function finish(error){if(finished)return;finished=true;clearTimeout(timer);ws.close();try{await reports;if(!result.usageReports)await usage('report',{sessionId:session.usageSessionId,sequence:1,usage:{},incomplete:true});}catch{}
   result.readyMs=Math.round(readyAt-opened);result.firstAudioMs=firstAudio&&speechEndedAt?Math.round(firstAudio-speechEndedAt):null;result.firstAudibleMs=firstAudible&&speechEndedAt?Math.round(firstAudible-speechEndedAt):null;result.firstTranscriptMs=firstTranscript&&speechEndedAt?Math.round(firstTranscript-speechEndedAt):null;result.completeMs=speechEndedAt?Math.round(now()-speechEndedAt):null;result.generatedAudioMs=Math.round(ttsSamples/24);
   if(error){result.error=error.message;}console.log(JSON.stringify(result));resolve(result);
  }
  ws=new WebSocket(session.websocketUrl+'?access_token='+encodeURIComponent(session.token));
  ws.on('open',()=>send({setup:session.setup}));
  ws.on('error',()=>finish(Error('WebSocket failed')));
  ws.on('close',()=>{if(!finished)finish(Error('Closed before reply'));});
  ws.on('message',raw=>{
   let d;try{d=JSON.parse(raw);}catch{return;}
   if(d.usageMetadata){const seq=++result.usageReports;reports=reports.then(()=>usage('report',{sessionId:session.usageSessionId,sequence:seq,usage:d.usageMetadata}));reports.catch(()=>{});}
   if(d.error){finish(Error('Google error'));return;}
   if(d.setupComplete){readyAt=now();void feed();}
   if(d.toolCall){for(const call of d.toolCall.functionCalls||[])void(async()=>{
    const start=now();let response;
    if(!['consulter_home_assistant','chercher_souvenirs'].includes(call.name)){response={error:'Benchmark : consultations uniquement.'};}
    else try{response=await post('live/tool',{sessionId:session.usageSessionId,callId:call.id,name:call.name,args:call.args});}catch{response={error:'Consultation indisponible.'};}
    result.tools.push({name:call.name,durationMs:Math.round(now()-start)});
    send({toolResponse:{functionResponses:[{id:call.id,name:call.name,response}]}});
   })();}
   const content=d.serverContent;if(!content)return;
   if(content.outputTranscription?.text){gotAnswer=true;if(!firstTranscript)firstTranscript=now();}
   for(const part of content.modelTurn?.parts||[]){const inline=part.inlineData;if(!inline?.mimeType?.startsWith('audio/pcm')||!inline.data)continue;const bytes=Buffer.from(inline.data,'base64');if(bytes.length&&!firstAudio)firstAudio=now();ttsSamples+=bytes.length/2;
    if(!firstAudible){for(let i=0;i+1<bytes.length;i+=2)if(Math.abs(bytes.readInt16LE(i))>=20){firstAudible=now();break;}}
   }
   if(content.turnComplete&&gotAnswer)void finish();
  });
  async function feed(){
   const gate=new JarvisVoiceGate({audio:buffer=>send({realtimeInput:{audio:{mimeType:'audio/pcm;rate=16000',data:Buffer.from(buffer).toString('base64')}}}),end:()=>send({realtimeInput:{audioStreamEnd:true}})});
   const start=now();let finalVoiceOffset=0;
   for(let i=0;i<audio.length;i++)if(Math.abs(audio[i])>=115)finalVoiceOffset=i/16;
   speechEndedAt=start+finalVoiceOffset;
   for(let offset=0;offset<audio.length+16000&&!finished;offset+=320){const frame=new Int16Array(320);if(offset<audio.length)frame.set(audio.subarray(offset,offset+320));gate.push(frame.buffer);const due=start+(offset+320)/16;await sleep(Math.max(0,due-now()));}
  }
 });
}
const cases=[['simple','Est-ce que tu m’entends ?'],['home-assistant','Quelle est la température du frigo de la cuisine ?']];
const inputs=[];for(const [label,text]of cases){console.log(JSON.stringify({preparing:label}));inputs.push([label,await spoken(text)]);}
const results=[];for(let repeat=1;repeat<=2;repeat++)for(const[label,audio]of inputs)results.push(await benchmark(label,audio,repeat));
writeFileSync(new URL('./data/benchmark-live-latest.json',import.meta.url),JSON.stringify({at:new Date().toISOString(),model:'gemini-3.8-live',method:'Real-time 16kHz synthetic spoken input through deployed local VAD and ephemeral Google Live API; current HA tools; cold sessions; no physical browser/speaker timing.',results},null,2)+'\n',{mode:0o600});
if(results.some(r=>r.error))process.exitCode=1;
