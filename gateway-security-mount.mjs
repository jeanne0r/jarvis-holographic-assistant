import {open} from 'node:fs/promises';
import {constants} from 'node:fs';
import {sessionRegistry} from './jarvis-session-auth.mjs';
import {centralGateway} from './gateway-security.mjs';
export async function ownedJSON(file){
 const fd=await open(file,constants.O_RDONLY|constants.O_NOFOLLOW);
 try{const st=await fd.stat();if(!st.isFile()||st.uid!==process.getuid()||(st.mode&0o077)||st.size>131072)throw Error('Private policy file required');return JSON.parse(await fd.readFile('utf8'))}finally{await fd.close()}
}
export async function mountCentralGateway(dispatch,{policyFile,assetFile,staticRoot,resource,physicalApproval,audit}={}){
 const first=await ownedJSON(policyFile),assets=await ownedJSON(assetFile);
 if(!Array.isArray(assets)||assets.some(a=>typeof a.path!=='string'||typeof a.file!=='string'||typeof a.type!=='string'||!/^[a-f0-9]{64}$/.test(a.sha256||'')))throw Error('Explicit asset manifest required');
 if(new Set(assets.map(a=>a.path)).size!==assets.length)throw Error('Duplicate static route');
 const sessions=sessionRegistry({...first,grants:new Map(first.grants),roles:new Map(first.roles),cookiePath:'/api'});
 const refresh=async()=>{const cfg=await ownedJSON(policyFile);if(cfg.origin!==first.origin)throw Error('Origin requires reviewed restart');sessions.updatePolicy({...cfg,grants:new Map(cfg.grants),roles:new Map(cfg.roles)})};
 return centralGateway({sessions,dispatch,refresh,resource,physicalApproval,audit,staticRoot,publicAssets:new Map(assets.map(a=>[a.path,a]))});
}
