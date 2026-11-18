// Test host only: never import the active gateway or its background loops.
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import {embeddedRelay} from '../hermes-embedded-relay.mjs';
const cfg=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
const relay=embeddedRelay({enabled:true,origin:cfg.origin,port:cfg.upstreamPort,switchFile:cfg.switchFile});
const server=http.createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,cfg.origin);
  if(await relay(req,res,url))return;
  const send=(data)=>{res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify(data))};
  if(cfg.simulatorStartSignal&&req.method==='POST'&&url.pathname==='/api/test/start-simulator'){await fs.writeFile(cfg.simulatorStartSignal,'start',{flag:'wx',mode:0o600});return send({simulator_only:true})}
  if(url.pathname.startsWith('/api/')){
   if(url.pathname.endsWith('/docs'))return send({docs:[],total:0,counts:{},lastSync:null});
   if(url.pathname.endsWith('/voice/status')||url.pathname.endsWith('/live/status'))return send({configured:false,engine:'hybrid'});
   return send({configured:false,counts:{},index:{state:'ready'},ledger:{},state:'ready',sources:[],points:[],items:[]});
  }
  let name=url.pathname.replace(/^\/jarvis\//,'');if(url.pathname==='/jarvis/')name='index.html';
  const root=['index.html','hermes-embedded.js','hermes-embedded.css',...(cfg.operationalAssets?['app.js']:[])].includes(name)?cfg.frontend:cfg.sourcePublic;
  const file=path.resolve(root,name);
  if(!file.startsWith(path.resolve(root)+path.sep))throw Error('Static path');
  const raw=await fs.readFile(file);
  const ext=path.extname(file);const types={'.html':'text/html','.js':'application/javascript','.mjs':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.json':'application/json','.png':'image/png','.wasm':'application/wasm'};
  res.writeHead(200,{'content-type':types[ext]||'application/octet-stream'});res.end(raw);
 }catch{res.writeHead(404);res.end()}
});
server.listen(new URL(cfg.origin).port,'127.0.0.1');
for(const sig of ['SIGTERM','SIGINT'])process.once(sig,()=>{server.closeAllConnections?.();server.close()});
