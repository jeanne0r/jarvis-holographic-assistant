// Private server-to-server identity proof. Never a browser token or bridge key.
import {createHash,createHmac,randomBytes,timingSafeEqual} from 'node:crypto';
import {PANEL_PREFIX} from './hermes-embedded-contract.mjs';
export const HUMAN_ASSERTION_HEADER='x-jarvis-human-assertion';
export function panelPermission(method,path){
 if(method==='GET'&&(['/hermes/config','/hermes/availability','/hermes/missions'].some(p=>path===PANEL_PREFIX+p)||new RegExp('^'+PANEL_PREFIX+'/hermes/missions/[A-Za-z0-9-]{1,128}(?:/(?:results|events))?$').test(path)))return 'missions.read';
 if(method==='POST'&&new RegExp('^'+PANEL_PREFIX+'/hermes/missions/[A-Za-z0-9-]{1,128}/cancel$').test(path))return 'missions.cancel';
 if(method==='POST'&&[PANEL_PREFIX+'/hermes/missions',PANEL_PREFIX+'/hybrid/ask'].includes(path))return 'missions.create';
 return null;
}
const digest=body=>createHash('sha256').update(body).digest('hex');
function settings({key,origin,now=()=>Date.now()}){
 if(!Buffer.isBuffer(key)||key.length!==32)throw Error('Dedicated 32-byte delegation key required');
 const u=new URL(origin);if(u.origin!==origin||!(u.protocol==='https:'||(u.protocol==='http:'&&u.hostname==='127.0.0.1')))throw Error('Pinned TLS origin required');
 return {key:Buffer.from(key),origin,now};
}
const mac=(key,wire)=>createHmac('sha256',key).update(wire).digest();
export function humanAssertionSigner(options){
 const {key,origin,now}=settings(options);
 return ({subject,space,permission,method,target,body})=>{
  if(typeof subject!=='string'||!/^[A-Za-z0-9_-]{1,128}$/.test(subject)||typeof space!=='string'||space.length>128||!Buffer.isBuffer(body)||body.length>8000||typeof target!=='string'||target.length>2048||panelPermission(method,new URL(target,origin).pathname)!==permission)throw Error('Bounded identity binding required');
  const issued=now(),payload={version:1,issuer:'jarvis-human-gateway',audience:'private-hermes-panel',origin,subject,space,permission,method,target,body_sha256:digest(body),nonce:randomBytes(16).toString('hex'),issued,expires:issued+5000};
  const wire=Buffer.from(JSON.stringify(payload)).toString('base64url');return wire+'.'+mac(key,wire).toString('base64url');
 };
}
export function humanAssertionVerifier(options){
 const {key,origin,now}=settings(options),seen=new Map();
 return (req,url,body)=>{
  const wire=req.headers[HUMAN_ASSERTION_HEADER];
  if(typeof wire!=='string'||wire.length>4096||!Buffer.isBuffer(body)||body.length>8000)throw Error('Delegated identity required');
  const parts=wire.split('.');if(parts.length!==2||parts.some(s=>!s||!/^[A-Za-z0-9_-]+$/.test(s)))throw Error('Invalid assertion');
  const signature=Buffer.from(parts[1],'base64url'),expected=mac(key,parts[0]);
  if(signature.length!==expected.length||!timingSafeEqual(signature,expected))throw Error('Invalid assertion');
  const p=JSON.parse(Buffer.from(parts[0],'base64url').toString('utf8'));
  const fields='audience,body_sha256,expires,issued,issuer,method,nonce,origin,permission,space,subject,target,version';
  const at=now();
  if(Object.keys(p).sort().join()!==fields||p.version!==1||p.issuer!=='jarvis-human-gateway'||p.audience!=='private-hermes-panel'||p.origin!==origin||!Number.isSafeInteger(p.issued)||!Number.isSafeInteger(p.expires)||p.issued>at||p.expires<=at||p.expires-p.issued!==5000||typeof p.subject!=='string'||!/^\w[\w-]{0,127}$/.test(p.subject)||typeof p.space!=='string'||!p.space||p.space.length>128||!/^[a-f0-9]{32}$/.test(p.nonce)||p.method!==req.method||p.target!==url.pathname+url.search||p.body_sha256!==digest(body)||p.permission!==panelPermission(req.method,url.pathname)||!p.permission)throw Error('Assertion binding denied');
  for(const [nonce,expiry]of seen)if(expiry<=at)seen.delete(nonce);
  if(seen.has(p.nonce)||seen.size>=10000)throw Error('Replayed assertion or capacity exceeded');
  seen.set(p.nonce,p.expires);return Object.freeze({subject:p.subject,space:p.space,permission:p.permission,kind:'human'});
 };
}
