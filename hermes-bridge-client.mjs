// Node 18. Only a controller loopback endpoint; never a model or Windows API.
import http from 'node:http';
export function bridgeClient({baseURL,token,scope='private',workerId,timeoutMs=1200,maxBytes=65536}={}){
 const base=new URL(baseURL);
 if(base.protocol!=='http:'||base.hostname!=='127.0.0.1'||base.username||base.password||base.pathname!=='/'||base.search||base.hash)throw Error('Controller loopback only');
 if(typeof token!=='string'||!/^[A-Za-z0-9_-]{32,256}$/.test(token)||!['private','shared'].includes(scope))throw Error('Server credential and scope required');
 if(!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>5000||!Number.isInteger(maxBytes)||maxBytes<1||maxBytes>1048576)throw Error('Bounded transport required');
 const request=(method,path,{body,headers={},signal}={})=>{
  if(!((['GET','POST'].includes(method)&&path==='/v1/missions')||(/^\/v1\/missions\/[A-Za-z0-9-]+(?:\/(events|results|canonical|cancel|approvals))?$/.test(path)&&((method==='GET'&&!/\/(cancel|approvals)$/.test(path))||(method==='POST'&&/\/(cancel|approvals)$/.test(path))))))throw Error('Bridge route denied');
  if(Object.keys(headers).some(k=>!['Idempotency-Key','Last-Event-ID'].includes(k)))throw Error('Caller header denied');
  for(const value of Object.values(headers))if(typeof value!=='string'||!/^[-A-Za-z0-9_]{1,120}$/.test(value))throw Error('Header value denied');
  const raw=body===undefined?undefined:Buffer.from(JSON.stringify(body));
  if(raw&&raw.length>16000)throw Error('Request limit');
  return new Promise((resolve,reject)=>{
   const req=http.request(new URL(path,base),{method,signal,headers:{...headers,Authorization:'Bearer '+token,...(raw?{'content-type':'application/json','content-length':raw.length}:{})}},res=>{
    const parts=[];let size=0;
    res.on('data',part=>{size+=part.length;if(size>maxBytes){reject(Error('Response limit'));res.destroy();req.destroy();return;}parts.push(part)});
    res.on('error',reject);
    res.on('end',()=>{try{
     const type=(res.headers['content-type']||'').split(';')[0];
     if(!['application/json','text/event-stream'].includes(type))throw Error('Response type denied');
     const text=Buffer.concat(parts).toString('utf8');
     resolve({status:res.statusCode,type,body:type==='application/json'?JSON.parse(text):text});
    }catch{reject(Error('Invalid bridge response'))}});
   });
   req.setTimeout(timeoutMs,()=>req.destroy(Error('Bridge timeout')));
   // Also bound the total duration, including a peer slowly sending bytes.
   const deadline=setTimeout(()=>req.destroy(Error('Bridge deadline')),timeoutMs);
   req.on('close',()=>clearTimeout(deadline));req.on('error',reject);req.end(raw);
  });
 };
 return Object.freeze({scope,request,async workerStatus(){
  if(!/^[A-Za-z0-9_-]{1,128}$/.test(workerId||''))throw Error('No bound worker');
  // Separate fixed transport; never accept a worker ID or endpoint from the browser.
  const response=await new Promise((resolve,reject)=>{const req=http.get(new URL('/v1/workers/'+workerId+'/status',base),{headers:{Authorization:'Bearer '+token}},res=>{let size=0,raw='';res.on('data',p=>{size+=p.length;if(size>4096)return req.destroy(Error('Heartbeat bound'));raw+=p});res.on('end',()=>{try{if(res.statusCode!==200)throw Error('Heartbeat denied');resolve(JSON.parse(raw))}catch(e){reject(e)}});res.on('error',reject)});const timer=setTimeout(()=>req.destroy(Error('Heartbeat deadline')),timeoutMs);req.on('close',()=>clearTimeout(timer));req.on('error',reject)});
  return response;
 }});
}
