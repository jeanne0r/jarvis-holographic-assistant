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
