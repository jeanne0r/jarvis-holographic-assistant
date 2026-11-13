import {CODEX_BIN,PROJECT_ROOT,PUBLIC_ROOT} from './runtime-paths.mjs';
import {hybridAnswer} from './hybrid-brain.mjs';
import {warmAnswer} from './codex-worker.mjs';
import {createInterface} from 'node:readline';
import {liveAnswer} from './live-brain.mjs';
import {spawn} from 'node:child_process';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {ANSWER_SCHEMA,CORE_INSTRUCTIONS} from './core-instructions.mjs';
import {fastAnswer} from './fast-brain.mjs';
import {coreInfo} from './core-settings.mjs';
export function answer(question,sources,context={},signal){
 if(coreInfo().engine==='hybrid')return hybridAnswer(question,sources,context,signal,{codex:generateAnswer});
 return coreInfo().engine==='gemini-live'?liveAnswer(question,sources,context,signal):coreInfo().engine==='gemini-fast'?fastAnswer(question,sources,context,signal):generateAnswer(question,sources,context,signal);
}
export async function generateAnswer(question,sources,context={},signal){
 if(process.env.JARVIS_CODEX_TRANSPORT!=='exec'){const result=await warmAnswer(question,sources,context,signal);result.sourceIds=result.sourceIds.filter(id=>sources.some(s=>s.id===id));return result;}
 return execAnswer(question,sources,context,signal);
}
export async function execAnswer(question,sources,context={},signal){
 const started=Date.now(),execution={engine:'codex',nativeCommands:0,mcpCalls:0,webSearches:0};
 const dir=await mkdtemp(PROJECT_ROOT+'/data/ai-');
 try {
 await writeFile(dir+'/schema.json',JSON.stringify(ANSWER_SCHEMA),{mode:0o600});

 const args=['exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','workspace-write','-c','approval_policy="never"','-c','web_search="live"','-c','project_doc_max_bytes=32768','-c','sandbox_workspace_write.network_access=true','-c','sandbox_workspace_write.writable_roots='+JSON.stringify([PUBLIC_ROOT]),'-c','model_reasoning_effort='+JSON.stringify(process.env.JARVIS_CORE_REASONING||'low'),'-c','developer_instructions='+JSON.stringify(CORE_INSTRUCTIONS),
 '-c','mcp_servers.jarvis.command="node"','-c','mcp_servers.jarvis.args='+JSON.stringify([PROJECT_ROOT+'/tools-server.mjs',context.space||'member1']),'-c','mcp_servers.jarvis.required=true','-c','mcp_servers.jarvis.default_tools_approval_mode="approve"'];
 if(process.env.JARVIS_CORE_MODEL)args.push('--model',process.env.JARVIS_CORE_MODEL);
 for(const f of ['apps','plugins','multi_agent','multi_agent_v2','browser_use','computer_use','image_generation','hooks','memories'])args.push('--disable',f);
 args.push('--json','--enable','shell_tool','--enable','unified_exec','--output-schema',dir+'/schema.json','--output-last-message',dir+'/result.json','-');
 await new Promise((resolve,reject)=>{
 const child=spawn(CODEX_BIN,args,{cwd:PROJECT_ROOT,env:{HOME:process.env.HOME,PATH:process.env.PATH,LANG:'C.UTF-8'},stdio:['pipe','pipe','ignore'],detached:true});
 const events=createInterface({input:child.stdout});events.on('line',line=>{try{const event=JSON.parse(line);if(event.type==='item.completed'){if(event.item?.type==='command_execution')execution.nativeCommands++;if(event.item?.type==='mcp_tool_call')execution.mcpCalls++;if(event.item?.type==='web_search')execution.webSearches++;}}catch{}});
 const kill=()=>{try{process.kill(-child.pid,'SIGKILL')}catch{}};
 const timer=setTimeout(kill,300000);signal?.addEventListener('abort',kill,{once:true});if(signal?.aborted)kill();
 child.on('error',()=>{clearTimeout(timer);signal?.removeEventListener('abort',kill);reject(Error('Connexion IA indisponible.'))});child.on('close',code=>{clearTimeout(timer);signal?.removeEventListener('abort',kill);code===0?resolve():reject(Error('Jarvis n’a pas pu répondre. Réessaie dans un instant.'))});
 child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify({question,sources:sources.slice(0,2).map(s=>({...s,body:s.body.slice(0,1200)})),context:{...context,history:(context.history||[]).slice(-8).map(m=>({...m,text:m.text.slice(0,1600)}))}}));
 });
 const result=JSON.parse(await readFile(dir+'/result.json','utf8'));result.sourceIds=result.sourceIds.filter(id=>sources.some(s=>s.id===id));result.execution={...execution,elapsedMs:Date.now()-started};return result;
 }finally{await rm(dir,{recursive:true,force:true})}
}
