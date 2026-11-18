// Stateless, bounded same-origin relay. No bridge credential or provider imports.
import http from 'node:http';
import {HUMAN_ASSERTION_HEADER,panelPermission} from './hermes-human-delegation.mjs';
import {open} from 'node:fs/promises';
import {constants} from 'node:fs';
import {PANEL_PREFIX,PANEL_COOKIE,panelRoute} from './hermes-embedded-contract.mjs';
const send=(res,status)=>{res.writeHead(status,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify({error:status===404?'Panel disabled':'Panel denied or unavailable'}));return true};
export function embeddedRelay({enabled=false,origin,port=8796,timeoutMs=1500,switchFile=null,sharedSession=null}={}){
 if(!Number.isInteger(port)||port<1024||port>65535||!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>3000)throw Error('Bounded loopback relay required');
 if(enabled){const u=new URL(origin);if(u.origin!==origin||!(u.protocol==='https:'||(u.protocol==='http:'&&u.hostname==='127.0.0.1')))throw Error('Pinned TLS origin required')}
 if(sharedSession&&(!sharedSession.sessions||sharedSession.sessions.origin!==origin||typeof sharedSession.sign!=='function'||typeof sharedSession.refresh!=='function'))throw Error('Verified shared session composition required');
 async function active(){
  if(!enabled)return false;
  if(switchFile===null)return {enabled:true};
  if(typeof switchFile!=='string'||!switchFile)return false;
  let f;try{f=await open(switchFile,constants.O_RDONLY|constants.O_NOFOLLOW);const st=await f.stat();if(!st.isFile()||st.uid!==process.getuid()||(st.mode&0o077)||st.size>128)return false;const cfg=JSON.parse(await f.readFile('utf8'));return Object.keys(cfg).every(k=>['enabled','admissionEnabled','voiceEnabled'].includes(k)&&typeof cfg[k]==='boolean')&&cfg.enabled===true?cfg:false}catch{return false}finally{await f?.close()}
 }
 return async(req,res,url)=>{
  if(url.pathname!==PANEL_PREFIX&&!url.pathname.startsWith(PANEL_PREFIX+'/'))return false;
  const features=await active();if(!features)return send(res,404);
  if(url.origin!==origin||req.headers.authorization!==undefined||req.headers.origin&&req.headers.origin!==origin||!panelRoute(req.method,url.pathname,features))return send(res,403);
  if(req.method!=='GET'&&req.headers.origin!==origin)return send(res,403);
  let human,permission,space;
  if(sharedSession){
   if(req.headers[HUMAN_ASSERTION_HEADER]!==undefined||url.pathname===PANEL_PREFIX+'/session')return send(res,403);
   try{await sharedSession.refresh();human=sharedSession.sessions.authenticate(req)}catch{return send(res,503)}
   if(!human||human.kind!=='human')return send(res,401);
   if([...url.searchParams.keys()].some(k=>k!=='space')||url.searchParams.getAll('space').length>1)return send(res,403);
   space=url.searchParams.get('space')||human.defaultSpace;permission=panelPermission(req.method,url.pathname);
   if(!permission||!sharedSession.sessions.isActive(human,permission,space))return send(res,403);
  }else if(req.headers[HUMAN_ASSERTION_HEADER]!==undefined)return send(res,403);
  const length=req.headers['content-length']??(req.method==='DELETE'?'0':undefined);
  const limit=features.admissionEnabled&&['/hermes/missions','/hybrid/ask'].some(p=>url.pathname===PANEL_PREFIX+p)?8000:512;
  if(req.headers['transfer-encoding']||req.method!=='GET'&&(!/^\d+$/.test(length||'')||Number(length)>limit))return send(res,413);
  const headers={'x-jarvis-panel-origin':origin};
  if(req.headers.origin)headers.Origin=origin;
  const cookies=(req.headers.cookie||'').split(';').map(s=>s.trim()).filter(s=>s.startsWith(PANEL_COOKIE+'='));
  if(cookies.length>1)return send(res,401);
  if(cookies.length&&!sharedSession)headers.Cookie=cookies.join('; ');
  if(req.method!=='GET'){headers['Content-Length']=length;headers['Content-Type']='application/json'}
  if(req.headers['last-event-id'])headers['Last-Event-ID']=req.headers['last-event-id'];
  if(req.headers['idempotency-key']){
   if(!/^[A-Za-z0-9_-]{1,120}$/.test(req.headers['idempotency-key']))return send(res,400);
   headers['Idempotency-Key']=req.headers['idempotency-key'];
  }
  let upstream,timer;
  try{
   timer=setTimeout(()=>req.destroy(Error('Panel body deadline')),timeoutMs);
   const parts=[];let size=0;
   for await(const part of req){size+=part.length;if(size>limit)return send(res,413);parts.push(part)}
   if(req.method!=='GET'&&size!==Number(length)||req.method==='GET'&&size)return send(res,400);
   clearTimeout(timer);
   if(sharedSession)headers[HUMAN_ASSERTION_HEADER]=sharedSession.sign({subject:human.subject,space,permission,method:req.method,target:url.pathname+url.search,body:Buffer.concat(parts)});
   const result=await new Promise((resolve,reject)=>{
    upstream=http.request({hostname:'127.0.0.1',port,method:req.method,path:url.pathname+url.search,headers},reply=>{
     const pieces=[];let length=0;
     reply.on('data',p=>{length+=p.length;if(length>65536){upstream.destroy();reject(Error('Response bound'));return}pieces.push(p)});
     reply.on('error',reject);reply.on('end',()=>resolve({status:reply.statusCode,headers:reply.headers,body:Buffer.concat(pieces)}));
    });
    timer=setTimeout(()=>upstream.destroy(Error('Relay deadline')),timeoutMs);
    upstream.on('error',reject);upstream.end(Buffer.concat(parts));
   });
   if(sharedSession){
    await sharedSession.refresh();
    if(!sharedSession.sessions.isActive(human,permission,space))return send(res,401);
    if(result.headers['set-cookie'])return send(res,502);
   }
   const type=(result.headers['content-type']||'').split(';')[0];
   if(!['application/json','text/event-stream'].includes(type)||result.status>=300&&result.status<400)return send(res,502);
   if(url.pathname===PANEL_PREFIX+'/hermes/config'&&result.status===200&&type==='application/json'){
    const cfg=JSON.parse(result.body.toString('utf8'));cfg.enabled=cfg.enabled===true&&features.admissionEnabled===true;cfg.textEnabled=cfg.textEnabled===true&&cfg.enabled;cfg.voiceEnabled=cfg.voiceEnabled===true&&cfg.enabled&&features.voiceEnabled===true;result.body=Buffer.from(JSON.stringify(cfg));
   }
   const output={'content-type':type,'cache-control':'no-store','x-content-type-options':'nosniff'};
   if(result.headers['set-cookie']){
    const values=result.headers['set-cookie'];
    if(!values.every(s=>s.startsWith(PANEL_COOKIE+'=')&&s.includes('Path='+PANEL_PREFIX+';')&&s.includes('HttpOnly')&&s.includes('SameSite=Strict')))return send(res,502);
    output['set-cookie']=values;
   }
   res.writeHead(result.status,output);res.end(result.body);return true;
  }catch{return send(res,503)}finally{clearTimeout(timer)}
 };
}
