import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {Readable,Writable} from 'node:stream';
import {EventEmitter} from 'node:events';
import {mkdtemp,writeFile,mkdir,symlink,rm,chmod} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {routeMatrix,classify,authorize,requestIdentity} from './gateway-route-policy.mjs';
import {mountCentralGateway} from './gateway-security-mount.mjs';
import {centralGateway,staticBytes} from './gateway-security.mjs';
import {sessionRegistry} from './jarvis-session-auth.mjs';
import {voiceOwners} from './voice-session-owner.mjs';
const origin='https://jarvis.test',now=()=>Date.now();
const token='a'.repeat(43),other='b'.repeat(43),service='c'.repeat(43),hash=x=>createHash('sha256').update(x).digest('hex');
let credentials=[{subject:'alice',sha256:hash(token),expiresAt:now()+60000},{subject:'bob',sha256:hash(other),expiresAt:now()+60000},{subject:'worker',kind:'service',sha256:hash(service),expiresAt:now()+60000}];
const permissions=[...new Set(routeMatrix.map(r=>r.permission))];
let grants=new Map([['alice',['test']],['bob',['test']],['worker',['test']]]),roles=new Map([['alice',permissions],['bob',permissions],['worker',permissions]]);
const sessions=sessionRegistry({credentials,grants,roles,origin,cookiePath:'/api'});
function request(method,url,body='',headers={}){const req=Readable.from(body?[Buffer.from(body)]:[]);req.url=url;req.method=method;req.headers={origin,'content-length':String(Buffer.byteLength(body)),...headers};req.socket={encrypted:true};return req}
class Response extends EventEmitter{
 constructor(){super();this.headers={};this.headersSent=false;this.destroyed=false;this.writableEnded=false;this.body=''}
 setHeader(k,v){this.headers[k.toLowerCase()]=v}removeHeader(k){delete this.headers[k.toLowerCase()]}
 writeHead(code,headers={}){this.status=code;for(const[k,v]of Object.entries(headers))this.setHeader(k,v);this.headersSent=true}
 write(chunk){this.body+=chunk}end(chunk=''){this.body+=chunk;this.writableEnded=true;this.emit('finish')}
 destroy(){this.destroyed=true;this.emit('close')}
}
async function login(value){const res=new Response();await sessions.handle(request('POST','/api/jarvis/session',JSON.stringify({token:value})),res,new URL(origin+'/api/jarvis/session'));return res}
const logged=await login(token);assert.equal(logged.status,200);assert.ok(Array.isArray(logged.headers['set-cookie']));const cookie=logged.headers['set-cookie'].at(-1).split(';')[0];
assert.ok(logged.headers['set-cookie'][0].includes('Path=/api/jarvis;'));assert.ok(logged.headers['set-cookie'][1].includes('Path=/api;'));
assert.equal((await login(service)).status,401);
let covered=0;
for(const row of routeMatrix){
 const p=row.path.replace(':id','synthetic-id').replace(':epoch','1234567890').replace(':file','manifest.json');
 assert.equal(classify(row.method,p)?.permission,row.permission);
 if(row.identity==='public'||row.identity==='session-protocol')continue;
 const base={method:row.method,path:p,space:'test',origin,expectedOrigin:origin,resourceAllowed:true,physicalApproval:true};
 assert.equal(authorize(base).allowed,false);
 assert.equal(authorize({...base,identity:{kind:'human',roles:[],spaces:['test']}}).allowed,false);
 assert.equal(authorize({...base,identity:{kind:'service',roles:permissions,spaces:['test']}}).allowed,false);
 const id={kind:'human',subject:'alice',roles:[row.permission],spaces:['test']};
 assert.equal(authorize({...base,identity:id}).allowed,true);
 if(row.space)assert.equal(authorize({...base,identity:id,space:'other'}).allowed,false);
 if(row.resource)assert.equal(authorize({...base,identity:id,resourceAllowed:false}).allowed,false);
 if(row.physical)assert.equal(authorize({...base,identity:id,physicalApproval:false}).allowed,false);
 covered++;
}
for(const p of ['/api/future','/api/runs/id/execute','/api/jarvis/hermes/missions/id/publish'])assert.equal(authorize({method:'POST',path:p}).allowed,false);
let invoked=[],resourceChecks=0;
const dispatch=async(req,res,url)=>{invoked.push(url.pathname);res.writeHead(200,{'access-control-allow-origin':'*'});res.end(JSON.stringify({identity:requestIdentity.get(req)?.subject,engine:'hybrid'}))};
const guard=centralGateway({sessions,dispatch,resource:async({row})=>{resourceChecks++;return row.path==='/api/jarvis/ask'}});
async function invoke(method,url,headers={},custom=guard){const req=request(method,url,'',headers),res=new Response();await custom(req,res,new URL(origin+url));return res}
assert.equal((await invoke('GET','/api/runs')).status,401);assert.equal(resourceChecks,0);
assert.equal((await invoke('POST','/api/dosing-calibration/run',{cookie})).status,403);assert.equal(invoked.length,0);
assert.equal((await invoke('GET','/api/projects',{cookie})).status,403);
assert.equal((await invoke('POST','/api/jarvis/ask',{cookie,origin:'https://evil.test'})).status,403);
assert.equal((await invoke('GET','/api/jarvis/docs?space=test&space=other',{cookie})).status,403);
const accepted=await invoke('POST','/api/jarvis/ask?space=test',{cookie});assert.equal(accepted.status,200);assert.equal(accepted.headers['access-control-allow-origin'],undefined);assert.equal(JSON.parse(accepted.body).engine,'hybrid');
assert.equal((await invoke('POST','/api/runs',{cookie,'x-role':'admin'})).status,403);
for(const target of ['/api/%2fruns','/api/../api/runs','/api/%2e%2e/api/runs','/api/%5cruns'])assert.equal((await invoke('GET',target,{cookie})).status,403);
const alice=sessions.authenticate(request('GET','/', '',{cookie}));
const bob=sessions.authenticate(request('GET','/', '',{authorization:'Bearer '+other}));
const ownership=voiceOwners();ownership.bind({sessionId:'voice-one'},alice,'test');ownership.check('voice-one',alice,'test');
for(const id of [bob,{...alice,sessionHandle:'new-login'}])assert.throws(()=>ownership.check('voice-one',id,'test'),/owner denied/);
assert.throws(()=>ownership.check('voice-one',alice,'other'),/owner denied/);
// Open response is forcibly closed on human logout, permission removal or policy failure.
async function openStream(headers){let response;const streamGuard=centralGateway({sessions,dispatch:async(req,res)=>{res.writeHead(200);res.write('PCM')},streamCheckMs:10,streamMaxMs:1000});response=await invoke('POST','/api/jarvis/voice/speak?space=test',headers,streamGuard);return response}
const stream=await openStream({cookie});assert.equal(stream.destroyed,false);
const logout=new Response();await sessions.handle(request('DELETE','/api/jarvis/session','',{cookie}),logout,new URL(origin+'/api/jarvis/session'));
await new Promise(r=>setTimeout(r,35));assert.equal(stream.destroyed,true);assert.equal((await invoke('POST','/api/jarvis/ask',{cookie})).status,401);
const streamBob=await openStream({authorization:'Bearer '+other});roles=new Map(roles);roles.set('bob',[]);sessions.updatePolicy({credentials,grants,roles});await new Promise(r=>setTimeout(r,35));assert.equal(streamBob.destroyed,true);
// Policy refresh failure also revokes an already open stream, fail closed.
let broken=false;
const failedPolicy=centralGateway({sessions,dispatch:async(req,res)=>{res.writeHead(200);res.write('open')},refresh:async()=>{if(broken)throw Error('unavailable')},streamCheckMs:10,streamMaxMs:1000});
const policyStream=await invoke('POST','/api/jarvis/voice/speak?space=test',{authorization:'Bearer '+token},failedPolicy);broken=true;
await new Promise(r=>setTimeout(r,35));assert.equal(policyStream.destroyed,true);
assert.equal((await invoke('GET','/api/jarvis/docs',{authorization:'Bearer '+token},failedPolicy)).status,503);
const restarted=sessionRegistry({credentials,grants,roles,origin,cookiePath:'/api'});assert.equal(restarted.authenticate(request('GET','/', '',{cookie})),null);
const dir=await mkdtemp(path.join(tmpdir(),'phase6d-static-'));
try{await mkdir(path.join(dir,'public'));await mkdir(path.join(dir,'public-evil'));await writeFile(path.join(dir,'public','app.js'),'safe');await writeFile(path.join(dir,'public-evil','secret'),'private');await symlink('../public-evil',path.join(dir,'public','linked'));await symlink('../public-evil/secret',path.join(dir,'public','leaf'));
 assert.equal((await staticBytes(path.join(dir,'public'),'app.js')).toString(),'safe');
 const assets=new Map([['/app.js',{file:'app.js',type:'application/javascript',sha256:hash('safe')}] ]);
 const staticGuard=centralGateway({sessions,dispatch,staticRoot:path.join(dir,'public'),publicAssets:assets});
 assert.equal((await invoke('GET','/app.js',{},staticGuard)).status,200);
 await writeFile(path.join(dir,'public','app.js'),'changed-after-review');
 assert.equal((await invoke('GET','/app.js',{},staticGuard)).status,503);
 const cfg=path.join(dir,'policy.json'),assetCfg=path.join(dir,'assets.json');
 const policy={origin,credentials,grants:[...grants],roles:[...roles]};
 await writeFile(cfg,JSON.stringify(policy),{mode:0o600});await writeFile(assetCfg,JSON.stringify([...assets].map(([path,a])=>({path,...a}))),{mode:0o600});
 const mounted=await mountCentralGateway(dispatch,{policyFile:cfg,assetFile:assetCfg,staticRoot:path.join(dir,'public')});
 assert.equal((await invoke('GET','/api/jarvis/voice/status',{authorization:'Bearer '+token},mounted)).status,200);
 await writeFile(cfg,JSON.stringify({...policy,credentials:credentials.filter(c=>c.subject!=='alice')}));
 assert.equal((await invoke('GET','/api/jarvis/voice/status',{authorization:'Bearer '+token},mounted)).status,401);
 await writeFile(cfg,'{invalid');assert.equal((await invoke('GET','/api/jarvis/voice/status',{authorization:'Bearer '+token},mounted)).status,503);
 await writeFile(cfg,JSON.stringify(policy));await chmod(cfg,0o644);assert.equal((await invoke('GET','/api/jarvis/voice/status',{authorization:'Bearer '+token},mounted)).status,503);
 await symlink(cfg,path.join(dir,'linked-policy'));await assert.rejects(()=>mountCentralGateway(dispatch,{policyFile:path.join(dir,'linked-policy'),assetFile:assetCfg,staticRoot:path.join(dir,'public')}));
 for(const p of ['../public-evil/secret','linked/secret','leaf','.env','foo/../app.js'])await assert.rejects(()=>staticBytes(path.join(dir,'public'),p));
}finally{await rm(dir,{recursive:true,force:true})}
console.log(JSON.stringify({passed:true,route_method_pairs:routeMatrix.length,protected_pairs_exercised:covered,physical_and_shell_handlers_called:0,real_provider_calls:0,voice_cross_subject_denied:true,open_stream_revoked:true,cookie_scope_migration:true,private_mount_revocation_fail_closed:true,static_symlink_and_prefix_denied:true}));
