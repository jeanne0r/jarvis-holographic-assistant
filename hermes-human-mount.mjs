// Configuration mount for the EXISTING secured entry, not the active legacy server.
import {createHash} from 'node:crypto';
import {ownedJSON} from './gateway-security-mount.mjs';
import {humanAssertionSigner} from './hermes-human-delegation.mjs';
import {composeHumanMissions} from './hermes-human-gateway.mjs';
const hash=s=>createHash('sha256').update(s).digest('hex');
export function validateSSOHumanPolicy(policy,origin,forbidden=[]){
 if(policy.origin!==origin||!Number.isSafeInteger(policy.revision)||policy.revision<1||!Array.isArray(policy.credentials)||policy.credentials.length<1||policy.credentials.some(c=>c.kind!=='human'||forbidden.includes(c.sha256)))throw Error('Explicit versioned human identities required');
 return policy;
}
export async function mountHumanMissions({entry,cfg,policy,serviceCredentials,audit}){
 const options=cfg.humanMissionSSO;
 if(options?.enabled!==true||Object.keys(options).sort().join()!=='enabled,keyFile,switchFile'||cfg.flags?.admission!==false||cfg.flags?.hybrid!==false)throw Error('Read/cancel-only reviewed SSO configuration required');
 if(typeof options.keyFile!=='string'||typeof options.switchFile!=='string')throw Error('Explicit private paths required');
 const record=await ownedJSON(options.keyFile);
 if(Object.keys(record).join()!=='key'||typeof record.key!=='string'||!/^[A-Za-z0-9_-]{43}$/.test(record.key))throw Error('Dedicated key record required');
 const key=Buffer.from(record.key,'base64url');
 if(key.length!==32||key.toString('base64url')!==record.key)throw Error('Canonical dedicated 32-byte key required');
 const strings=value=>typeof value==='string'?[value]:value&&typeof value==='object'?Object.values(value).flatMap(strings):[];
 const forbiddenTokens=[...strings(serviceCredentials),...(process.env.GATEWAY_TOKEN?[process.env.GATEWAY_TOKEN]:[])];
 if(forbiddenTokens.some(value=>value===record.key||key.equals(Buffer.from(value,'base64url'))))throw Error('Delegation key reused a service identity');
 const forbidden=[...forbiddenTokens.map(hash),hash(record.key)];
 validateSSOHumanPolicy(policy,cfg.origin,forbidden);
 const refresh=async()=>{
  const fresh=validateSSOHumanPolicy(await ownedJSON(cfg.policyFile),cfg.origin,forbidden);
  entry.sessions.updatePolicy({...fresh,grants:new Map(fresh.grants),roles:new Map(fresh.roles)});
 };
 const sign=humanAssertionSigner({key,origin:cfg.origin});
 return composeHumanMissions({entry:{sessions:entry.sessions,handle:entry.handle},refresh,sign,origin:cfg.origin,switchFile:options.switchFile,audit});
}
