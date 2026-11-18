// Optional embedded API on the already isolated private panel host.
import {open} from 'node:fs/promises';
import {start} from './pilot-interactive.mjs';
import {ownedJSON} from '../gateway-security-mount.mjs';
import {embeddedPanel} from '../hermes-embedded-api.mjs';
import {privateHumanDelegation} from '../hermes-private-human-policy.mjs';
import {PANEL_PREFIX} from '../hermes-embedded-contract.mjs';
import {bridgeClient} from '../hermes-bridge-client.mjs';
import {constants as flags} from 'node:fs';
import path from 'node:path';
const config=process.argv[2];
async function main(){
 const cfg=await ownedJSON(config),profile=cfg.embeddedPanel;
 if(!profile||profile.enabled!==true||typeof profile.origin!=='string')throw Error('Explicit embedded profile required');
 const delegation=await privateHumanDelegation(cfg,config);
 const operations=c=>{const flags={...(c.operations||{}),queueEnabled:c.onDemand?.commissioned===true};return flags.workerEnabled===true&&!(Date.now()/1000<flags.runtime?.expiresAt)?{...flags,admissionEnabled:false,textEnabled:false,voiceEnabled:false}:flags};
 const legacyPolicy=c=>({credentials:[{subject:'pilot-operator',sha256:c.humanHash,expiresAt:c.expiresAt}],grants:new Map([['pilot-operator',['user']]]),roles:new Map([['pilot-operator',['missions.read','missions.cancel',...(operations(c).admissionEnabled===true?['missions.create']:[])] ]])});
 const policy=c=>delegation?delegation.policy(c):legacyPolicy(c);
 const topologyOf=c=>JSON.stringify({...c,humanHash:null,expiresAt:null,embeddedPanel:null,humanDelegation:c.humanDelegation?{enabled:c.humanDelegation.enabled,keyFile:c.humanDelegation.keyFile}:undefined});
 const topology=topologyOf(cfg);
 const audit=async row=>{const f=await open(path.join(path.dirname(config),'audit.jsonl'),flags.O_WRONLY|flags.O_APPEND|flags.O_NOFOLLOW);try{const st=await f.stat();if(!st.isFile()||st.uid!==process.getuid()||(st.mode&0o077))throw Error('Private audit required');await f.write(JSON.stringify({...row,at:new Date().toISOString()})+'\n');await f.sync()}finally{await f.close()}};
 const embedded=embeddedPanel({origin:profile.origin,delegationVerifier:delegation?.verify,policy:policy(cfg),operations:()=>operations(cfg),client:bridgeClient({baseURL:'http://127.0.0.1:'+cfg.bridgePort,token:cfg.bridgeToken,workerId:'windows-hermes'}),audit,refresh:async()=>{
  const fresh=await ownedJSON(config);
  if(topologyOf(fresh)!==topology||fresh.embeddedPanel?.origin!==profile.origin)throw Error('Topology pinned');
  return fresh.embeddedPanel.enabled===true?policy(fresh):null;
 }});
 const server=await start(config),previous=server.listeners('request');server.removeAllListeners('request');
 server.on('request',(req,res)=>{
  const url=new URL(req.url,'http://127.0.0.1:'+cfg.frontPort);
  if(url.pathname===PANEL_PREFIX||url.pathname.startsWith(PANEL_PREFIX+'/'))void embedded(req,res,url);
  else if(url.pathname.startsWith('/api/')&&(!cfg.operations||req.method==='GET'))for(const handler of previous)handler(req,res);
  else {res.writeHead(404,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify({error:'Use the existing Jarvis frontend'}))}
 });
}
main().catch(()=>{console.error('Embedded private API refused; no provider started.');process.exitCode=1});
