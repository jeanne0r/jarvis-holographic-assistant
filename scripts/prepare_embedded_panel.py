"""Reproducible isolated patches only. Never deploys or reads private state."""
import difflib,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NEW=['hermes-embedded-api.mjs','hermes-embedded-contract.mjs','ops/pilot-embedded.mjs']
PRESERVE=['ops/pilot-network/check-system-filter.py','ops/pilot-network/startup-guard.py','ops/pilot-network/jarvis-hermes-pilot-system.service']
def digest(raw):return hashlib.sha256(raw).hexdigest()
def replace_once(text,old,new):
 if text.count(old)!=1:raise ValueError('Reviewed source anchor changed: '+old[:60])
 return text.replace(old,new,1)
def assets():
 auth=(ROOT/'public/jarvis-auth.js').read_text()
 auth=auth.replace("'/api/jarvis/'","'/api/jarvis/hermes-panel/'").replace("'/api/jarvis/session'","'/api/jarvis/hermes-panel/session'")
 auth=auth.replace('JarvisAuth','JarvisHermesAuth').replace('jarvisAccount','hermesAccount').replace('jarvis:session-','jarvis:hermes-session-')
 auth=auth.replace('Connexion Jarvis','Connexion missions').replace('Compte Jarvis','Compte missions')
 panel=(ROOT/'public/hermes-missions.js').read_text().replace('JarvisAuth','JarvisHermesAuth').replace('JarvisCanonical','JarvisHermesCanonical').replace('jarvis:session-','jarvis:hermes-session-')
 panel=replace_once(panel,'document.body.append(button);',"(document.querySelector('.header-actions')||document.body).append(button);")
 panel=replace_once(panel,"make('p','Laboratoire synthétique · aucun équipement ni import personnel.',content);","make('p','Laboratoire synthétique · réponses du modèle non vérifiées. Aucun équipement ni import personnel.',content);")
 panel=replace_once(panel,"create.type='button';","create.type='button';create.hidden=true;")
 panel=replace_once(panel,"make('h2','Missions Hermes',dialog);","make('h2','Missions Hermes',dialog);const account=document.querySelector('#hermesAccountButton');if(account)dialog.append(account);")
 panel=replace_once(panel,"function space(){return document.querySelector('#spaceSelect')?.value||identity?.spaces?.[0]}","function space(){return identity?.spaces?.[0]}")
 a=panel.index("  const selector=document.querySelector('#spaceSelect');");b=panel.index("  try{const config=",a);panel=panel[:a]+panel[b:]
 panel=panel.replace("'jarvis:spacechange'","'jarvis:hermes-spacechange'")
 panel=replace_once(panel,"  if(result.canonical){","  if(result.canonicalUnavailable)canonical.textContent='Métadonnées canoniques indisponibles. Réponse du modèle non vérifiée.';\n  if(result.canonical){")
 panel=panel.replace("'PC Gamer indisponible ou présence non confirmée. Missions conservées.'","'Exécution Hermes désactivée. Historique disponible.'")
 panel=panel.replace("'Connexion Jarvis'","'Connexion missions'")
 canonical=(ROOT/'public/hermes-canonical.js').read_text().replace('JarvisCanonical','JarvisHermesCanonical')
 js='// Generated from existing formatter, login and panel. See prepare_embedded_panel.py.\n'+canonical+'\n'+auth+'\n'+panel
 css=(ROOT/'public/hermes-missions.css').read_text()+'''\n/* Embedded in the existing header, with an independent mission identity. */\n.header-actions #hermesMissionsButton{position:static;max-width:none;margin:0}#hermesAccountDialog{width:min(440px,94vw);color:var(--text,#e6f5ff);background:var(--panel,#081825)}#hermesAccountDialog input{display:block;width:100%;margin:1rem 0;padding:.6rem}#hermesMissionsDialog [hidden]{display:none!important}#hermesMissionCanonical{white-space:pre-wrap;overflow-wrap:anywhere}\n'''
 return js,css

