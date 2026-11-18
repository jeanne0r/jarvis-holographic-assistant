// Dev-only preview: static assets + synthetic mock of /api/jarvis/hermes-panel. No real data.
import http from 'node:http';import fs from 'node:fs/promises';import path from 'node:path';
const [,,assets,port='18790']=process.argv;const now=Date.now()/1000;
const canonical=id=>({schema:'canonical_metadata.v1',origin:'sqlite',mission_id:id,selection_origin:'authenticated_host_tool_receipts',receipt_ids:['r1'],items:[
 {memory_id:'9d0a1803-1c5c-47e3-8dc7-ac740dc74d28',revision_id:'82904f0f-3aa6-4d27-981b-db063557f03f',source_ref:'synthetic://doselab/correction',stored_validation_status:'user_confirmed',revision_status:'user_confirmed',observed_utc:'2023-11-14T22:15:00Z',valid_from_utc:'2023-11-14T22:15:00Z',valid_to_utc:null,is_current_revision:true},
 {memory_id:'9d0a1803-1c5c-47e3-8dc7-ac740dc74d28',revision_id:'11114f0f-3aa6-4d27-981b-db063557f03f',source_ref:'synthetic://doselab/old',stored_validation_status:'user_confirmed',revision_status:'superseded',observed_utc:'2023-11-14T22:13:20Z',valid_from_utc:'2023-11-14T22:13:20Z',valid_to_utc:'2023-11-14T22:15:00Z',is_current_revision:false},
 {memory_id:'f2cfb154-1e84-441b-b0d5-6f8ad224126d',revision_id:'bea76ff8-f999-45a6-b00d-fd48148e7659',source_ref:'synthetic://doselab/experience',stored_validation_status:'user_confirmed',revision_status:'user_confirmed',observed_utc:'2023-11-14T22:16:40Z',valid_from_utc:'2023-11-14T22:16:40Z',valid_to_utc:null,is_current_revision:true},
 {memory_id:'a1a1a1a1-1e84-441b-b0d5-6f8ad224126d',revision_id:'b2b2b2b2-f999-45a6-b00d-fd48148e7659',source_ref:'mission://e1a94db6-0001-4db5-8c0f-defefacd1e5d',stored_validation_status:'inferred',revision_status:'inferred',observed_utc:'2026-11-16T20:11:51Z',valid_from_utc:'2026-11-16T20:11:51Z',valid_to_utc:null,is_current_revision:true}]});
const P='Demande explicite utilisateur (données et outils synthétiques seulement) : ';
// 17.11 real sources (mock values, no real data): two host reads of a fictitious VSV entity.
const H='ha://sensor.vsv_dosage/history/168h@20261117T1200Z',I='influx://homeassistant/sensor.vsv_dosage/90d/1440m@20261117T1200Z';
const realCanonical=id=>({schema:'canonical_metadata.v1',origin:'sqlite',mission_id:id,selection_origin:'authenticated_host_tool_receipts',receipt_ids:['r1','r2'],items:[
 {memory_id:'c1c1c1c1-0000-4000-8000-000000000001',revision_id:'d1d1d1d1-0000-4000-8000-000000000001',source_ref:H,stored_validation_status:'observed',revision_status:'observed',observed_utc:'2026-11-17T12:00:00Z',valid_from_utc:'2026-11-17T12:00:00Z',valid_to_utc:null,is_current_revision:true},
 {memory_id:'c1c1c1c1-0000-4000-8000-000000000002',revision_id:'d1d1d1d1-0000-4000-8000-000000000002',source_ref:I,stored_validation_status:'observed',revision_status:'observed',observed_utc:'2026-11-17T12:00:05Z',valid_from_utc:'2026-11-17T12:00:05Z',valid_to_utc:null,is_current_revision:true}]});
