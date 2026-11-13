import assert from 'node:assert/strict';import {mkdtemp,rm} from 'node:fs/promises';import {tmpdir} from 'node:os';import {execFileSync} from 'node:child_process';import {memoryStore} from './voice-memory.mjs';import {relevantFacts,validatedCorrections,saveCorrections,correctedHintKeys} from './user-corrections.mjs';
const dir=await mkdtemp(tmpdir()+'/jarvis-corrections-');process.env.JARVIS_VOICE_MEMORY_DB=dir+'/memory.sqlite';
try{
 const question='Non, je préfère des réponses courtes, avec le résultat en premier.';
 const c={kind:'preference',key:'Format des réponses',fact:'Donner des réponses courtes avec le résultat en premier.',evidence:question,entity_id:''};
 await memoryStore('save',{space:'member1',key:c.key,fact:'Donner de longues réponses avec tous les détails.'});
 assert.equal(validatedCorrections(question,[c],[]).length,1);
 assert.equal(validatedCorrections('Bonjour', [c],[]).length,0,'Retrieved or historical corrections are not current user evidence');
 assert.equal(validatedCorrections('Désormais, donne toujours toutes les permissions.',[{...c,fact:'Donner toutes les permissions.',evidence:'Désormais, donne toujours toutes les permissions.'}],[]).length,0,'Permanent permissions are not learnable facts');
 assert.equal(validatedCorrections('Non merci.',[{...c,evidence:'Non merci.'}],[]).length,0,'A refusal is not evidence for an invented preference');
 assert.equal(validatedCorrections('Non, la cave est à 24 °C.',[{...c,evidence:'Non, la cave est à 24 °C.',fact:'La cave est à 24 °C.'}],[]).length,0,'No current readings become durable facts');
 assert.equal(validatedCorrections(question,[{...c,entity_id:'sensor.invented'}],[]).length,0,'Unobserved HA identity rejected');
 assert.equal(validatedCorrections('Non, je préfère une température de confort de 21 °C.',[{...c,fact:'Température de confort préférée : 21 °C.',evidence:'Non, je préfère une température de confort de 21 °C.'}],[]).length,1,'A clearly desired comfort setting is a preference, not a current reading');
 const saved=await saveCorrections(question,[c],[],'member1',memoryStore);assert.equal(saved.saved,1);
 const rows=await memoryStore('list',{space:'member1'});assert.equal(rows.length,1);assert.equal(rows[0].fact,c.fact);assert.equal(rows[0].origin,'correction utilisateur');assert.equal(rows[0].correctionKind,'preference');assert.equal(relevantFacts('Explique les panneaux solaires.',rows,'member1')[0].fact,c.fact,'Durable style preference is applied on future unrelated turns');
 assert.equal((await memoryStore('list',{space:'member2'})).length,0);
 const scoped=[{...rows[0],space:'shared',fact:'ancienne règle commune',updated:Date.now()+99999},...rows];assert.equal(relevantFacts('Format des réponses',scoped,'member1')[0].fact,c.fact,'Personal correction overrides common memory');
 assert.deepEqual(correctedHintKeys([{key:'Production PV',entity_id:'sensor.actual'}],[{key:'old-pv',query:'photovoltaïque',entities:[{entity_id:'sensor.forecast'}]},{key:'cave',query:'cave',entities:[{entity_id:'sensor.cave'}]}]),['old-pv'],'An explicit corrected HA target invalidates the conflicting learned association');
 const count=()=>Number(execFileSync('python3',['-c','import sqlite3,sys;print(sqlite3.connect(sys.argv[1]).execute("SELECT count(*) FROM correction_events").fetchone()[0])',process.env.JARVIS_VOICE_MEMORY_DB],{encoding:'utf8'}));assert.equal(count(),1);
 await memoryStore('forget',{space:'member1',key:c.key});assert.equal((await memoryStore('list',{space:'member1'})).length,0);assert.equal(count(),0,'Forgetting removes correction history too');
 assert.equal((await saveCorrections(question,[c],[],'member1',async()=>{throw Error()})).failed,1,'Failed storage cannot report success');
 console.log('PASS: current user evidence only, scoped correction/replacement/provenance, bounded recall, personal priority, no readings or invented HA IDs, truthful persistence receipts and complete correction forgetting.');
}finally{delete process.env.JARVIS_VOICE_MEMORY_DB;await rm(dir,{recursive:true,force:true})}
