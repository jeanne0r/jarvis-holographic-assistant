import {copyFile,mkdir,access,writeFile,chmod} from 'node:fs/promises';
import {PROJECT_ROOT} from '../runtime-paths.mjs';
await mkdir(PROJECT_ROOT+'/data',{recursive:true,mode:0o700});
await mkdir(PROJECT_ROOT+'/memory',{recursive:true,mode:0o700});
try{await access(PROJECT_ROOT+'/.env')}catch{await copyFile(PROJECT_ROOT+'/.env.example',PROJECT_ROOT+'/.env');await chmod(PROJECT_ROOT+'/.env',0o600);console.log('Created .env. Fill in your own credentials.');}
try{await access(PROJECT_ROOT+'/data/core-engine.json')}catch{await writeFile(PROJECT_ROOT+'/data/core-engine.json',JSON.stringify({engine:'hybrid',voice:'gemini-speech'})+'\n',{mode:0o600});}
console.log('Runtime directories ready. No credentials or memories imported.');
