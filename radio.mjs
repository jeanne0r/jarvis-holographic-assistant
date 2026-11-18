// Discover stations at request time; never accept a model-invented stream URL.
import {resolveSrv,lookup} from 'node:dns/promises';
import {BlockList,isIP} from 'node:net';
const blocked=new BlockList();
for(const [ip,bits] of [['0.0.0.0',8],['10.0.0.0',8],['100.64.0.0',10],['127.0.0.0',8],['169.254.0.0',16],['172.16.0.0',12],['192.168.0.0',16],['192.0.0.0',24],['192.0.2.0',24],['198.18.0.0',15],['198.51.100.0',24],['203.0.113.0',24],['224.0.0.0',3]])blocked.addSubnet(ip,bits,'ipv4');
for(const [ip,bits] of [['::',128],['::1',128],['fc00::',7],['fe80::',10],['ff00::',8],['2001:db8::',32]])blocked.addSubnet(ip,bits,'ipv6');
export function publicAddress(ip){if(ip.startsWith('::ffff:'))return publicAddress(ip.slice(7));const family=isIP(ip);return !!family&&!blocked.check(ip,family===6?'ipv6':'ipv4');}
export async function streamUrl(value,dependencies={}){
 const u=new URL(value);if(u.protocol!=='https:'||u.username||u.password||u.href.length>3000)throw Error('Flux radio HTTPS public requis.');
 const host=u.hostname.replace(/^\[|\]$/g,'');if(!host.includes('.')||/\.(local|localhost|internal|test|invalid)$/.test(host)||host==='localhost')throw Error('Adresse radio non publique.');
 const addresses=await (dependencies.lookup||lookup)(host,{all:true});if(!addresses.length||addresses.some(a=>!publicAddress(a.address)))throw Error('Adresse radio non publique.');return u.href;
}
let serverCache;
async function servers(){
 if(serverCache&&serverCache.expires>Date.now())return serverCache.hosts;
 const records=await resolveSrv('_api._tcp.radio-browser.info');const hosts=records.filter(r=>/^[a-z0-9-]+\.api\.radio-browser\.info$/.test(r.name)&&r.port===443).map(r=>r.name);if(!hosts.length)throw Error('Annuaire radio indisponible.');serverCache={hosts,expires:Date.now()+3600000};return hosts;
}
async function directory(path,params,dependencies){
 if(dependencies.directory)return dependencies.directory(path,params);
 for(const host of await servers())try{const url=new URL('https://'+host+path);url.search=new URLSearchParams(params);const r=await fetch(url,{headers:{'user-agent':'Jarvis/1.0 (personal radio player)'},signal:AbortSignal.timeout(4000)});if(r.ok){const data=await r.json();if(Array.isArray(data))return data;}}catch{}
 throw Error('L’annuaire radio ne répond pas. Réessaie dans un instant.');
}
const normalize=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
export async function searchRadios(args,dependencies={}){
 let rows;const query=String(args.genre||args.query||'').trim().replace(/^(?:(?:la|une)\s+)?radio\s+/i,'');
 if(args.station_id){if(!/^[a-f0-9-]{36}$/i.test(args.station_id))throw Error('Identifiant de station invalide.');rows=await directory('/json/stations/byuuid/'+args.station_id,{},dependencies);}
 else{
  if(!query||query.length>180)throw Error('Précise un nom de station ou un genre musical.');
  const params={hidebroken:'true',limit:'30',order:'clickcount',reverse:'true'};
  const searches=args.genre?[directory('/json/stations/search',{...params,tag:query},dependencies)]:[directory('/json/stations/search',{...params,name:query},dependencies),directory('/json/stations/search',{...params,tag:query},dependencies)];
  const results=await Promise.allSettled(searches);rows=results.flatMap(r=>r.status==='fulfilled'?r.value:[]);if(results.every(r=>r.status==='rejected'))throw Error('La recherche radio est indisponible.');
 }
 const unique=[...new Map(rows.filter(s=>s.lastcheckok===1&&s.stationuuid).map(s=>[s.stationuuid,s])).values()];
 const q=normalize(query);const score=s=>(normalize(s.name)===q?1000:normalize(s.name).startsWith(q)?100:0)+(/french|français/i.test(s.language)?15:0)+(['FR','CH'].includes(s.countrycode)?10:0)+Math.log1p(Math.max(0,Number(s.clickcount)||0));
 unique.sort((a,b)=>score(b)-score(a));const selected=[];
 for(const s of unique){try{let candidate=s.url_resolved||s.url;const parsed=new URL(candidate);if(parsed.protocol==='http:'){parsed.protocol='https:';if(parsed.port==='80')parsed.port='';candidate=parsed.href;}const url=await streamUrl(candidate,dependencies);selected.push({id:s.stationuuid,name:String(s.name).trim().slice(0,150),url,tags:String(s.tags||'').slice(0,200),country:String(s.country||''),checkedAt:s.lastcheckoktime_iso8601||null,source:'Radio Browser'});if(selected.length===5)break;}catch{}}
 return selected;
}
export async function probeRadio(value,dependencies={}){
 if(dependencies.probe)return dependencies.probe(value);
 const signal=AbortSignal.timeout(4000);let url=value;
 for(let redirects=0;redirects<4;redirects++){
  url=await streamUrl(url,dependencies);const r=await fetch(url,{redirect:'manual',signal,headers:{'user-agent':'Jarvis/1.0','range':'bytes=0-31'}});
  const type=r.headers.get('content-type')||'',location=r.headers.get('location');await r.body?.cancel();
  if([301,302,303,307,308].includes(r.status)&&location){url=new URL(location,url).href;continue;}
  if(!r.ok||!/(audio\/|application\/(vnd\.apple\.mpegurl|x-mpegurl|ogg|octet-stream))/i.test(type))throw Error('Le flux ne renvoie pas d’audio.');return {url,contentType:type};
 }
 throw Error('Le flux radio redirige trop de fois.');
}
export async function resolveRadio(args,dependencies={}){
 const stations=await searchRadios(args,dependencies);
 for(const station of stations.slice(0,3))try{const check=await probeRadio(station.url,dependencies);return {...station,url:check.url,contentType:check.contentType,verifiedAt:new Date().toISOString()};}catch{}
 throw Error('Aucun flux HTTPS accessible trouvé pour cette demande. Précise la station ou essaie un autre genre.');
}
