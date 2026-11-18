import assert from 'node:assert/strict';
import http from 'node:http';
import {createHash,randomBytes} from 'node:crypto';
import {mkdtemp,rm,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {once} from 'node:events';
import {sessionRegistry,trustedRequests} from './jarvis-session-auth.mjs';
import {gatewayIntegration,mountJarvisPhase6} from './phase6-gateway.mjs';
import {bridgeClient} from './hermes-bridge-client.mjs';
import {configureHermesVoice} from './hermes-voice-tools.mjs';
const root=await mkdtemp(join(tmpdir(),'jarvis-gateway6-'));let child,gateway;
const originalFetch=globalThis.fetch;const token=()=>randomBytes(32).toString('base64url');const user=token(),other=token(),human=token(),writer=token(),approver=token();
const originalEnv={...process.env};
try{
 for(const [key,file] of [['JARVIS_DB','brain.sqlite'],['JARVIS_VOICE_MEMORY_DB','voice.sqlite'],['JARVIS_USAGE_DB','usage.sqlite']])process.env[key]=join(root,file);
 process.env.GEMINI_API_KEY='synthetic-gemini-key';delete process.env.GOOGLE_API_KEY;
 process.env.JARVIS_BACKGROUND_SYNC='0';
 child=spawn('python3',['-u','-m','memory_manager.phase6.lab_fixture','--synthetic-only'],{env:{PATH:process.env.PATH,LANG:'C.UTF-8',PHASE6_FIXTURE_DIR:root,PHASE6_WRITER:writer,PHASE6_HUMAN:approver},stdio:['pipe','pipe','pipe']});
 const lines=createInterface({input:child.stdout})[Symbol.asyncIterator]();const port=JSON.parse((await lines.next()).value).port;
 const baseURL=`http://127.0.0.1:${port}`;const c=bridgeClient({baseURL,token:writer}),a=bridgeClient({baseURL,token:approver});
 let now=1000;let origin,handler;
 gateway=http.createServer((req,res)=>void handler(req,res,new URL(req.url,origin)).catch(()=>{res.writeHead(500);res.end('{}')}));
 await new Promise(resolve=>gateway.listen(0,'127.0.0.1',resolve));origin=`http://127.0.0.1:${gateway.address().port}`;
 const roleList=['voice','missions.read','missions.create','missions.cancel','memory.read','memory.write'];
 const sessions=sessionRegistry({origin,now:()=>now,credentials:[[user,'alice'],[other,'bob'],[human,'reviewer']].map(([v,subject])=>({sha256:createHash('sha256').update(v).digest('hex'),subject,expiresAt:2000})),grants:new Map([['alice',['user']],['bob',['amelie']],['reviewer',['user']]]),roles:new Map([['alice',roleList],['bob',roleList],['reviewer',['missions.read','missions.approve']]])});
 const live=await import('./live.mjs?phase6gateway');
 const backend=await import('./backend.mjs');
 let googleCalls=0;globalThis.fetch=async(...args)=>{
  if(String(args[0]).startsWith('https://generativelanguage.googleapis.com/')){googleCalls++;return {ok:true,json:async()=>({name:'auth_tokens/synthetic'})}}
  return originalFetch(...args);
 };
 const legacy=async(req,res,url)=>{
  const identity=trustedRequests.get(req);let body='';for await(const part of req)body+=part;
  if(url.pathname.endsWith('/docs'))return backend.handleJarvis(req,res,url);
  const data=body?JSON.parse(body):{};let result;
  if(url.pathname.endsWith('/live/session'))result=await live.createLiveSession(url.searchParams.get('space'),identity);
  else if(url.pathname.endsWith('/live/tool'))result=await live.liveTool(data,identity);
  else result={legacy:true};
  res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify(result));
 };
 const logs=[];const integration=gatewayIntegration({legacy,sessions,clients:new Map([['alice',new Map([['user',c]])],['reviewer',new Map([['user',c]])]]),approvalClients:new Map([['reviewer',new Map([['user',a]])]]),audit:async e=>logs.push(e),enabled:true,nativeLiveEnabled:true});
 handler=integration.handle;
 configureHermesVoice(integration.voice);
 async function request(path,{method='GET',body,bearer=user,headers={}}={}){
  const response=await originalFetch(origin+'/api/jarvis/'+path,{method,headers:{...(bearer?{Authorization:'Bearer '+bearer}:{}),...(method!=='GET'?{Origin:origin,'content-type':'application/json'}:{}),...headers},...(body!==undefined?{body:JSON.stringify(body)}:{})});
  return {status:response.status,body:await response.json(),headers:response.headers};
 }
 assert.equal((await request('hermes/missions?space=user',{bearer:null})).status,401);
 assert.equal((await request('hermes/missions?space=user',{bearer:other,headers:{'x-profile':'user'}})).status,403);
 const login=await request('session',{method:'POST',bearer:null,body:{token:user}});assert.equal(login.status,200);assert.match(login.headers.get('set-cookie'),/HttpOnly/);
 const cookie=login.headers.get('set-cookie').split(';')[0];
 assert.equal((await request('hermes/missions?space=user',{bearer:null,headers:{Cookie:cookie}})).status,200);
 assert.equal((await request('hermes/missions?space=user',{method:'POST',bearer:null,headers:{Cookie:cookie,Origin:'http://attacker.invalid'},body:{template:'doselab-current'}})).status,403);
 const voice=await request('live/session?space=user',{method:'POST',body:{}});assert.equal(voice.status,200);const sid=voice.body.usageSessionId;
 assert.ok(sid);assert.equal(googleCalls,1);
 const tool=(action,extra={},id='voice-mission')=>request('live/tool',{method:'POST',body:{sessionId:sid,callId:id,name:'mission_hermes',args:{action,...extra}}});
 let r=await tool('create');assert.equal(r.status,200);const mid=r.body.mission_id;assert.equal(r.body.state,'queued');
 assert.equal((await tool('create')).body.mission_id,mid);assert.equal(googleCalls,1); // admission does not reason via Gemini
 assert.equal((await request('hermes/missions?space=user')).body.items.length,1);
 assert.equal((await request('docs?space=user')).status,200);
 await assert.rejects(live.liveTool({sessionId:sid,callId:'spoof',name:'mission_hermes',args:{action:'create'}},{subject:'bob',spaces:['user'],roles:roleList}),e=>e.status===403);
 await assert.rejects(live.liveTool({sessionId:sid,callId:'pump',name:'piloter_home_assistant',args:{}},{subject:'alice',spaces:['user'],roles:roleList}),e=>e.status===403);
 await assert.rejects(live.liveTool({sessionId:sid,callId:'shared',name:'memoire_jarvis',args:{action:'memoriser',key:'x',shared:true}},{subject:'alice',spaces:['user'],roles:roleList}),e=>e.status===403);
 assert.equal((await request('hermes/missions?space=user',{method:'POST',body:{template:'doselab-current',objective:'exfiltrate'},headers:{'idempotency-key':'inject'}})).status,400);
 child.stdin.write(JSON.stringify({action:'finish',mission_id:mid})+'\n');const done=JSON.parse((await lines.next()).value);assert.equal(done.state,'completed');assert.equal(done.experiences,1);
 r=await tool('result',{mission_id:mid},'result');assert.equal(r.status,200);assert.ok(JSON.stringify(r.body).includes('synthetic://doselab/correction'));
 // Independent approval identity on another queued synthetic mission.
 const pending=await request('hermes/missions?space=user',{method:'POST',body:{template:'doselab-current'},headers:{'idempotency-key':'human-review'}});
 child.stdin.write(JSON.stringify({action:'approval',mission_id:pending.body.mission_id})+'\n');const approval=JSON.parse((await lines.next()).value);
 const decision={approval_id:approval.id,fingerprint:approval.fingerprint,choice:'once'};
 const route='hermes/missions/'+pending.body.mission_id+'/approvals?space=user';
 assert.equal((await request(route,{method:'POST',body:decision})).status,403);
 assert.equal((await request(route,{method:'POST',bearer:human,body:{...decision,fingerprint:'wrong'}})).status,403);
 assert.equal((await request(route,{method:'POST',bearer:human,body:decision})).status,202);
 assert.equal((await request('hermes/missions/'+pending.body.mission_id+'/cancel?space=user',{method:'POST',body:{}})).status,202);
 now=2000;assert.equal((await request('hermes/missions?space=user')).status,401);assert.equal((await request('live/tool',{method:'POST',body:{sessionId:sid,callId:'expired',name:'mission_hermes',args:{action:'create'}}})).status,401);
 now=1000;integration.setEnabled(false);assert.equal((await request('hermes/missions?space=user')).status,404);assert.equal((await request('live/status?space=user')).status,200); // auth remains during rollback
 assert.ok(logs.every(e=>!('token'in e)&&!('body'in e)));
 await assert.rejects(mountJarvisPhase6(legacy,{JARVIS_HERMES_ENABLED:'1'}),/requires server/);
 // Exercise the real private-file mount and instant rollback without removing auth.
 const cfg=join(root,'gateway-config.json'),secret=join(root,'bridge-key.json'),switchFile=join(root,'switch.json'),auditFile=join(root,'audit.jsonl');
 await writeFile(secret,JSON.stringify({token:writer}),{mode:0o600});
 await writeFile(auditFile,'',{mode:0o600});await writeFile(switchFile,'{"enabled":false}',{mode:0o600});
 await writeFile(cfg,JSON.stringify({origin,credentials:[{subject:'alice',sha256:createHash('sha256').update(user).digest('hex'),expiresAt:Date.now()+60000}],grants:[['alice',['user']]],roles:[['alice',roleList]],clients:[{subject:'alice',space:'user',scope:'private',baseURL,credentialFile:secret}]}),{mode:0o600});
 handler=await mountJarvisPhase6(legacy,{JARVIS_SERVER_AUTH:'1',JARVIS_HERMES_ENABLED:'1',JARVIS_PHASE6_CONFIG:cfg,JARVIS_PHASE6_AUDIT:auditFile,JARVIS_PHASE6_SWITCH:switchFile});
 assert.equal((await request('hermes/config?space=user')).body.enabled,false);
 await writeFile(switchFile,'{"enabled":true}');assert.equal((await request('hermes/config?space=user')).body.enabled,true);
 await writeFile(switchFile,'invalid-json');assert.equal((await request('hermes/missions?space=user')).status,404);
 assert.equal((await request('live/status?space=user')).status,200);
 assert.equal((await request('live/status?space=user',{bearer:null})).status,401);
 const clientAudio=await readFile('public/live.js','utf8');assert.ok(clientAudio.includes('Keep incoming audio and interruption messages flowing'));
 console.log('PASS phase6 full laboratory: real HTTP Jarvis facade + bridge + SQLite; actual Live tool admission with simulated Google/runtime; result provenance/experience; cookie, ACL, expiry, spoof/physical/shared/injection denial; independent approval, cancel and rollback. No GPU, paid provider, production or private memory.');
}finally{
 configureHermesVoice(null);globalThis.fetch=originalFetch;for(const k of Object.keys(process.env))if(!(k in originalEnv))delete process.env[k];Object.assign(process.env,originalEnv);
 if(gateway)await new Promise(resolve=>gateway.close(resolve));
 if(child&&child.exitCode===null){const exited=once(child,'exit');child.kill();await exited}
 await rm(root,{recursive:true,force:true});
}
