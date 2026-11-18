import assert from 'node:assert/strict';import {mkdtemp,rm} from 'node:fs/promises';import {tmpdir} from 'node:os';import {haLearning,learningRows,learnedHints,invalidatedHints,haObservation,explicitAliasHints} from './ha-learning.mjs';
const dir=await mkdtemp(tmpdir()+'/jarvis-learning-');process.env.JARVIS_HA_LEARNING_DB=dir+'/learning.sqlite';
try{
 const states=[{entity_id:'sensor.pv',name:'Installation PV Power',unit:'kW',device_class:'power',state:'3.2'},{entity_id:'sensor.estimated',name:'Forecast power',unit:'W',device_class:'power',state:'1800'}];
 const observations=[{args:{query:'photovoltaïque',domain:'sensor',device_class:'power'},result:{connected:true,matched:2,states}}];
 assert.equal(learningRows(observations,['sensor.invented']).length,0,'Unobserved model IDs are never stored');assert.equal(learningRows([{...observations[0],result:{connected:false,states}}],['sensor.pv']).length,0);
 assert.equal(explicitAliasHints('Production photovoltaïque actuelle ?', [{label:'Production PV',entity_id:'sensor.user_choice'}])[0].entities[0].entity_id,'sensor.user_choice');
 const rows=learningRows(observations,['sensor.pv']);assert.equal(rows[0].entities.length,1);assert(!('state' in rows[0].entities[0]));await haLearning('save',{space:'user',rows});
 const hints=await learnedHints('Quelle est la production PV actuelle ?','user');assert.equal(hints[0].entities[0].entity_id,'sensor.pv');assert.equal((await learnedHints('Quelle température fait-il à la cave ?','user')).length,0);assert.equal((await learnedHints('Production PV ?','amelie')).length,0);
 assert(!JSON.stringify(await haLearning('list',{space:'user'})).includes('3.2'),'No readings persisted');
 assert.equal(invalidatedHints(hints,[{args:{query:'sensor.pv'},result:{connected:true,matched:0,states:[]}}]).length,1,'Deleted sensor invalidates hint');
 assert.equal(invalidatedHints(hints,[{args:{query:'sensor.pv'},result:{connected:true,matched:1,states:[{...states[0],name:'New appliance'}]}}]).length,1,'Renamed sensor invalidates hint');
 assert.equal(invalidatedHints(hints,[{args:{query:'sensor.pv'},result:{connected:true,matched:1,states:[{...states[0],state:'4.5'}]}}]).length,0,'Changing values do not invalidate identity');
 assert.equal(haObservation({tool:'piloter_home_assistant'}),null);
 await haLearning('forget',{space:'amelie',key:hints[0].key});assert.equal((await haLearning('list',{space:'user'})).length,1);await haLearning('forget',{space:'user',key:hints[0].key});assert.equal((await haLearning('list',{space:'user'})).length,0);
 console.log('PASS: durable scoped hints, multilingual reuse, observation validation, no readings stored, stale identity invalidation and scoped forgetting.');
}finally{delete process.env.JARVIS_HA_LEARNING_DB;await rm(dir,{recursive:true,force:true})}
