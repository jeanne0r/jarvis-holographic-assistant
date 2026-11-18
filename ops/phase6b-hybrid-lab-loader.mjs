// P6-L2 lab only. Ordinary providers are fake; /ask and Hermes admission stay real.
import {pathToFileURL} from 'node:url';
import {join,resolve as absolutePath} from 'node:path';
const copy=absolutePath(process.env.P6L2_LAB_COPY||'');
if(!copy.includes('/data/phase6/')||!copy.endsWith('/copy/server'))throw Error('Explicit isolated P6-L2 copy required');
const backend=pathToFileURL(join(copy,'backend.mjs')).href;
const brain=pathToFileURL(join(copy,'hybrid-brain.mjs')).href;
export async function resolveModule(specifier,context,next){
 if(context.parentURL===backend&&specifier==='./ai.mjs'){
  const code=`import {hybridAnswer} from ${JSON.stringify(brain)};
   export async function answer(q,s,c,signal){
    const counts=globalThis.p6l2Providers??={classifications:0,gemini:0,codex:0};
    return hybridAnswer(q,s,c,signal,{
     classify:async()=>{counts.classifications++;return q.startsWith('local:')?'codex':'gemini'},
     memoryStore:async()=>[],
     gemini:async()=>{counts.gemini++;return {answer:'Gemini simulé : réponse ordinaire.',sourceIds:[]}},
     codex:async()=>{counts.codex++;return {answer:'Codex simulé : diagnostic synthétique.',sourceIds:[]}}
    });
   }`;
  return {url:'data:text/javascript,'+encodeURIComponent(code),shortCircuit:true};
 }
 return next(specifier,context);
}
export {resolveModule as resolve};
