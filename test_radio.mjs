import assert from 'node:assert/strict';
import {publicAddress,streamUrl,searchRadios,resolveRadio} from './radio.mjs';
const lookup=async()=>[{address:'8.8.8.8',family:4}];
for(const ip of ['127.0.0.1','10.0.0.4','192.0.2.16','169.254.169.254','::1','fc00::1','::ffff:127.0.0.1'])assert(!publicAddress(ip),ip);
assert(publicAddress('8.8.8.8'));assert(publicAddress('2606:4700:4700::1111'));
for(const url of ['http://stream.example.org/live','https://localhost/live','https://ha.local/live','https://a:b@stream.example.org/live'])await assert.rejects(streamUrl(url,{lookup}));
await assert.rejects(streamUrl('https://stream.example.org/live',{lookup:async()=>[{address:'192.0.2.16'}]}));
const calls=[];const directory=async(path,args)=>{calls.push({path,args});return [{stationuuid:'11111111-1111-4111-8111-111111111111',name:args.name||args.tag||'Saved station',url_resolved:'https://stream.example.org/live',lastcheckok:1,clickcount:10},{stationuuid:'broken',name:'Broken',url_resolved:'https://stream.example.org/broken',lastcheckok:0},{stationuuid:'private',name:'Private',url_resolved:'https://home.local/secret',lastcheckok:1}];};
const deps={directory,lookup,probe:async url=>({url,contentType:'audio/mpeg'})};
for(const query of ['an entirely new station','jazz','classique']){const found=await resolveRadio({query},deps);assert.equal(found.name,query);assert(found.verifiedAt);assert.equal(found.source,'Radio Browser');}
await resolveRadio({genre:'soul'},deps);assert(calls.some(c=>c.args.tag==='soul'));
const saved=await resolveRadio({station_id:'11111111-1111-4111-8111-111111111111'},deps);assert.equal(saved.name,'Saved station');assert(calls.some(c=>c.path.includes('/byuuid/')));
await assert.rejects(resolveRadio({query:'station'}, {...deps,probe:async()=>{throw Error('Offline')}}));
assert.equal((await searchRadios({query:'test'},deps)).length,1);
const upgrade=await resolveRadio({query:'new station'},{...deps,directory:async()=>[{stationuuid:'new',name:'New',url:'http://stream.example.org/live',lastcheckok:1}]});assert.equal(upgrade.url,'https://stream.example.org/live');
await assert.rejects(resolveRadio({station_id:'../private'},deps));
console.log('PASS: live name/genre discovery, saved station re-resolution, broken and private endpoints rejected, HTTPS upgrade only with successful stream probe, and failures never reported as playback.');
