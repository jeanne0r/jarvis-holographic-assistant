// Private endpoint wrapper for unchanged legacy voice/app implementations.
// Does not import a backend or listen on import. No /ask, runs, memory, shell route.
import {timingSafeEqual} from 'node:crypto';
import {trustedRequests} from './jarvis-session-auth.mjs';
const voiceRoutes=new Set(['voice/status','live/status','voice/session','voice/transcribe','voice/speak','capabilities','openai/usage','live/costs','live/usage','live/balance']);
export function compatibilityService({credential,policyFor,resourceFor,handlers,recordCreated=async()=>{},validateSession,origin}){
 if(typeof credential!=='string'||credential.length<32||typeof validateSession!=='function')throw Error('Distinct service credential');
 return async(req,res)=>{
  const send=s=>{res.writeHead(s,{'content-type':'application/json'});res.end(JSON.stringify({error:'Service denied'}))};
  try{
   const presented=Buffer.from(req.headers.authorization||''),expected=Buffer.from('Bearer '+credential);
   if(presented.length!==expected.length||!timingSafeEqual(presented,expected))return send(401);
   const subject=req.headers['x-jarvis-subject'],space=req.headers['x-jarvis-space'],handle=req.headers['x-jarvis-session-handle'];
   const policy=await policyFor(subject);
   if(!policy||!policy.spaces.includes(space))return send(403);
   const id={subject,kind:'human',spaces:policy.spaces,roles:policy.roles,sessionHandle:handle,space,proxyOrigin:origin};
   const url=new URL(req.url,origin),action=url.pathname.slice('/api/jarvis/'.length);
   const route=handlers.get(req.method+' '+url.pathname);
   if(!route)return send(403);
   if(!policy.roles.includes(route.permission)||!await validateSession(id,route.permission,space))return send(403);
   if(url.pathname.startsWith('/api/jarvis/')){
    if(!voiceRoutes.has(action)||typeof handle!=='string'||!/^((session|credential):[a-f0-9]{64})$/.test(handle))return send(403);
    trustedRequests.set(req,id);url.searchParams.set('space',space);
   }else{
    // Resource checked under the service's own storage identity, not trusted merely
    // because the gateway supplied an ID. No arbitrary backend host or account.
    const resource=await resourceFor(id,req.headers['x-jarvis-resource'],route);
    if(!resource||resource.space!==space||resource.owner!==subject&&!policy.commonRead?.includes(space))return send(403);
   }
   // Legacy origin checks use the pinned origin; client headers cannot choose it.
   req.headers.origin=origin;req.headers.host=new URL(origin).host;
   // Creator resources are registered by a host callback before delivering JSON.
   if(route.creates){const end=res.end.bind(res);res.end=(bytes)=>{let result;try{result=JSON.parse(bytes)}catch{return send(503)};void recordCreated(id,route,result).then(()=>end(bytes)).catch(()=>res.destroy())}}
   await route.handler(req,res,url);
  }catch{if(res.headersSent)res.destroy();else send(503)}
 };
}
