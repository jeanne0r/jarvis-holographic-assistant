// Private storage transport only. No process creation and no direct database access.
import net from 'node:net';
import {randomUUID} from 'node:crypto';
export function storageClient({socketPath,credential,identity,timeoutMs=30000}){
 if(!socketPath?.startsWith('/')||typeof credential!=='string'||credential.length<32||identity?.kind!=='human'||!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>30000)throw Error('Storage binding');
 return (method,args={})=>new Promise((resolve,reject)=>{
  const raw=Buffer.from(JSON.stringify({credential,method,args:{...args,subject:identity.subject}}));
  if(raw.length>4*1024**2)return reject(Error('Storage frame bound'));
  const socket=net.createConnection(socketPath);let received=Buffer.alloc(0),size,done=false;
  const timer=setTimeout(()=>socket.destroy(Error('Storage deadline; do not replay writes')),timeoutMs);
  socket.on('connect',()=>{const h=Buffer.alloc(4);h.writeUInt32BE(raw.length);socket.write(Buffer.concat([h,raw]))});
  socket.on('data',part=>{received=Buffer.concat([received,part]);if(received.length>4*1024**2+4)return socket.destroy(Error('Storage response bound'));if(size===undefined&&received.length>=4){size=received.readUInt32BE();if(size<1||size>4*1024**2)return socket.destroy(Error('Storage frame'))}if(size!==undefined&&received.length>=size+4){try{const r=JSON.parse(received.subarray(4,size+4));if(!r.ok)throw Error('Storage operation denied');done=true;resolve(r.value);socket.end()}catch(e){socket.destroy(e)}}});
  socket.on('error',reject);socket.on('close',()=>{clearTimeout(timer);if(!done)reject(Error('Storage interrupted; no automatic replay'))});
 });
}
export function persistentBindings({identity,rpc,broker,hybrid,tools,files,accountServices={},physical}){
 const common={space:identity.space||identity.defaultSpace};
 const call=(name,args={})=>rpc(name,{...common,...args});
 const runRow=r=>{const payload=typeof r.payload==='string'?JSON.parse(r.payload):r.payload;if(payload?.context?.space!==common.space)throw Error('Run space denied');return {...r,space:payload.context.space,version:1,status:r.state}};
 const run=async key=>runRow(await broker.call(identity,'get',{job:key,space:common.space}));
 const repo={
  list:(kind,query)=>kind==='run'?broker.call(identity,'list',{space:common.space}).then(rows=>rows.flatMap(r=>{try{return [runRow(r)]}catch{return []}})):call('list',{kind,space:query.space||common.space,query}),
  metadata:async(kind,id)=>kind==='run'?run(id):kind==='memory'?call('fact.metadata',{data:{key:id}}):call('metadata',{kind,id}),
  get:(kind,id)=>kind==='run'?run(id):call('get',{kind,id}),
  create:(kind,data)=>call('create',{kind,data}),
  mutate:async(kind,id,data,guard)=>{
   if(kind==='memory')id=JSON.stringify([common.space,id]);
   return call('mutate',{kind,id,data,guard});
  },
 };
 const memory=async(action,data)=>{
  const space=data.space||common.space;
  if(action==='list')return call('facts',{space});
  if(!['save','forget','save_correction'].includes(action))throw Error('Fact action');
  // No automatic promotion of a model correction; sidecar status remains inferred.
  return call(action==='forget'?'fact.forget':'fact.save',{space,data});
 };
 memory.metadata=(key,space)=>call('fact.metadata',{space,data:{key}});
 const services={
  'projects.list':()=>call('projects.list'),
  'files.tree':({project})=>files.tree({project}),
  'chat.read':({project})=>call('chat.read',{project}),
  'chat.clear':({project})=>call('chat.clear',{project}),
  'conversation.record':({space,data})=>call('conversation.record',{space,data}),
  'codex.submit':({project,prompt})=>broker.call(identity,'submit',{project,key:randomUUID(),payload:{question:prompt,context:{space:common.space}},space:common.space}),
  'memory/status':async({space})=>({persistent:true,savedFacts:(await call('facts',{space})).length,index:{state:'unknown'}}),
  'memory/map':({space,offset})=>call('map',{space,offset}),
  'memory.sync':({space})=>call('sync',{space}),
  'memory.import':async({space,stream,maxBytes})=>{
   const size=Number(stream.headers['content-length']);if(size>maxBytes)throw Error('Import bound');
   const u=await call('upload.begin',{space,size});let offset=0;
   try{for await(const part of stream){for(let i=0;i<part.length;i+=32768){const chunk=part.subarray(i,i+32768);await call('upload.chunk',{space,upload:u.upload,offset,chunk:chunk.toString('base64')});offset+=chunk.length}}
    if(offset!==size)throw Error('Incomplete import');return await call('upload.finish',{space,upload:u.upload});
   }catch(e){await call('upload.abort',{space,upload:u.upload}).catch(()=>{});throw e}
  },
  'hybrid.answer':hybrid,'tools.call':({space,name,args})=>tools(identity,space,name,args),
  'physical.execute':physical||(()=>{throw Error('Physical service not commissioned')}),
  ...accountServices,
 };
 return {repo,services,memory};
}
