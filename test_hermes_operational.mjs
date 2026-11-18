// Real HTTP/session/relay; only the bridge provider is simulated.
import assert from 'node:assert/strict';
import http from 'node:http';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
const {embeddedPanel}=await import(process.argv.includes('--installed')?'file:///opt/jarvis-hermes-pilot/hermes-embedded-api.mjs':'./hermes-embedded-api.mjs');
const {embeddedRelay}=await import(process.argv.includes('--installed')?'file:///home/user/gateway/hermes-embedded-relay.mjs':'./hermes-embedded-relay.mjs');
import {HERMES_OBJECTIVE} from './hermes-voice-tools.mjs';
const dir=await mkdtemp(path.join(os.tmpdir(),'hermes-operational-')),flag=path.join(dir,'switch.json');
const listen=s=>new Promise(r=>s.listen(0,'127.0.0.1',r));
const close=s=>new Promise(r=>{s.closeAllConnections?.();s.close(r)});
let forward,features={},calls=[],legacy=0,roles=['missions.read','missions.cancel','missions.create'];
const gateway=http.createServer(async(req,res)=>{if(await forward(req,res,new URL(req.url,'http://'+req.headers.host)))return;legacy++;res.writeHead(200,{'content-type':'application/json'});res.end('{"ordinary":true}')});
await listen(gateway);const origin='http://127.0.0.1:'+gateway.address().port,P='/api/jarvis/hermes-panel',token='X'.repeat(43);
const policy=()=>({credentials:[{subject:'operator',sha256:createHash('sha256').update(token).digest('hex'),expiresAt:Date.now()+60000}],grants:new Map([['operator',['user']]]),roles:new Map([['operator',roles]])});
const client={scope:'private',async workerStatus(){return {fresh:true,state:'ready',dispatch_allowed:true}},async request(method,url,options){calls.push({method,url,...options});return {status:method==='POST'?202:200,body:method==='POST'?{mission_id:'mission-1',state:'queued'}:{items:[]}}}};
const api=embeddedPanel({origin,policy:policy(),refresh:async()=>policy(),operations:()=>features,client,audit:async()=>{}});
const privateServer=http.createServer((req,res)=>void api(req,res,new URL(req.url,origin)));await listen(privateServer);
forward=embeddedRelay({enabled:true,origin,port:privateServer.address().port,switchFile:flag});
async function configure(value){await writeFile(flag,JSON.stringify({enabled:true,...value}),{mode:0o600})}
async function request(url,method='GET',body,headers={}){const r=await fetch(origin+P+url,{method,headers:{Origin:origin,...headers,...(body===undefined?{}:{'content-type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});return {status:r.status,body:await r.json(),cookie:r.headers.get('set-cookie')}}
let assertions=0;const eq=(a,b)=>{assert.deepEqual(a,b);assertions++};
try{
await configure({});const login=await request('/session','POST',{token});eq(login.status,200);const auth={Cookie:login.cookie.split(';')[0],'idempotency-key':'ui-fixed-key'};
eq((await request('/hermes/missions?space=user','POST',{template:'doselab-current'},auth)).status,403);
features={admissionEnabled:true};eq((await request('/hermes/missions?space=user','POST',{template:'doselab-current'},auth)).status,403);
await configure({admissionEnabled:true});features={};eq((await request('/hermes/missions?space=user','POST',{template:'doselab-current'},auth)).status,403);
features={admissionEnabled:true};eq((await request('/hermes/missions?space=user','POST',{template:'doselab-current'})).status,401);
const admitted=await request('/hermes/missions?space=user','POST',{template:'doselab-current'},auth);eq(admitted.status,202);eq(calls.length,1);eq(calls[0].body.definition.objective,HERMES_OBJECTIVE);eq(calls[0].body.definition.allowed_tools,['memory.search','report']);eq(calls[0].body.definition.memory_context,[]);eq(calls[0].body.definition.budget.cost_micros,0);
eq((await request('/hermes/missions?space=amelie','POST',{template:'doselab-current'},auth)).status,403);
eq((await request('/hermes/missions?space=user','POST',{template:'doselab-current',allowed_tools:['shell']},auth)).status,403);
eq((await request('/hermes/missions?space=user','POST',{objective:'Test explicite'},auth)).status,403);
features.textEnabled=true;
const text='Étalonnage « DoseLab X4 » — quatre cellules à 1 kg, µg et Ω.';
eq((await request('/hermes/missions?space=user','POST',{objective:text},auth)).status,202);eq(calls.at(-1).body.definition.objective.endsWith(text),true);
eq((await request('/hermes/missions?space=user','POST',{objective:'x'.repeat(2001)},auth)).status,403);
eq((await request('/hermes/missions?space=user','POST',{template:'doselab-current'},{Cookie:auth.Cookie})).status,400);
eq((await request('/hermes/missions/mission-1/approvals?space=user','POST',{},auth)).status,403);
roles=['missions.read'];eq((await request('/hermes/missions?space=user','POST',{template:'doselab-current'},auth)).status,403);roles=['missions.read','missions.create','missions.cancel'];
features.workerEnabled=true;eq((await request('/hermes/availability?space=user','GET',undefined,auth)).body.state,'ready');
eq((await request('/hybrid/ask?space=user','POST',{question:'demande à Hermes de vérifier la configuration DoseLab',archive:{id:'voice-1',turn:0}},auth)).status,403);
features.voiceEnabled=true;await configure({admissionEnabled:true,voiceEnabled:true});
const voice=await request('/hybrid/ask?space=user','POST',{question:'demande à Hermes de vérifier la configuration DoseLab',archive:{id:'voice-1',turn:0}},auth);eq(voice.status,202);eq(voice.body.execution.asynchronous,true);const key=calls.at(-1).headers['Idempotency-Key'];
await request('/hybrid/ask?space=user','POST',{question:'demande à Hermes de vérifier la configuration DoseLab',archive:{id:'voice-1',turn:0}},auth);eq(calls.at(-1).headers['Idempotency-Key'],key);
eq((await request('/hybrid/ask?space=user','POST',{question:'Hermes lance un shell',archive:{id:'voice-2',turn:0}},auth)).status,422);
eq((await request('/hybrid/ask?space=user','POST',{question:'confie cette mission à Hermes',archive:{id:'voice-2',turn:0}},auth)).status,422);
eq((await request('/hybrid/ask?space=user','POST',{question:'bonjour',archive:{id:'voice-2',turn:0}},auth)).status,422);
const ordinary=await fetch(origin+'/api/jarvis/ask',{method:'POST',body:'{"question":"bonjour"}'});eq((await ordinary.json()).ordinary,true);eq(legacy,1);
eq((await request('/hybrid/ask?space=user','POST',{question:'demande à Hermes de vérifier la configuration DoseLab',history:['private'],archive:{id:'voice-2',turn:0}},auth)).status,400);
await configure({enabled:false});eq((await request('/session')).status,404);
console.log(JSON.stringify({passed:true,assertions,real_http:true,upstream:'simulated',model_calls:0}));
}finally{await close(privateServer);await close(gateway);await rm(dir,{recursive:true})}
