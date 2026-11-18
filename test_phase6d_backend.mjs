// Exercise the actual prepared handler body without executing imports/timers.
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {Readable} from 'node:stream';
import {EventEmitter} from 'node:events';
import {trustedRequests} from './jarvis-session-auth.mjs';
import {requestIdentity} from './gateway-route-policy.mjs';
import {voiceOwners} from './voice-session-owner.mjs';
const source=await readFile(new URL(process.argv.includes('--minimal')?'./docs/phase6d/candidate-backend.mjs.txt':'./backend.mjs',import.meta.url),'utf8');
const handler=source.slice(source.indexOf('export async function handleJarvis')).replace('export ','');
let calls=0,created=0;
const json=(res,status,data)=>{res.status=status;res.body=data};
const handle=vm.runInNewContext('('+handler+')',{
 trustedRequests,requestIdentity,voiceOwnership:voiceOwners(),json,body:async req=>{let s='';for await(const c of req)s+=c;return Buffer.from(s)},
 speechSession:space=>({sessionId:'voice-'+(++created),space}),speechStatus:()=>({engine:'hybrid'}),
 transcribeSpeech:async()=>{calls++;return {text:'synthetic'}},speakSpeech:async()=>{calls++;return Buffer.from('WAV')},streamSpeech:async()=>{calls++},
 Buffer,AbortController,Error,SyntaxError,JSON,Set,Map,Date,
});
function req(id,body,headers={}){const r=Readable.from([Buffer.from(body)]);r.method='POST';r.headers={origin:'https://jarvis.test',host:'jarvis.test',...headers};r.socket={encrypted:true};requestIdentity.set(r,id);return r}
const alice={subject:'a',kind:'human',sessionHandle:'a1',spaces:['user'],roles:['voice']};
const bob={...alice,subject:'b',sessionHandle:'b1'};
async function run(action,id,data,headers={}){const res=new EventEmitter();res.writeHead=status=>res.status=status;res.end=data=>res.body=data;res.destroyed=false;await handle(req(id,JSON.stringify(data),headers),res,new URL('https://jarvis.test/api/jarvis/'+action+'?space=user'));return res}
const made=await run('voice/session',alice,{});assert.equal(made.status,200);const sessionId=made.body.sessionId;
assert.equal((await run('voice/transcribe',bob,{}, {'x-jarvis-voice-session':sessionId})).status,403);
assert.equal((await run('voice/speak',bob,{sessionId,text:'test'})).status,403);
assert.equal(calls,0);
assert.equal((await run('voice/transcribe',alice,{}, {'x-jarvis-voice-session':sessionId})).status,200);assert.equal(calls,1);
assert.equal((await run('voice/speak',{...alice,sessionHandle:'new-session'},{sessionId,text:'test'})).status,403);
if(!process.argv.includes('--minimal')){const r=req(alice,'{}');r.socket={encrypted:false};trustedRequests.set(r,{...alice,proxyOrigin:'https://jarvis.test'});const response=new EventEmitter();await handle(r,response,new URL('https://jarvis.test/api/jarvis/voice/session?space=user'));assert.equal(response.status,200)}
console.log(JSON.stringify({passed:true,actual_prepared_handler_body:true,production_module_imported:false,providers_simulated:true,same_space_voice_theft_denied:true}));
