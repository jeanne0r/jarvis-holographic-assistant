import assert from 'node:assert/strict';
import http from 'node:http';
import {randomBytes,createHash} from 'node:crypto';
import {mkdtemp,rm,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {Readable} from 'node:stream';
import {bridgeClient} from './hermes-bridge-client.mjs';
import {phase6Jarvis,resultInbox} from './jarvis-phase6.mjs';
import {experimentalHermes} from './jarvis-hermes-experimental.mjs';
import {serverAuthenticator} from './hermes-server-auth.mjs';

const dir=await mkdtemp(join(tmpdir(),'jarvis-phase6-'));
const token=randomBytes(32).toString('base64url');
let child;
async function start(){
 const code=`import os,hashlib\nfrom pathlib import Path\nfrom memory_manager.store import Memory\nfrom memory_manager.phase2.database import migrate\nfrom memory_manager.api import server\nfrom memory_manager.phase2.http_bridge import dispatch\np=Path(os.environ['PHASE6_FIXTURE_DIR'])/'memory.sqlite'\nm=Memory(p,create=not p.exists());migrate(m);m.close()\nclients={hashlib.sha256(os.environ['PHASE6_FIXTURE_TOKEN'].encode()).hexdigest():{'name':'alice','scopes':['private'],'roles':['reader','mission_writer']}}\ns=server(p,clients,0,extension=dispatch)\nprint(s.server_address[1],flush=True)\ns.serve_forever()\n`;
 child=spawn('python3',['-u','-c',code],{env:{PATH:process.env.PATH,LANG:'C.UTF-8',PYTHONDONTWRITEBYTECODE:'1',PHASE6_FIXTURE_DIR:dir,PHASE6_FIXTURE_TOKEN:token},stdio:['ignore','pipe','pipe']});
 const port=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture timeout')),5000);child.stdout.once('data',d=>{clearTimeout(timer);resolve(Number(d.toString().trim()))});child.once('exit',()=>{clearTimeout(timer);reject(Error('Fixture exited'))})});
 assert.ok(port>0);return bridgeClient({baseURL:`http://127.0.0.1:${port}`,token});
}
async function stop(){if(child&&child.exitCode===null){const exited=once(child,'exit');child.kill();await exited}child=null}
const browserToken=randomBytes(32).toString('base64url');
const authenticate=serverAuthenticator({credentials:[{sha256:createHash('sha256').update(browserToken).digest('hex'),subject:'alice',expiresAt:Date.now()+60000}],grants:new Map([['alice',['a']]])});
let legacyCalls=0,audits=[];
function fixture(method,path,body){const raw=body===undefined?'':JSON.stringify(body);const req=Readable.from(raw?[Buffer.from(raw)]:[]);req.method=method;req.headers={authorization:'Bearer '+browserToken,'content-length':String(Buffer.byteLength(raw)),'idempotency-key':'phase6-test','x-profile':'admin'};const res={writeHead(s,h){this.status=s;this.headers=h},end(b){this.body=b}};return {req,res,url:new URL('http://localhost/api/jarvis/'+path)}}
async function call(gate,method,path,body){const f=fixture(method,path,body);await gate.handle(f.req,f.res,f.url);return f.res}
function gateFor(client){return phase6Jarvis({authenticate,legacy:async(req,res)=>{legacyCalls++;res.writeHead(200);res.end('existing-voice')},hermes:experimentalHermes({enabled:true,authenticate,clients:new Map([['alice',new Map([['a',client]])]])}),grants:new Map([['alice',['hermes','GET docs','POST capabilities/run']]]),audit:async e=>audits.push(e)})}
try{
 let client=await start();const gate=gateFor(client);
 assert.equal((await call(gate,'GET','hermes/missions/x?space=a')).status,404);
 assert.equal((await call(gate,'POST','live/session')).body,'existing-voice'); // off: unchanged legacy
 gate.setEnabled(true);
 let r=await call(gate,'POST','hermes/missions?space=a',{objective:'Synthetic offline DoseLab report'});
 assert.equal(r.status,202);const id=JSON.parse(r.body).mission_id;
 assert.ok(id);assert.equal((await call(gate,'POST','hermes/missions?space=a',{objective:'Synthetic offline DoseLab report'})).body,r.body);
 assert.equal((await call(gate,'GET','hermes/missions/'+id+'?space=a')).status,200);
 assert.equal((await call(gate,'GET','docs?space=other')).status,403);
 assert.equal((await call(gate,'GET','docs?space=a&space=other')).status,403);
 assert.equal((await call(gate,'POST','capabilities/run?space=a',{name:'ha.pump'})).status,403);
 assert.equal((await call(gate,'POST','hermes/missions/'+id+'/approvals?space=a',{})).status,404);
 const unauth=fixture('GET','docs?space=a');delete unauth.req.headers.authorization;
 await gate.handle(unauth.req,unauth.res,unauth.url);assert.equal(unauth.res.status,401);
 const page=await call(gate,'GET','hermes/missions/'+id+'/events?space=a');assert.equal(page.status,200);assert.equal(page.headers['content-type'],'text/event-stream');
 await stop();
 assert.equal((await call(gate,'GET','hermes/missions/'+id+'?space=a')).status,503);
 gate.setEnabled(false);assert.equal((await call(gate,'POST','live/session')).body,'existing-voice');
 client=await start();const restarted=gateFor(client);restarted.setEnabled(true);
 r=await call(restarted,'GET','hermes/missions/'+id+'?space=a');assert.equal(JSON.parse(r.body).state,'queued'); // real SQLite reopened; no Hermes dispatch
 assert.equal((await call(restarted,'POST','hermes/missions/'+id+'/cancel?space=a',{})).status,202);
 assert.equal(JSON.parse((await call(restarted,'GET','hermes/missions/'+id+'?space=a')).body).state,'cancelled');
 assert.ok(audits.length>0);assert.ok(audits.every(e=>!('body'in e)&&!('token'in e)));
 // Real durable cursor file and restart, synthetic notification payload.
 const cursorFile=join(dir,'cursors.json');await writeFile(cursorFile,'{}');const seen=new Set();
 const callbacks={load:async key=>JSON.parse(await readFile(cursorFile,'utf8'))[key],save:async(key,value)=>{const d=JSON.parse(await readFile(cursorFile,'utf8'));d[key]=value;await writeFile(cursorFile,JSON.stringify(d))},notify:async n=>seen.add(n.id)};
 const event={seq:9,mission_id:id,kind:'completed',data:'{"output":"untrusted data"}'};
 const sse=`id: 9\nevent: completed\ndata: ${JSON.stringify(event)}\n\n`;
 await resultInbox(callbacks).consume({subject:'alice',space:'a',missionId:id},sse);
 await resultInbox(callbacks).consume({subject:'alice',space:'a',missionId:id},sse);assert.equal(seen.size,1);
 await assert.rejects(resultInbox(callbacks).consume({subject:'alice',space:'other',missionId:'foreign'},sse),/binding/);
 assert.throws(()=>bridgeClient({baseURL:'http://example.com',token}),/loopback/);
 assert.throws(()=>client.request('GET','/v1/missions/x',{headers:{Authorization:'Bearer attacker'}}),/header denied/);
 const probe=http.createServer((req,res)=>{
  if(req.url.endsWith('/slow'))return;
  res.setHeader('content-type','application/json');
  if(req.url.endsWith('/redirect')){res.writeHead(302,{location:'https://example.com'});return res.end('{}')}
  res.end(JSON.stringify({payload:'x'.repeat(2048)}));
 });
 await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));
 try{
  const bounded=bridgeClient({baseURL:`http://127.0.0.1:${probe.address().port}`,token,timeoutMs:80,maxBytes:128});
  assert.equal((await bounded.request('GET','/v1/missions/redirect')).status,302); // no follow or remote token forwarding
  await assert.rejects(bounded.request('GET','/v1/missions/large'),/limit|aborted/);
  await assert.rejects(bounded.request('GET','/v1/missions/slow'),/deadline|timeout/i);
 }finally{await new Promise(resolve=>probe.close(resolve))}
 console.log('PASS phase6: real local HTTP/SQLite admission, idempotence, events, controller restart, queued persistence, cancel; server auth/ACL/physical and approval denial; flag rollback and durable notification cursor. No Hermes/GPU/production.');
}finally{await stop();await rm(dir,{recursive:true,force:true})}
