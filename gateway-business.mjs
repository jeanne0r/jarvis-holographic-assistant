// Server-only business adapters. Repository/service objects are trusted host dependencies.
import {createHash,randomUUID} from 'node:crypto';
import {requestIdentity,classify,routeMatrix} from './gateway-route-policy.mjs';
const deny=()=>Object.assign(Error('Resource denied'),{status:403});
export function businessACL(policy){
 const projectGrants=structuredClone(policy.projects||{}),scopes=structuredClone(policy.scopes||{});
 const permitted=(id,permission,space)=>id?.kind==='human'&&id.roles.includes(permission)&&(!space||id.spaces.includes(space));
 const projects=(id,write=false)=>Object.entries(projectGrants).filter(([_,g])=>(g[write?'writers':'readers']||[]).includes(id.subject)).map(([key])=>key);
 function resource(id,row,write=false){
  if(!id||!row||!id.spaces.includes(row.space)||!(scopes[row.space]?.[write?'writers':'readers']||[]).includes(id.subject))return false;
  if(row.project&&!projects(id,write).includes(row.project))return false;
  if(row.space==='commun')return (scopes[row.space]?.[write?'writers':'readers']||[]).includes(id.subject);
  return row.owner===id.subject||(row[write?'writers':'readers']||[]).includes(id.subject);
 }
 return Object.freeze({permitted,projects,resource,spaces(id,write=false){return id.spaces.filter(s=>(scopes[s]?.[write?'writers':'readers']||[]).includes(id.subject))}});
}
export async function readJSON(req,max=64000){
 if(req.headers['transfer-encoding']||!/^\d+$/.test(req.headers['content-length']||'')||Number(req.headers['content-length'])>max)throw Object.assign(Error('Body bound'),{status:413});
 const parts=[];let n=0;for await(const p of req){n+=p.length;if(n>max)throw Object.assign(Error('Body bound'),{status:413});parts.push(p)}
 if(n!==Number(req.headers['content-length']))throw Error('Body length');return JSON.parse(Buffer.concat(parts).toString('utf8')||'{}');
}
export function authorizedRepository(acl,repo){
 return Object.freeze({
  async list(id,kind,{space,project,...filters}={}){
   if(space&&!acl.spaces(id).includes(space)||project&&!acl.projects(id).includes(project))throw deny();
   // Query restriction precedes reading content; output filtering is defense in depth.
   const rows=await repo.list(kind,{...filters,owner:id.subject,spaces:space?[space]:acl.spaces(id),projects:project?[project]:acl.projects(id)});
   return rows.filter(r=>acl.resource(id,r)&&(!space||r.space===space)&&(!project||r.project===project));
  },
  async get(id,kind,key,write=false){const meta=await repo.metadata(kind,key);if(!acl.resource(id,meta,write))throw deny();const value=await repo.get(kind,key);if(!acl.resource(id,value,write))throw deny();return value},
  async create(id,kind,data){if(!acl.spaces(id,true).includes(data.space)||data.project&&!acl.projects(id,true).includes(data.project))throw deny();return repo.create(kind,{...data,owner:id.subject})},
  async mutate(id,kind,key,change){const meta=await repo.metadata(kind,key);if(!acl.resource(id,meta,true))throw deny();if(change.target&&!acl.spaces(id,true).includes(change.target))throw deny();return repo.mutate(kind,key,change,{expectedOwner:meta.owner,expectedVersion:meta.version,actor:id.subject})},
 });
}
export function businessAdapters({acl,repo,services,physicalApprovals,syncSources={},admitSynthetic,serviceBindings={}}){
 const store=authorizedRepository(acl,repo);
 const supported=new Set(['/api/projects','/api/tree','/api/chat','/api/runs','/api/runs/:id','/api/runs/:id/events',...['ask','docs','doc','notes','move','sync','import','memory/map','memory/status','conversations/record','capabilities/run','evolution/status','evolution/diff'].map(x=>'/api/jarvis/'+x)]);
 const auxiliary={
  '/api/mirror/apple':'calendar-config','/api/mirror/tasks':'task','/api/fridge/items/:id':'fridge-item','/api/fridge/items/:id/remove':'fridge-item',
  '/api/astro/connect':'astro-display','/api/german/answer':'exercise','/api/german/close':'exercise','/api/solana-paper/runs/:epoch/:file':'paper-archive',
 };
 for(const p of Object.keys(auxiliary))supported.add(p);
 for(const row of routeMatrix)if(!row.path.startsWith('/api/jarvis/')&&row.path!=='/api/health')supported.add(row.path);
 for(const p of ['/api/dosing-calibration/run','/api/s9/power'])supported.add(p);
 const keyFor=(url,body)=>body.id||url.searchParams.get('id')||url.pathname.split('/').filter(Boolean).at(-1);
 const send=(res,status,data)=>{if(data?.[Symbol.for('jarvis.private.response')]){res.writeHead(data.status,data.headers);return res.end(data.bytes)}res.writeHead(status,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify(data))};
 const service=async(name,id,params)=>{if(typeof services[name]!=='function')throw Object.assign(Error('Service unavailable'),{status:503});return services[name]({identity:id,...params})};
 return Object.freeze({
  resource:async({row})=>supported.has(row.path), // Enforcement lives in dispatch below, never legacy fall-through.
  physicalApproval:async()=>true, // Exact body-bound approval checked AFTER bounded parsing below, before any effects.
  async dispatch(req,res,url,next){
   const row=classify(req.method,url.pathname);if(!row||!supported.has(row.path))return next(req,res,url);
   const id=requestIdentity.get(req);if(!id)throw deny();const space=url.searchParams.get('space')||id.defaultSpace;
   try{
    if(!acl.permitted(id,row.permission,row.space?space:undefined))throw deny();
    if(row.path==='/api/jarvis/import'){
     if(!acl.spaces(id,true).includes(space))throw deny();
     const size=Number(req.headers['content-length']);if(!Number.isSafeInteger(size)||size<1||size>3*1024**3||req.headers['transfer-encoding'])throw Object.assign(Error('Import bound'),{status:413});
     return send(res,200,await service('memory.import',id,{space,stream:req,maxBytes:3*1024**3}));
    }
    const data=['GET','HEAD'].includes(req.method)?{}:await readJSON(req,180000);
    if(row.path==='/api/projects')return send(res,200,{projects:(await service('projects.list',id,{allowed:acl.projects(id)})).filter(p=>acl.projects(id).includes(typeof p==='string'?p:p.name))});
    if(row.path==='/api/tree'){
     const project=url.searchParams.get('project')||'default';if(!acl.projects(id).includes(project))throw deny();
     return send(res,200,{project,tree:await service('files.tree',id,{project})});
    }
    if(row.path==='/api/chat'){
     const project=url.searchParams.get('project')||'default';if(!acl.projects(id,req.method!=='GET').includes(project))throw deny();
     return send(res,200,{project,messages:await service(req.method==='GET'?'chat.read':'chat.clear',id,{project})});
    }
    if(row.path==='/api/runs'&&req.method==='GET')return send(res,200,{runs:await store.list(id,'run')});
    if(row.path==='/api/runs'&&req.method==='POST'){
     if(Object.keys(data).some(k=>!['project','prompt'].includes(k))||!acl.projects(id,true).includes(data.project)||typeof data.prompt!=='string')throw deny();
     return send(res,202,await service('codex.submit',id,{project:data.project,prompt:data.prompt}));
    }
    if(row.path.startsWith('/api/runs/:id')){
     const key=url.pathname.split('/')[3],run=await store.get(id,'run',key);
     if(row.path.endsWith('/events')){const after=Number(req.headers['last-event-id']||'0');if(!Number.isSafeInteger(after)||after<0)throw Error('Event cursor');const events=(run.events||[]).map((e,i)=>({seq:e.seq||i+1,data:e.data||e})).filter(e=>e.seq>after);res.writeHead(200,{'content-type':'text/event-stream','cache-control':'no-store'});return res.end(events.map(e=>'id: '+e.seq+'\ndata: '+(typeof e.data==='string'?e.data:JSON.stringify(e.data))+'\n\n').join('')||': idle\n\n')}return send(res,200,run);
    }
    const action=row.path.slice('/api/jarvis/'.length);
    if(action==='docs'){const docs=await store.list(id,'document',{space,q:url.searchParams.get('q')||''});const counts={};for(const d of docs)counts[d.kind||'Mémoire']=(counts[d.kind||'Mémoire']||0)+1;return send(res,200,{docs,total:docs.length,counts,lastSync:null})}
    if(action==='doc')return send(res,200,await store.get(id,'document',url.searchParams.get('id')));
    if(action==='notes')return send(res,201,await store.create(id,'document',{...data,space}));
    if(action==='move')return send(res,200,await store.mutate(id,'document',data.id,{target:data.target}));
    if(action==='memory/map'||action==='memory/status'){
     const items=await store.list(id,'memory',{space});return send(res,200,await service(action,id,{space,items,offset:url.searchParams.get('offset'),allowedSpaces:acl.spaces(id)}));
    }
    if(action==='sync'||action==='import'){
     if(!acl.spaces(id,true).includes(space))throw deny();
     // No browser path or caller-selected source root. Host chooses sources by actor+space.
     if(action==='sync'&&Object.keys(data).length||action==='import'&&Object.keys(data).some(k=>!['upload_id'].includes(k)))throw deny();
     return send(res,200,await service('memory.'+action,id,{space,sources:syncSources[id.subject]?.[space]||[],uploadId:data.upload_id}));
    }
    if(action==='conversations/record'){
     const key=data.id;const old=await repo.metadata('conversation',key);
     if(old&&!acl.resource(id,old,true))throw deny();
     if(!acl.spaces(id,true).includes(space))throw deny();
     return send(res,200,await service('conversation.record',id,{space,data,expectedOwner:old?.owner||id.subject}));
    }
    if(action==='ask'){
     if(typeof data.question!=='string'||!data.question.trim()||data.question.length>2000)throw Error('Question bound');
     if(admitSynthetic){const admitted=await admitSynthetic(id,space,data);if(admitted)return send(res,admitted.status,admitted.body)}
     const context={space,identity:id,history:Array.isArray(data.history)?data.history.slice(-12):[],channel:data.channel==='voice'?'voice':'written',view:['galaxy','library','atelier','chat'].includes(data.view)?data.view:'chat',application:typeof data.application==='string'?data.application.slice(0,80):null};
     const archiveId=data.archive?.id||randomUUID(),turn=Number.isSafeInteger(data.archive?.turn)?data.archive.turn:0;
     if(!/^[a-fA-F0-9-]{36}$/.test(archiveId)||turn<0||turn>99999)throw Error('Conversation identity bound');
     const old=await repo.metadata('conversation',archiveId);if(old&&!acl.resource(id,old,true))throw deny();
     const journal={id:archiveId,turn,space,channel:context.channel,user:data.question,assistant:'',status:'partial'};
     await service('conversation.record',id,{space,data:{...journal,revision:1},expectedOwner:old?.owner||id.subject});
     const controller=new AbortController(),stop=()=>{if(!res.writableEnded)controller.abort()};res.once('close',stop);
     try{const result=await service('hybrid.answer',id,{question:data.question,context,signal:controller.signal});controller.signal.throwIfAborted();await service('conversation.record',id,{space,data:{...journal,assistant:result.answer,revision:2,status:'complete'},expectedOwner:id.subject});return send(res,200,result)}finally{res.removeListener('close',stop)}
    }
    if(action==='capabilities/run')return send(res,200,await service('tools.call',id,{space,name:data.name,args:data.args||{}}));
    if(action.startsWith('evolution/')){const resource=await store.get(id,'evolution',url.searchParams.get('id'));return send(res,200,await service(action,id,{resource}))}
    if(row.physical){
     // No approval token supplied by a model. This is a separate human approval store.
     const fingerprint=createHash('sha256').update(JSON.stringify([row.path,id.subject,data])).digest('hex');
     if(!physicalApprovals||!await physicalApprovals.consume({subject:id.subject,permission:row.permission,fingerprint}))throw deny();
     return send(res,200,await service('physical.execute',id,{route:row.path,data,fingerprint}));
    }
    const kind=auxiliary[row.path];
    if(row.path==='/api/mirror/tasks'&&['GET','POST'].includes(req.method)){const binding=serviceBindings[id.subject]?.[row.path];if(!binding)throw deny();const resource=await repo.metadata('service-account',binding);if(!acl.resource(id,resource,req.method!=='GET'))throw deny();return send(res,200,await service(row.path,id,{data,resource,method:req.method,path:url.pathname,parameters:Object.fromEntries(url.searchParams)}))}
    if(kind){
     const index=row.path.split('/').indexOf(':id');
     const key=index>=0?url.pathname.split('/')[index]:(data.id||url.searchParams.get('id')||serviceBindings[id.subject]?.[row.path]);
     if(index>=0&&data.id&&data.id!==key)throw deny();
     const metadata=await repo.metadata(kind,key);
     if(!acl.resource(id,metadata,req.method!=='GET'))throw deny();
     return send(res,200,await service(row.path,id,{data,key,resource:metadata,method:req.method,path:url.pathname,parameters:Object.fromEntries(url.searchParams)}));
    }
    if(!row.path.startsWith('/api/jarvis/')){
     const binding=serviceBindings[id.subject]?.[row.path];if(!binding)throw deny();
     const account=await repo.metadata('service-account',binding);if(!acl.resource(id,account,!['GET','HEAD'].includes(req.method)))throw deny();
     return send(res,200,await service(row.path,id,{resource:account,data,parameters:Object.fromEntries(url.searchParams),path:url.pathname,method:req.method}));
    }
    throw deny();
   }catch(error){return send(res,error.status||400,{error:error.status===403?'Resource denied':'Operation unavailable'})}
  },
 });
}
