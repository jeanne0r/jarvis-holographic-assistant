// One registry of human sessions shared by central policy, business adapters and Hermes.
import {centralGateway} from './gateway-security.mjs';
import {gatewayIntegration} from './phase6-gateway.mjs';
import {requestIdentity} from './gateway-route-policy.mjs';
import {hybridAdmission} from './hybrid-mission-admission.mjs';
import {HERMES_OBJECTIVE} from './hermes-voice-tools.mjs';
export function composeGateway({sessions,business,legacy,clients,approvalClients,audit,flags,publicAssets,staticRoot,refresh}){
 const facade=gatewayIntegration({legacy,sessions,clients,approvalClients,audit,enabled:false,historyEnabled:flags.history===true});
 const send=(res,s,data)=>{res.writeHead(s,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify(data))};
 const dispatch=async(req,res,url)=>{
  facade.setEnabled(flags.admission===true);
  if(url.pathname.startsWith('/api/jarvis/hermes/')){
   const identity=requestIdentity.get(req),space=url.searchParams.get('space')||identity.defaultSpace;
   url.searchParams.set('space',space);
   if(url.pathname==='/api/jarvis/hermes/availability'){
    try{const client=clients.get(identity.subject)?.get(space);return send(res,200,await client.workerStatus())}catch{return send(res,200,{state:'unknown',fresh:false,dispatch_allowed:false})}
   }
   return facade.handle(req,res,url);
  }
  return business.dispatch(req,res,url,legacy);
 };
 return centralGateway({sessions,refresh,audit,dispatch,publicAssets,staticRoot,
  resource:async ctx=>ctx.row.path.startsWith('/api/jarvis/hermes/')||business.resource(ctx),
  physicalApproval:business.physicalApproval,
 });
}
// Called by the authorized /ask adapter BEFORE classification/model/private context.
export function syntheticAdmission({clients,flags,audit}){
 return async(identity,space,data)=>hybridAdmission({identity,space,audit,enabled:()=>flags.admission===true&&flags.hybrid===true,
  create:async key=>{
   const client=clients.get(identity.subject)?.get(space);if(!client)throw Error('No bound identity');
   const result=await client.request('POST','/v1/missions',{headers:{'Idempotency-Key':key},body:{scope:client.scope,definition:{objective:HERMES_OBJECTIVE,trigger:'jarvis-experimental',priority:1,memory_context:[],plan:['retrieve','report'],allowed_tools:['memory.search','memory.propose','report'],budget:{tokens:0,cost_micros:0,local_tokens:98304,seconds:240,attempts:1}}}});
   if(result.status!==202)throw Error('Admission denied');return result.body;
  },
 })(data);
}
