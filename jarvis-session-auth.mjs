// Server-issued human sessions, independent of visual profiles and bridge secrets.
import {createHash,randomBytes} from 'node:crypto';
import {serverAuthenticator} from './hermes-server-auth.mjs';
export const trustedRequests=new WeakMap();
const hash=value=>createHash('sha256').update(value).digest('hex');
export function sessionRegistry({credentials,grants,roles,origin,now=()=>Date.now(),sessionTTL=30*60*1000,cookiePath='/api/jarvis',revision}){
 const base=new URL(origin);
 if(!['/api/jarvis','/api'].includes(cookiePath))throw Error('Reviewed cookie scope required');
 if(base.origin!==origin||!(base.protocol==='https:'||(base.protocol==='http:'&&base.hostname==='127.0.0.1'))||!Number.isSafeInteger(sessionTTL)||sessionTTL<1000||sessionTTL>3600000)throw Error('Pinned secure origin and bounded lifetime required');
 const issued=new Map();let verify,records,spaces,permissions,currentRevision=null,currentFingerprint=null;
 function updatePolicy(policy){
  if(!(policy.roles instanceof Map)||!(policy.grants instanceof Map)||!Array.isArray(policy.credentials))throw Error('Server policy required');
  // Validate fully before publishing any new policy; callers fail closed on error.
  const nextVerify=serverAuthenticator({credentials:policy.credentials,grants:policy.grants,now});
  const nextRecords=new Map();
  for(const c of policy.credentials){if(nextRecords.has(c.sha256))throw Error('Duplicate credential');nextRecords.set(c.sha256,{...c})}
  const nextSpaces=new Map([...policy.grants].map(([k,v])=>{if(!Array.isArray(v)||v.some(s=>typeof s!=='string'))throw Error('Space grants');return [k,[...v]]}));
  const nextRoles=new Map([...policy.roles].map(([k,v])=>{if(!Array.isArray(v)||v.some(r=>typeof r!=='string'))throw Error('Role grants');return [k,[...new Set(v)]]}));
  const fingerprint=hash(JSON.stringify([policy.credentials.map(c=>[c.subject,c.sha256,c.expiresAt,c.kind||'human']).sort(),[...nextSpaces].sort(),[...nextRoles].sort()]));
  if(policy.revision!==undefined&&(!Number.isSafeInteger(policy.revision)||policy.revision<1))throw Error('Positive policy revision required');
  if(currentRevision!==null&&(policy.revision===undefined||policy.revision<currentRevision||policy.revision===currentRevision&&fingerprint!==currentFingerprint))throw Error('Policy rollback or unversioned change denied');
  verify=nextVerify;records=nextRecords;spaces=nextSpaces;permissions=nextRoles;
  currentRevision=policy.revision??null;currentFingerprint=fingerprint;
  for(const [key,session] of issued){const issuer=records.get(session.issuer);if(session.expiresAt<=now()||!issuer||issuer.subject!==session.subject||issuer.expiresAt<=now())issued.delete(key)}
 }
 updatePolicy({credentials,grants,roles,revision});
 function identity(subject,record,sessionHandle){
  const grants=spaces.get(subject);if(!grants?.length)return null;
  return {subject,kind:record?.kind||'human',sessionHandle,spaces:[...grants],roles:[...(permissions.get(subject)||[])],defaultSpace:grants[0]};
 }
 function presented(req){
  const cookies=(req.headers.cookie||'').split(';').map(x=>x.trim()).filter(x=>x.startsWith('JarvisSession='));
  if(cookies.length>1)return null;
  if(req.headers.authorization!==undefined){
   if(typeof req.headers.authorization!=='string'||!/^Bearer [A-Za-z0-9_-]{43,128}$/.test(req.headers.authorization))return null;
   return {value:req.headers.authorization.slice(7),bearer:true};
  }
  return cookies.length?{value:cookies[0].slice('JarvisSession='.length),bearer:false}:null;
 }
 function authenticate(req){
  const entry=presented(req);if(!entry||!/^[A-Za-z0-9_-]{43,128}$/.test(entry.value))return null;
  const key=hash(entry.value),session=issued.get(key);
  if(session){
   const issuer=records.get(session.issuer);
   if(session.expiresAt<=now()||!issuer||issuer.subject!==session.subject||issuer.expiresAt<=now()){issued.delete(key);return null}
   return identity(session.subject,issuer,'session:'+key);
  }
  // Cookies never accept the long-lived login credential. Explicit API bearer
  // credentials remain supported and are revoked by removing them from policy.
  if(!entry.bearer)return null;
  const principal=verify({headers:{authorization:'Bearer '+entry.value}});
  return principal?identity(principal.subject,records.get(key),'credential:'+key):null;
 }
 const sameOrigin=req=>req.headers.origin===origin;
 function isActive(id,permission,space){
  if(!id?.sessionHandle)return false;const [type,key]=id.sessionHandle.split(':');
  const session=type==='session'?issued.get(key):null,issuer=records.get(session?.issuer||key);
  if(type!=='session'&&type!=='credential'||!issuer||issuer.subject!==id.subject||issuer.expiresAt<=now()||(type==='session'&&(!session||session.expiresAt<=now())))return false;
  return spaces.get(id.subject)?.includes(space)&&permissions.get(id.subject)?.includes(permission);
 }
 return {authenticate,isActive,sameOrigin,origin,updatePolicy,policyRevision:()=>currentRevision,async handle(req,res,url){
  if(url.pathname!=='/api/jarvis/session')return false;
  const send=(code,data,headers={})=>{res.writeHead(code,{'content-type':'application/json','cache-control':'no-store',...headers});res.end(JSON.stringify(data));return true};
  if(req.method==='GET'){const id=authenticate(req);return send(id?200:401,id?{subject:id.subject,spaces:id.spaces,roles:id.roles}:{error:'Authentication required'})}
  if(!sameOrigin(req))return send(403,{error:'Origin denied'});
  if(req.method==='DELETE'){
   const entry=presented(req);if(entry)issued.delete(hash(entry.value));
   for(const cookie of (req.headers.cookie||'').split(';').map(x=>x.trim()))if(cookie.startsWith('JarvisSession='))issued.delete(hash(cookie.slice('JarvisSession='.length)));
   return send(200,{signedOut:true},{'set-cookie':cookiePath==='/api'?[`JarvisSession=; Path=/api/jarvis; HttpOnly; SameSite=Strict; Max-Age=0${base.protocol==='https:'?'; Secure':''}`,`JarvisSession=; Path=${cookiePath}; HttpOnly; SameSite=Strict; Max-Age=0${base.protocol==='https:'?'; Secure':''}`]:`JarvisSession=; Path=${cookiePath}; HttpOnly; SameSite=Strict; Max-Age=0${base.protocol==='https:'?'; Secure':''}`});
  }
  if(req.method!=='POST')return send(405,{error:'Method denied'});
  if(req.headers['transfer-encoding']||!/^\d+$/.test(req.headers['content-length']||'')||Number(req.headers['content-length'])>512)return send(413,{error:'Body limit'});
  const chunks=[];let size=0;
  for await(const chunk of req){size+=chunk.length;if(size>512)return send(413,{error:'Body limit'});chunks.push(chunk)}
  if(size!==Number(req.headers['content-length']))return send(400,{error:'Body length'});
  let data;try{data=JSON.parse(Buffer.concat(chunks).toString())}catch{return send(400,{error:'Invalid JSON'})}
  if(!data||Object.keys(data).join()!=='token'||typeof data.token!=='string')return send(400,{error:'Session token only'});
  const principal=verify({headers:{authorization:'Bearer '+data.token}}),id=principal?identity(principal.subject,records.get(hash(data.token))):null;
  if(!id||id.kind!=='human')return send(401,{error:'Session denied'});
  for(const [key,s] of issued)if(s.expiresAt<=now())issued.delete(key);
  if(issued.size>=1000)return send(429,{error:'Session capacity reached'});
  const issuer=hash(data.token),expiresAt=Math.min(records.get(issuer).expiresAt,now()+sessionTTL);
  const token=randomBytes(32).toString('base64url');issued.set(hash(token),{subject:id.subject,issuer,expiresAt});
  const sessionCookie=`JarvisSession=${token}; Path=${cookiePath}; HttpOnly; SameSite=Strict; Max-Age=${Math.max(0,Math.floor((expiresAt-now())/1000))}${base.protocol==='https:'?'; Secure':''}`;
  return send(200,{subject:id.subject,spaces:id.spaces,expiresAt},{'set-cookie':cookiePath==='/api'?[`JarvisSession=; Path=/api/jarvis; HttpOnly; SameSite=Strict; Max-Age=0${base.protocol==='https:'?'; Secure':''}`,sessionCookie]:sessionCookie});
 }};
}
export function requiredPermission(method,action){
 if(action==='live/tool')return 'voice'; // Each actual tool receives an independent permission check.
 if(action.startsWith('hermes/'))return action.endsWith('/approvals')?'missions.approve':method==='GET'?'missions.read':action.endsWith('/cancel')?'missions.cancel':'missions.create';
 if(method==='GET')return ({docs:'memory.read',doc:'memory.read','memory/map':'memory.read','memory/status':'memory.read','live/status':'voice','voice/status':'voice',capabilities:'voice','live/costs':'usage.read','openai/usage':'usage.read','evolution/status':'development','evolution/diff':'development'})[action];
 if(method==='POST')return ({'live/session':'voice','voice/session':'voice','voice/transcribe':'voice','voice/speak':'voice','conversations/record':'memory.write',notes:'memory.write',move:'memory.move',sync:'memory.admin',import:'memory.admin',ask:'conversation','capabilities/run':'capabilities','live/usage':'usage.write','live/balance':'usage.admin'})[action];
 return undefined;
}
