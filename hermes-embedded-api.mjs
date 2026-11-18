// Namespaced human sessions on the private pilot. No gateway/visual-profile trust.
import {Readable} from 'node:stream';
import {HUMAN_ASSERTION_HEADER} from './hermes-human-delegation.mjs';
import {sessionRegistry} from './jarvis-session-auth.mjs';
import {experimentalHermes} from './jarvis-hermes-experimental.mjs';
import {PANEL_PREFIX,PANEL_COOKIE,panelRoute} from './hermes-embedded-contract.mjs';
import {HERMES_OBJECTIVE} from './hermes-voice-tools.mjs';
import {hybridAdmission} from './hybrid-mission-admission.mjs';
import {missionObjective,missionDefinition} from './hermes-mission-policy.mjs';
const send=(res,status,data)=>{res.writeHead(status,{'content-type':'application/json','cache-control':'no-store','x-content-type-options':'nosniff'});res.end(JSON.stringify(data));return true};
export function embeddedPanel({origin,policy,client,audit,refresh=async()=>policy,operations=()=>({}),now,delegationVerifier=null}){
 const base=new URL(origin);
 if(base.origin!==origin||!(base.protocol==='https:'||(base.protocol==='http:'&&base.hostname==='127.0.0.1')))throw Error('Pinned TLS origin required');
 if(delegationVerifier!==null&&typeof delegationVerifier!=='function')throw Error('Explicit delegation verifier required');
 const sessions=sessionRegistry({...policy,origin,now});
 let current=policy;
 const bound=new WeakMap();
 function clients(){
  const map=new Map();
  for(const [subject,spaces]of current.grants)if(spaces.includes('user'))map.set(subject,new Map([['user',client]]));
  return map;
 }
 const facade=experimentalHermes({enabled:true,authenticate:req=>bound.get(req),clients:{get:subject=>clients().get(subject)}});
 return async(req,res,url)=>{
  if(url.pathname!==PANEL_PREFIX&&!url.pathname.startsWith(PANEL_PREFIX+'/'))return false;
  try{
   if(req.headers['x-jarvis-panel-origin']!==origin)return send(res,403,{error:'Pinned relay required'});
   if(req.headers.origin&&req.headers.origin!==origin)return send(res,403,{error:'Origin denied'});
   if(req.headers.authorization!==undefined)return send(res,403,{error:'Human session required'});
   const features=await operations();
   if(!panelRoute(req.method,url.pathname,features))return send(res,403,{error:'Panel operation denied'});
   const fresh=await refresh();
   if(!fresh)return send(res,404,{error:'Panel disabled'});
   sessions.updatePolicy(fresh);current=fresh;
   if(delegationVerifier&&req.headers.cookie)return send(res,401,{error:'Server delegation required'});
   // This namespace cannot consume general Jarvis or pilot cookies.
   const cookies=(req.headers.cookie||'').split(';').map(x=>x.trim()).filter(x=>x.startsWith(PANEL_COOKIE+'='));
   if(cookies.length>1)return send(res,401,{error:'Ambiguous session'});
   req.headers={...req.headers,cookie:cookies.map(c=>'JarvisSession='+c.slice(PANEL_COOKIE.length+1)).join('; ')};
   const sub=url.pathname.slice(PANEL_PREFIX.length);
   const virtual=new URL(origin+'/api/jarvis'+(sub==='/session'?'/session':sub));
   virtual.search=url.search;
   if(sub==='/session'&&delegationVerifier)return send(res,403,{error:'Use the common human session'});
   if(sub==='/session'){
    const response={writeHead(status,headers){
     const h={...headers};
     if(h['set-cookie']){
      const rewrite=c=>c.replace(/^JarvisSession=/,PANEL_COOKIE+'=').replace('Path=/api/jarvis','Path='+PANEL_PREFIX);
      h['set-cookie']=Array.isArray(h['set-cookie'])?h['set-cookie'].map(rewrite):rewrite(h['set-cookie']);
     }
     res.writeHead(status,h);
    },end:body=>res.end(body)};
    await sessions.handle(req,response,virtual);return true;
   }
   let delegated=null,id;
   if(delegationVerifier){
    // No private cookie or login credential is accepted in unified mode.
    if(req.headers.cookie)return send(res,401,{error:'Delegated identity only'});
    const rawParts=[];let size=0;
    for await(const part of req){size+=part.length;if(size>8000)return send(res,413,{error:'Body bound'});rawParts.push(part)}
    const raw=Buffer.concat(rawParts);
    if((req.method==='GET'&&size)||(req.method!=='GET'&&(req.headers['transfer-encoding']||!/^\d+$/.test(req.headers['content-length']||'')||Number(req.headers['content-length'])!==size)))return send(res,400,{error:'Body length'});
    try{delegated=delegationVerifier(req,url,raw)}catch{return send(res,401,{error:'Delegated identity denied'})}
    const spaces=current.grants.get(delegated.subject)||[],roles=current.roles.get(delegated.subject)||[];
    id={subject:delegated.subject,kind:'human',spaces,roles,defaultSpace:spaces[0]};
    const restored=Readable.from(raw.length?[raw]:[]);restored.method=req.method;restored.headers=req.headers;req=restored;
   }else{
    if(req.headers[HUMAN_ASSERTION_HEADER]!==undefined)return send(res,403,{error:'Delegation disabled'});
    id=sessions.authenticate(req);
   }
   if(!id||id.kind!=='human')return send(res,401,{error:'Human authentication required'});
   if(!['GET','HEAD'].includes(req.method)&&!sessions.sameOrigin(req))return send(res,403,{error:'Origin denied'});
   if([...url.searchParams.keys()].some(k=>k!=='space')||url.searchParams.getAll('space').length>1)return send(res,403,{error:'Unambiguous space only'});
   const space=url.searchParams.get('space')||id.defaultSpace;
   const admitting=req.method==='POST'&&['/hermes/missions','/hybrid/ask'].includes(sub);
   const permission=admitting?'missions.create':req.method==='POST'?'missions.cancel':'missions.read';
   const allowed=delegated?delegated.space===space&&delegated.permission===permission&&id.spaces.includes(space)&&id.roles.includes(permission):sessions.isActive(id,permission,space);
   if(space!=='user'||!allowed)return send(res,403,{error:'Space or permission denied'});
   if(admitting){
    if(req.headers['transfer-encoding']||!/^\d+$/.test(req.headers['content-length']||'')||Number(req.headers['content-length'])>8000)return send(res,413,{error:'Bounded admission required'});
    const parts=[];let size=0;for await(const part of req){size+=part.length;if(size>8000)return send(res,413,{error:'Body limit'});parts.push(part)}
    if(size!==Number(req.headers['content-length']))return send(res,400,{error:'Body length'});
    const data=JSON.parse(Buffer.concat(parts).toString('utf8'));
    const create=async(objective,key)=>{
     if(typeof key!=='string'||!/^[A-Za-z0-9_-]{1,120}$/.test(key))return {status:400,body:{error:'Stable idempotency key required'}};
     const body={scope:'private',definition:missionDefinition(objective)};
     await audit({event:'embedded_mission_admission',subject:id.subject,space,request_key:key});
     return client.request('POST','/v1/missions',{body,headers:{'Idempotency-Key':key}});
    };
    if(sub==='/hybrid/ask'){
     if(Object.keys(data).some(k=>!['question','archive'].includes(k))||typeof data.question!=='string'||data.question.length>2000)return send(res,400,{error:'Explicit bounded request required'});
     const handler=hybridAdmission({identity:id,space,enabled:()=>features.voiceEnabled===true,create:async key=>{const result=await create(HERMES_OBJECTIVE,key);if(result.status!==202)throw Error('Admission not confirmed');return result.body},audit});
     const result=await handler(data);return send(res,result?.status||422,result?.body||{error:'Explicit Hermes template required'});
    }
    const objective=missionObjective(data,features);
    if(objective===null)return send(res,403,{error:'Allowed template or explicit text required'});
    const result=await create(objective,req.headers['idempotency-key']);return send(res,result.status,result.body);
   }
   if(req.method==='POST'){
    if(req.headers['transfer-encoding']||!/^\d+$/.test(req.headers['content-length']||'')||Number(req.headers['content-length'])>32)return send(res,413,{error:'Bounded cancel body required'});
    let body='';for await(const part of req)body+=part.toString();
    if(Buffer.byteLength(body)!==Number(req.headers['content-length'])||body.length>32||JSON.stringify(JSON.parse(body))!=='{}')return send(res,400,{error:'Empty cancel object only'});
   }
   await audit({event:'embedded_panel_admitted',subject:id.subject,space,method:req.method,route:sub});
   if(sub==='/hermes/config')return send(res,200,{enabled:features.admissionEnabled===true,readEnabled:true,textEnabled:features.textEnabled===true,voiceEnabled:features.voiceEnabled===true,syntheticOnly:true,onDemand:features.queueEnabled===true,templates:features.admissionEnabled===true?['doselab-current']:[]});
   if(sub==='/hermes/availability'){
    if(features.workerEnabled===true||features.queueEnabled===true){try{return send(res,200,await client.workerStatus())}catch{return send(res,200,{fresh:false,state:'unknown',dispatch_allowed:false,automatic_replay:false})}}
    return send(res,200,{fresh:false,state:'unavailable',dispatch_allowed:false,reason:'Executor not enabled; no Windows probe'});
   }
   bound.set(req,id);virtual.searchParams.set('space',space);
   if(delegated){
    // Recheck the private policy before releasing a buffered response. A shared
    // space/session grant in the gateway does not override private revocation.
    let status,headers,body;
    const capture={writeHead(code,h){status=code;headers=h},end(value){body=value}};
    await facade(req,capture,virtual);
    const finalPolicy=await refresh();
    if(finalPolicy)sessions.updatePolicy(finalPolicy);
    if(!finalPolicy?.grants?.get(id.subject)?.includes(space)||!finalPolicy.roles?.get(id.subject)?.includes(permission))return send(res,403,{error:'Private permission revoked'});
    if(!Number.isInteger(status)||body===undefined||Buffer.byteLength(body)>65536)return send(res,502,{error:'Bounded response required'});
    res.writeHead(status,headers);res.end(body);return true;
   }
   return await facade(req,res,virtual);
  }catch{return send(res,503,{error:'Panel unavailable; no replay'})}
 };
}
