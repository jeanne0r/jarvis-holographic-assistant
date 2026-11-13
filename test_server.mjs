import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import net from 'node:net';
async function start(password=''){
 const probe=net.createServer();probe.listen(0,'127.0.0.1');await once(probe,'listening');const port=probe.address().port;await new Promise(r=>probe.close(r));
 const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,HOST:'127.0.0.1',PORT:String(port),JARVIS_ACCESS_PASSWORD:password,HTTPS_KEY:'',HTTPS_CERT:'',JARVIS_IMPORT_CODEX_SESSIONS:'false'},stdio:['ignore','pipe','pipe']});
 let output='';child.stdout.on('data',x=>output+=x);child.stderr.on('data',x=>output+=x);
 for(let i=0;i<60;i++){if(child.exitCode!==null)throw Error(output);try{await fetch(`http://127.0.0.1:${port}/api/health`);return {child,base:`http://127.0.0.1:${port}`}}catch{await new Promise(r=>setTimeout(r,50));}}
 child.kill();throw Error('Server startup timed out');
}
for(const password of ['', 'test-only-password']){
 const {child,base}=await start(password);
 try{
  const headers=password?{authorization:'Basic '+Buffer.from('jarvis:'+password).toString('base64')}:{};
  if(password)assert.equal((await fetch(base+'/api/health')).status,401);
  assert.equal((await fetch(base+'/api/health',{headers})).status,200);
  const index=await fetch(base+'/jarvis/',{headers});assert.equal(index.status,200);assert((await index.text()).includes('id="voiceStop"'));
  for(const p of ['/jarvis/hologram.js','/jarvis/vendor/three.module.min.js','/api/jarvis/voice/status','/api/jarvis/docs?space=member1','/api/jarvis/memory/status?space=member1'])assert.equal((await fetch(base+p,{headers})).status,200,p);
  assert.equal((await fetch(base+'/jarvis/%2e%2e%2f.env',{headers})).status,403);
  assert.equal((await fetch(base+'/.env',{headers})).status,404);
  assert.deepEqual(await (await fetch(base+'/api/jarvis/apps',{headers})).json(),{apps:[]});
  assert.equal((await fetch(base+'/api/jarvis/ask',{method:'POST',headers:{...headers,'content-type':'application/json',origin:'https://untrusted.example.test'},body:'{}'})).status,403);
 }finally{child.kill('SIGTERM');await once(child,'exit');}
}
console.log('PASS standalone server: clean startup, UI/assets, memory, optional apps, authentication, traversal denial and cross-origin rejection.');
