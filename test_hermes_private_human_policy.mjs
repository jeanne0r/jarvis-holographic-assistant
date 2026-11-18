import assert from 'node:assert/strict';
import {mkdtemp,writeFile,chmod,symlink,rm} from 'node:fs/promises';
import {randomBytes,createHash} from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import {delegatedHumanPolicy,privateHumanDelegation} from './hermes-private-human-policy.mjs';
const directory=await mkdtemp(path.join(os.tmpdir(),'human-private-policy-'));
let assertions=0;const eq=(a,b)=>{assert.deepEqual(a,b);assertions++};
try{
 const key=randomBytes(32),keyFile=path.join(directory,'human-delegation.key'),configFile=path.join(directory,'config.json');
 await writeFile(keyFile,key,{mode:0o600});
 const cfg={embeddedPanel:{origin:'https://192.0.2.16:8788'},bridgeToken:randomBytes(32).toString('base64url'),humanDelegation:{enabled:true,keyFile,revision:1,subjects:[{subject:'synthetic-human',spaces:['user'],roles:['missions.read','missions.cancel']}]}};
 eq(await privateHumanDelegation({},configFile),null);
 eq(delegatedHumanPolicy(cfg).roles.get('synthetic-human'),['missions.read','missions.cancel']);
 eq(typeof (await privateHumanDelegation(cfg,configFile)).verify,'function');
 for(const patch of [{roles:['missions.read','admin']},{roles:['missions.read','missions.create']},{roles:['missions.read','missions.approve']},{spaces:['commun']},{subject:'../owner'},{owner:'new-owner'}]){
  assert.throws(()=>delegatedHumanPolicy({...cfg,humanDelegation:{...cfg.humanDelegation,subjects:[{...cfg.humanDelegation.subjects[0],...patch}]}}));assertions++;
 }
 await chmod(keyFile,0o644);await assert.rejects(()=>privateHumanDelegation(cfg,configFile));assertions++;await chmod(keyFile,0o600);
 await assert.rejects(()=>privateHumanDelegation({...cfg,bridgeToken:key.toString('base64url')},configFile));assertions++;
 await assert.rejects(()=>privateHumanDelegation({...cfg,humanHash:createHash('sha256').update(key.toString('base64url')).digest('hex')},configFile));assertions++;
 const elsewhere=path.join(directory,'other.key');await writeFile(elsewhere,key,{mode:0o600});
 await assert.rejects(()=>privateHumanDelegation({...cfg,humanDelegation:{...cfg.humanDelegation,keyFile:elsewhere}},configFile));assertions++;
 await rm(keyFile);await symlink(elsewhere,keyFile);await assert.rejects(()=>privateHumanDelegation(cfg,configFile));assertions++;
 console.log(JSON.stringify({passed:true,assertions,key_files:'temporary synthetic only',production_modified:false}));
}finally{await rm(directory,{recursive:true,force:true})}
