// Actual candidate dispatch/handleApi source in VM; all effects injected as stubs.
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {EventEmitter} from 'node:events';
import {Readable} from 'node:stream';
import {centralGateway} from './gateway-security.mjs';
import {requestIdentity} from './gateway-route-policy.mjs';
import {sessionRegistry} from './jarvis-session-auth.mjs';
const raw=await readFile('./docs/phase6d/candidate-server-routing.js.txt','utf8');
const functions=raw.replace(raw.slice(raw.indexOf('async function serveStatic('),raw.indexOf('async function dispatchRequest(')),'');
let shellStubs=0,physicalStubs=0,hybridStubs=0;
const context={URL,requestIdentity,sendJson:(res,s,data)=>{res.writeHead(s);res.end(JSON.stringify(data))},
 readBody:async()=>JSON.stringify({project:'allowed',power:1000}),
 triggerEspDosingCalibration:async()=>{physicalStubs++;return {synthetic:true}},
 setS9PowerTarget:async()=>{physicalStubs++;return {synthetic:true}},
 startRun:async()=>{shellStubs++;return {id:'mock',events:[]}},
 handleJarvis:async(req,res,url)=>{hybridStubs++;res.writeHead(200);res.end(JSON.stringify({engine:'hybrid',questionRoute:url.pathname}))},
 handlePaper:()=>{throw Error('unexpected')},handleAstro:()=>{throw Error('unexpected')},handleGerman:()=>{throw Error('unexpected')},
};
const dispatch=vm.runInNewContext(functions+'\ndispatchRequest',context);
const t='x'.repeat(43),origin='https://gateway.test';
const sessions=sessionRegistry({origin,credentials:[{subject:'human',sha256:createHash('sha256').update(t).digest('hex'),expiresAt:Date.now()+60000}],grants:new Map([['human',['user']]]),roles:new Map([['human',['runs.create','physical.dosing.calibrate','physical.s9.power','conversation']]])});
class Res extends EventEmitter{removeHeader(){}writeHead(s){this.status=s;this.headersSent=true}end(b){this.body=b;this.emit('finish')}destroy(){this.destroyed=true;this.emit('close')}}
let resourcePermit=false,physicalPermit=false;
const guard=centralGateway({sessions,dispatch:(req,res,url)=>dispatch(req,res,'https'),resource:async()=>resourcePermit,physicalApproval:async()=>physicalPermit});
async function call(method,url,auth=true){const req=Readable.from([]);req.method=method;req.url=url;req.headers={host:'gateway.test',origin,...(auth?{authorization:'Bearer '+t}:{})};const res=new Res();await guard(req,res,new URL(origin+url));return res}
assert.equal((await call('POST','/api/runs',false)).status,401);
assert.equal((await call('POST','/api/runs')).status,403);assert.equal(shellStubs,0);
assert.equal((await call('POST','/api/dosing-calibration/run')).status,403);assert.equal(physicalStubs,0);
resourcePermit=true;
assert.equal((await call('POST','/api/dosing-calibration/run')).status,403);assert.equal(physicalStubs,0);
physicalPermit=true;
assert.equal((await call('POST','/api/dosing-calibration/run')).status,200);assert.equal(physicalStubs,1);
assert.equal((await call('POST','/api/s9/power')).status,200);assert.equal(physicalStubs,2);
assert.equal((await call('POST','/api/runs')).status,201);assert.equal(shellStubs,1);
assert.equal((await call('POST','/api/jarvis/ask?space=user')).status,200);assert.equal(hybridStubs,1);
assert.equal((await call('POST','/api/future-danger')).status,403);
console.log(JSON.stringify({passed:true,actual_candidate_gateway_dispatch:true,shell_calls_real:0,physical_calls_real:0,stub_shell_calls:shellStubs,stub_physical_calls:physicalStubs,ordinary_hybrid_dispatch_preserved:true}));
