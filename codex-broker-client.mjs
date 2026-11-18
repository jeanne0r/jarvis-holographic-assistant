// Gateway-side transport: no child_process, CLI config, filesystem or shell execution.
import net from 'node:net';
import {randomUUID} from 'node:crypto';
export function codexBrokerClient({socketPath,credential,sessions,projects,timeoutMs=1500}){
 if(!socketPath?.startsWith('/')||typeof credential!=='string'||credential.length<32||timeoutMs<1||timeoutMs>5000)throw Error('Private broker configuration');
 function request(identity,method,args,permission){
  if(identity.kind!=='human'||!sessions.isActive(identity,permission,args.space||identity.defaultSpace))throw Error('Broker human authority denied');
  const {space,...payload}=args,raw=Buffer.from(JSON.stringify({credential,method,args:{...payload,subject:identity.subject}}));
  if(raw.length>64000)throw Error('Broker bound');
  return new Promise((resolve,reject)=>{
   const socket=net.createConnection(socketPath);let bytes=Buffer.alloc(0),size;
   const timer=setTimeout(()=>socket.destroy(Error('Broker deadline')),timeoutMs);
   socket.on('connect',()=>{const header=Buffer.alloc(4);header.writeUInt32BE(raw.length);socket.write(Buffer.concat([header,raw]))});
   socket.on('data',part=>{bytes=Buffer.concat([bytes,part]);if(bytes.length>65540)return socket.destroy(Error('Broker response bound'));if(size===undefined&&bytes.length>=4){size=bytes.readUInt32BE();if(size>65536)return socket.destroy(Error('Broker bound'))}if(size!==undefined&&bytes.length>=size+4){try{const reply=JSON.parse(bytes.subarray(4,4+size));if(!reply.ok)throw Error('Broker denied');resolve(reply.value);socket.end()}catch(e){socket.destroy(e)}}});
   socket.on('error',reject);socket.on('close',()=>{clearTimeout(timer);if(size===undefined||bytes.length<size+4)reject(Error('Broker interrupted; no replay'))});
  });
 }
 return Object.freeze({call:(id,method,args)=>request(id,method,args,({submit:'runs.create',get:'runs.read',list:'runs.read',cancel:'runs.cancel'})[method]||'__denied__'),async answer({identity,question,context,signal}){
  signal?.throwIfAborted();const project=projects[identity.subject]?.[context.space];if(!project)throw Error('No bound project');
  const contextData=Object.fromEntries(Object.entries(context).filter(([k])=>['space','history','channel','view','application'].includes(k)));
  const mission=await request(identity,'submit',{project,key:randomUUID(),payload:{question,context:contextData},space:context.space},'conversation');
  // Preserve ordinary hybrid conversation: wait asynchronously for this exact
  // admitted job, never recreate it on transport failure or interruption.
  const end=Date.now()+300000;
  while(Date.now()<end){
   if(signal?.aborted){await request(identity,'cancel',{job:mission.id,space:context.space},'conversation').catch(()=>{});signal.throwIfAborted()}
   const row=await request(identity,'get',{job:mission.id,space:context.space},'conversation');
   if(row.state==='completed'){const result=typeof row.result==='string'?JSON.parse(row.result):row.result;if(typeof result?.answer!=='string'||typeof result?.speech!=='string')throw Error('Incomplete Codex result');return result}
   if(['uncertain','failed','cancelled','cancel_requested'].includes(row.state))throw Error('Codex stopped; no automatic replay');
   await new Promise(r=>setTimeout(r,100));
  }
  throw Error('Codex deadline; inspect existing job before retry');
 }});
}
