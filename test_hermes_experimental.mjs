import assert from 'node:assert/strict';
import {Readable} from 'node:stream';
import {experimentalHermes} from './jarvis-hermes-experimental.mjs';
let calls=[];
const client={scope:'private',async request(method,path,options){calls.push({method,path,...options});return {status:method==='POST'?202:200,body:{mission_id:'synthetic-id',state:'queued'}}}};
const clients=new Map([['alice',new Map([['alice',client]])]]);
function fixture(method='POST',path='/missions?space=alice',data={objective:'Analyse synthetic DoseLab'}){
 const raw=JSON.stringify(data);const req=Readable.from([Buffer.from(raw)]);req.method=method;req.headers={'content-length':String(Buffer.byteLength(raw)),'idempotency-key':'fixture1'};
 const res={writeHead(status,headers){this.status=status;this.headers=headers},end(body){this.body=body}};
 return {req,res,url:new URL('http://localhost/api/jarvis/hermes'+path)};
}
async function call(handler,f){assert.equal(await handler(f.req,f.res,f.url),true);return f.res}
const handler=experimentalHermes({enabled:true,authenticate:async()=>({subject:'alice',spaces:['alice']}),clients});
assert.equal((await call(experimentalHermes(),fixture())).status,404);
assert.equal((await call(experimentalHermes({enabled:true,authenticate:async()=>null,clients}),fixture())).status,401);
assert.equal((await call(handler,fixture('POST','/missions?space=bob'))).status,403);
assert.equal((await call(handler,fixture('POST','/missions?space=alice',{objective:'x',allowed_tools:['shell']}))).status,400);
let r=await call(handler,fixture());assert.equal(r.status,202);assert.equal(JSON.parse(r.body).state,'queued');
assert.equal(calls[0].body.definition.budget.cost_micros,0);assert.equal(calls[0].body.definition.allowed_tools.includes('shell'),false);
assert.equal(calls[0].body.definition.budget.local_tokens,98304);
assert.equal((await call(handler,fixture('GET','/missions/synthetic-id?space=alice'))).status,200);
assert.equal((await call(handler,fixture('GET','/missions/synthetic-id/events?space=alice'))).status,200);
assert.equal((await call(handler,fixture('POST','/missions/synthetic-id/cancel?space=alice'))).status,202);
assert.equal((await call(handler,fixture('POST','/missions/synthetic-id/approvals?space=alice'))).status,404);
const off=experimentalHermes({enabled:true,authenticate:async()=>({subject:'alice',spaces:['alice']}),clients:new Map([['alice',new Map([['alice',{request:async()=>{throw Error('offline')}}]])]])});
assert.equal((await call(off,fixture())).status,503);
const stalled=experimentalHermes({enabled:true,timeoutMs:5,authenticate:async()=>({subject:'alice',spaces:['alice']}),clients:new Map([['alice',new Map([['alice',{request:()=>new Promise(()=>{})}]])]])});
assert.equal((await call(stalled,fixture())).status,503);
console.log('PASS experimental adapter: disabled/auth/ACL/admission/fixed budget/read/events/cancel/approval denied/offline; mocked bridge, no gateway mounted');
