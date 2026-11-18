import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
let cached=null,pending=null;
export function normalizeLimits(data,checkedAt=new Date().toISOString()){
 const buckets=Object.values(data.rateLimitsByLimitId||{});if(!buckets.length&&data.rateLimits)buckets.push(data.rateLimits);
 const window=w=>w&&Number.isFinite(w.usedPercent)?{usedPercent:w.usedPercent,remainingPercent:Math.max(0,100-w.usedPercent),windowDurationMins:w.windowDurationMins,resetsAt:Number.isFinite(w.resetsAt)?new Date(w.resetsAt*1000).toISOString():null}:null;
 return {state:buckets.length?'ready':'unavailable',checkedAt,ordinaryUsageAllowed:data.ordinaryUsageAllowed??null,buckets:buckets.map(b=>({id:b.limitId,name:b.limitName||b.limitId,plan:b.planType||null,primary:window(b.primary),secondary:window(b.secondary),reached:b.rateLimitReachedType||null,credits:b.credits?{hasCredits:b.credits.hasCredits,unlimited:b.credits.unlimited,balance:typeof b.credits.balance==='string'?b.credits.balance:null}:null})),availableResets:data.rateLimitResetCredits?.availableCount??null};
}
function readLimits(){return new Promise((resolve,reject)=>{
 const p=spawn('/home/user/.local/bin/codex',['app-server','--stdio'],{cwd:'/home/user/workspace/jarvis',env:{HOME:process.env.HOME,PATH:process.env.PATH,LANG:'C.UTF-8'},stdio:['pipe','pipe','ignore']});let done=false;
 const lines=createInterface({input:p.stdout});const finish=(error,data)=>{if(done)return;done=true;clearTimeout(timer);lines.close();p.kill();error?reject(error):resolve(normalizeLimits(data));};
 const timer=setTimeout(()=>finish(Error('Lecture des quotas OpenAI indisponible.')),12000);
 const send=x=>p.stdin.write(JSON.stringify(x)+'\n');p.stdin.on('error',()=>{});p.on('error',()=>finish(Error('Connexion Codex indisponible.')));p.on('close',()=>{if(!done)finish(Error('Lecture des quotas OpenAI interrompue.'))});
 lines.on('line',line=>{try{const x=JSON.parse(line);if(x.id===1){if(x.error)return finish(Error('Connexion Codex indisponible.'));send({method:'initialized'});send({id:2,method:'account/rateLimits/read',params:{}})}if(x.id===2){if(x.error)return finish(Error('Quotas non accessibles avec cette connexion OpenAI.'));finish(null,x.result)}}catch{}});
 send({id:1,method:'initialize',params:{clientInfo:{name:'jarvis_usage',version:'1.0.0'},capabilities:{experimentalApi:true}}});
})}
export async function openaiUsage(){
 if(cached&&Date.now()-Date.parse(cached.checkedAt)<60000)return cached;
 if(!pending)pending=readLimits().then(data=>(cached=data)).catch(()=>cached?{...cached,state:'stale'}:{state:'unavailable',checkedAt:null,buckets:[],availableResets:null}).finally(()=>pending=null);
 return pending;
}
