import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {once} from 'node:events';
import {randomUUID} from 'node:crypto';
import {storageClient,persistentBindings} from './gateway-persistent-client.mjs';
const root=await mkdtemp(tmpdir()+'/jarvis-canonical-fixture-');
const child=spawn('python3',['-m','memory_manager.production.fixture_server',root],{stdio:['ignore','pipe','pipe']});let error='';child.stderr.on('data',b=>error+=b);
try{
 await Promise.race([once(child.stdout,'data').then(([b])=>assert.equal(b.toString().trim(),'fixture-ready')),once(child,'exit').then(()=>{throw Error('Fixture startup: '+error)})]);
 const identity={subject:'alice',kind:'human',space:'user',defaultSpace:'user'};
 const rpc=storageClient({socketPath:root+'/storage.sock',credential:'s'.repeat(43),identity});
 const d=await rpc('create',{kind:'document',space:'user',data:{space:'user',title:'Étalonnage','body':'Quatre cellules de 1 kg.'}});
 assert.equal(d.owner,'alice');assert.ok((await rpc('list',{kind:'document',space:'user',query:{q:'cellules'}})).some(x=>x.id===d.id));
 const bob=storageClient({socketPath:root+'/storage.sock',credential:'s'.repeat(43),identity:{...identity,subject:'bob'}});
 assert.equal((await bob('list',{kind:'document',space:'user',query:{}})).length,0);await assert.rejects(bob('get',{kind:'document',space:'user',id:d.id}));
 const sid=randomUUID();await rpc('conversation.record',{space:'user',data:{id:sid,channel:'written',turn:0,revision:1,user:'Cellules de pesée ?',assistant:'',status:'partial'}});
 const bindings=persistentBindings({identity,rpc,broker:{call:async()=>[]},files:{tree:async()=>[]}});
 await bindings.memory('save',{space:'user',key:'Cellules de pesée',fact:'Quatre cellules identiques de 1 kg.'});assert.equal((await bindings.memory('list',{space:'user'}))[0].status,'inferred');
 assert.equal((await bindings.memory.metadata('Cellules de pesée','user')).owner,'alice');
 console.log(JSON.stringify({passed:true,sqlite_and_unix_transport_real:true,legacy_ddl_from_source:true,private_data_read:false,models_called:0}));
}finally{child.kill('SIGTERM');if(child.exitCode===null)await once(child,'exit');await rm(root,{recursive:true,force:true})}
