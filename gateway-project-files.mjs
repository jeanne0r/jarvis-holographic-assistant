// Read-only project filesystem adapter; no traversal, symlinks, homes or secret files.
import path from 'node:path';
import {lstat,realpath,readdir,open} from 'node:fs/promises';
import {constants} from 'node:fs';
const forbidden=p=>p.split('/').some(x=>['.env','.git','.ssh','.codex','_secrets','node_modules'].includes(x)||/^\.env\./.test(x));
export function projectFiles(roots){
 async function location(project,relative=''){
  const root=roots[project];if(!root||path.isAbsolute(relative)||relative.includes('\\')||relative.split('/').some(x=>x==='..')||forbidden(relative))throw Error('File scope denied');
  const base=await realpath(root),target=path.resolve(base,relative);if(target!==base&&!target.startsWith(base+path.sep))throw Error('File boundary');
  let current=base;for(const p of relative.split('/').filter(Boolean)){current=path.join(current,p);if((await lstat(current)).isSymbolicLink())throw Error('Symlink denied')}
  return {base,target};
 }
 return Object.freeze({async tree({project}){
  const {target}=await location(project);const entries=await readdir(target,{withFileTypes:true});if(entries.length>2000)throw Error('Tree bound');
  return entries.filter(e=>!e.isSymbolicLink()&&!forbidden(e.name)).map(e=>({name:e.name,type:e.isDirectory()?'directory':'file'}));
 },async read(project,relative){const {base,target}=await location(project,relative);const f=await open(target,constants.O_RDONLY|constants.O_NOFOLLOW);try{const actual=await realpath('/proc/self/fd/'+f.fd),s=await f.stat();if(!actual.startsWith(base+path.sep)||!s.isFile()||s.size>524288)throw Error('File bound');return await f.readFile('utf8')}finally{await f.close()}}});
}
