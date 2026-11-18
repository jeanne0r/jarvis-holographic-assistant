import {readFile} from 'node:fs/promises';
// Only a key explicitly designated as a browser key is ever sent to the client.
// Never publish the existing private MAPS_API_KEY or Gemini key by inference.
export async function mapsConfig(){
 let key=process.env.GOOGLE_MAPS_BROWSER_KEY;
 if(!key){try{key=JSON.parse(await readFile('/home/user/workspace/jarvis/data/maps-browser.json','utf8')).key;}catch{}}
 return key?{configured:true,key}:{configured:false,message:'Clé Google Maps pour navigateur non configurée. Les liens Google Maps restent disponibles.'};
}
export async function youtubeKey(){
 if(process.env.YOUTUBE_API_KEY)return process.env.YOUTUBE_API_KEY;
 try{return JSON.parse(await readFile('/home/user/workspace/jarvis/data/integrations-server.json','utf8')).youtubeKey||null;}catch{return null;}
}
