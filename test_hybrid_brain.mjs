import assert from 'node:assert/strict';
import {classifyRoute,hybridAnswer,needsLocalTool} from './hybrid-brain.mjs';
import {travel} from './capabilities.mjs';
const none={type:'none',target:'',title:'',text:''};
const answer=()=>({answer:'Réponse française.',speech:'Réponse française.',sourceIds:[],action:none,userCorrections:[],resolvedEntities:[]});
for(const channel of ['written','voice']){
 let codex=0,gemini=0;
 const deps={memoryStore:async()=>[],classify:async()=> 'gemini',codex:async()=>{codex++;return answer()},gemini:async(q,s,c,signal,d)=>{
  gemini++;assert.equal(c.channel,channel);assert(d.instruction.includes('moteur Gemini'));return answer();
 }};
 const result=await hybridAnswer('Trouve une radio jazz',[],{space:'user',channel},undefined,deps);
 assert.equal(result.execution.engine,'gemini');assert.equal(codex,0);assert.equal(gemini,1);
 const local=await hybridAnswer('Et la cave ?',[],{space:'user',channel,history:[{role:'user',text:'Température du salon ?'}]},undefined,{...deps,classify:async(q,c)=>{assert.equal(c.history[0].text,'Température du salon ?');return 'codex'}});
 assert.equal(local.execution.engine,'codex');assert.equal(codex,1);assert.equal(gemini,1);
}
for(const call of [
 {name:'confier_au_codex_local',args:{}},
 {name:'medias_jarvis',args:{action:'radio',target:'media_player.homepod'}},
 {name:'medias_jarvis',args:{action:'catalogue'}},
 {name:'trajet_jarvis',args:{destination:'travail'}},
 {name:'consulter_home_assistant',args:{query:'cave'}},
 {name:'web_jarvis',args:{action:'ouvrir',url:'https://192.0.2.16:8788/miroir/'}},
])assert(needsLocalTool({...call,arguments_json:JSON.stringify(call.args)}));
assert(!needsLocalTool({name:'medias_jarvis',arguments_json:'{"action":"radio","query":"jazz","target":"ici"}'}));
assert(!needsLocalTool({name:'trajet_jarvis',arguments_json:'{"origin":"Lausanne","destination":"Genève"}'}));
let nativeCalls=0,local=0;
const base={classify:async()=> 'gemini',memoryStore:async()=>[],meter:async()=>{},tools:async()=>({tools:[{name:'medias_jarvis',inputSchema:{type:'object'}},{name:'piloter_home_assistant',inputSchema:{type:'object'}}],call:async()=>{nativeCalls++;return {}}}),codex:async(q,s,c)=>{local++;assert.equal(q,'Mets du jazz sur mon HomePod');return answer()},fetch:async()=>new Response(JSON.stringify({usageMetadata:{promptTokenCount:100,candidatesTokenCount:20},candidates:[{content:{parts:[{text:JSON.stringify({...answer(),toolCalls:[{name:'medias_jarvis',arguments_json:'{"action":"radio","target":"ici"}'},{name:'medias_jarvis',arguments_json:'{"action":"radio","target":"media_player.homepod"}'}]})}]}}]}))};
const forwarded=await hybridAnswer('Mets du jazz sur mon HomePod',[],{space:'user'},undefined,base);
assert.equal(local,1);assert.equal(nativeCalls,0,'preflight must inspect full batch before effects');assert.equal(forwarded.execution.engine,'codex');
const controller=new AbortController();controller.abort();await assert.rejects(classifyRoute('question',{},controller.signal,base),e=>e.name==='AbortError');
let reports=0;
assert.equal(await classifyRoute('Radio jazz',{},undefined,{meter:async a=>{if(a==='report')reports++},fetch:async(url,opts)=>{const input=JSON.parse(opts.body);assert.equal(input.generationConfig.responseJsonSchema.properties.route.enum.length,3);return new Response(JSON.stringify({candidates:[{content:{parts:[{text:'{"route":"gemini"}'}]}}]}))}}),'gemini');assert.equal(reports,1);
await assert.rejects(classifyRoute('Radio jazz',{},undefined,{meter:async()=>{},fetch:async()=>new Response('{}',{status:503})}),/aiguillage/);
const publicRoute=await travel({origin:'Lausanne',destination:'Genève'},{space:'user'},{states:()=>{throw Error('Public routes must not read HA')}});assert.equal(publicRoute.clientAction.type,'travel');
console.log('PASS hybrid: both channels, public bypass, contextual local delegation, whole-batch guard before effects, public travel without HA, metering, cancellation and no silent fallback.');
// 18.11 route 3: an analysis of the measurement history is handed to Hermes by the browser.
// No Codex, Gemini or tool call, and the question is passed through unchanged.
{
 let calls=0;
 const r=await hybridAnswer('Devrais-je recalibrer le dosage du VSV d’après l’historique ?',[],{space:'user',channel:'voice'},undefined,
  {classify:async()=>({route:'hermes',displayRequested:false}),codex:async()=>{calls++},gemini:async()=>{calls++},memoryStore:async()=>{calls++;return []},tools:async()=>{calls++}});
 assert.equal(calls,0);assert.equal(r.execution.engine,'hermes-handoff');assert.deepEqual(r.sourceIds,[]);assert.equal(r.action,null);
 assert.equal(r.hermes.question,'Devrais-je recalibrer le dosage du VSV d’après l’historique ?');assert.match(r.answer,/Hermes/);
 assert.equal(await classifyRoute('q',{},undefined,{meter:async()=>{},fetch:async()=>new Response(JSON.stringify({candidates:[{content:{parts:[{text:'{"route":"hermes","displayRequested":false}'}]}}]}))}),'hermes');
 await assert.rejects(classifyRoute('q',{},undefined,{meter:async()=>{},fetch:async()=>new Response(JSON.stringify({candidates:[{content:{parts:[{text:'{"route":"shell","displayRequested":false}'}]}}]}))}));
}
console.log('hybrid brain: ok');
