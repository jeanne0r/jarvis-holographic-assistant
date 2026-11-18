// Explicit commissioning entry. No start/import by gateway; no equipment call on import.
import {readFile,writeFile,rename,open} from 'node:fs/promises';
import {createHash,randomUUID,timingSafeEqual} from 'node:crypto';
import {createServer} from 'node:http';
import {ownedJSON} from './gateway-security-mount.mjs';
import {powerBridge,fixedPowerTransport} from './s9-power-service.mjs';
import {privateBackend} from './gateway-service-transport.mjs';
export async function main(configFile){
 const cfg=await ownedJSON(configFile);
 if(cfg.commissioned!==true||cfg.enabled!==true||!cfg.networkAllowlistReviewed||!cfg.singleWriterLeaseConfirmed)throw Error('Separate physical commissioning required');
 const secrets=await ownedJSON(cfg.credentialsFile),transport=fixedPowerTransport({...cfg,...secrets});
 const store=async state=>{const temp=cfg.stateFile+'.'+randomUUID();try{await writeFile(temp,JSON.stringify(state),{flag:'wx',mode:0o600});const f=await open(temp,'r');try{await f.sync()}finally{await f.close()}await rename(temp,cfg.stateFile);const dir=await open(new URL('.', 'file://'+cfg.stateFile).pathname,'r');try{await dir.sync()}finally{await dir.close()}}finally{await import('node:fs/promises').then(fs=>fs.unlink(temp).catch(()=>{}))}};
 const bridge=powerBridge({...transport,enabled:true,pollMs:cfg.pollMs,load:()=>ownedJSON(cfg.stateFile),save:store});
 const approvals=privateBackend({socketPath:cfg.approvalSocket,credential:secrets.approvalService});
 const server=createServer(async(req,res)=>{
  const send=(status,data)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(data))};
  try{
   const given=Buffer.from(req.headers.authorization||''),expected=Buffer.from('Bearer '+secrets.gatewayTransport);
   if(given.length!==expected.length||!timingSafeEqual(given,expected))return send(401,{error:'Denied'});
   if(req.method==='GET'&&req.url==='/status')return send(200,bridge.status());
   if(req.method!=='POST'||req.url!=='/power')return send(403,{error:'Denied'});
   let raw='';for await(const b of req){raw+=b;if(Buffer.byteLength(raw)>2048)throw Error('Bound')}
   const data=JSON.parse(raw);if(Object.keys(data).sort().join()!=='power,receipt,subject'||typeof data.subject!=='string'||!Number.isFinite(data.power))throw Error('Power schema');
   const fingerprint=createHash('sha256').update(JSON.stringify(['/api/s9/power',data.subject,{power:data.power}])).digest('hex');
   const result=await bridge.manual(data.power,async()=>{
    const reply=await approvals({identity:{subject:data.subject,kind:'human'},method:'POST',path:'/api/physical/consume',data:{receipt:data.receipt,fingerprint,permission:'physical.s9.power'},resource:{space:'physical'}});
    if(reply.status!==200||JSON.parse(reply.bytes).consumed!==true)throw Error('Independent approval required');
   });return send(200,result);
  }catch{return send(503,{error:'Power service unavailable; no retry'})}
 });
 // Existing socket is not silently deleted; operator must verify stopped instance.
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(cfg.socket,resolve)});
 await import('node:fs/promises').then(fs=>fs.chmod(cfg.socket,0o600));
 await bridge.start();
 let stopping=false;const stop=async()=>{if(stopping)return;stopping=true;await new Promise(r=>server.close(r));await bridge.stop()};
 process.once('SIGTERM',()=>void stop());process.once('SIGINT',()=>void stop());return {server,bridge,stop};
}
if(process.argv[1]===new URL(import.meta.url).pathname){if(process.argv.length!==3)throw Error('Explicit private config required');await main(process.argv[2])}
