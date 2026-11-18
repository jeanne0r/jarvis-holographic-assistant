// Laboratory only: replace providers/archive at module boundary, not /ask routing.
const brain=new URL('./hybrid-brain.mjs',import.meta.url).href;
export async function resolve(specifier,context,next){
 if(context.parentURL?.endsWith('/backend.mjs')){
  const sources={
   './core-settings.mjs':`export const coreInfo=()=>({engine:'hybrid'});`,
   './archive.mjs':`export async function archive(){globalThis.labArchives=(globalThis.labArchives||0)+1;return {}}`,
   './ai.mjs':`import {hybridAnswer} from ${JSON.stringify(brain)};
    export async function answer(q,s,c,signal){return hybridAnswer(q,s,c,signal,{
     classify:async()=>{globalThis.labClassifications=(globalThis.labClassifications||0)+1;return q.startsWith('local:')?'codex':'gemini'},
     memoryStore:async()=>[],
     codex:async()=>{globalThis.labCodex=(globalThis.labCodex||0)+1;return {answer:'Codex simulé',sourceIds:[]}},
     gemini:async()=>{globalThis.labGemini=(globalThis.labGemini||0)+1;return {answer:'Gemini simulé',sourceIds:[]}}
    })}`,
  };
  if(sources[specifier])return {url:'data:text/javascript,'+encodeURIComponent(sources[specifier]),shortCircuit:true};
 }
 return next(specifier,context);
}
