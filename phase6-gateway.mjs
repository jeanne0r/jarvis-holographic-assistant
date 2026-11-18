// Optional gateway mount; all production effects require an explicit reviewed flag.
import {hybridAdmission,trustedHybridAdmissions} from './hybrid-mission-admission.mjs';
import {Readable} from 'node:stream';
import {createHash} from 'node:crypto';
import {lstat,open} from 'node:fs/promises';
import {constants} from 'node:fs';
import {sessionRegistry,trustedRequests,requiredPermission} from './jarvis-session-auth.mjs';
import {experimentalHermes} from './jarvis-hermes-experimental.mjs';
import {bridgeClient} from './hermes-bridge-client.mjs';
import {HERMES_OBJECTIVE} from './hermes-voice-tools.mjs';

export function gatewayIntegration({legacy,sessions,clients,approvalClients,audit,enabled=false,hybridEnabled=false,nativeLiveEnabled=false,historyEnabled=false}){
 let flag=enabled===true;historyEnabled=historyEnabled===true;hybridEnabled=hybridEnabled===true;nativeLiveEnabled=nativeLiveEnabled===true;
 const facade=experimentalHermes({enabled:true,authenticate:req=>trustedRequests.get(req),clients,approvalClients});
 const send=(res,status,body)=>{res.writeHead(status,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify(body));return true};
 async function invoke(identity,space,method,sub,body,key){
  const raw=body===undefined?'':JSON.stringify(body),req=Readable.from(raw?[Buffer.from(raw)]:[]);
  req.method=method;req.headers={'content-length':String(Buffer.byteLength(raw)),...(key?{'idempotency-key':key}:{})};
  trustedRequests.set(req,identity);let result;
  const res={writeHead(status){this.status=status},end(text){result={status:this.status,body:JSON.parse(text)}}};
  await facade(req,res,new URL('http://127.0.0.1/api/jarvis/hermes/'+sub+'?space='+encodeURIComponent(space)));
  if(result.status>=400)throw Error('Mission unavailable or denied');return result.body;
 }
 const voice=async({identity,space,args,callId,sessionId})=>{
  if(!flag)throw Error('Hermes disabled');
  const role={create:'missions.create',status:'missions.read',result:'missions.read'}[args.action];
  if(!role||!identity.roles.includes(role)||!identity.spaces.includes(space))throw Error('Mission denied');
  if(args.action==='create'){
   if(args.mission_id!==undefined)throw Error('Synthetic template only');
   const key=createHash('sha256').update(JSON.stringify([identity.subject,sessionId,callId])).digest('hex');
   return invoke(identity,space,'POST','missions',{objective:HERMES_OBJECTIVE},key);
  }
  if(!/^[A-Za-z0-9-]{1,128}$/.test(args.mission_id||''))throw Error('Mission id required');
  return invoke(identity,space,'GET','missions/'+args.mission_id+(args.action==='result'?'/results':''));
 };
 voice.enabled=()=>flag;
 return {voice,setEnabled(value){if(typeof value!=='boolean')throw Error('Boolean flag');flag=value},async handle(req,res,url){
  if(!url.pathname.startsWith('/api/jarvis/'))return false;
  if(await sessions.handle(req,res,url))return true;
  const identity=sessions.authenticate(req);if(!identity)return send(res,401,{error:'Authentication required'});
  if(!['GET','HEAD'].includes(req.method)&&!sessions.sameOrigin(req))return send(res,403,{error:'Origin denied'});
  const spaces=url.searchParams.getAll('space');if(spaces.length>1)return send(res,403,{error:'Ambiguous space'});
  const space=spaces[0]||identity.defaultSpace;
  if(!identity.spaces.includes(space))return send(res,403,{error:'Space denied'});
  const action=url.pathname.slice('/api/jarvis/'.length);
  if(action==='hermes/config')return send(res,200,{enabled:flag,readEnabled:flag||historyEnabled,syntheticOnly:true,templates:flag?['doselab-current']:[],availability:'worker-reports-via-mission-events'});
  if(action.startsWith('hermes/')&&!flag){
   const historyRoute=action==='hermes/missions'||/^hermes\/missions\/[A-Za-z0-9-]+(?:\/(?:events|results|cancel))?$/.test(action);
   const consultation=req.method==='GET'||(req.method==='POST'&&action.endsWith('/cancel'));
   if(!historyEnabled||!historyRoute||!consultation)return send(res,404,{error:'Hermes admissions disabled'});
  }
  if(['live/session','live/tool'].includes(action)&&!nativeLiveEnabled)return send(res,403,{error:'Native Live is outside the hybrid pilot'});
  const permission=requiredPermission(req.method,action);
  if(!permission||!identity.roles.includes(permission))return send(res,403,{error:'Route denied'});
  if(action==='memory/map'&&!identity.spaces.includes('commun'))return send(res,403,{error:'Map includes common space; explicit grant required'});
  // Initial integration never opens broad shell/sync/import/development routes.
  if(['sync','import','evolution/status','evolution/diff'].includes(action))return send(res,403,{error:'Requires separate route review'});
  trustedRequests.set(req,identity);url.searchParams.set('space',space);
  if(action==='ask')trustedHybridAdmissions.set(req,hybridAdmission({identity,space,enabled:()=>flag&&hybridEnabled,audit,create:key=>invoke(identity,space,'POST','missions',{objective:HERMES_OBJECTIVE},key)}));
  try{
   await audit({event:'route_admitted',subject:identity.subject,space,route:action,method:req.method});
   if(action.startsWith('hermes/')){
    if(action==='hermes/missions'&&req.method==='POST'){
     // Voice and UI share the same fixed synthetic template. No private objective
     // or browser-provided memory context is sent to Windows.
     if(req.headers['transfer-encoding']||!/^\d+$/.test(req.headers['content-length']||'')||Number(req.headers['content-length'])>512)return send(res,413,{error:'Template body limit'});
     let raw='';for await(const part of req){raw+=part.toString();if(Buffer.byteLength(raw)>512)return send(res,413,{error:'Template body limit'})}
     if(Buffer.byteLength(raw)!==Number(req.headers['content-length']))return send(res,400,{error:'Body length'});
     const data=JSON.parse(raw);
     if(Object.keys(data).join()!=='template'||data.template!=='doselab-current')return send(res,400,{error:'Synthetic template only'});
     const result=await invoke(identity,space,'POST','missions',{objective:HERMES_OBJECTIVE},req.headers['idempotency-key']);
     return send(res,202,result);
    }
    await facade(req,res,url);return true;
   }
   await legacy(req,res,url);return true;
  }catch{return send(res,503,{error:'Service unavailable; no automatic replay'})}
 }};
}

