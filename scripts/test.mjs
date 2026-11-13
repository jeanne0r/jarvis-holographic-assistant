import {readdir,mkdtemp,rm} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import os from 'node:os';import path from 'node:path';
const dir=await mkdtemp(path.join(os.tmpdir(),'jarvis-tests-'));
const env={...process.env,JARVIS_DB:dir+'/brain.sqlite',JARVIS_VOICE_MEMORY_DB:dir+'/voice.sqlite',JARVIS_USAGE_DB:dir+'/usage.sqlite',JARVIS_IMPORT_CODEX_SESSIONS:'false',GEMINI_API_KEY:'',GOOGLE_API_KEY:'',HOME_ASSISTANT_TOKEN:'',HOME_ASSISTANT_URL:''};
let failed=false;
try{
 for(const file of (await readdir('.')).filter(f=>/^test_.*\.mjs$/.test(f)).sort()){
  const r=spawnSync(process.execPath,[file],{env,stdio:'inherit'});if(r.status!==0){failed=true;break;}
 }
 if(!failed){const r=spawnSync('python3',['-m','unittest','discover','-s','.','-p','test_*.py'],{env,stdio:'inherit'});failed=r.status!==0;}
 if(!failed){const r=spawnSync('python3',['-m','unittest','discover','-s','semantic','-p','test_*.py'],{env,stdio:'inherit'});failed=r.status!==0;}
}finally{await rm(dir,{recursive:true,force:true});}
if(failed)process.exitCode=1;
