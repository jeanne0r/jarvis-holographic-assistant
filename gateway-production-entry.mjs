// Reviewed entry factory: imports no legacy server, backend, worker or physical loop.
// All effects require private service transports; unclassified paths never fall through.
import {businessACL,businessAdapters,authorizedRepository} from './gateway-business.mjs';
import {composeGateway,syntheticAdmission} from './gateway-final-compose.mjs';
import {sessionRegistry} from './jarvis-session-auth.mjs';
import {requestIdentity,classify} from './gateway-route-policy.mjs';
import {persistentBindings} from './gateway-persistent-client.mjs';
import {toolAuthority} from './gateway-tool-authority.mjs';
import {authorizedHybrid} from './gateway-hybrid-authorized.mjs';
const legacyVoice=new Set(['voice/status','live/status','voice/session','voice/transcribe','voice/speak','capabilities','openai/usage','live/costs','live/usage','live/balance']);
export function productionEntry({policy,refreshPolicy,assets,staticRoot,flags={history:false,admission:false,hybrid:false},clients=new Map(),approvalClients=new Map(),storageFor,broker,files,compatibility,accountServices,physicalApprovals,toolHandlers={},toolDeclarations=[],audit,hybridDependencies={},serviceBindings={},syncSources={}}){
 for(const [key,value]of Object.entries({storageFor,compatibility,audit,refreshPolicy}))if(typeof value!=='function')throw Error('Required binding '+key);
 if(!broker||!files||!accountServices)throw Error('Required production services');
 const sessions=sessionRegistry({...policy,grants:new Map(policy.grants),roles:new Map(policy.roles),cookiePath:'/api'});
 const acl=businessACL(policy.business),admitSynthetic=syntheticAdmission({clients,flags,audit});
 // Business topology is pinned for the lifetime of this release. Role/space revocations hot reload.
 const topology=JSON.stringify(policy.business);
 const refresh=async()=>{const p=await refreshPolicy();if(p.origin!==policy.origin||JSON.stringify(p.business)!==topology)throw Error('Topology changed; reviewed restart needed');sessions.updatePolicy({...p,grants:new Map(p.grants),roles:new Map(p.roles)})};
 const binding=(identity)=>{
  const rpc=storageFor(identity);
  const base=persistentBindings({identity,rpc,broker,files,accountServices});
  const tools=toolAuthority({sessions,acl,memory:authorizedRepository(acl,base.repo),handlers:toolHandlers,physicalApprovals});
  const hybrid=authorizedHybrid({acl,sessions,tools,toolDeclarations,memoryStore:base.memory,broker,dependencies:hybridDependencies});
  return businessAdapters({acl,repo:base.repo,services:{...base.services,'hybrid.answer':hybrid,'tools.call':({space,name,args})=>tools(identity,space,name,args)},physicalApprovals,syncSources,serviceBindings,admitSynthetic});
 };
 const business={resource:ctx=>binding(ctx.identity).resource(ctx),physicalApproval:async()=>true,dispatch:(req,res,url,next)=>binding(requestIdentity.get(req)).dispatch(req,res,url,next)};
 const legacy=async(req,res,url)=>{
  const row=classify(req.method,url.pathname),action=url.pathname.slice('/api/jarvis/'.length);
  if(!row||!url.pathname.startsWith('/api/jarvis/')||!legacyVoice.has(action))throw Error('No legacy bypass');
  return compatibility({identity:requestIdentity.get(req),req,res,url});
 };
 return {sessions,handle:composeGateway({sessions,business,legacy,clients,approvalClients,audit,flags,refresh,publicAssets:new Map(assets.map(a=>[a.path,a])),staticRoot})};
}
