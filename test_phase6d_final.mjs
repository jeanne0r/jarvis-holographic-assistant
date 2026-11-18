import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {EventEmitter} from 'node:events';
import {Readable} from 'node:stream';
import {sessionRegistry} from './jarvis-session-auth.mjs';
import {routeMatrix} from './gateway-route-policy.mjs';
import {businessACL,businessAdapters,authorizedRepository} from './gateway-business.mjs';
import {toolAuthority,scopedMemoryStore} from './gateway-tool-authority.mjs';
import {authorizedHybrid} from './gateway-hybrid-authorized.mjs';
import {composeGateway,syntheticAdmission} from './gateway-final-compose.mjs';
const origin='https://final.test',token='s'.repeat(43),bobToken='b'.repeat(43),hash=t=>createHash('sha256').update(t).digest('hex');
const permissions=[...new Set(routeMatrix.map(r=>r.permission)),'memory.write','media.browser','physical.ha.control','physical.media.control'];
const creds=[{subject:'alice',sha256:hash(token),expiresAt:Date.now()+60000},{subject:'bob',sha256:hash(bobToken),expiresAt:Date.now()+60000}];
const grants=new Map([['alice',['user','commun']],['bob',['user']]]),roles=new Map([['alice',permissions],['bob',permissions.filter(x=>x!=='missions.approve')]]);
const sessions=sessionRegistry({credentials:creds,grants,roles,origin,cookiePath:'/api'});
const acl=businessACL({projects:{dose:{readers:['alice','bob'],writers:['alice']},other:{readers:['bob'],writers:['bob']}},scopes:{user:{readers:['alice','bob'],writers:['alice','bob']},commun:{readers:['alice'],writers:['alice']}}});
const rows=[{id:'doc-a',owner:'alice',space:'user',project:'dose',version:1,kind:'Codex',title:'synthetic-a'},{id:'doc-b',owner:'bob',space:'user',project:'other',version:1,title:'synthetic-b'},{id:'shared',owner:'house',space:'commun',version:1,title:'shared'}];
const queries=[],effects=[],calls=[];let modelCalls=0,brokerCalls=0,bridgeCalls=0;
const repo={metadata:async(kind,id)=>rows.find(x=>x.id===id),get:async(kind,id)=>rows.find(x=>x.id===id),list:async(kind,q)=>{queries.push(q);return rows},create:async(kind,data)=>{const row={...data,id:'new',version:1};rows.push(row);return row},mutate:async(kind,key,data,guard)=>{const row=rows.find(x=>x.id===key);assert.equal(guard.expectedOwner,row.owner);assert.equal(guard.expectedVersion,row.version);row.version++;if(data.target)row.space=data.target;return {moved:true,space:row.space}}};
const physicalApprovals={allowed:null,async consume(p){if(JSON.stringify(p)!==this.allowed)return false;this.allowed=null;return true}};
const store=authorizedRepository(acl,repo);
const tools=toolAuthority({sessions,acl,memory:store,physicalApprovals,handlers:{piloter_home_assistant:async()=>{effects.push('FAKE_HA');return {simulated:true}},medias_jarvis:async()=>({clientAction:{type:'media'}}),web_jarvis:async()=>({url:'https://example.test'})}});
const services={
 'projects.list':async()=>[{name:'dose'},{name:'other'},{name:'forbidden'}],
 'files.tree':async({project})=>[{name:project+'.txt'}], 'chat.read':async()=>[{text:'synthetic'}], 'chat.clear':async()=>[],
 'codex.submit':async()=>({id:'new-job',state:'queued'}),
 'memory/map':async({items})=>({points:items}), 'memory/status':async({items})=>({savedFacts:items.length}),
 'memory.sync':async p=>{calls.push(p);return {changed:0}},'memory.import':async({stream})=>{let n=0;for await(const c of stream)n+=c.length;return {imported:n}},
 'conversation.record':async p=>{calls.push(p);return {saved:true}},
 'evolution/status':async({resource})=>resource,'evolution/diff':async()=>({patch:'synthetic'}),
 'physical.execute':async()=>{effects.push('FAKE_PHYSICAL');return {simulated:true}},
 'tools.call':async({identity,space,name,args})=>tools(identity,space,name,args),
};
for(const row of routeMatrix)if(!row.path.startsWith('/api/jarvis/'))services[row.path]=async()=>({synthetic:true});
services['hybrid.answer']=authorizedHybrid({acl,sessions,tools,toolDeclarations:[],memoryStore:async()=>[],broker:{answer:async({identity})=>{assert.equal(identity.subject,'alice');brokerCalls++;return {answer:'Codex synthétique',speech:'Codex synthétique',sourceIds:[],action:{type:'none'}}}},dependencies:{classify:async q=>q==='technique'?'codex':'gemini',gemini:async()=>{modelCalls++;return {answer:'Gemini simulé',speech:'Gemini simulé',sourceIds:[],action:{type:'none'}}}}});
const client={scope:'private',workerStatus:async()=>({state:'unknown',fresh:false,dispatch_allowed:false}),request:async(method,path)=>{bridgeCalls++;return {status:method==='POST'?202:200,body:path.endsWith('/results')?{events:[{kind:'completed',data:JSON.stringify({output:'Date modèle 2023-11-15'})}]}:path.endsWith('/canonical')?{projection:{schema:'canonical_metadata.v1',origin:'sqlite',selection_origin:'authenticated_host_tool_receipts',mission_id:'mission-one',receipt_ids:['host-receipt'],items:[]}}:path==='/v1/missions'&&method==='GET'?{items:[{id:'mission-one',state:'queued'}]}:path.endsWith('/approvals')?{state:'denied'}:{mission_id:'mission-one',state:'queued'}}}};
const clients=new Map([['alice',new Map([['user',client]])]]),flags={history:true,admission:false,hybrid:false};
const bindings={alice:Object.fromEntries(routeMatrix.filter(r=>!r.path.startsWith('/api/jarvis/')).map(r=>[r.path,'doc-a']))};
const business=businessAdapters({acl,repo,services,physicalApprovals,syncSources:{alice:{user:['synthetic-source']}},serviceBindings:bindings,admitSynthetic:syntheticAdmission({clients,flags,audit:async()=>{}})});
const guard=composeGateway({sessions,business,clients,approvalClients:new Map(),audit:async()=>{},flags,legacy:async(req,res)=>{res.writeHead(200);res.end(JSON.stringify({legacyTransport:true}))}});
class Res extends EventEmitter{constructor(){super();this.headers={}}removeHeader(){}writeHead(s,h={}){this.status=s;Object.assign(this.headers,h)}end(raw=''){this.raw=raw;try{this.body=JSON.parse(raw)}catch{}this.emit('finish')}destroy(){this.emit('close')}}
async function call(method,path,data,who='alice',extra={}){const raw=data===undefined?'':typeof data==='string'?data:JSON.stringify(data);const req=Readable.from(raw?[Buffer.from(raw)]:[]);req.url=path;req.method=method;req.headers={origin,authorization:'Bearer '+(who==='alice'?token:bobToken),'content-length':String(Buffer.byteLength(raw)),...extra};const res=new Res();await guard(req,res,new URL(origin+path));return res}
assert.equal((await call('GET','/api/projects')).body.projects.length,1);
assert.equal((await call('GET','/api/tree?project=other')).status,403);
assert.equal((await call('DELETE','/api/chat?project=dose',{},'bob')).status,403);
const docs=(await call('GET','/api/jarvis/docs?space=user')).body;assert.equal(docs.total,1);assert.equal(docs.docs[0].id,'doc-a');assert.equal(queries.at(-1).owner,'alice');
assert.equal((await call('GET','/api/jarvis/doc?space=user&id=doc-b')).status,403);
assert.equal((await call('POST','/api/jarvis/move?space=user',{id:'doc-b',target:'commun'})).status,403);
assert.equal((await call('POST','/api/jarvis/sync?space=user',{})).status,200);assert.deepEqual(calls.at(-1).sources,['synthetic-source']);
assert.equal((await call('POST','/api/jarvis/sync?space=user',{path:'/home/user'})).status,403);
assert.equal((await call('POST','/api/jarvis/import?space=user','SYNTHETIC')).body.imported,9);
assert.equal((await call('POST','/api/jarvis/conversations/record?space=user',{id:'doc-b'})).status,403);
assert.equal((await call('GET','/api/jarvis/docs?space=commun',undefined,'bob')).status,403);
assert.equal((await call('POST','/api/runs',{project:'other',prompt:'x'})).status,403);
assert.equal((await call('POST','/api/runs',{project:'dose',prompt:'x',env:{TOKEN:'fake'}})).status,403);
assert.equal((await call('POST','/api/runs',{project:'dose',prompt:'x'})).status,202);
assert.equal((await call('GET','/api/runs/doc-b')).status,403);
assert.equal((await call('GET','/api/runs/doc-a/events')).headers['content-type'],'text/event-stream');
for(const q of ['bonjour','technique'])assert.equal((await call('POST','/api/jarvis/ask?space=user',{question:q,identity:{subject:'bob',roles:['admin']}})).status,200);
assert.equal(modelCalls,1);assert.equal(brokerCalls,1);assert.equal(bridgeCalls,0);
const phrase={question:'Jarvis, demande à Hermes de vérifier la configuration DoseLab.',archive:{id:'synthetic',turn:1}};
assert.equal((await call('POST','/api/jarvis/ask?space=user',phrase)).status,503);assert.equal(brokerCalls,1);
flags.admission=true;flags.hybrid=true;
assert.equal((await call('POST','/api/jarvis/ask?space=user',phrase)).status,202);assert.equal(brokerCalls,1);
flags.admission=false;
assert.equal((await call('GET','/api/jarvis/hermes/missions?space=user')).status,200);
assert.equal((await call('POST','/api/jarvis/hermes/missions?space=user',{template:'doselab-current'})).status,404);
assert.equal((await call('GET','/api/jarvis/hermes/availability?space=user')).body.fresh,false);
const result=(await call('GET','/api/jarvis/hermes/missions/mission-one/results?space=user')).body;assert.equal(result.canonical.selection_origin,'authenticated_host_tool_receipts');assert.ok(result.events[0].data.includes('2023-11-15'));
const identity=sessions.authenticate({headers:{authorization:'Bearer '+token}});
await assert.rejects(()=>tools(identity,'user','piloter_home_assistant',{entity_id:'fake.pump'}));assert.equal(effects.length,0);
const p='/api/dosing-calibration/run',body={calibration:'synthetic'};assert.equal((await call('POST',p,body)).status,403);
physicalApprovals.allowed=JSON.stringify({subject:'alice',permission:'physical.dosing.calibrate',fingerprint:hash(JSON.stringify([p,'alice',body]))});
assert.equal((await call('POST',p,body)).status,200);assert.deepEqual(effects,['FAKE_PHYSICAL']);assert.equal((await call('POST',p,body)).status,403);
// Every remaining historical account family is exercised with a bound fake account.
let families=0;
for(const row of routeMatrix){if(row.path.startsWith('/api/jarvis/')||row.path==='/api/health'||row.path.startsWith('/api/runs')||['/api/projects','/api/tree','/api/chat'].includes(row.path)||row.physical)continue;
 const path=row.path.replace(':id','doc-a').replace(':epoch','1234567890').replace(':file','manifest.json');
 const r=await call(row.method,path,row.method==='GET'||row.method==='HEAD'?undefined:{id:'doc-a'});
 assert.equal(r.status,200,JSON.stringify([row.method,path,r.body]));families++;
}
let rawWrites=0;
const rawFacts=async action=>{if(action!=='list')rawWrites++;return [{owner:'alice',space:'user',fact:'owned'},{owner:'bob',space:'user',fact:'private-other'}]};
const facts=scopedMemoryStore(identity,'user',acl,rawFacts,sessions);
assert.equal((await facts('list')).length,1);await assert.rejects(()=>facts('forget',{key:'foreign'}));assert.equal(rawWrites,0);
roles.set('alice',[]);sessions.updatePolicy({credentials:creds,grants,roles});
await assert.rejects(()=>tools(identity,'user','medias_jarvis',{target:'ici'}));assert.equal((await call('POST','/api/jarvis/ask?space=user',{question:'bonjour'})).status,403);
// Real Unix MCP transport, with server-bound actor and a fake read-only handler.
const {toolsBroker}=await import('./codex-tools-broker.mjs');const {request:toolRequest}=await import('./codex-tool-proxy.mjs');
const {mkdtemp,rm}=await import('node:fs/promises');const {tmpdir}=await import('node:os');
const folder=await mkdtemp(tmpdir()+'/jarvis-tools-'),sock=folder+'/tools.sock';
let allowed=true;const endpoint=toolsBroker({identity:{subject:'bound-human'},space:'user',sessions:{isActive:()=>allowed},authority:async(id,space,name)=>{assert.equal(id.subject,'bound-human');assert.equal(space,'user');if(name!=='read')throw Error('Denied');return {synthetic:true}},declarations:[{name:'read'}]});
await new Promise(r=>endpoint.listen(sock,r));
try{const value=await toolRequest(sock,{method:'tools/call',params:{name:'read',arguments:{subject:'evil'}}});assert.ok(value.content[0].text.includes('synthetic'));allowed=false;assert.equal((await toolRequest(sock,{method:'tools/call',params:{name:'read'}})).isError,true)}finally{await new Promise(r=>endpoint.close(r));await rm(folder,{recursive:true,force:true})}
console.log(JSON.stringify({passed:true,account_route_pairs:families,hybrid_public_and_codex_simulated:true,server_lists_filtered:true,shared_space_acl:true,imports_streamed:true,one_session_registry:true,hermes_history_separate_from_admission:true,canonical_and_heartbeat_wired:true,physical_actions_real:0,remote_api_calls:0}));
