import assert from 'node:assert/strict';
import {fastAnswer} from './fast-brain.mjs';
const action={type:'none',target:'',title:'',text:''};
const outputs=[{answer:'',sourceIds:[],action,toolCalls:[{name:'consulter_home_assistant',arguments_json:'{"query":"total_w"}'}]},{answer:'La maison consomme 987 W.',sourceIds:['invented','actual'],action,toolCalls:[]}];
let calls=0,reads=0;const bills=[];
const dependencies={meter:async(a,d)=>bills.push({a,d}),tools:async space=>{assert.equal(space,'member1');return {tools:[{name:'consulter_home_assistant',inputSchema:{type:'object'}}],call:async(name,args)=>{reads++;assert.equal(args.query,'total_w');return {states:[{state:'987',unit:'W'}]};}};},fetch:async(url,options)=>{
 const body=JSON.parse(options.body),input=JSON.parse(body.contents[0].parts[0].text);assert.equal(body.generationConfig.thinkingConfig.thinkingLevel,'MINIMAL');assert(!('audio' in input));assert.equal(input.context.history[0].text,'Quel capteur ?');
 if(calls)assert.equal(input.observations[0].result.states[0].state,'987');
 return new Response(JSON.stringify({usageMetadata:{promptTokenCount:1000,candidatesTokenCount:50},candidates:[{content:{parts:[{text:JSON.stringify(outputs[calls++])}]}}]}));
}};
const result=await fastAnswer('C’est ça !',[{id:'actual'}],{space:'member1',history:[{role:'assistant',text:'Quel capteur ?'}]},undefined,dependencies);
assert.equal(reads,1);assert.equal(calls,2);assert.deepEqual(result.sourceIds,['actual']);assert(!('toolCalls' in result));assert.equal(bills.filter(b=>b.a==='report').length,2);assert(bills.filter(b=>b.a==='report').every(b=>b.d.usage.promptTokensDetails[0].modality==='TEXT'));
const controller=new AbortController();controller.abort();await assert.rejects(fastAnswer('test',[],{space:'member1'},controller.signal,dependencies),e=>e.name==='AbortError');assert.equal(reads,1);
console.log('PASS: one shared fast engine, scoped tool loop, fresh HA observations, common history, filtered source IDs, per-round text metering and cancellation.');
// Opening content must not finish at an intermediate search-result window.
let step=0;const displayActions=[];
const openOutputs=[
 {answer:'',sourceIds:[],action,toolCalls:[{name:'web_jarvis',arguments_json:'{"action":"rechercher","query":"chaîne télévision en direct officiel"}'}]},
 {answer:'Voici des résultats.',sourceIds:[],action,toolCalls:[]},
 {answer:'',sourceIds:[],action,toolCalls:[{name:'web_jarvis',arguments_json:'{"action":"ouvrir","url":"https://diffuseur.example.org/direct"}'}]},
 {answer:'La page officielle est ouverte.',sourceIds:[],action,toolCalls:[]}
];
const display=await fastAnswer('Affiche le direct dans une fenêtre',[],{space:'member1',displayRequested:true},undefined,{
 meter:async()=>{},tools:async()=>({tools:[{name:'web_jarvis',inputSchema:{type:'object'}}],call:async(name,args)=>{displayActions.push(args.action);return {clientAction:{type:'web',kind:args.action==='ouvrir'?'site':'search',url:args.url}}}}),
 fetch:async(url,options)=>{if(step===2){const input=JSON.parse(JSON.parse(options.body).contents[0].parts[0].text);assert(input.observations.some(o=>o.name==='verification_execution'&&o.result.incomplete));}return new Response(JSON.stringify({candidates:[{content:{parts:[{text:JSON.stringify(openOutputs[step++])}]}}]}));}
});
assert.deepEqual(displayActions,['rechercher','ouvrir']);assert.equal(display.effects.at(-1).kind,'site');assert.equal(step,4);
console.log('PASS: requested content opening continues beyond intermediate search results.');
let googleStep=0;const google=await fastAnswer('Ouvre une recherche Google',[],{space:'member1',displayRequested:true},undefined,{meter:async()=>{},tools:async()=>({tools:[{name:'web_jarvis',inputSchema:{type:'object'}}],call:async()=>({clientAction:{type:'web',kind:'search',openResults:true,googleUrl:'https://www.google.com/search?q=test'}})}),fetch:async()=>new Response(JSON.stringify({candidates:[{content:{parts:[{text:JSON.stringify(googleStep++?{answer:'Résultats Google.',sourceIds:[],action,toolCalls:[]}:{answer:'',sourceIds:[],action,toolCalls:[{name:'web_jarvis',arguments_json:'{"action":"rechercher","query":"test","open_results":true}'}]})}]}}]}))});assert.equal(googleStep,2);assert.equal(google.effects.length,1);
console.log('PASS: requested Google results do not force an unrelated site opening.');