def prepare(dest):
 dest=Path(dest)
 if dest.exists():raise FileExistsError('Never replace an existing preparation')
 dest.mkdir(parents=True);(dest/'patches').mkdir();release=dest/'pilot-release';release.mkdir()
 prior=json.loads((ROOT/'docs/pilot-interactive/manifest.json').read_text());oldmanifest=(ROOT/'docs/pilot-interactive/manifest.json').read_bytes()
 for name,h in prior['files'].items():
  raw=(ROOT/name).read_bytes()
  if digest(raw)!=h:raise ValueError('Pinned source mismatch: '+name)
  out=release/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(raw)
 for name in NEW+PRESERVE:
  out=release/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,out)
 target='memory_manager/phase6/interactive.py';old=(release/target).read_text();new=replace_once(old,"ROOT/'ops/pilot-interactive.mjs'","ROOT/'ops/pilot-embedded.mjs'");(release/target).write_text(new)
 manifest={**prior,'files':{n:digest((release/n).read_bytes()) for n in list(prior['files'])+NEW+PRESERVE},'derived_from_sha256':digest(oldmanifest),'purpose':'embedded read/cancel-only API; original archive unchanged'}
 (release/'docs/pilot-interactive').mkdir(parents=True,exist_ok=True)
 (release/'docs/pilot-interactive/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (dest/'patches/pilot.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+target,tofile='b/'+target)))
 gw=Path('/home/user/gateway/server.js');oldgw=gw.read_text();newgw="import {embeddedRelay} from './hermes-embedded-relay.mjs';\n"+oldgw
 newgw=replace_once(newgw,'const HOST =',"const handleHermesPanel = embeddedRelay({enabled:process.env.JARVIS_HERMES_PANEL==='1',origin:process.env.JARVIS_HERMES_PANEL_ORIGIN,switchFile:process.env.JARVIS_HERMES_PANEL_SWITCH||''});\nconst HOST =")
 newgw=replace_once(newgw,'    if (url.pathname.startsWith("/api/jarvis/"))',"    if (await handleHermesPanel(req,res,url)) return;\n    if (url.pathname.startsWith(\"/api/jarvis/\"))")
 gateway=dest/'gateway';gateway.mkdir();(gateway/'server.js').write_text(newgw)
 for n in ['hermes-embedded-relay.mjs','hermes-embedded-contract.mjs','hermes-human-delegation.mjs']:shutil.copyfile(ROOT/n,gateway/n)
 (dest/'patches/gateway.patch').write_text(''.join(difflib.unified_diff(oldgw.splitlines(True),newgw.splitlines(True),fromfile='a/server.js',tofile='b/server.js')))
 js,css=assets();public=dest/'frontend';public.mkdir();(public/'hermes-embedded.js').write_text(js);(public/'hermes-embedded.css').write_text(css)
 html=Path('/home/user/gateway/public/jarvis/index.html').read_text();newhtml=replace_once(html,'</head>','<link rel="stylesheet" href="hermes-embedded.css?v=1"><script src="hermes-embedded.js?v=1" defer></script></head>');(public/'index.html').write_text(newhtml)
 sourcehtml=Path('/home/user/workspace/jarvis/public/index.html').read_text()
 if sourcehtml!=html:raise ValueError('Served/source HTML differ; review before preparing patch')
 (dest/'patches/frontend-source.patch').write_text(''.join(difflib.unified_diff(html.splitlines(True),newhtml.splitlines(True),fromfile='a/public/index.html',tofile='b/public/index.html')))
 (dest/'patches/frontend.patch').write_text(''.join(difflib.unified_diff(html.splitlines(True),newhtml.splitlines(True),fromfile='a/public/jarvis/index.html',tofile='b/public/jarvis/index.html')))
 # All other source/audio scripts remain byte-for-byte unchanged.
 installed_root=Path('/opt/jarvis-hermes-pilot')
 installed_manifest=(installed_root/'deployment-files.json').read_bytes()
 installed_files=json.loads(installed_manifest)
 if any(digest((installed_root/n).read_bytes())!=h for n,h in installed_files.items()):raise ValueError('Installed pilot code drift')
 manifestfiles={str(p.relative_to(dest)):digest(p.read_bytes()) for p in dest.rglob('*') if p.is_file()}
 info={'production_modified':False,'default_flag':'off','gateway_input_sha256':digest(oldgw.encode()),'html_input_sha256':digest(html.encode()),'historical_pilot_manifest_sha256':digest(oldmanifest),'files':manifestfiles,'additions_gateway':['hermes-embedded-relay.mjs','hermes-embedded-contract.mjs','hermes-human-delegation.mjs'],'modified_gateway':['server.js','public/jarvis/index.html'],'added_assets':['public/jarvis/hermes-embedded.js','public/jarvis/hermes-embedded.css'],'pilot_source_patch':[target],'pilot_additions':NEW,'gateway_has_bridge_secret':False,'admission_enabled':False,'voice_enabled':False,'installed_pilot_manifest_sha256':digest(installed_manifest),'installed_pilot_code_before':installed_files}
 installed={str(p.relative_to(release)):digest(p.read_bytes()) for p in release.rglob('*') if p.is_file()}
 (release/'deployment-files.json').write_text(json.dumps(installed,indent=2)+'\n')
 info['files']['pilot-release/deployment-files.json']=digest((release/'deployment-files.json').read_bytes())
 (dest/'manifest.json').write_text(json.dumps(info,indent=2)+'\n')
 return info
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('destination');a=p.parse_args();prepare(a.destination);print('Isolated patch prepared; no deployment, service, personal data or model call.')
