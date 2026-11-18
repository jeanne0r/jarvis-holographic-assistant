// Inert integration seam. No backend import (it starts production store sync).
// These are the reviewed read routes only; all other legacy routes fail closed
// when this staging gate is enabled. Gemini integration needs a separate review.
const READ=new Set(['docs','doc','memory/map','memory/status','live/status','voice/status','capabilities']);
export function phase6Jarvis({enabled=false,authenticate,legacy,hermes,grants,audit}={}){
 if(typeof legacy!=='function'||typeof hermes!=='function'||typeof authenticate!=='function'||!(grants instanceof Map)||typeof audit!=='function')throw Error('Trusted server dependencies required');
 const acl=new Map([...grants].map(([subject,routes])=>[subject,new Set(routes)]));
 let active=enabled===true;
 const deny=(res,status)=>{res.writeHead(status,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify({error:'Access denied'}));return true};
 return {setEnabled(value){if(typeof value!=='boolean')throw Error('Boolean flag required');active=value},async handle(req,res,url){
  if(!url.pathname.startsWith('/api/jarvis/'))return false;
  const isHermes=url.pathname==='/api/jarvis/hermes'||url.pathname.startsWith('/api/jarvis/hermes/');
  if(!active){if(isHermes)return deny(res,404);await legacy(req,res,url);return true}
  try{
   const identity=await authenticate(req);
   if(!identity||typeof identity.subject!=='string'||!Array.isArray(identity.spaces))return deny(res,401);
   const spaces=url.searchParams.getAll('space');
   if(spaces.length!==1||!identity.spaces.includes(spaces[0]))return deny(res,403);
   const action=url.pathname.slice('/api/jarvis/'.length);
   const route=isHermes?'hermes':`${req.method} ${action}`;
   if(!acl.get(identity.subject)?.has(route)||(!isHermes&&(req.method!=='GET'||!READ.has(action))))return deny(res,403);
   // A durable sink is supplied by the host. No query, body, credential or output
   // is logged; failure of that sink prevents dispatch.
   await audit({subject:identity.subject,space:spaces[0],route,event:'route_admitted'});
   await (isHermes?hermes(req,res,url):legacy(req,res,url));return true;
  }catch{return deny(res,503)}
 }};
}

// At-least-once notifications. The host supplies durable cursors and an idempotent
// notify callback; neither executes returned text or alters mission permissions.
export function resultInbox({load,save,notify}={}){
 if([load,save,notify].some(f=>typeof f!=='function'))throw Error('Durable host callbacks required');
 return {async consume({subject,space,missionId},sse){
  if(![subject,space,missionId].every(v=>typeof v==='string'&&v.length>0&&v.length<=128)||typeof sse!=='string'||Buffer.byteLength(sse)>65536)throw Error('Bounded inbox page required');
  const key=JSON.stringify([subject,space,missionId]);let cursor=await load(key)??0;
  if(!Number.isSafeInteger(cursor)||cursor<0)throw Error('Invalid durable cursor');
  for(const frame of sse.replaceAll('\r\n','\n').split('\n\n')){
   const lines=frame.split('\n');const id=lines.find(l=>l.startsWith('id: '))?.slice(4);
   if(id===undefined)continue;
   if(!/^\d{1,12}$/.test(id))throw Error('Invalid event ID');
   const seq=Number(id);if(seq<=cursor)continue;
   const kind=lines.find(l=>l.startsWith('event: '))?.slice(7);
   const data=JSON.parse(lines.filter(l=>l.startsWith('data: ')).map(l=>l.slice(6)).join('\n'));
   if(!data||data.mission_id!==missionId||Number(data.seq)!==seq||data.kind!==kind)throw Error('Event binding mismatch');
   if(['completed','failed','cancelled','awaiting_approval','reconciliation_required'].includes(kind)){
    await notify({id:JSON.stringify([subject,space,missionId,seq]),subject,space,missionId,kind,data,validation:'unreviewed'});
   }
   await save(key,seq);cursor=seq;
  }
  return cursor;
 }};
}
