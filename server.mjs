import {createServer} from 'node:http';
import {createServer as createHttpsServer} from 'node:https';
import {createHash,timingSafeEqual} from 'node:crypto';
import {readFile,mkdir,stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {PROJECT_ROOT,PUBLIC_ROOT} from './runtime-paths.mjs';
const host=process.env.HOST||'127.0.0.1',port=Number(process.env.PORT||8787),password=process.env.JARVIS_ACCESS_PASSWORD||'';
const loopback=['127.0.0.1','localhost','::1'].includes(host);
if(!loopback&&!password)throw Error('Set JARVIS_ACCESS_PASSWORD before binding to a LAN address.');
if(!loopback&&(!process.env.HTTPS_KEY||!process.env.HTTPS_CERT))throw Error('Configure HTTPS_KEY and HTTPS_CERT before binding to the LAN.');
await mkdir(path.join(PROJECT_ROOT,'data'),{recursive:true,mode:0o700});
const {handleJarvis}=await import('./backend.mjs');
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.wasm':'application/wasm','.tflite':'application/octet-stream','.json':'application/json','.txt':'text/plain; charset=utf-8'};
const digest=x=>createHash('sha256').update(x).digest();
export async function handler(req,res){
 try{
  if(password){const expected='Basic '+Buffer.from('jarvis:'+password).toString('base64');if(!timingSafeEqual(digest(req.headers.authorization||''),digest(expected))){res.writeHead(401,{'www-authenticate':'Basic realm="Jarvis", charset="UTF-8"','cache-control':'no-store'});res.end('Authentication required');return;}}
  const url=new URL(req.url,`http://${req.headers.host||'localhost'}`);
  if(loopback&&!['127.0.0.1','localhost','[::1]'].includes(url.hostname)){res.writeHead(421);res.end('Invalid host');return;}
  res.setHeader('Content-Security-Policy',"frame-ancestors 'self'");
  res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','same-origin');
  if(url.pathname==='/api/health'){res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify({ok:true}));return;}
  if(url.pathname==='/api/jarvis/apps'){
   let apps=[];try{apps=JSON.parse(await readFile(PROJECT_ROOT+'/data/app-links.json','utf8'))}catch{}
   apps=Array.isArray(apps)?apps.filter(a=>{try{const u=new URL(a.url,`http://${req.headers.host}`);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&typeof a.id==='string'&&typeof a.title==='string'}catch{return false}}).map(({id,title,url})=>({id,title,url})):[];
   res.writeHead(200,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify({apps}));return;
  }
  if(url.pathname.startsWith('/api/jarvis/')){await handleJarvis(req,res,url);return;}
  if(['/','/jarvis'].includes(url.pathname)){res.writeHead(302,{location:'/jarvis/'});res.end();return;}
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);res.end();return;}
  if(!url.pathname.startsWith('/jarvis/')){res.writeHead(404);res.end('Not found');return;}
  const relative=decodeURIComponent(url.pathname.slice('/jarvis/'.length))||'index.html';
  const target=path.resolve(PUBLIC_ROOT,relative);
  if(!target.startsWith(PUBLIC_ROOT+path.sep)){res.writeHead(403);res.end();return;}
  const info=await stat(target);if(!info.isFile()){res.writeHead(404);res.end();return;}
  res.writeHead(200,{'content-type':mime[path.extname(target)]||'application/octet-stream','cache-control':'no-cache'});
  res.end(req.method==='HEAD'?undefined:await readFile(target));
 }catch{if(!res.headersSent)res.writeHead(404);res.end('Not found');}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const tls=process.env.HTTPS_KEY&&process.env.HTTPS_CERT;
 const server=tls?createHttpsServer({key:await readFile(process.env.HTTPS_KEY),cert:await readFile(process.env.HTTPS_CERT)},handler):createServer(handler);
 server.listen(port,host,()=>console.log(`Jarvis ready at ${tls?'https':'http'}://${host}:${port}/jarvis/`));
}
