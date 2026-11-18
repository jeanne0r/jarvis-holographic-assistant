// Standalone replacement entry, never imported into the live server during preparation.
import {createServer} from 'node:https';
import {readFile} from 'node:fs/promises';
import {ownedJSON} from './gateway-security-mount.mjs';
import {productionEntry} from './gateway-production-entry.mjs';
import {mountHumanMissions,validateSSOHumanPolicy} from './hermes-human-mount.mjs';
import {accountBindings} from './gateway-account-bindings.mjs';
import {storageClient} from './gateway-persistent-client.mjs';
import {codexBrokerClient} from './codex-broker-client.mjs';
import {forwardPrivate,privateBackend} from './gateway-service-transport.mjs';
import {projectFiles} from './gateway-project-files.mjs';
import {bridgeClient} from './hermes-bridge-client.mjs';
import {open} from 'node:fs/promises';
export async function buildFromConfig(configFile){
 const cfg=await ownedJSON(configFile),policy=await ownedJSON(cfg.policyFile);
 if(cfg.humanMissionSSO?.enabled===true)validateSSOHumanPolicy(policy,cfg.origin);
 if(cfg.engine!=='hybrid'||cfg.remoteBudgetChf!==0||cfg.commissioned!==true)throw Error('Reviewed commissioning prerequisites required');
 const secret=await ownedJSON(cfg.credentialsFile),assets=await ownedJSON(cfg.assetFile);
 let runtime;
 const broker=codexBrokerClient({socketPath:cfg.brokerSocket,credential:secret.broker,sessions:{isActive:(...a)=>runtime.sessions.isActive(...a)},projects:cfg.codexProjects});
 const clients=async rows=>{const map=new Map();for(const r of rows||[]){const key=await ownedJSON(r.credentialFile);if(!map.has(r.subject))map.set(r.subject,new Map());map.get(r.subject).set(r.space,bridgeClient({...r,token:key.token}))}return map};
 const upstreams={};
 for(const [route,endpoint]of Object.entries(cfg.accountRoutes||{})){
  const proxy=privateBackend({socketPath:endpoint.socket,credential:secret.accounts[endpoint.name]});
  upstreams[route]=async({identity,data,resource,key,parameters,path,method})=>{
   if(!endpoint.methods.includes(method))throw Error('Application method denied');
   const result=await proxy({identity,method,path:(path||route)+(parameters?'?'+new URLSearchParams(parameters):''),data:['GET','HEAD'].includes(method)?undefined:data,resource});
   if(result.status>=400)throw Error('Application service unavailable');
   return {[Symbol.for('jarvis.private.response')]:true,...result};
  };
 }
 const {lstat}=await import('node:fs/promises');const ast=await lstat(cfg.auditFile);if(!ast.isFile()||ast.isSymbolicLink()||ast.uid!==process.getuid()||(ast.mode&0o077))throw Error('Private existing audit file required');
 const audit=async event=>{const f=await open(cfg.auditFile,'a');try{await f.write(JSON.stringify({...event,at:new Date().toISOString()})+'\n');await f.sync()}finally{await f.close()}};
 const storageFor=identity=>storageClient({socketPath:cfg.storageSocket,credential:secret.storage,identity});
 const voiceApi=privateBackend({socketPath:cfg.voiceSocket,credential:secret.voice});
 const declarations=await ownedJSON(cfg.toolsFile);
 const toolHandlers=Object.fromEntries(declarations.map(d=>[d.name,async(args,{identity,space})=>{const result=await voiceApi({identity,method:'POST',path:'/api/internal/tools',data:{name:d.name,args,space}});if(result.status!==200)throw Error('Tool service denied');return JSON.parse(result.bytes)}]));
 const hybridDependencies=identity=>({meter:async(action,data)=>{if(!['session','report'].includes(action))throw Error('Meter action');const result=await voiceApi({identity,method:'POST',path:'/api/internal/usage',data:{action,data}});if(result.status!==200)throw Error('Meter service unavailable');return JSON.parse(result.bytes)}});
 const accountServices=accountBindings({rpcFor:storageFor,accountIds:cfg.accountIds,upstreams});
 runtime=productionEntry({policy,refreshPolicy:()=>ownedJSON(cfg.policyFile),assets,staticRoot:cfg.staticRoot,flags:cfg.flags,
  storageFor,broker,files:projectFiles(cfg.projectRoots),accountServices,
  hybridDependencies,toolHandlers,toolDeclarations:declarations,serviceBindings:cfg.serviceBindings,syncSources:cfg.syncSources,clients:await clients(cfg.clients),approvalClients:await clients(cfg.approvalClients),audit,
  compatibility:p=>forwardPrivate({...p,socketPath:cfg.voiceSocket,credential:secret.voice}),
 });
 if(cfg.humanMissionSSO?.enabled===true)runtime.handle=await mountHumanMissions({entry:runtime,cfg,policy,serviceCredentials:secret,audit});
 return {runtime,cfg};
}
export async function main(configFile){
 const {runtime,cfg}=await buildFromConfig(configFile);
 const server=createServer({key:await readFile(cfg.tlsKey),cert:await readFile(cfg.tlsCert)},(req,res)=>{
  const url=new URL(req.url,cfg.origin);void runtime.handle(req,res,url).catch(()=>{if(res.headersSent)res.destroy();else{res.writeHead(503);res.end()}});
 });server.listen(cfg.port,cfg.bind);return server;
}
if(process.argv[1]===new URL(import.meta.url).pathname){if(process.argv.length!==3)throw Error('Explicit private configuration required');await main(process.argv[2])}
