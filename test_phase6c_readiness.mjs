// Offline unit tests only. No backend import, model, GPU, production or private data.
import assert from 'node:assert/strict';
import {Readable} from 'node:stream';
import {createHash,randomBytes} from 'node:crypto';
import {mkdtemp,writeFile,rm,symlink,chmod} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {sessionRegistry} from './jarvis-session-auth.mjs';
import {gatewayIntegration,mountJarvisPhase6} from './phase6-gateway.mjs';
await import('./public/hermes-canonical.js');
const token=randomBytes(32).toString('base64url'),origin='http://127.0.0.1:39876';
const digest=createHash('sha256').update(token).digest('hex');let now=1000;
const credentials=[{subject:'human',sha256:digest,expiresAt:100000}],grants=new Map([['human',['user']]]),roles=new Map([['human',['voice','missions.read','conversation']]]);
const sessions=sessionRegistry({credentials,grants,roles,origin,now:()=>now,sessionTTL:60000});
function fixture(method,path,data,headers={}){
 const raw=data===undefined?'':JSON.stringify(data),req=Readable.from(raw?[Buffer.from(raw)]:[]);req.method=method;req.headers={origin,'content-length':String(Buffer.byteLength(raw)),...headers};
 const res={writeHead(status,headers){this.status=status;this.headers=headers},end(value){this.body=JSON.parse(value)}};
 return {req,res,url:new URL(origin+'/api/jarvis/'+path)};
}
async function call(handle,method,path,data,headers){const f=fixture(method,path,data,headers);await handle(f.req,f.res,f.url);return f.res}
const login=()=>call(sessions.handle,'POST','session',{token});
const first=await login(),second=await login();assert.equal(first.status,200);
const a=first.headers['set-cookie'].split(';')[0],b=second.headers['set-cookie'].split(';')[0];
assert.notEqual(a,b);assert.ok(!a.includes(token));assert.match(a,/JarvisSession=/);assert.match(first.headers['set-cookie'],/Max-Age=60/);
assert.equal(sessions.authenticate({headers:{cookie:'JarvisSession='+token}}),null);
assert.equal(sessions.authenticate({headers:{cookie:a}}).subject,'human');
await call(sessions.handle,'DELETE','session',undefined,{cookie:a,authorization:'Bearer '+token});
assert.equal(sessions.authenticate({headers:{cookie:a}}),null);assert.ok(sessions.authenticate({headers:{cookie:b}}));
sessions.updatePolicy({credentials,grants:new Map([['human',['amelie']]]),roles:new Map([['human',['voice']]])});
let id=sessions.authenticate({headers:{cookie:b}});assert.deepEqual(id.spaces,['amelie']);assert.deepEqual(id.roles,['voice']);
sessions.updatePolicy({credentials:[],grants,roles});assert.equal(sessions.authenticate({headers:{cookie:b}}),null);
assert.equal(sessions.authenticate({headers:{authorization:'Bearer '+token}}),null);
sessions.updatePolicy({credentials,grants,roles});assert.equal(sessions.authenticate({headers:{cookie:b}}),null); // no resurrection
const c=(await login()).headers['set-cookie'].split(';')[0];now=61001;assert.equal(sessions.authenticate({headers:{cookie:c}}),null);
assert.equal((await call(sessions.handle,'POST','session',{token},{origin:'http://attacker.invalid'})).status,403);
// PC-off/history-only mode never contacts a runtime; create/approve remain shut.
sessions.updatePolicy({credentials,grants,roles:new Map([['human',['voice','missions.read','missions.cancel','missions.create','missions.approve']]])});
const forwarded=[];const client={scope:'private',request:async(method,path)=>{forwarded.push({method,path});return {status:method==='GET'?200:202,body:method==='GET'?{items:[{id:'synthetic-queued',state:'queued'}]}:{state:'cancelled'}}}};
const readonly=gatewayIntegration({sessions,legacy:()=>{throw Error('Unexpected legacy route')},clients:new Map([['human',new Map([['user',client]])]]),audit:async()=>{},historyEnabled:true});
const auth={authorization:'Bearer '+token};
assert.equal((await call(readonly.handle,'GET','hermes/config?space=user',undefined,auth)).body.readEnabled,true);
assert.equal((await call(readonly.handle,'GET','hermes/missions?space=user',undefined,auth)).body.items[0].state,'queued');
assert.equal((await call(readonly.handle,'POST','hermes/missions?space=user',{template:'doselab-current'},auth)).status,404);
assert.equal((await call(readonly.handle,'POST','hermes/missions/synthetic-queued/approvals?space=user',{choice:'once'},auth)).status,404);
assert.equal((await call(readonly.handle,'POST','hermes/missions/synthetic-queued/cancel?space=user',{},auth)).status,202);
assert.deepEqual(forwarded.map(r=>r.path),['/v1/missions','/v1/missions/synthetic-queued/cancel']);
assert.equal((await call(readonly.handle,'GET','hermes/missions?space=amelie',undefined,auth)).status,403);
const root=await mkdtemp(join(tmpdir(),'phase6c-policy-'));let refreshMean;
try{
 const config=join(root,'identity.json'),audit=join(root,'audit.jsonl');let legacyCalls=0;
 const cfg={origin,credentials:[{...credentials[0],expiresAt:Date.now()+60000}],grants:[['human',['user']]],roles:[['human',['voice','conversation']]],clients:[{subject:'human',space:'user',baseURL:'http://127.0.0.1:8792',credentialFile:join(root,'not-created-bridge-secret.json')}],approvalClients:[]};
 const write=async value=>writeFile(config,JSON.stringify(value),{mode:0o600});await write(cfg);await writeFile(audit,'',{mode:0o600});
 const handle=await mountJarvisPhase6(async(req,res)=>{legacyCalls++;res.writeHead(200,{});res.end('{"voice":"legacy-unchanged"}')},{JARVIS_SERVER_AUTH:'1',JARVIS_PHASE6_CONFIG:config,JARVIS_PHASE6_AUDIT:audit});
 const signed=await call(handle,'POST','session',{token}),cookie=signed.headers['set-cookie'].split(';')[0];
 const headers={cookie};assert.equal((await call(handle,'GET','voice/status',undefined,headers)).status,200);
 const start=performance.now();for(let i=0;i<40;i++)assert.equal((await call(handle,'GET','voice/status',undefined,headers)).status,200);refreshMean=(performance.now()-start)/40;
 await write({...cfg,roles:[['human',['voice']]]});assert.equal((await call(handle,'POST','ask',{question:'Synthetic'},headers)).status,403);
 assert.equal((await call(handle,'GET','voice/status',undefined,headers)).status,200); // same unrevoked cookie survives role update
 await write({...cfg,credentials:[]});assert.equal((await call(handle,'GET','voice/status',undefined,headers)).status,401);
 await write(cfg);assert.equal((await call(handle,'GET','voice/status',undefined,headers)).status,401);
 const again=await call(handle,'POST','session',{token}),valid={cookie:again.headers['set-cookie'].split(';')[0]};
 await writeFile(config,'broken');const previous=legacyCalls;
 assert.equal((await call(handle,'GET','voice/status',undefined,valid)).status,503);assert.equal(legacyCalls,previous);
 await write({...cfg,clients:[{baseURL:'http://attacker.invalid'}]});assert.equal((await call(handle,'GET','voice/status',undefined,valid)).status,503);
 await write(cfg);await chmod(config,0o644);assert.equal((await call(handle,'GET','voice/status',undefined,valid)).status,503);await chmod(config,0o600);
 const alias=join(root,'link.json');await symlink(config,alias);
 await assert.rejects(mountJarvisPhase6(()=>{}, {JARVIS_SERVER_AUTH:'1',JARVIS_PHASE6_CONFIG:alias,JARVIS_PHASE6_AUDIT:audit}));
 assert.equal((await call(handle,'GET','voice/status',undefined,valid)).status,200);
}finally{await rm(root,{recursive:true,force:true})}
const raw='Correction annoncée au 2023-11-15. Éléments « précis » <img src=x onerror=alert(1)>.';
const row={memory_id:'synthetic-stable-id',revision_id:'synthetic-revision',source_ref:'synthetic://doselab/correction',observed_utc:'2023-11-14T22:15:00Z',stored_validation_status:'user_confirmed',revision_status:'user_confirmed',valid_from_utc:'2023-11-14T22:15:00Z',valid_to_utc:null};
const projection={schema:'canonical_metadata.v1',origin:'sqlite',items:[row]},before=JSON.stringify(projection);
const sections=globalThis.JarvisCanonical.sections(raw,projection);assert.equal(sections.modelText,raw);assert.ok(sections.metadataText.includes('2023-11-14T22:15:00Z'));assert.ok(!sections.metadataText.includes('2023-11-15'));assert.equal(JSON.stringify(projection),before);
assert.throws(()=>globalThis.JarvisCanonical.sections(raw,{...projection,origin:'model'}));
console.log(JSON.stringify({passed:true,session_rotation_logout_revocation:true,hot_policy_fail_closed:true,unchanged_valid_voice_identity:true,canonical_dates_without_silent_rewrite:true,history_only_with_create_and_approve_denied:true,policy_request_average_ms:Number(refreshMean.toFixed(3)),production_writes:0,gpu_calls:0}));
