// Private stdio MCP bridge shared by the written and spoken Codex engine.
import {createInterface} from 'node:readline';
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {homeAssistantTools,consultHomeAssistant,listHomeAssistantServices,controlHomeAssistant} from './home-assistant.mjs';
import {voiceMemoryTool,voiceMemory,memoryStore} from './voice-memory.mjs';
import {knowledgeTool,voiceKnowledge} from './knowledge.mjs';
import {capabilityTools,capabilityHandler} from './capabilities.mjs';

const declarations=[...homeAssistantTools,voiceMemoryTool,knowledgeTool,...capabilityTools];
function jsonSchema(value){
 if(Array.isArray(value))return value.map(jsonSchema);
 if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([key,v])=>[key,key==='type'?v.toLowerCase():jsonSchema(v)]));
 return value;
}
export async function createJarvisTools(space,dependencies={}){
 if(!['user','amelie','malik','theo','commun'].includes(space))throw Error('Espace inconnu.');
 const memories=await (dependencies.memoryStore||memoryStore)('list',{space});
 const session={space,engine:dependencies.engine,entities:new Set(),services:new Map(),memories,economy:true};
 const handlers={consulter_home_assistant:consultHomeAssistant,commandes_home_assistant:listHomeAssistantServices,piloter_home_assistant:controlHomeAssistant,memoire_jarvis:voiceMemory,chercher_souvenirs:voiceKnowledge,...Object.fromEntries(capabilityTools.map(t=>[t.name,(args,s)=>capabilityHandler(t.name,args,s)])),...dependencies.handlers};
 const results=new Map(),commands=new Map();let calls=0;
 return {
  tools:declarations.map(d=>({name:d.name,description:d.description,inputSchema:jsonSchema(d.parameters),annotations:{readOnlyHint:['consulter_home_assistant','commandes_home_assistant','chercher_souvenirs'].includes(d.name),destructiveHint:d.name==='piloter_home_assistant'||d.name==='memoire_jarvis',openWorldHint:false}})),
  async call(name,args={},id){
   const declaration=declarations.find(d=>d.name===name);
   if(!declaration)throw Error('Outil inconnu.');
   if(++calls>30)throw Error('Trop de consultations pour cette réponse.');
   if(!args||typeof args!=='object'||Array.isArray(args)||JSON.stringify(args).length>5000)throw Error('Paramètres invalides.');
   const safe=Object.fromEntries(Object.entries(args).filter(([key])=>Object.hasOwn(declaration.parameters.properties,key)));
   const fingerprint=JSON.stringify([name,safe]);
   if(results.has(id)) {const prior=results.get(id);if(prior.fingerprint!==fingerprint)throw Error('Appel déjà utilisé.');return prior.promise;}
   if(name==='piloter_home_assistant'&&commands.has(fingerprint))return commands.get(fingerprint);
   const promise=Promise.resolve().then(()=>handlers[name](safe,session));
   if(name==='piloter_home_assistant')commands.set(fingerprint,promise);
   results.set(id,{fingerprint,promise});return promise;
  },
 };
}

async function main(){
 // Credentials stay inside the private tool server, never in prompts or CLI arguments.
 for(const file of ['/home/user/gateway/.env','/home/user/workspace/_secrets/.env']){
  try{for(const line of(await readFile(file,'utf8')).split('\n')){const m=line.match(/^(HOME_ASSISTANT_(?:URL|TOKEN)|GEMINI_API_KEY|GOOGLE_API_KEY)=(.*)$/);if(m)process.env[m[1]]=m[2].replace(/^['"]|['"]$/g,'');}}catch{}
 }
 const bridge=await createJarvisTools(process.argv[2],{engine:'codex'});
 const send=value=>process.stdout.write(JSON.stringify(value)+'\n');
 let chain=Promise.resolve(),closed=false;
 createInterface({input:process.stdin,crlfDelay:Infinity}).on('close',()=>{closed=true;}).on('line',line=>{
  let message;try{message=JSON.parse(line);}catch{return;}
  if(message.id===undefined)return;
  chain=chain.then(async()=>{
   if(closed)return;
   const {id,method,params={}}=message;
   try{
    let result;
    if(method==='initialize')result={protocolVersion:params.protocolVersion,capabilities:{tools:{}},serverInfo:{name:'jarvis-private-tools',version:'1.0.0'}};
    else if(method==='ping')result={};
    else if(method==='tools/list')result={tools:bridge.tools};
    else if(method==='tools/call'){
     try{result={content:[{type:'text',text:JSON.stringify(await bridge.call(params.name,params.arguments,id))}]};}
     catch(error){result={isError:true,content:[{type:'text',text:error.message}]};}
    }else {send({jsonrpc:'2.0',id,error:{code:-32601,message:'Méthode inconnue.'}});return;}
    send({jsonrpc:'2.0',id,result});
   }catch{send({jsonrpc:'2.0',id,error:{code:-32603,message:'Outils Jarvis indisponibles.'}});}
  });
 });
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)main().catch(()=>process.exit(1));
