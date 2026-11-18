// Durable panel host. No backend/worker/browser automation/provider imports.
import http from 'node:http';
import {constants} from 'node:fs';
import {readFile,open} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {ownedJSON} from '../gateway-security-mount.mjs';
import {sessionRegistry} from '../jarvis-session-auth.mjs';
import {centralGateway} from '../gateway-security.mjs';
import {gatewayIntegration} from '../phase6-gateway.mjs';
import {bridgeClient} from '../hermes-bridge-client.mjs';
import {requestIdentity} from '../gateway-route-policy.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export async function start(configFile){
 const cfg=await ownedJSON(configFile);
 if(cfg.syntheticOnly!==true||cfg.dispatchEnabled!==false||cfg.origin!=='http://127.0.0.1:'+cfg.frontPort||!Number.isInteger(cfg.frontPort)||!Number.isInteger(cfg.bridgePort)||cfg.frontPort===cfg.bridgePort||[cfg.frontPort,cfg.bridgePort].some(p=>p<1024||p>65535))throw Error('Private synthetic queue-only profile required');
 const roles=['missions.read','missions.create','missions.cancel'];
 const policy=c=>({credentials:[{subject:'pilot-operator',sha256:c.humanHash,expiresAt:c.expiresAt}],grants:new Map([['pilot-operator',['user']]]),roles:new Map([['pilot-operator',roles]])});
 const sessions=sessionRegistry({...policy(cfg),origin:cfg.origin,cookiePath:'/api'});
 const client=bridgeClient({baseURL:'http://127.0.0.1:'+cfg.bridgePort,token:cfg.bridgeToken});
 const clients=new Map([['pilot-operator',new Map([['user',client]])]]);
 const audit=async row=>{const f=await open(path.join(path.dirname(configFile),'audit.jsonl'),constants.O_WRONLY|constants.O_APPEND|constants.O_NOFOLLOW);try{const st=await f.stat();if(!st.isFile()||st.uid!==process.getuid()||(st.mode&0o077))throw Error('Private audit file required');await f.write(JSON.stringify({...row,at:new Date().toISOString()})+'\n');await f.sync()}finally{await f.close()}};
 const facade=gatewayIntegration({legacy:()=>{throw Error('No legacy fallback')},sessions,clients,approvalClients:new Map(),audit,enabled:true,historyEnabled:true});
 const assets=new Map();
 // Only explicitly packaged panel assets, no access to arbitrary source paths.
 for(const [url,file,type]of [['/','ops/pilot-interactive.html','text/html'],['/jarvis-auth.js','public/jarvis-auth.js','application/javascript'],['/hermes-missions.js','public/hermes-missions.js','application/javascript'],['/hermes-canonical.js','public/hermes-canonical.js','application/javascript'],['/hermes-missions.css','public/hermes-missions.css','text/css']])assets.set(url,{file,type,sha256:createHash('sha256').update(await readFile(path.join(root,file))).digest('hex')});
 const dispatch=async(req,res,url)=>{
  if(url.pathname==='/api/jarvis/hermes/availability'){
   res.writeHead(200,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify({state:'unavailable',fresh:false,dispatch_allowed:false,reason:'Exécuteur non activé ; aucun démarrage automatique.'}));return;
  }
  if(!url.pathname.startsWith('/api/jarvis/hermes/'))throw Error('Outside pilot');
  return facade.handle(req,res,url);
 };
 const topology=JSON.stringify({...cfg,humanHash:null,expiresAt:null});
 const refresh=async()=>{const fresh=await ownedJSON(configFile);if(JSON.stringify({...fresh,humanHash:null,expiresAt:null})!==topology)throw Error('Pinned topology changed');sessions.updatePolicy(policy(fresh))};
 const handle=centralGateway({sessions,refresh,audit,dispatch,resource:async({row})=>row.path.startsWith('/api/jarvis/hermes/'),staticRoot:root,publicAssets:assets});
 const server=http.createServer((req,res)=>void handle(req,res,new URL(req.url,cfg.origin)));
 server.requestTimeout=10000;server.headersTimeout=5000;server.keepAliveTimeout=1000;
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(cfg.frontPort,'127.0.0.1',resolve)});
 const close=()=>{server.closeAllConnections?.();server.close()};process.once('SIGTERM',close);process.once('SIGINT',close);
 console.log(JSON.stringify({ready:true,origin:cfg.origin,dispatch_enabled:false}));return server;
}
if(process.argv[1]===fileURLToPath(import.meta.url))start(process.argv[2]).catch(()=>{console.error('Pilot startup refused; inspect private configuration and approved hashes.');process.exitCode=1});
