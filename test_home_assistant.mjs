import assert from 'node:assert/strict';
import {consultHomeAssistant,listHomeAssistantServices,controlHomeAssistant} from './home-assistant.mjs';
// No HA connection or device commands: all network requests are mocked.
process.env.HOME_ASSISTANT_URL='not-a-real-url';process.env.HOME_ASSISTANT_TOKEN='never-returned';
const session={entities:new Set(),services:new Map()};let posts=0,failPost=false;
const states=[{entity_id:'light.tv',state:'on',attributes:{friendly_name:'Lumière TV salon',brightness:66,secret:'private'}},{entity_id:'light.group',state:'on',attributes:{entity_id:['light.tv']}},{entity_id:'sensor.temp',state:'unavailable',attributes:{friendly_name:'Température cuisine'}},{entity_id:'person.test',state:'home',attributes:{latitude:123}}];
// An unused local port makes area lookup fail immediately; no real HA endpoint.
process.env.HOME_ASSISTANT_URL='http://127.0.0.1:1';
globalThis.fetch=async(url,options)=>{
 if(options.method==='POST'){posts++;if(failPost)throw Error('private');assert.equal(url.pathname,'/api/services/light/turn_on');assert.deepEqual(JSON.parse(options.body),{brightness_pct:40,entity_id:['light.tv']});return {ok:true,json:async()=>[]};}
 if(url.pathname==='/api/services')return {ok:true,json:async()=>[{domain:'light',services:{turn_on:{fields:{brightness_pct:{selector:{number:{min:0,max:100}}},extras:{fields:{color_name:{selector:{text:{}}}}}}},reload:{fields:{}}}},{domain:'homeassistant',services:{restart:{}}}]};
 return {ok:true,json:async()=>states};
};
const overview=await consultHomeAssistant({query:''},session);assert.equal(overview.domains.person,1);
const r=await consultHomeAssistant({query:'tv',domain:'light'},session);assert.equal(r.states[0].brightness_pct,26);assert(!JSON.stringify(r).includes('private'));assert(!JSON.stringify(r).includes('never-returned'));
assert.equal((await consultHomeAssistant({query:'temperature'})).states[0].state,'unavailable');
assert.equal((await consultHomeAssistant({query:'',domain:'light',area:'salon'})).states,undefined);
await assert.rejects(consultHomeAssistant({query:'',offset:-1}));
await assert.rejects(controlHomeAssistant({domain:'light',service:'turn_on',entity_ids:['light.tv']},session));
const catalog=await listHomeAssistantServices({domain:'light'},session);assert.deepEqual(catalog.services.map(s=>s.service),['turn_on']);assert('color_name' in catalog.services[0].fields);
for(const args of [
 {domain:'homeassistant',service:'restart',entity_ids:['light.tv']},
 {domain:'light',service:'turn_on',entity_ids:['light.unknown']},
 {domain:'light',service:'turn_on',entity_ids:['all']},
 {domain:'light',service:'turn_on',entity_ids:['light.tv'],data_json:'{"entity_id":"all"}'},
 {domain:'light',service:'turn_on',entity_ids:['light.tv'],data_json:'{"area_id":"salon"}'},
 {domain:'light',service:'turn_on',entity_ids:['light.tv'],data_json:'{"arbitrary":42}'},
])await assert.rejects(controlHomeAssistant(args,session));
assert.equal(posts,0);
const action={domain:'light',service:'turn_on',entity_ids:['light.tv'],data_json:'{"brightness_pct":40}'};
assert.equal((await controlHomeAssistant(action,session)).accepted,true);assert.equal(posts,1);
failPost=true;await assert.rejects(controlHomeAssistant(action,session),e=>e.message.includes('inconnu')&&!e.message.includes('private'));assert.equal(posts,2);
console.log('PASS: all-domain overview, brightness %, unavailable state, minimal attributes, flattened command fields, exact discovered targets, parameter validation, command readback, no automatic retries.');
