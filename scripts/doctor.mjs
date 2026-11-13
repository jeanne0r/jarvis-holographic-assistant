import {spawnSync} from 'node:child_process';
import {access} from 'node:fs/promises';
import {CODEX_BIN,PROJECT_ROOT} from '../runtime-paths.mjs';
const checks=[];const add=(name,ok,detail)=>checks.push({name,ok,detail});
add('Node.js',Number(process.versions.node.split('.')[0])>=22,process.versions.node);
add('Python',spawnSync('python3',['--version']).status===0,'Python 3.10+ required');
add('Gemini',Boolean(process.env.GEMINI_API_KEY||process.env.GOOGLE_API_KEY),'API key presence only; not printed or sent');
const codex=spawnSync(CODEX_BIN,['--version'],{encoding:'utf8'});add('Codex CLI',codex.status===0,codex.status===0?'Installed':'Install and run codex login');
add('Home Assistant',Boolean(process.env.HOME_ASSISTANT_URL&&process.env.HOME_ASSISTANT_TOKEN),'Optional; both URL and token are required for HA requests');
add('Semantic memory',Boolean(process.env.JARVIS_SEMANTIC_URL&&process.env.QDRANT__SERVICE__API_KEY),'Optional; SQLite retrieval works without Qdrant');
try{await access(PROJECT_ROOT+'/data');add('Runtime directory',true,'Ready')}catch{add('Runtime directory',false,'Run npm run setup')}
for(const c of checks)console.log(`${c.ok?'OK':'MISSING'} ${c.name}: ${c.detail}`);
console.log('Doctor does not verify provider model access, Codex login, or HA connectivity.');
