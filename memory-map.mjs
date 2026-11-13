import {spawn} from 'node:child_process';
let running=0;
export async function memoryMap(space,offset=null){
 if(running>=2)throw Error('Une carte est en préparation. Réessaie dans un instant.');
 running++;
 try{return await new Promise((resolve,reject)=>{
  const child=spawn('python3',[new URL('./semantic/map3d.py',import.meta.url).pathname],{stdio:['pipe','pipe','ignore']});let out='';
  const timeout=setTimeout(()=>child.kill('SIGKILL'),25000);
  child.stdout.on('data',x=>{out+=x;if(out.length>8000000)child.kill('SIGKILL');});child.stdin.on('error',()=>{});
  child.once('error',()=>{clearTimeout(timeout);reject(Error('Carte indisponible.'));});
  child.once('close',()=>{clearTimeout(timeout);try{const r=JSON.parse(out);r.ok?resolve(r.data):reject(Error(r.error));}catch{reject(Error('Carte indisponible pour le moment.'));}});
  child.stdin.end(JSON.stringify({space,offset}));
 });}finally{running--;}
}
