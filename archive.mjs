import {spawn} from 'node:child_process';
export function archive(action,data){
 return new Promise((resolve,reject)=>{
  const child=spawn('python3',[new URL('./store.py',import.meta.url).pathname,'conversation_'+action],{stdio:['pipe','pipe','ignore']});let output='';
  const timer=setTimeout(()=>child.kill('SIGKILL'),12000);
  child.stdout.on('data',chunk=>output+=chunk);child.stdin.on('error',()=>{});
  child.on('error',()=>{clearTimeout(timer);reject(Error('Enregistrement des échanges indisponible.'));});
  child.on('close',()=>{clearTimeout(timer);try{const r=JSON.parse(output);r.ok?resolve(r.data):reject(Error(r.error));}catch{reject(Error('Enregistrement des échanges indisponible.'));}});
  child.stdin.end(JSON.stringify(data));
 });
}
