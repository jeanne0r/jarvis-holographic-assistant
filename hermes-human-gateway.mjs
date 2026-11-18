// Inert mount: uses the existing human registry and loopback relay, no legacy imports.
import {embeddedRelay} from './hermes-embedded-relay.mjs';
const send=(res,status,data)=>{res.writeHead(status,{'content-type':'application/json','cache-control':'no-store','x-content-type-options':'nosniff'});res.end(JSON.stringify(data));return true};
export function humanMissionsGateway({sessions,refresh,sign,origin,port=8796,switchFile,audit}){
 if(!sessions||!Number.isSafeInteger(sessions.policyRevision?.())||sessions.origin!==origin||typeof refresh!=='function'||typeof audit!=='function')throw Error('Verified common session registry required');
 const panel=embeddedRelay({enabled:true,origin,port,switchFile,sharedSession:{sessions,refresh,sign}});
 return async(req,res,url)=>{
  if(url.pathname!=='/api/jarvis/session')return panel(req,res,url);
  if(url.origin!==origin||req.headers.authorization!==undefined||req.headers['x-jarvis-human-assertion']!==undefined||req.headers.origin&&req.headers.origin!==origin)return send(res,403,{error:'Common human session only'});
  try{
   await refresh();
   // Audit metadata only; never record credentials, cookies or request bodies.
   await audit({event:'human_session_protocol',method:req.method});
   return await sessions.handle(req,res,url);
  }catch{return send(res,503,{error:'Human identity policy unavailable'})}
 };
}

// Compose with the existing secured production entry, never the legacy router.
// This mount does not declare the current legacy server safe or replace its guard.
export function composeHumanMissions({entry,...options}){
 if(!entry?.sessions||typeof entry.handle!=='function')throw Error('Secured gateway entry required');
 const missions=humanMissionsGateway({...options,sessions:entry.sessions});
 return async(req,res,url)=>{
  if(url.pathname.startsWith('/api/jarvis/hermes/'))return send(res,403,{error:'Use the session-bound mission facade'});
  if(await missions(req,res,url))return true;
  await entry.handle(req,res,url);return true;
 };
}
