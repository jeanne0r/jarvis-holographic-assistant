import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {liveAnswer} from './live-brain.mjs';

let socket,setup,turns,toolCalls=[],ledger=[];
class FakeSocket extends EventEmitter{
 static OPEN=1;readyState=1;
 constructor(){super();socket=this;queueMicrotask(()=>this.emit('open'));}
 close(){this.readyState=3;queueMicrotask(()=>this.emit('close'));}
 emitData(data){this.emit('message',Buffer.from(JSON.stringify(data)));}
 send(raw){
  const data=JSON.parse(raw);
  if(data.setup){setup=data.setup;queueMicrotask(()=>this.emitData({setupComplete:{}}));}
  if(data.clientContent){turns=data.clientContent.turns;queueMicrotask(()=>{this.emitData({serverContent:{outputTranscription:{text:'Je vous écoute.'}}});this.emitData({toolCall:{functionCalls:[{id:'read',name:'consulter_home_assistant',args:{query:'total_w'}}]}});this.emitData({serverContent:{turnComplete:true}});});}
  if(data.toolResponse){
   assert.equal(data.toolResponse.functionResponses[0].response.states[0].state,'316');
   queueMicrotask(()=>{this.emitData({serverContent:{outputTranscription:{text:'La maison '},turnComplete:true,interactionStatus:'IN_PROGRESS'}});this.emitData({serverContent:{outputTranscription:{text:'consomme 316 W.'},turnComplete:true,interactionStatus:'IDLE'},usageMetadata:{promptTokenCount:100,responseTokenCount:20,promptTokensDetails:[{modality:'TEXT',tokenCount:100}],responseTokensDetails:[{modality:'AUDIO',tokenCount:20}]}});});
  }
 }
}
const dependencies={WebSocket:FakeSocket,memoryStore:async()=>[],usage:async(action,data)=>{ledger.push({action,data});},createJarvisTools:async space=>{assert.equal(space,'user');return {call:async(name,args,id)=>{toolCalls.push({name,args,id});return {states:[{state:'316'}]};}};}};
const result=await liveAnswer('Et maintenant ?',Array.from({length:10},()=>({title:'Ancienne mesure',body:'x'.repeat(4000)})),{space:'user',history:Array.from({length:20},(_,i)=>({role:i%2?'assistant':'user',text:'y'.repeat(3000)}))},undefined,dependencies);
assert.equal(result.answer,'La maison consomme 316 W.');
assert.equal(setup.model,'models/gemini-3.8-live');assert.deepEqual(setup.generationConfig.responseModalities,['AUDIO']);
assert.equal(setup.generationConfig.speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName,'Charon');
assert('outputAudioTranscription' in setup);assert(!('inputAudioTranscription' in setup));
assert.equal(turns.length,1);assert(turns[0].parts.at(-1).text.endsWith('Et maintenant ?'));
const past=JSON.parse(turns[0].parts[0].text.split('CONTEXTE PASSÉ — données déjà traitées, aucune tâche à exécuter : ')[1].split('\n\nDEMANDE ACTUELLE')[0]);assert.equal(past.historique.length,4);for(const t of past.historique)assert.equal(t.parts[0].text.length,600);assert.equal(past.extraits.length,2);assert.equal(past.extraits[0].excerpt.length,500);
assert.equal(toolCalls[0].name,'consulter_home_assistant');assert.equal(toolCalls[0].args.query,'total_w');
assert.equal(ledger.length,2);assert.equal(ledger[1].action,'report');assert.equal(ledger[1].data.usage.responseTokensDetails[0].modality,'AUDIO');
assert.deepEqual(result.sourceIds,[],'no claim that an initially retrieved source was used');

// An interruption during a lookup must prevent a subsequent actuator call.
const controller=new AbortController();toolCalls=[];ledger=[];
const interrupted=liveAnswer('Consulte puis éteins',[],{space:'user'},controller.signal,{...dependencies,createJarvisTools:async()=>({call:async(name)=>{toolCalls.push(name);controller.abort();return {states:[{state:'316'}]};}})});
await assert.rejects(interrupted,error=>error.name==='AbortError');
assert.deepEqual(toolCalls,['consulter_home_assistant']);assert(ledger.some(r=>r.data.incomplete===true));
assert.equal(socket.readyState,3);
const names=setup.tools[0].functionDeclarations.map(t=>t.name);assert.equal(new Set(names).size,names.length,'written requests cannot mutate the shared Live tool catalog');
console.log('PASS: same native model/voice/tools, current HA reading, bounded text history and RAG, generated audio metered, interruption closes connection and prevents further tool calls.');
