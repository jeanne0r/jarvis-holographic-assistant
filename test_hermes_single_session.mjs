// Real HTTP and both independent ACL policies; synthetic transport only, no GPU.
import assert from 'node:assert/strict';
import http from 'node:http';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {createHash,randomBytes} from 'node:crypto';
import {sessionRegistry} from './jarvis-session-auth.mjs';
import {composeHumanMissions} from './hermes-human-gateway.mjs';
import {centralGateway} from './gateway-security.mjs';
import {humanAssertionSigner,humanAssertionVerifier,HUMAN_ASSERTION_HEADER as H} from './hermes-human-delegation.mjs';
import {embeddedPanel} from './hermes-embedded-api.mjs';
import {PANEL_PREFIX as P} from './hermes-embedded-contract.mjs';
const listen=s=>new Promise(r=>s.listen(0,'127.0.0.1',r));
const close=s=>new Promise(r=>{s.closeAllConnections?.();s.close(r)});
const hash=s=>createHash('sha256').update(s).digest('hex');
let handle,clock=Date.now(),calls=[],envelopes=[],delay=null,refreshFails=false,audit=[];
const gateway=http.createServer(async(req,res)=>{
 if(req.url.startsWith('/api/')&&await handle(req,res,new URL(req.url,origin)))return;
 if(req.method==='GET'&&req.url==='/jarvis/'){res.writeHead(200,{'content-type':'text/html; charset=utf-8'});res.end('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><div class="header-actions"></div><link rel="stylesheet" href="/jarvis/hermes-embedded.css"><script defer src="/jarvis/hermes-embedded.js"></script>');return}
 const name=req.url.replace('/jarvis/','');
 if(req.method==='GET'&&['hermes-embedded.js','hermes-embedded.css'].includes(name)){res.writeHead(200,{'content-type':name.endsWith('.js')?'text/javascript; charset=utf-8':'text/css; charset=utf-8'});res.end(await readFile('data/lot-b-sso/frontend/'+name));return}
 res.writeHead(404);res.end('{}');
});await listen(gateway);
const origin='http://127.0.0.1:'+gateway.address().port;
const tokens={alice:randomBytes(32).toString('base64url'),bob:randomBytes(32).toString('base64url'),service:randomBytes(32).toString('base64url')};
let common={revision:1,credentials:Object.entries(tokens).map(([subject,t])=>({subject,sha256:hash(t),expiresAt:clock+3600000,kind:subject==='service'?'service':'human'})),grants:new Map([['alice',['user']],['bob',['user','commun']],['service',['user']]]),roles:new Map([['alice',['missions.read','missions.cancel']],['bob',['missions.read']],['service',['missions.read']]])};
let privatePolicy={credentials:[],grants:new Map([['alice',['user']],['bob',['user']]]),roles:new Map([['alice',['missions.read','missions.cancel']],['bob',['missions.read']]])};
const sessions=sessionRegistry({...common,origin,now:()=>clock,cookiePath:'/api'}),key=randomBytes(32);
const sign=humanAssertionSigner({key,origin,now:()=>clock}),verify=humanAssertionVerifier({key,origin,now:()=>clock});
const client={scope:'private',async request(method,path,options){calls.push({method,path,options});if(delay)await delay;return {status:method==='POST'?202:200,body:{items:[{id:'synthetic-one',state:'queued',objective:'Démonstration synthétique'}]}}}};
const api=embeddedPanel({origin,policy:privatePolicy,refresh:async()=>privatePolicy,client,audit:async row=>audit.push(row),now:()=>clock,delegationVerifier:verify});
const privateServer=http.createServer((req,res)=>{if(req.headers[H])envelopes.push({wire:req.headers[H],cookie:req.headers.cookie,url:req.url});void api(req,res,new URL(req.url,origin))});await listen(privateServer);
handle=composeHumanMissions({entry:{sessions,handle:centralGateway({sessions,dispatch:async()=>{throw Error('No unsecured handler permitted')}})},refresh:async()=>{if(refreshFails)throw Error('policy unavailable');sessions.updatePolicy(common)},sign,origin,port:privateServer.address().port,switchFile:null,audit:async row=>audit.push(row)});
async function call(path,{method='GET',body,cookie,headers={},privateSide=false}={}){
 const base=privateSide?'http://127.0.0.1:'+privateServer.address().port:origin;
 const response=await fetch(base+path,{method,headers:{...(cookie?{Cookie:cookie}:{}),...(method==='GET'?{}:{Origin:origin}),...headers,...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 return {status:response.status,body:await response.json(),cookie:response.headers.get('set-cookie')};
}
async function login(who){const r=await call('/api/jarvis/session',{method:'POST',body:{token:tokens[who]}});assert.equal(r.status,200);const match=/JarvisSession=([A-Za-z0-9_-]{43})(?:;|$)/.exec(r.cookie);assert.ok(match);return 'JarvisSession='+match[1]}
let assertions=0;const eq=(a,b)=>{assert.deepEqual(a,b);assertions++};
try{
 eq((await call(P+'/hermes/missions?space=user')).status,401);eq(calls.length,0);
 eq((await call('/api/unclassified')).status,403);
 eq((await call('/api/projects')).status,401);
 eq((await call(P+'/hermes/missions?space=user',{headers:{'x-user':'alice','x-space':'user'}})).status,401);
 eq((await call('/api/jarvis/session',{method:'POST',body:{token:tokens.service}})).status,401);
 eq((await call('/api/jarvis/session',{headers:{Authorization:'Bearer '+tokens.alice}})).status,403);
 const cookie=await login('alice'),bob=await login('bob');
 eq((await call('/api/projects',{cookie})).status,403);
 eq(cookie.startsWith('JarvisSession='),true);eq(cookie.includes('JarvisHermesSession'),false);
 eq((await call('/api/jarvis/session',{cookie})).body.subject,'alice');
 eq((await call(P+'/hermes/missions?space=user',{cookie})).status,200);eq(envelopes.at(-1).cookie,undefined);
 eq((await call(P+'/hermes/missions?space=user',{cookie:bob})).status,200);
 eq((await call(P+'/hermes/missions?space=commun',{cookie:bob})).status,403);
 eq((await call(P+'/hermes/missions?space=user&space=commun',{cookie})).status,403);
 eq((await call(P+'/hermes/missions?space=user&owner=bob',{cookie})).status,403);
 eq((await call(P+'/session',{method:'POST',body:{token:tokens.alice},cookie})).status,403);
 eq((await call(P+'/hermes/missions/one/cancel?space=user',{method:'POST',body:{},cookie:bob})).status,403);
 eq((await call(P+'/hermes/missions/one/cancel?space=user',{method:'POST',body:{},cookie,headers:{Origin:'https://attacker.invalid'}})).status,403);
 eq((await call(P+'/hermes/missions/one/cancel?space=user',{method:'POST',body:{},cookie})).status,202);
 eq((await call(P+'/hermes/missions',{method:'POST',body:{template:'doselab-current'},cookie})).status,403);
 eq((await call(P+'/hermes/missions/one/approvals',{method:'POST',body:{},cookie})).status,403);
 const captured=envelopes.find(e=>e.url.endsWith('space=user'));
 eq((await call(captured.url,{privateSide:true,headers:{'x-jarvis-panel-origin':origin,[H]:captured.wire}})).status,401);
 eq((await call(P+'/hermes/missions?space=user',{cookie,headers:{[H]:captured.wire}})).status,403);
 eq((await call(P+'/hermes/missions?space=user',{privateSide:true,headers:{'x-jarvis-panel-origin':origin}})).status,401);
 // New forged-body/path/expired signatures: private verifier independently rejects.
 const proof=(method,target,body=Buffer.alloc(0))=>sign({subject:'alice',space:'user',permission:method==='GET'?'missions.read':'missions.cancel',method,target,body});
 let target=P+'/hermes/missions/one/cancel?space=user';
 eq((await call(target,{privateSide:true,method:'POST',body:{different:true},headers:{'x-jarvis-panel-origin':origin,[H]:proof('POST',target,Buffer.from('{}'))}})).status,401);
 const readPath=P+'/hermes/missions?space=user',valid=proof('GET',readPath);
 eq((await call(readPath.replace('user','commun'),{privateSide:true,headers:{'x-jarvis-panel-origin':origin,[H]:valid}})).status,401);
 const expired=proof('GET',readPath);clock+=5001;
 eq((await call(readPath,{privateSide:true,headers:{'x-jarvis-panel-origin':origin,[H]:expired}})).status,401);
 const beforePrivateDenial=calls.length;privatePolicy={...privatePolicy,roles:new Map([['alice',[]],['bob',['missions.read']]])};
 eq((await call(readPath,{cookie})).status,403);eq(calls.length,beforePrivateDenial);
 privatePolicy={...privatePolicy,roles:new Map([['alice',['missions.read','missions.cancel']],['bob',['missions.read']]])};
 // A private grant can also be revoked while the common login stays valid.
 let privateRelease;delay=new Promise(r=>privateRelease=r);const privateCount=calls.length;
 const privatePending=call(readPath,{cookie});
 for(let i=0;i<100&&calls.length===privateCount;i++)await new Promise(r=>setTimeout(r,5));
 assert.equal(calls.length,privateCount+1);
 privatePolicy={...privatePolicy,roles:new Map([['alice',[]],['bob',['missions.read']]])};
 privateRelease();delay=null;eq((await privatePending).status,403);
 privatePolicy={...privatePolicy,roles:new Map([['alice',['missions.read','missions.cancel']],['bob',['missions.read']]])};
 // Revocation while a previously authorized bridge response is in flight.
 let release;delay=new Promise(r=>release=r);const before=calls.length;
 const pending=call(readPath,{cookie});
 for(let i=0;i<100&&calls.length===before;i++)await new Promise(r=>setTimeout(r,5));
 assert.equal(calls.length,before+1);
 common={...common,revision:common.revision+1,credentials:common.credentials.filter(c=>c.subject!=='alice')};release();delay=null;
 eq((await pending).status,401);eq((await call(readPath,{cookie})).status,401);
 refreshFails=true;eq((await call(readPath,{cookie:bob})).status,503);refreshFails=false;
 eq((await call('/api/jarvis/session',{method:'DELETE',cookie:bob})).status,200);
 eq((await call(readPath,{cookie:bob})).status,401);
 const renewed=await login('bob');clock+=1800001;
 eq((await call(readPath,{cookie:renewed})).status,401);
 eq(audit.some(row=>Object.keys(row).some(k=>/token|cookie|assertion|password/i.test(k))),false);
 if(process.argv.includes('--browser')){
  const directory=await mkdtemp(path.join(os.tmpdir(),'jarvis-sso-browser-'));
  try{
   const file=path.join(directory,'synthetic.json');await writeFile(file,JSON.stringify({origin,syntheticCredential:tokens.bob}),{mode:0o600});
   const process=spawn('node',['test_hermes_sso_browser.cjs',file],{stdio:['ignore','pipe','pipe']});
   let stdout='',stderr='';process.stdout.on('data',d=>stdout+=d);process.stderr.on('data',d=>stderr+=d);
   const code=await new Promise(r=>process.once('exit',r));assert.equal(code,0,stderr);console.log(stdout.trim());
  }finally{await rm(directory,{recursive:true,force:true})}
 }
 console.log(JSON.stringify({passed:true,assertions,single_human_login:true,real_http:true,independent_private_acl:true,replay_body_path_expiry_denied:true,revocation_in_flight:true,private_browser_credentials:0,model_calls:0,production_modified:false}));
}finally{await close(privateServer);await close(gateway)}
