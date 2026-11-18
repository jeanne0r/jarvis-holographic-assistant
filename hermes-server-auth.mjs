// Node 18, offline preparation. Opaque server-issued sessions, never visual profiles.
import {createHash,timingSafeEqual} from 'node:crypto';
export function serverAuthenticator({credentials,grants,now=()=>Date.now()}={}){
 if(!Array.isArray(credentials)||!(grants instanceof Map))throw Error('Server registry required');
 const records=credentials.map(c=>{
  if(!/^[a-f0-9]{64}$/.test(c.sha256)||typeof c.subject!=='string'||!Number.isFinite(c.expiresAt))throw Error('Invalid session record');
  return {...c,digest:Buffer.from(c.sha256,'hex')};
 });
 const acl=new Map([...grants].map(([subject,spaces])=>[subject,Object.freeze([...spaces])]));
 return req=>{
  const header=req.headers.authorization;
  if(typeof header!=='string'||!/^Bearer [A-Za-z0-9_-]{43,128}$/.test(header))return null;
  const hash=createHash('sha256').update(header.slice(7)).digest();
  const match=records.find(c=>timingSafeEqual(hash,c.digest)&&c.expiresAt>now());
  if(!match||!acl.has(match.subject))return null;
  return {subject:match.subject,spaces:[...acl.get(match.subject)]};
 };
}