async function privateJSON(path){
 const file=await open(path,constants.O_RDONLY|constants.O_NOFOLLOW);
 try{const st=await file.stat();if(!st.isFile()||(st.mode&0o077)||st.uid!==process.getuid()||st.size>131072)throw Error('Bounded private owned config required');return JSON.parse(await file.readFile('utf8'))}finally{await file.close()}
}
export async function mountJarvisPhase6(legacy,env=process.env){
 if(env.JARVIS_HERMES_NATIVE_LIVE==='1')throw Error('Native Live requires its separate reviewed patch; hybrid pilot only');
 if(env.JARVIS_SERVER_AUTH!=='1'){
  if(env.JARVIS_HERMES_ENABLED==='1'||env.JARVIS_HERMES_HISTORY==='1')throw Error('Hermes requires server authentication');
  return legacy;
 }
 const cfg=await privateJSON(env.JARVIS_PHASE6_CONFIG);
 const sessions=sessionRegistry({credentials:cfg.credentials,grants:new Map(cfg.grants),roles:new Map(cfg.roles),origin:cfg.origin});
 const make=async records=>{
  const out=new Map();
  for(const row of records||[]){
   const secret=await privateJSON(row.credentialFile);
   if(!out.has(row.subject))out.set(row.subject,new Map());
   out.get(row.subject).set(row.space,bridgeClient({baseURL:row.baseURL,token:secret.token,scope:row.scope}));
  }return out;
 };
 const auditPath=env.JARVIS_PHASE6_AUDIT;
 const st=await lstat(auditPath);if(!st.isFile()||st.isSymbolicLink()||(st.mode&0o077)||st.uid!==process.getuid())throw Error('Private existing audit file required');
 const audit=async event=>{const f=await open(auditPath,'a');try{await f.write(JSON.stringify({...event,at:new Date().toISOString()})+'\n');await f.sync()}finally{await f.close()}};
 const connected=env.JARVIS_HERMES_ENABLED==='1'||env.JARVIS_HERMES_HISTORY==='1';
 const integration=gatewayIntegration({legacy,sessions,clients:connected?await make(cfg.clients):new Map(),approvalClients:connected?await make(cfg.approvalClients):new Map(),audit,enabled:false,hybridEnabled:env.JARVIS_HERMES_HYBRID==='1',nativeLiveEnabled:false,historyEnabled:env.JARVIS_HERMES_HISTORY==='1'});
 const armed=env.JARVIS_HERMES_ENABLED==='1';
 if(armed&&!env.JARVIS_PHASE6_SWITCH)throw Error('Private feature switch file required');
 return async(req,res,url)=>{
  // Revocation/ACL changes do not require restarting the gateway or audio.
  // Only identity policy is hot-reloaded. Transport/approval topology is pinned.
  try{
   const fresh=await privateJSON(env.JARVIS_PHASE6_CONFIG);
   if(fresh.origin!==cfg.origin||JSON.stringify(fresh.clients)!==JSON.stringify(cfg.clients)||JSON.stringify(fresh.approvalClients)!==JSON.stringify(cfg.approvalClients))throw Error('Topology requires separate review');
   sessions.updatePolicy({credentials:fresh.credentials,grants:new Map(fresh.grants),roles:new Map(fresh.roles)});
  }catch{res.writeHead(503,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify({error:'Identity policy unavailable; request denied'}));return true}
  let enabled=false;
  if(armed){try{const state=await privateJSON(env.JARVIS_PHASE6_SWITCH);enabled=Object.keys(state).join()==='enabled'&&state.enabled===true}catch{/* missing or invalid switch disables Hermes only */}}
  integration.setEnabled(enabled);
  return integration.handle(req,res,url);
 };
}
