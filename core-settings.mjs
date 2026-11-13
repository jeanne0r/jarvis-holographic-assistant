import {readFileSync} from 'node:fs';
let settings={engine:'hybrid'};
try{settings=JSON.parse(readFileSync(new URL('./data/core-engine.json',import.meta.url),'utf8'));}catch{}
if(process.env.JARVIS_ENGINE)settings.engine=process.env.JARVIS_ENGINE;
if(!['codex','gemini-fast','gemini-live','hybrid'].includes(settings.engine))throw Error('Moteur Jarvis inconnu.');
export function coreInfo(){return settings.engine==='hybrid'?{engine:'hybrid',provider:'google+openai',model:process.env.JARVIS_GEMINI_TEXT_MODEL||'gemini-3.5-flash-lite',localModel:process.env.JARVIS_CORE_MODEL||'default',routing:'Gemini : général et Internet ; Codex : HA, machines et LAN'}:settings.engine==='gemini-live'?{engine:'gemini-live',provider:'google',model:process.env.JARVIS_GEMINI_LIVE_MODEL||'gemini-3.8-live'}:settings.engine==='gemini-fast'?{engine:'gemini-fast',provider:'google',model:process.env.JARVIS_GEMINI_TEXT_MODEL||'gemini-3.5-flash-lite'}:{engine:'codex',provider:'openai',model:process.env.JARVIS_CORE_MODEL||'default'};}
