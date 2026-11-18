// Fixed private upstreams only; never client-selected URLs, hosts or paths.
import http from 'node:http';
export function privateBackend({socketPath,credential,timeoutMs=12000}){
 if(!socketPath?.startsWith('/')||typeof credential!=='string'||credential.length<32)throw Error('Private upstream');
 return async({identity,method,path,data,resource,headers={}})=>new Promise((resolve,reject)=>{
  if(identity?.kind!=='human'||!path.startsWith('/api/')||/[\r\n#]/.test(path))return reject(Error('Upstream request'));
  const bytes=data===undefined?null:Buffer.from(JSON.stringify(data));
  const req=http.request({socketPath,path,method,headers:{...headers,authorization:'Bearer '+credential,'x-jarvis-subject':identity.subject,'x-jarvis-session-handle':identity.sessionHandle||'','x-jarvis-space':resource?.space||identity.space||identity.defaultSpace,'x-jarvis-resource':resource?.id||'',...(bytes?{'content-type':'application/json','content-length':bytes.length}:{})}},res=>{
   const chunks=[];let n=0;res.on('data',b=>{n+=b.length;if(n>16*1024**2)res.destroy(Error('Backend bound'));else chunks.push(b)});res.on('error',reject);res.on('end',()=>resolve({status:res.statusCode,headers:{'content-type':res.headers['content-type']||'application/json','cache-control':'no-store'},bytes:Buffer.concat(chunks)}));
  });req.setTimeout(timeoutMs,()=>req.destroy(Error('Backend deadline')));req.on('error',reject);req.end(bytes);
 });
}
// PCM and microphone bytes remain streaming. No decoding/re-encoding in gateway.
export function forwardPrivate({socketPath,credential,identity,req,res,url}){
 return new Promise((resolve,reject)=>{
  const headers={...req.headers,authorization:'Bearer '+credential,'x-jarvis-subject':identity.subject,'x-jarvis-session-handle':identity.sessionHandle,'x-jarvis-space':identity.space||identity.defaultSpace};
  for(const k of ['connection','upgrade','proxy-authorization','cookie','x-jarvis-resource'])delete headers[k];
  const upstream=http.request({socketPath,path:url.pathname+url.search,method:req.method,headers},reply=>{
   const out={};for(const k of ['content-type','content-length','cache-control','x-jarvis-audio-format','x-jarvis-sample-rate'])if(reply.headers[k])out[k]=reply.headers[k];
   res.writeHead(reply.statusCode,out);reply.on('error',reject);reply.pipe(res);reply.on('end',resolve);
  });
  upstream.setTimeout(45000,()=>upstream.destroy(Error('Private stream deadline')));upstream.on('error',reject);
  res.once('close',()=>{if(!res.writableEnded)upstream.destroy()});req.pipe(upstream);
 });
}
