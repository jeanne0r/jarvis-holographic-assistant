// Central guard candidate. Injected handlers; no imports of live gateway/backends.
import {open,lstat,realpath} from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {trustedRequests} from './jarvis-session-auth.mjs';
import {authorize,classify,requestIdentity} from './gateway-route-policy.mjs';
const send=(res,status,data)=>{res.writeHead(status,{'content-type':'application/json','cache-control':'no-store','x-content-type-options':'nosniff'});res.end(JSON.stringify(data))};
const within=(root,file)=>file===root||file.startsWith(root+path.sep);
export async function staticBytes(root,relative){
 if(typeof relative!=='string'||relative.includes('\\')||relative.split('/').some(p=>!p||p==='.'||p==='..'||p.startsWith('.')))throw Error('Static path denied');
 const base=await realpath(root),target=path.resolve(base,relative);if(!within(base,target))throw Error('Static boundary');
 let component=base;
 for(const part of relative.split('/')){component=path.join(component,part);if((await lstat(component)).isSymbolicLink())throw Error('Static symlink denied')}
 const f=await open(target,constants.O_RDONLY|constants.O_NOFOLLOW);
 try{
  const actual=await realpath('/proc/self/fd/'+f.fd); // Target host is Linux; fail closed elsewhere.
  const st=await f.stat();if(!within(base,actual)||!st.isFile()||st.size>32*1024*1024)throw Error('Static file denied');
  return await f.readFile();
 }finally{await f.close()}
}
export function centralGateway({sessions,dispatch,resource=async()=>false,physicalApproval=async()=>false,refresh=async()=>{},publicAssets=new Map(),staticRoot,streamCheckMs=1000,streamMaxMs=45000,audit=async()=>{}}){
 if(streamCheckMs<10||streamCheckMs>1000||streamMaxMs>45000)throw Error('Bounded revocation checks required');
 return async(req,res,url)=>{
  // Check raw target before URL normalization. No encoded separators or dot segments.
  let raw;try{raw=decodeURIComponent(req.url.split('?')[0])}catch{return send(res,400,{error:'Invalid URL'})}
  if(raw.includes('\\')||/%2f|%5c/i.test(req.url.split('?')[0])||raw.split('/').some(p=>p==='.'||p==='..'))return send(res,403,{error:'Path denied'});
  try{
   await refresh();
   // All responses are same-origin. No wildcard CORS, even if a legacy handler tries it.
   const writeHead=res.writeHead.bind(res);
   res.writeHead=(status,...args)=>{res.removeHeader?.('access-control-allow-origin');const last=args.at(-1);if(last&&typeof last==='object'&&!Array.isArray(last)){const safe={};for(const [k,v]of Object.entries(last))if(!k.toLowerCase().startsWith('access-control-'))safe[k]=v;args[args.length-1]=safe}return writeHead(status,...args)};
   if(req.headers.origin&&req.headers.origin!==sessions.origin)return send(res,403,{error:'Origin denied'});
   if(!url.pathname.startsWith('/api/')){
    if(!['GET','HEAD'].includes(req.method)||!publicAssets.has(url.pathname))return send(res,404,{error:'Static route denied'});
    const asset=publicAssets.get(url.pathname),bytes=await staticBytes(staticRoot,asset.file);
    if(!/^[a-f0-9]{64}$/.test(asset.sha256||'')||createHash('sha256').update(bytes).digest('hex')!==asset.sha256)throw Error('Unreviewed static bytes');
    let output=bytes;
    if(asset.bootstrapAuth===true){
     if(!asset.type.startsWith('text/html')||!publicAssets.has('/jarvis/jarvis-auth.js'))throw Error('Reviewed standalone auth asset required');
     const html=bytes.toString('utf8');
     if(!/src=["'](?:\/jarvis\/)?jarvis-auth\.js["']/.test(html)){const script='<script defer src="/jarvis/jarvis-auth.js"></script>';output=Buffer.from(html.includes('</head>')?html.replace('</head>',script+'</head>'):script+html)}
    }
    res.writeHead(200,{'content-type':asset.type,'cache-control':'no-store','x-content-type-options':'nosniff'});return res.end(req.method==='HEAD'?undefined:output);
   }
   const row=classify(req.method,url.pathname);if(!row)return send(res,403,{error:'Unclassified route'});
   if(row.permission==='public')return send(res,200,{ok:true});
   if(await sessions.handle(req,res,url))return;
   const id=sessions.authenticate(req),values=url.searchParams.getAll('space');
   if(values.length>1)return send(res,403,{error:'Ambiguous space'});
   const space=values[0]||id?.defaultSpace;
   // Cheap identity/origin checks must precede any resource adapter.
   const preliminary=authorize({method:req.method,path:url.pathname,identity:id,space,origin:req.headers.origin,expectedOrigin:sessions.origin,resourceAllowed:true,physicalApproval:true});
   if(!preliminary.allowed)return send(res,preliminary.status,{error:preliminary.reason});
   const allowed=authorize({method:req.method,path:url.pathname,identity:id,space,origin:req.headers.origin,expectedOrigin:sessions.origin,resourceAllowed:!row.resource||await resource({req,url,identity:id,space,row}),physicalApproval:!row.physical||await physicalApproval({req,url,identity:id,space,row})});
   if(!allowed.allowed)return send(res,allowed.status,{error:allowed.reason});
   const context={...id,space};requestIdentity.set(req,context);trustedRequests.set(req,context);
   await audit({subject:id.subject,permission:row.permission,space,method:req.method,route:row.path});
   const streaming=url.pathname.endsWith('/events')||url.pathname==='/api/jarvis/voice/speak';
   let timer,deadline;
   if(streaming){
    const stop=()=>{clearInterval(timer);clearTimeout(deadline)};
    res.once('close',stop);res.once('finish',stop);
    timer=setInterval(()=>{void refresh().then(()=>{if(!sessions.isActive(id,row.permission,space))res.destroy()}).catch(()=>res.destroy())},streamCheckMs);timer.unref();
    deadline=setTimeout(()=>res.destroy(),streamMaxMs);deadline.unref();
   }
   await dispatch(req,res,url);
  }catch{if(res.headersSent)res.destroy();else send(res,503,{error:'Policy or service unavailable'})}
 };
}
