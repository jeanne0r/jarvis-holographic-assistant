// Node 18. Inert until explicitly mounted with trusted server-side identities.
// This module performs no imports of production stores, no agent execution.
const PREFIX='/api/jarvis/hermes';
const tools=['memory.search','memory.propose','report'];
export function experimentalHermes({enabled=false,authenticate,clients,approvalClients,timeoutMs=1500}={}){
 if(enabled&&(!authenticate||!clients))throw Error('Trusted identities required');
 if(!Number.isFinite(timeoutMs)||timeoutMs<=0||timeoutMs>5000)throw Error('Bounded transport timeout required');
 return async function(req,res,url){
  if(url.pathname!==PREFIX&&!url.pathname.startsWith(PREFIX+'/'))return false;
  const send=(code,value,type='application/json')=>{res.writeHead(code,{'content-type':type,'cache-control':'no-store'});res.end(type==='application/json'?JSON.stringify(value):value);return true};
  if(!enabled)return send(404,{error:'Disabled'});
  try{
   // authenticate MUST verify a server-issued identity, including requested space.
   // Never implement it using a browser-provided owner or mere Origin equality.
   const identity=await authenticate(req);
   if(!identity)return send(401,{error:'Authentication required'});
   const space=url.searchParams.get('space');
   if(typeof identity.subject!=='string'||!Array.isArray(identity.spaces)||!space||!identity.spaces.includes(space))return send(403,{error:'Space denied'});
   const approving=url.pathname.endsWith('/approvals');
   if(approving&&!approvalClients)return send(404,{error:'Operation denied'});
   const client=(approving?approvalClients:clients)?.get(identity.subject)?.get(space);
   if(!client)return send(403,{error:'No bound server identity'});
   const sub=url.pathname.slice(PREFIX.length);
   let path='/v1/missions',body,method=req.method;
   const headers={};
   if(sub==='/missions'&&method==='GET'){
    // Canonical server-owned listing, no browser owner filter.
   }else if(sub==='/missions'&&method==='POST'){
    const key=req.headers['idempotency-key'];
    if(typeof key!=='string'||!/^[a-zA-Z0-9_-]{1,120}$/.test(key))return send(400,{error:'Idempotency key required'});
    if(req.headers['transfer-encoding']||!/^\d+$/.test(req.headers['content-length']||'')||Number(req.headers['content-length'])>8000)return send(413,{error:'Body limit'});
    const parts=[];let length=0;
    for await(const part of req){length+=part.length;if(length>8000)return send(413,{error:'Body limit'});parts.push(part)}
    if(length!==Number(req.headers['content-length']))return send(400,{error:'Body length'});
    const data=JSON.parse(Buffer.concat(parts).toString());
    if(Object.keys(data).join()!=='objective'||typeof data.objective!=='string'||data.objective.length<1||data.objective.length>2000)return send(400,{error:'Objective only'});
    body={scope:client.scope,definition:{objective:data.objective,trigger:'jarvis-experimental',priority:1,memory_context:[],plan:['retrieve','report'],allowed_tools:tools,
       budget:{tokens:0,cost_micros:0,local_tokens:98304,seconds:240,attempts:1}}};
    headers['Idempotency-Key']=key;
   }else{
    const match=/^\/missions\/([a-zA-Z0-9-]+)(?:\/(events|cancel|results|approvals))?$/.exec(sub);
    if(!match||!(method==='GET'&&!['cancel','approvals'].includes(match[2])||method==='POST'&&['cancel','approvals'].includes(match[2])))return send(404,{error:'Operation denied'});
    if(match[2]==='approvals'){
     if(!identity.roles?.includes('missions.approve'))return send(403,{error:'Human approval required'});
     if(req.headers['transfer-encoding']||!/^\d+$/.test(req.headers['content-length']||'')||Number(req.headers['content-length'])>1000)return send(413,{error:'Body limit'});
     let raw='';for await(const part of req){raw+=part.toString();if(Buffer.byteLength(raw)>1000)return send(413,{error:'Body limit'})}
     if(Buffer.byteLength(raw)!==Number(req.headers['content-length']))return send(400,{error:'Body length'});
     body=JSON.parse(raw);
     if(Object.keys(body).sort().join()!=='approval_id,choice,fingerprint'||!['once','deny'].includes(body.choice))return send(400,{error:'Exact approval only'});
    }
    path+='/'+match[1]+(match[2]?'/'+match[2]:'');
    if(method==='POST'&&match[2]!=='approvals')body={};
    if(match[2]==='events'){
     const after=req.headers['last-event-id']||'0';
     if(!/^\d{1,12}$/.test(after))return send(400,{error:'Invalid event cursor'});
     headers['Last-Event-ID']=after;
    }
   }
   // client is an injected, per-owner/per-space private transport. Its endpoint
   // and credential never come from the request. No model / paid fallback here.
   const controller=new AbortController();let timer;
   const expiry=new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error('Deadline'))},timeoutMs)});
   try{
    const result=await Promise.race([client.request(method,path,{body,headers,signal:controller.signal}),expiry]);
    if(![200,201,202,400,401,403,404,409,422,503].includes(result.status))return send(502,{error:'Bridge error'});
    if(matchCanonical(path,method,result)){
     try{const canonical=await client.request('GET',path.replace(/\/results$/,'/canonical'),{signal:controller.signal});if(canonical.status===200)result.body={...result.body,canonical:canonical.body.projection};else result.body={...result.body,canonicalUnavailable:true}}catch{result.body={...result.body,canonicalUnavailable:true}}
    }
    return send(result.status,result.body,result.type||'application/json');
   }finally{clearTimeout(timer)}
  }catch{return send(503,{error:'Bridge unavailable; existing conversation remains available'})}
 };
}

function matchCanonical(path,method,result){return method==='GET'&&path.endsWith('/results')&&result.status===200&&result.body&&typeof result.body==='object'}