const realAnswer='**Oui, un recalibrage semble justifié.** Sur 7 jours, le dosage moyen est de 36,2 mL pour une consigne de 40 mL, avec 4 jours consécutifs sous 37 mL. Source : `'+H+'`\n\nSur 90 jours, la dérive commence vers le 28 octobre. Source : `'+I+'`\n\nSources :\n- `'+H+'`\n- `'+I+'`';
const answer='**Configuration actuelle des cellules de charge DoseLab X4 :** 4 cellules à 1 kg chacune — confirmé par l’utilisateur. Source : `synthetic://doselab/correction`\n\n### Évolution\n- État initial : [1, 2, 5, 10] kg — `superseded` — Source : `synthetic://doselab/old`\n- Modification : [1, 1, 1, 1] kg — `user_confirmed` — Source : `synthetic://doselab/correction`\n\n**Leçon diagnostique :** une procédure a échoué faute de contrôle de fraîcheur des mesures. Source : `synthetic://doselab/experience`\n\n| Cellule | Capacité |\n|---|---|\n| 1–4 | 1 kg |\n\nSources :\n- synthetic://doselab/old\n- synthetic://doselab/correction\n- synthetic://doselab/experience';
let missions=[
 {id:'7777bbbb-0000-4000-8000-000000000001',state:'completed',real:true,objective:P+'Dois-je recalibrer le dosage du VSV d’après l’historique des mesures ?',created:now-600,updated:now-600+80,q:{model_cites_source_ref:true,unverified_mission_sources_read:0,cites_unverified_source:false,measurements_read:2,cites_measurement:true}},
 {id:'73de8f3b-3873-4d98-ac11-e2193f72e918',state:'completed',objective:P+'Le DoseLab X4 : quelle est la configuration actuelle de ses cellules de charge, et qu’est-ce qui a changé ?',created:now-3600,updated:now-3600+95,q:{model_cites_source_ref:true,unverified_mission_sources_read:1,cites_unverified_source:false}},
 {id:'e1a77905-8170-472a-aa39-cc60a2348693',state:'completed',objective:P+'Quelles sont les capacités actuelles des cellules de charge du DoseLab X4, et ont-elles changé ?',created:now-40000,updated:now-40000+21,q:{model_cites_source_ref:false}},
 {id:'5555aaaa-1111-4444-8888-000000000001',state:'running',objective:P+'Compare les deux dernières révisions DoseLab et résume les écarts.',created:now-120,updated:now-30},
 {id:'5555aaaa-1111-4444-8888-000000000002',state:'queued',objective:P+'Liste les procédures synthétiques sans contrôle de fraîcheur.',created:now-60,updated:now-60},
 {id:'90e50f56-0000-4000-8000-000000000000',state:'failed',objective:P+'Rapport DoseLab (tentative du 16.11)',created:now-90000,updated:now-89970},
 {id:'aa7b7903-0000-4000-8000-000000000000',state:'cancelled',objective:P+'Vérifie la configuration DoseLab (ancienne enveloppe)',created:now-88000,updated:now-87000},
];
const send=(res,code,data)=>{res.writeHead(code,{'content-type':'application/json'});res.end(JSON.stringify(data))};
let logged=false;
http.createServer(async(req,res)=>{const url=new URL(req.url,'http://x');const p=url.pathname;
 let body='';for await(const c of req)body+=c;
 if(p==='/'||p==='/jarvis/'){res.writeHead(200,{'content-type':'text/html'});return res.end('<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jarvis (aperçu)</title><style>body{margin:0;background:#050b10;color:#cfe;font:15px system-ui}header{display:flex;justify-content:space-between;align-items:center;padding:12px 18px;border-bottom:1px solid #123}</style><link rel="stylesheet" href="hermes-embedded.css"></head><body><header><b>J.A.R.V.I.S.</b><div class="header-actions"></div></header><main style="padding:40px;opacity:.5">Interface Jarvis (aperçu)</main><script src="hermes-embedded.js" defer></script></body></html>')}
 if(p.startsWith('/jarvis/')){try{const f=await fs.readFile(path.join(assets,path.basename(p)));res.writeHead(200,{'content-type':p.endsWith('.css')?'text/css':'application/javascript'});return res.end(f)}catch{res.writeHead(404);return res.end()}}
 const s=p.replace('/api/jarvis/hermes-panel','');
 if(s==='/session'){if(req.method==='POST'){logged=JSON.parse(body).token==='demo';return send(res,logged?200:401,logged?{ok:true}:{error:'Code invalide'})}if(req.method==='DELETE'){logged=false;return send(res,200,{})}return logged?send(res,200,{subject:'user',spaces:['lab'],roles:['missions.read','missions.create']}):send(res,401,{error:'login'})}
 if(!logged)return send(res,401,{error:'login'});
 if(s==='/hermes/config')return send(res,200,{enabled:true,readEnabled:true,textEnabled:true,voiceEnabled:false});
 if(s==='/hermes/availability')return send(res,200,{fresh:true,state:'ready'});
 if(s==='/hermes/missions'&&req.method==='POST'){const o=JSON.parse(body).objective;const m={id:crypto.randomUUID(),state:'queued',objective:P+o,created:Date.now()/1000,updated:Date.now()/1000};missions.unshift(m);return send(res,202,{mission_id:m.id})}
 if(s==='/hermes/missions')return send(res,200,{items:missions.map(({q,real,...m})=>m)});
 const m1=/^\/hermes\/missions\/([^/]+)(\/results|\/cancel)?$/.exec(s);const m=m1&&missions.find(x=>x.id===m1[1]);if(!m)return send(res,404,{error:'?'});
 if(m1[2]==='/cancel'){m.state='cancelled';m.updated=Date.now()/1000;return send(res,200,{})}
 if(!m1[2])return send(res,200,{...m,definition:{objective:m.objective},approvals:[]});
 const ev=[{seq:1,mission_id:m.id,event_key:'admitted',kind:'queued',data:'{}'}];
 if(m.state==='completed'){ev.push({seq:2,mission_id:m.id,event_key:'terminal',kind:'completed',data:JSON.stringify({output:m.real?realAnswer:answer})});ev.push({seq:3,mission_id:m.id,event_key:'q',kind:'report_quality',data:JSON.stringify(m.q)})}
 if(m.state==='failed')ev.push({seq:2,mission_id:m.id,event_key:'terminal',kind:'failed',data:JSON.stringify({reason:'Pilot quota or mission denied'})});
 return send(res,200,m.state==='completed'?{events:ev,canonical:m.real?realCanonical(m.id):canonical(m.id)}:{events:ev,canonicalUnavailable:m.state!=='queued'&&m.state!=='running'});
}).listen(+port,'127.0.0.1',()=>console.log('preview on',port));
