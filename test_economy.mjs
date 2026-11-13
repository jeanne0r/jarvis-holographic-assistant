import assert from 'node:assert/strict';
import {consultHomeAssistant,listHomeAssistantServices} from './home-assistant.mjs';
import {liveSetup} from './live.mjs';
process.env.HOME_ASSISTANT_URL='http://127.0.0.1:1';process.env.HOME_ASSISTANT_TOKEN='test';
const states=Array.from({length:22},(_,i)=>({entity_id:'light.lamp_'+i,state:'on',attributes:{friendly_name:'Lampe '+i,brightness:84,options:Array(40).fill('long option')}}));
states.unshift({entity_id:'light.group',state:'on',attributes:{entity_id:['light.lamp_1','light.lamp_2']}});
const catalog=[{domain:'light',services:{
 turn_on:{fields:{effect:{selector:{select:{options:Array.from({length:30},(_,i)=>'effect '+i)}}}}},
 turn_off:{fields:{transition:{selector:{number:{min:0,max:60}}}}},
}}];
globalThis.fetch=async url=>({ok:true,json:async()=>url.pathname==='/api/services'?catalog:states});

const session={economy:true,entities:new Set(),services:new Map()};
const page=await consultHomeAssistant({query:'',domain:'light'},session);assert.equal(page.states.length,10);assert.equal(page.nextOffset,10);assert.equal(page.states[0].entity_id,'light.group');assert.deepEqual(page.states[0].members,['light.lamp_1','light.lamp_2']);
assert(!('options' in page.states[1]));assert.equal(page.states[1].brightness_pct,33);
const details=await consultHomeAssistant({query:'lamp 1',domain:'light',details:true},session);assert('options' in details.states[0]);
const listing=await listHomeAssistantServices({domain:'light'},session);assert.deepEqual(listing.services,[{service:'turn_on'},{service:'turn_off'}]);
const exact=await listHomeAssistantServices({domain:'light',service:'turn_on'},session);assert.equal(exact.services.length,1);assert.equal(exact.services[0].fields.effect.selector.select.options.length,12);assert.equal(exact.services[0].fields.effect.selector.select.optionsTruncated,true);
assert.equal(session.services.get('light.turn_on').fields.effect.selector.select.options.length,30,'full validation schema stays server-side');
const full=await listHomeAssistantServices({domain:'light',service:'turn_on',details:true},session);assert.equal(full.services[0].fields.effect.selector.select.options.length,30);
const setup=liveSetup([]);assert.equal(setup.contextWindowCompression.triggerTokens,'3072');assert.equal(setup.contextWindowCompression.slidingWindow.targetTokens,'2048');assert.equal(setup.realtimeInputConfig.activityHandling,'START_OF_ACTIVITY_INTERRUPTS');
console.log('PASS: economical pagination, details on demand, correct group identity, exact command fields, bounded selectors, server validation schema preserved, context limits and interruptions.');
