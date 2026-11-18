import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import http from 'node:http';
import {EventEmitter} from 'node:events';
import {createHash} from 'node:crypto';
import {centralGateway} from './gateway-security.mjs';
import {privateBackend} from './gateway-service-transport.mjs';
import {compatibilityService} from './gateway-compatibility-service.mjs';
const root=await mkdtemp(tmpdir()+'/jarvis-private-compat-'),hash=b=>createHash('sha256').update(b).digest('hex');
const credential='x'.repeat(43),identity={kind:'human',subject:'alice',space:'user',defaultSpace:'user',sessionHandle:'session:'+'a'.repeat(64)};let active=true,calls=0;
const app=compatibilityService({credential,origin:'https://jarvis.test',policyFor:async id=>id==='alice'?{spaces:['user'],roles:['voice']}:null,resourceFor:async()=>null,validateSession:async id=>active&&id.sessionHandle===identity.sessionHandle,handlers:new Map([['GET /api/jarvis/voice/status',{permission:'voice',handler:async(req,res)=>{calls++;res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify({simulated:true}))}}]])});
const server=http.createServer(app);
try{
 await new Promise(r=>server.listen(root+'/voice.sock',r));const client=privateBackend({socketPath:root+'/voice.sock',credential});
 assert.equal((await client({identity,method:'GET',path:'/api/jarvis/voice/status'})).status,200);
 active=false;assert.equal((await client({identity,method:'GET',path:'/api/jarvis/voice/status'})).status,403);assert.equal(calls,1);
 assert.equal((await client({identity,method:'POST',path:'/api/jarvis/ask',data:{question:'do something'}})).status,403);
 // Standalone login is explicitly added to reviewed HTML; original file unchanged.
 const html='<!doctype html><html><head></head><body>Fixture</body></html>';await writeFile(root+'/index.html',html);await writeFile(root+'/jarvis-auth.js','/* synthetic auth */');
 const guard=centralGateway({sessions:{handle:async()=>false,origin:'https://jarvis.test'},staticRoot:root,publicAssets:new Map([['/',{file:'index.html',type:'text/html',sha256:hash(html),bootstrapAuth:true}],['/jarvis/jarvis-auth.js',{file:'jarvis-auth.js',type:'application/javascript',sha256:hash('/* synthetic auth */')}]]),dispatch:()=>{throw Error('Unexpected API')}});
 const req={url:'/',method:'GET',headers:{}},res=new EventEmitter();res.writeHead=function(s){this.status=s};res.end=function(b){this.body=b};res.removeHeader=()=>{};
 await guard(req,res,new URL('https://jarvis.test/'));assert.equal(res.status,200);assert.ok(res.body.toString().includes('defer src="/jarvis/jarvis-auth.js"'));
 console.log(JSON.stringify({passed:true,private_http_unix_real:true,revoked_session_refused:true,legacy_ask_not_exposed:true,standalone_auth_bootstrap:true,providers_called:0}));
}finally{await new Promise(r=>server.close(r));await rm(root,{recursive:true,force:true})}
