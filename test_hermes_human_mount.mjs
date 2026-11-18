import assert from 'node:assert/strict';
import {mkdtemp,writeFile,chmod,rm} from 'node:fs/promises';
import {randomBytes,createHash} from 'node:crypto';
import {Readable} from 'node:stream';
import os from 'node:os';
import path from 'node:path';
import {mountHumanMissions,validateSSOHumanPolicy} from './hermes-human-mount.mjs';
import {sessionRegistry} from './jarvis-session-auth.mjs';
const dir=await mkdtemp(path.join(os.tmpdir(),'hermes-human-mount-'));
let assertions=0;const eq=(a,b)=>{assert.deepEqual(a,b);assertions++};
try{
 const origin='https://192.0.2.16:8788',token=randomBytes(32).toString('base64url'),key=randomBytes(32).toString('base64url');
 const policy={origin,revision:1,credentials:[{subject:'synthetic-human',kind:'human',sha256:createHash('sha256').update(token).digest('hex'),expiresAt:Date.now()+60000}],grants:[['synthetic-human',['user']]],roles:[['synthetic-human',['missions.read','missions.cancel']]]};
 const cfg={origin,policyFile:path.join(dir,'policy.json'),flags:{admission:false,hybrid:false},humanMissionSSO:{enabled:true,keyFile:path.join(dir,'key.json'),switchFile:path.join(dir,'switch.json')}};
 for(const [file,value]of [[cfg.policyFile,policy],[cfg.humanMissionSSO.keyFile,{key}],[cfg.humanMissionSSO.switchFile,{enabled:true}]])await writeFile(file,JSON.stringify(value),{mode:0o600});
 const sessions=sessionRegistry({...policy,grants:new Map(policy.grants),roles:new Map(policy.roles),cookiePath:'/api'});
 let legacy=0;const entry={sessions,handle:async(req,res)=>{legacy++;res.writeHead(403);res.end('{}')}};
 const audit=async()=>{},options={entry,cfg,policy,serviceCredentials:{broker:randomBytes(32).toString('base64url')},audit};
 const mounted=await mountHumanMissions(options);eq(typeof mounted,'function');
 async function call(method,target,body,headers={}){
  const raw=body===undefined?'':JSON.stringify(body),req=Readable.from(raw?[Buffer.from(raw)]:[]);
  req.method=method;req.url=target;req.headers={...headers,'content-length':String(Buffer.byteLength(raw))};
  let status,responseHeaders,result;
  await mounted(req,{writeHead(s,h){status=s;responseHeaders=h},end(v){result=JSON.parse(v)}},new URL(target,origin));
  return {status,headers:responseHeaders,body:result};
 }
 const login=await call('POST','/api/jarvis/session',{token},{origin});eq(login.status,200);
 const cookies=login.headers['set-cookie'];eq(cookies.every(c=>c.includes('Secure')&&c.includes('HttpOnly')&&c.includes('SameSite=Strict')),true);
 const issued=cookies.find(c=>/^JarvisSession=[A-Za-z0-9_-]{43};/.test(c));assert.ok(issued);assertions++;
 eq(issued.includes('Path=/api;'),true);eq(issued.includes('Domain='),false);
 eq((await call('POST','/api/jarvis/session',{token},{origin:'https://wrong.invalid'})).status,403);
 eq((await call('POST','/api/jarvis/session',{token,profile:'admin'},{origin})).status,400);
 eq((await call('GET','/api/jarvis/hermes/missions')).status,403);eq(legacy,0);
 await call('GET','/api/unknown');eq(legacy,1); // guarded entry, never an imported live backend
 await assert.rejects(()=>mountHumanMissions({...options,cfg:{...cfg,flags:{admission:true,hybrid:false}}}));assertions++;
 await assert.rejects(()=>mountHumanMissions({...options,serviceCredentials:{broker:key}}));assertions++;
 await chmod(cfg.humanMissionSSO.keyFile,0o644);await assert.rejects(()=>mountHumanMissions(options));assertions++;
 assert.throws(()=>validateSSOHumanPolicy({...policy,revision:undefined},origin));assertions++;
 assert.throws(()=>validateSSOHumanPolicy({...policy,credentials:[{...policy.credentials[0],kind:'service'}]},origin));assertions++;
 assert.throws(()=>validateSSOHumanPolicy(policy,origin,[policy.credentials[0].sha256]));assertions++;
 console.log(JSON.stringify({passed:true,assertions,https_cookie_flags:true,private_key_permissions:true,alternate_hermes_path_denied:true,production_modified:false}));
}finally{await rm(dir,{recursive:true,force:true})}
