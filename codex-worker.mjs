import {relevantFacts,saveCorrections,correctedHintKeys} from './user-corrections.mjs';
import {memoryStore} from './voice-memory.mjs';
import {learnedHints,learningRows,haObservation,haLearning,invalidatedHints,explicitAliasHints} from './ha-learning.mjs';
// Warm transport, isolated ephemeral thread and private MCP session per request.
// Never replay a failed turn: it may already have executed a requested action.
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {CORE_INSTRUCTIONS,ANSWER_SCHEMA} from './core-instructions.mjs';
const ROOT='/home/user/workspace/jarvis',workers=new Map();
const abortError=()=>Object.assign(Error('Demande interrompue.'),{name:'AbortError'});
export class CodexWorker {
 constructor(space,{spawnImpl=spawn,onTool=()=>{},learningStore=haLearning,explicitMemory=memoryStore}={}){
  this.onTool=onTool;this.learningStore=learningStore;this.explicitMemory=explicitMemory;this.pending=new Map();this.jobs=new Map();this.serial=0;this.dead=false;
  const config={approval_policy:'never',sandbox_mode:'workspace-write',model:process.env.JARVIS_CORE_MODEL||'gpt-6.1-sol',web_search:'live',project_doc_max_bytes:32768,'sandbox_workspace_write.network_access':true,'sandbox_workspace_write.writable_roots':['/home/user/gateway/public/jarvis'],model_reasoning_effort:process.env.JARVIS_CORE_REASONING||'low','mcp_servers.jarvis.command':'node','mcp_servers.jarvis.args':[ROOT+'/tools-server.mjs',space],'mcp_servers.jarvis.required':true,'mcp_servers.jarvis.default_tools_approval_mode':'approve'};
  for(const name of ['apps','plugins','multi_agent','multi_agent_v2','browser_use','computer_use','image_generation','hooks','memories'])config['features.'+name]=false;
  config['features.shell_tool']=true;config['features.unified_exec']=true;
  this.process=spawnImpl('/home/user/.local/bin/codex',[...Object.entries(config).flatMap(([key,value])=>['-c',key+'='+JSON.stringify(value)]),'app-server','--stdio'],{cwd:ROOT,env:{HOME:process.env.HOME,PATH:process.env.PATH,LANG:'C.UTF-8'},stdio:['pipe','pipe','ignore'],detached:true});
  this.process.stdin.on('error',()=>{});
  this.lines=createInterface({input:this.process.stdout});this.lines.on('line',line=>{try{this.receive(JSON.parse(line))}catch{}});
  this.process.on('error',()=>this.close());this.process.on('close',()=>this.close());
  this.ready=this.rpc('initialize',{clientInfo:{name:'jarvis_core',version:'1.0.0'},capabilities:{experimentalApi:true}}).then(()=>this.send({method:'initialized'}));
  this.ready.catch(()=>this.close());this.touch();
 }
 touch(){clearTimeout(this.idle);this.idle=setTimeout(()=>{if(this.jobs.size||this.pending.size)this.touch();else this.close()},600000);this.idle.unref();}
 send(message){if(this.dead)throw Error('Connexion Codex interrompue.');this.process.stdin.write(JSON.stringify(message)+'\n');}
 rpc(method,params){if(this.dead)return Promise.reject(Error('Connexion Codex interrompue.'));return new Promise((resolve,reject)=>{const id=++this.serial;const timer=setTimeout(()=>{this.pending.delete(id);reject(Error('Codex ne répond pas à la connexion.'))},20000);this.pending.set(id,{resolve,reject,timer});this.send({id,method,params})})}
 receive(event){
  if(event.id!==undefined){const pending=this.pending.get(event.id);if(!pending)return;this.pending.delete(event.id);clearTimeout(pending.timer);event.error?pending.reject(Error('Codex a refusé cette opération.')):pending.resolve(event.result);return;}
  const params=event.params||{},job=this.jobs.get(params.threadId);if(!job)return;
  const now=Date.now()-job.started;
  if(event.method==='turn/started'){job.turnId=params.turn.id;if(job.signal?.aborted)this.interrupt(job);}
  if(event.method==='item/started'&&params.item?.type==='mcpToolCall')job.toolStarts.set(params.item.id,Date.now());
  if(event.method==='item/completed'){
   const item=params.item;job.execution.firstItemMs??=now;
   if(item.type==='agentMessage'&&item.phase!=='commentary')job.text=item.text;
   if(item.type==='commandExecution')job.execution.nativeCommands++;
   if(item.type==='webSearch')job.execution.webSearches++;
   if(item.type==='mcpToolCall'){const observation=haObservation(item);if(observation)job.observations.push(observation);if(item.tool==='piloter_home_assistant')job.controlled=true;job.execution.mcpCalls++;const start=job.toolStarts.get(item.id);if(start)job.execution.toolMs+=Date.now()-start;this.onTool(item);}
  }
  if(event.method==='turn/completed'){
   if(job.signal?.aborted)return job.reject(abortError());
   if(params.turn.status!=='completed')return job.reject(Error('Codex n’a pas terminé la réponse. Réessaie dans un instant.'));
   try{const result=JSON.parse(job.text);if(typeof result.answer!=='string'||typeof result.speech!=='string'||!Array.isArray(result.sourceIds)||!result.action)throw Error();result.execution={...job.execution,elapsedMs:now};job.resolve(result)}catch{job.reject(Error('La réponse de Codex est incomplète.'))}
  }
 }
 interrupt(job){if(job.turnId)this.rpc('turn/interrupt',{threadId:job.threadId,turnId:job.turnId}).catch(()=>{});}
 async answer(question,sources,context,signal){
  const started=Date.now();signal?.throwIfAborted();await this.ready;signal?.throwIfAborted();this.touch();
  let hints=[],facts=[];try{const memories=await this.explicitMemory('list',{space:context.space||'user'});facts=relevantFacts(question,memories,context.space||'user');const explicit=explicitAliasHints(question,memories);hints=explicit.length?explicit:await learnedHints(question,context.space||'user',this.learningStore)}catch{}signal?.throwIfAborted();
  const thread=await this.rpc('thread/start',{cwd:ROOT,model:process.env.JARVIS_CORE_MODEL||'gpt-6.1-sol',approvalPolicy:'never',sandbox:'workspace-write',ephemeral:true,developerInstructions:CORE_INSTRUCTIONS});
  let job,timer,abort;
  try{
   signal?.throwIfAborted();
   const done=new Promise((resolve,reject)=>{job={threadId:thread.thread.id,started,resolve,reject,signal,text:'',observations:[],controlled:false,toolStarts:new Map(),execution:{engine:'codex',transport:'warm-app-server',model:thread.model,nativeCommands:0,mcpCalls:0,webSearches:0,toolMs:0,setupMs:Date.now()-started,reusedLookups:hints.length,reusedFacts:facts.length}};this.jobs.set(job.threadId,job)});
   // Attach rejection handler immediately, including while turn/start is in flight.
   done.catch(()=>{});
   abort=()=>{this.interrupt(job);job.reject(abortError())};signal?.addEventListener('abort',abort,{once:true});
   timer=setTimeout(()=>{this.interrupt(job);job.reject(Error('Codex a dépassé le temps de réponse.'))},300000);
   const input={question,sources:sources.slice(0,2).map(s=>({...s,body:s.body.slice(0,1200)})),context:{...context,memoryFacts:facts,homeAssistantHints:hints,history:(context.history||[]).slice(-8).map(m=>({...m,text:m.text.slice(0,1600)}))}};
   const turn=await this.rpc('turn/start',{threadId:job.threadId,input:[{type:'text',text:JSON.stringify(input),text_elements:[]}],effort:process.env.JARVIS_CORE_REASONING||'low',outputSchema:ANSWER_SCHEMA});job.turnId=turn.turn.id;
   if(signal?.aborted)this.interrupt(job);
   const result=await done;
   if(!signal?.aborted)for(const key of invalidatedHints(hints.filter(h=>h.key),job.observations))try{await this.learningStore('forget',{space:context.space||'user',key})}catch{}
   if(!signal?.aborted&&!job.controlled&&result.action.type==='none'){const rows=learningRows(job.observations,result.resolvedEntities);if(rows.length)try{const saved=await this.learningStore('save',{space:context.space||'user',rows});result.execution.learnedLookups=saved.saved||0}catch{}}
   if(!signal?.aborted&&!job.controlled&&result.action.type==='none'){const corrections=await saveCorrections(question,result.userCorrections,job.observations,context.space||'user',this.explicitMemory);result.execution.savedCorrections=corrections.saved;
    if(corrections.saved)try{const prior=await this.learningStore('list',{space:context.space||'user'});for(const key of correctedHintKeys(corrections.applied,prior))await this.learningStore('forget',{space:context.space||'user',key})}catch{}
    const receipt=corrections.failed?'Je n’ai pas pu enregistrer durablement cette correction.':corrections.saved?'Correction enregistrée pour les prochaines conversations.':'';
    if(receipt){result.answer+=' '+receipt;result.speech+=' '+receipt;}
   }
   delete result.userCorrections;delete result.resolvedEntities;return result;
  }finally{
   clearTimeout(timer);signal?.removeEventListener('abort',abort);this.jobs.delete(thread.thread.id);
   this.rpc('thread/unsubscribe',{threadId:thread.thread.id}).catch(()=>{});this.touch();
  }
 }
 close(){if(this.dead)return;this.dead=true;clearTimeout(this.idle);this.lines.close();try{process.kill(-this.process.pid,'SIGKILL')}catch{}
  for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error('Connexion Codex interrompue.'))}this.pending.clear();for(const j of this.jobs.values())j.reject(Error('Connexion Codex interrompue.'));this.jobs.clear();
 }
}
export function warmAnswer(question,sources,context={},signal){const space=context.space||'user';if(!['user','amelie','malik','theo','commun'].includes(space))throw Error('Espace inconnu.');let worker=workers.get(space);if(!worker||worker.dead){worker=new CodexWorker(space);workers.set(space,worker)}return worker.answer(question,sources,context,signal)}
export function closeCodexWorkers(){for(const worker of workers.values())worker.close();workers.clear()}
