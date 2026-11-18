// Separate responsibility for the EXISTING S9 power bridge, not a new S19 controller.
// Import has no timers, I/O or equipment effects. Transport and durable state injected.
export function powerBridge({enabled,readTarget,applyTarget,load,save,audit=async()=>{},pollMs=10000}){
 if(!Number.isInteger(pollMs)||pollMs<1000||pollMs>300000)throw Error('Poll interval');
 let state={lastRequestedPower:null,lastAppliedPower:null,pending:null},busy=false,timer,stopped=true,active,freshStart=true;
 function drive(){if(busy)return active;active=poll();return active}
 async function init(){freshStart=true;state={...state,...await load()};if(state.pending)state.uncertain=true;return {...state}}
 async function poll(){
  if(stopped||!enabled||busy||state.uncertain)return;
  busy=true;
  try{
   const target=Math.round(Number(await readTarget()));if(!Number.isFinite(target)||stopped)return;
   if(freshStart||state.lastRequestedPower===null){freshStart=false;state.lastRequestedPower=target;await save(state);return}
   if(target===state.lastRequestedPower)return;
   // Preserve legacy latch-before-apply, but persist intent to prevent blind replay.
   state.lastRequestedPower=target;state.pending={target,at:new Date().toISOString()};await save(state);
   try{const result=await applyTarget(target);state.lastAppliedPower=result.power;state.pending=null;await save(state);await audit({event:'power-applied',power:result.power})}
   catch{state.uncertain=true;await save(state);await audit({event:'power-uncertain'});}
  }catch{await audit({event:'poll-unavailable'})}finally{busy=false}
 }
 return {init,status:()=>({...state,busy,enabled,stopped}),async start(){if(!stopped)throw Error('Already running');await init();stopped=false;await drive();timer=setInterval(drive,pollMs);timer.unref()},async stop(){stopped=true;clearInterval(timer);await active},
  // Reconciliation requires an independent human decision; never inferred/model-driven.
  async reconcile({approved,requested,applied}){if(approved!==true||busy||!stopped||!Number.isFinite(requested)||!Number.isFinite(applied))throw Error('Stopped human reconciliation required');state={lastRequestedPower:requested,lastAppliedPower:applied,pending:null};await save(state)},
  manual(power,approval){
   if(stopped||busy||state.uncertain)throw Error('Service unavailable');busy=true;
   active=(async()=>{let intent=false;try{await approval();if(stopped)throw Error('Stopped before intent');state.pending={target:power,manual:true,at:new Date().toISOString()};intent=true;await save(state);const result=await applyTarget(power);state.lastAppliedPower=result.power;state.pending=null;await save(state);return result}catch(e){if(intent){state.uncertain=true;await save(state)}throw e}finally{busy=false}})();
   return active;
  },
  tick:drive,
 };
}
export function fixedPowerTransport({haURL,minerURL,haToken,username,password,min,max,entity,fetchImpl=fetch}){
 const ha=new URL(haURL),miner=new URL(minerURL);
 for(const u of [ha,miner])if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.search||u.hash)throw Error('Fixed local endpoint');
 if(fetchImpl===globalThis.fetch&&[ha,miner].some(u=>! /^(?:127\.|10\.|192\.168\.|172\.(?:1[6-9]|2[0-9]|3[01])\.)/.test(u.hostname)))throw Error('Private literal equipment endpoint required');
 if(!/^[a-z_]+\.[a-z0-9_]+$/.test(entity)||!Number.isFinite(min)||!Number.isFinite(max)||min>max)throw Error('Power contract');
 const graphql=async(query,variables,cookie)=>{
  const r=await fetchImpl(new URL('/graphql',miner),{method:'POST',redirect:'error',signal:AbortSignal.timeout(5000),headers:{'content-type':'application/json',...(cookie?{cookie}:{})},body:JSON.stringify({query,variables})});
  const data=await r.json();if(!r.ok||data.errors?.length)throw Error('Miner request failed');return {data:data.data,cookie:r.headers.get('set-cookie')?.split(';')[0]};
 };
 return {async readTarget(){const r=await fetchImpl(new URL('/api/states/'+entity,ha),{headers:{authorization:'Bearer '+haToken},redirect:'error',signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error('HA unavailable');return (await r.json()).state},async applyTarget(power){
  const target=Math.round(Math.max(min,Math.min(max,Number(power))));if(!Number.isFinite(target))throw Error('Power invalid');
  const login=await graphql('mutation Login($u:String!,$p:String!){ auth { login(username:$u,password:$p) { __typename ... on AuthError { message } } } }',{u:username,p:password});
  if(login.data?.auth?.login?.__typename==='AuthError'||!login.cookie)throw Error('Miner authentication failed');
  const r=await graphql('mutation SetPower($input: AutotuningIn!, $apply: Boolean!) { bosminer { config { updateAutotuning(input: $input, apply: $apply) { __typename ... on AutotuningError { message } ... on AttributeError { message } } } } }',{input:{mode:'POWER_TARGET',powerTarget:target},apply:true},login.cookie);
  const type=r.data?.bosminer?.config?.updateAutotuning?.__typename;if(type&&type!=='AutotuningOut')throw Error('Miner rejected power');return {power:target,resultType:type||null};
 }};
}
