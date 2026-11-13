import assert from 'node:assert/strict';
import {createJarvisTools} from './tools-server.mjs';
let writes=0;const bridge=await createJarvisTools('member2',{memoryStore:async(action,{space})=>{assert.equal(space,'member2');return [];},handlers:{
 consulter_home_assistant:async(args,s)=>{assert(!('url' in args));s.entities.add('light.test');return {states:[{entity_id:'light.test'}]};},
 commandes_home_assistant:async(args,s)=>{s.services.set('light.turn_off',{fields:{}});return {services:['turn_off']};},
 piloter_home_assistant:async(args,s)=>{assert.equal(s.space,'member2');assert(s.entities.has(args.entity_ids[0]));assert(s.services.has(args.domain+'.'+args.service));writes++;return {accepted:true};},
}});
assert.equal(bridge.tools.length,9);assert(bridge.tools.every(t=>t.inputSchema.type==='object'));
assert(bridge.tools.find(t=>t.name==='consulter_home_assistant').annotations.readOnlyHint);
await bridge.call('consulter_home_assistant',{query:'salon',url:'https://other.invalid'},1);await bridge.call('commandes_home_assistant',{domain:'light'},2);
const command={domain:'light',service:'turn_off',entity_ids:['light.test']};await bridge.call('piloter_home_assistant',command,3);await bridge.call('piloter_home_assistant',command,3);assert.equal(writes,1);
await bridge.call('piloter_home_assistant',command,5);assert.equal(writes,1,'never repeat the same device command within a question');
await assert.rejects(bridge.call('piloter_home_assistant',{...command,service:'turn_on'},3));await assert.rejects(bridge.call('shell',{},4));await assert.rejects(createJarvisTools('other'));
console.log('PASS: shared scoped tool catalog, native HA/memory/knowledge adapters, read-only annotations, allowlisted parameters, duplicate call suppression, no shell.');
