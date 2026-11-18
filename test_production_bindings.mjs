import assert from 'node:assert/strict';
import {productionEntry} from './gateway-production-entry.mjs';
import {powerBridge,fixedPowerTransport} from './s9-power-service.mjs';
import {Readable} from 'node:stream';
import {EventEmitter} from 'node:events';
import {createHash} from 'node:crypto';
import {routeMatrix} from './gateway-route-policy.mjs';
import {persistentBindings} from './gateway-persistent-client.mjs';
const origin='https://jarvis.test',token='a'.repeat(43),hash=x=>createHash('sha256').update(x).digest('hex');
const policy={origin,credentials:[{subject:'alice',sha256:hash(token),expiresAt:Date.now()+60000}],grants:[['alice',['user']]],roles:[['alice',['conversation','memory.read','memory.write','voice','projects.read','runs.read']]],business:{projects:{dose:{readers:['alice'],writers:['alice']}},scopes:{user:{readers:['alice'],writers:['alice']}}}};
const storeCalls=[],effects=[];let activePolicy=policy;
const rpc=async(method,args)=>{storeCalls.push({method,args});if(method==='conversation.record')return {saved:true};if(method==='facts')return [];if(method==='metadata')return null;if(method==='projects.list')return ['dose'];if(method==='list')return [];throw Error('Unexpected storage method '+method)};
const runtime=productionEntry({policy,refreshPolicy:async()=>activePolicy,assets:[],staticRoot:'/does-not-exist',storageFor:id=>{assert.equal(id.subject,'alice');return rpc},broker:{answer:async()=>{throw Error('Unexpected Codex')},call:async()=>[]},files:{tree:async()=>[]},accountServices:{},compatibility:async({res})=>{effects.push('voice');res.writeHead(200);res.end('{}')},audit:async()=>{},hybridDependencies:{classify:async()=> 'gemini',gemini:async()=>({answer:'Bonjour synthétique',speech:'Bonjour synthétique',sourceIds:[],action:{type:'none'}})}});
async function call(method,path,data,auth=token){const raw=data===undefined?'':JSON.stringify(data),req=Readable.from(raw?[Buffer.from(raw)]:[]);req.method=method;req.url=path;req.headers={origin,'content-length':String(Buffer.byteLength(raw)),...(auth?{authorization:'Bearer '+auth}:{})};const res=new EventEmitter();res.writeHead=function(s){this.status=s};res.removeHeader=()=>{};res.end=function(b){this.body=b;this.writableEnded=true;this.emit('finish')};await runtime.handle(req,res,new URL(path,origin));return res}
assert.equal((await call('POST','/api/jarvis/ask?space=user',{question:'bonjour'})).status,200);
assert.equal(storeCalls.filter(x=>x.method==='conversation.record').length,2);
assert.equal((await call('POST','/api/jarvis/ask?space=user',{question:'bonjour'},null)).status,401);
assert.equal((await call('GET','/api/projects')).status,200);
assert.equal((await call('POST','/api/runs',{project:'dose',prompt:'shell'})).status,403);
assert.equal((await call('POST','/api/jarvis/live/tool?space=user',{})).status,403);
assert.equal((await call('POST','/api/jarvis/voice/session?space=user',{})).status,200);
activePolicy={...policy,credentials:[]};assert.equal((await call('POST','/api/jarvis/ask?space=user',{question:'bonjour'})).status,401);
// Actual state machine with fake equipment, persisted across construction.
let saved={},target=1000,applied=[],fail=false;
const setup=()=>powerBridge({enabled:true,pollMs:5000,load:async()=>structuredClone(saved),save:async s=>{saved=structuredClone(s)},readTarget:async()=>target,applyTarget:async p=>{if(fail)throw Error('fake failure');applied.push(p);return {power:p}}});
let power=setup();await power.start();assert.deepEqual(applied,[]);target=1100;await power.tick();assert.deepEqual(applied,[1100]);await power.stop();
target=1150;power=setup();await power.start();assert.deepEqual(applied,[1100]);fail=true;target=1200;await power.tick();assert.equal(power.status().uncertain,true);await power.stop();
power=setup();await power.start();assert.equal(power.status().uncertain,true);await power.tick();assert.deepEqual(applied,[1100]);await power.stop();
await assert.rejects(power.reconcile({approved:false,requested:1200,applied:1100}));await power.reconcile({approved:true,requested:1200,applied:1100});
// Exact network contract: only a fake fetch implementation, never a real connection.
const urls=[];const transport=fixedPowerTransport({haURL:'http://ha.test',minerURL:'http://miner.test',entity:'input_number.s9_power_target',haToken:'synthetic',username:'test',password:'test',min:800,max:1420,fetchImpl:async(url,opts)=>{urls.push(String(url));return {ok:true,headers:new Map([['set-cookie','sid=synthetic; HttpOnly']]),json:async()=>url.pathname.startsWith('/api/states/')?{state:'1000'}:JSON.parse(opts.body).query.includes('Login')?{data:{auth:{login:{__typename:'AuthOk'}}}}:{data:{bosminer:{config:{updateAutotuning:{__typename:'AutotuningOut'}}}}}}}});
assert.equal(await transport.readTarget(),'1000');assert.equal((await transport.applyTarget(2000)).power,1420);assert.equal(urls.length,3);
console.log(JSON.stringify({passed:true,entry_hybrid_provider_simulated:true,auth_and_revocation:true,no_legacy_codex_bypass:true,power_state_restart_no_replay:true,physical_requests_real:0,remote_inference_calls:0}));
