// Opt-in private-side mount. Explicit synthetic-space grants, no owner adoption.
import {open} from 'node:fs/promises';
import {constants} from 'node:fs';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {humanAssertionVerifier} from './hermes-human-delegation.mjs';
export function delegatedHumanPolicy(cfg){
 const data=cfg.humanDelegation;
 if(!data||Object.keys(data).sort().join()!=='enabled,keyFile,revision,subjects'||data.enabled!==true||!Number.isSafeInteger(data.revision)||data.revision<1||!Array.isArray(data.subjects)||data.subjects.length<1||data.subjects.length>64)throw Error('Explicit delegated subjects required');
 const grants=new Map(),roles=new Map();
 for(const row of data.subjects){
  if(!row||Object.keys(row).sort().join()!=='roles,spaces,subject'||typeof row.subject!=='string'||!/^[A-Za-z0-9_-]{1,128}$/.test(row.subject)||grants.has(row.subject)||JSON.stringify(row.spaces)!=='["user"]'||!Array.isArray(row.roles)||!row.roles.includes('missions.read')||new Set(row.roles).size!==row.roles.length||row.roles.some(r=>!['missions.read','missions.cancel'].includes(r)))throw Error('Read/cancel synthetic grants only');
  grants.set(row.subject,[...row.spaces]);roles.set(row.subject,[...row.roles]);
 }
 return {credentials:[],grants,roles,revision:data.revision};
}
export async function privateHumanDelegation(cfg,configFile){
 if(cfg.humanDelegation===undefined)return null;
 delegatedHumanPolicy(cfg);
 const expected=path.join(path.dirname(path.resolve(configFile)),'human-delegation.key');
 if(cfg.humanDelegation.keyFile!==expected)throw Error('Private state key path required');
 const file=await open(expected,constants.O_RDONLY|constants.O_NOFOLLOW);let key;
 try{const st=await file.stat();if(!st.isFile()||st.uid!==process.getuid()||(st.mode&0o077)||st.size!==32)throw Error('Private owned 32-byte key required');key=await file.readFile();if(key.length!==32)throw Error('Key size changed')}finally{await file.close()}
 for(const secret of [cfg.bridgeToken,...Object.values(cfg.operations?.runtime||{})]){
  if(typeof secret!=='string')continue;
  if(key.equals(Buffer.from(secret))||key.equals(Buffer.from(secret,'base64url')))throw Error('Service identity reuse denied');
 }
 if(createHash('sha256').update(key.toString('base64url')).digest('hex')===cfg.humanHash)throw Error('Human credential reuse denied');
 return {verify:humanAssertionVerifier({key,origin:cfg.embeddedPanel.origin}),policy:delegatedHumanPolicy};
}
