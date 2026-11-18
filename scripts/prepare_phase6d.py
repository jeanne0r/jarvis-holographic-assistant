"""Generate classified route coverage and independent review lots, never deploy."""
import difflib,hashlib,json,subprocess,tempfile,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'docs/phase6d';DEST.mkdir(exist_ok=True)
J=Path('/home/user/workspace/jarvis');G=Path('/home/user/gateway')
SOURCES=[G/'server.js',J/'backend.mjs',Path('/home/user/workspace/astro-degustation/gateway.mjs'),Path('/home/user/workspace/solana-paper/gateway.mjs'),Path('/home/user/workspace/allemand-en-poche/backend.mjs')]
def sha(b):return hashlib.sha256(b).hexdigest() if b is not None else None
matrix=json.loads(subprocess.check_output(['node','--input-type=module','-e',"import {routeMatrix} from './gateway-route-policy.mjs';console.log(JSON.stringify(routeMatrix))"],cwd=ROOT,text=True))
# Capture code conditions, not data or runtime effects. These include fallback branches.
evidence=[]
for f in SOURCES:
 lines=f.read_text().splitlines()
 evidence.append({'source':str(f),'sha256':sha(f.read_bytes()),'route_conditions':[{'line':i+1,'code':line.strip()} for i,line in enumerate(lines) if any(s in line for s in ['url.pathname','action===','action ===','includes(action)','route===','route ==='])]})
clients=[]
for base in [G/'public/jarvis',G/'public/miroir',G/'public/astro',G/'public/solana-paper',G/'public/allemand-en-poche']:
 if not base.exists():continue
 for f in sorted(base.rglob('*')):
  if f.is_file() and not f.is_symlink() and f.suffix in {'.js','.html'}:
   refs=sorted(set(re.findall(r"/api/[A-Za-z0-9_./:-]+",f.read_text(errors='replace'))))
   if refs:clients.append({'file':str(f),'references':refs,'dynamic_calls_require_adapter_review':True})
# Enumerate proposed public code/assets, never data exports, ZIP/PDF/JSON or symlinks.
import mimetypes
assets=[]
base=G/'public'
for f in sorted(base.rglob('*')):
 if f.is_file() and not f.is_symlink() and f.suffix.lower() in {'.js','.css','.wasm','.tflite','.svg','.png','.jpg','.jpeg','.webp','.woff','.woff2','.ico'} and not any(part.startswith('.') for part in f.relative_to(base).parts):
  rel=str(f.relative_to(base));assets.append({'path':'/'+rel,'file':rel,'type':mimetypes.guess_type(rel)[0] or 'application/octet-stream','sha256':sha(f.read_bytes())})
for app in ['jarvis','miroir','astro','solana-paper']:
 f=base/app/'index.html'
 if f.exists():
  for suffix in ['', '/', '/index.html']:assets.append({'path':'/'+app+suffix,'file':app+'/index.html','type':'text/html; charset=utf-8','sha256':sha(f.read_bytes())})
# This is an inventory candidate, not a permission to publish assets or a live config.
(DEST/'public-assets-candidate.json').write_text(json.dumps(assets,indent=2)+'\n')
report={'mode':'static-source-audit-no-handler-import','sources':evidence,'route_method_pairs':matrix,'client_source_references':clients,'unknown_api_route_or_method':'deny','public_api':['GET /api/health (minimal response)','GET/POST/DELETE /api/jarvis/session (session protocol, not anonymous application access)'],'static_public':'explicit candidate enumerated in public-assets-candidate.json; data/export extensions excluded; human review required','production_writes':0}
(DEST/'route-matrix.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
md=['# Matrice de couverture phase 6D','', 'Registre explicite : 100 couples route/méthode. Les clients indiqués sont les catégories du contrat ; les références réellement observées sont dans le JSON. La compatibilité dynamique n’est pas présumée.','', '| Méthode | Route | Identité | Permission | Contrôle complémentaire | Effets possibles | Clients du contrat |','|---|---|---|---|---|---|---|']
for r in matrix:md.append('| '+' | '.join([r['method'],r['path'],r['identity'],r['permission'],','.join(k for k in ['space','resource','physical','approval'] if r.get(k)) or '—',r['effect'],','.join(r['clients'])])+' |')
(DEST/'ROUTE_MATRIX.md').write_text('\n'.join(md)+'\n')
server=(G/'server.js').read_text()
server="import {mountCentralGateway} from '/home/user/workspace/jarvis/gateway-security-mount.mjs';\nimport {requestIdentity} from '/home/user/workspace/jarvis/gateway-route-policy.mjs';\n"+server
server=server.replace('async function routeRequest(req, res, protocol = "http") {','async function dispatchRequest(req, res, protocol = "http") {')
server=server.replace('!isAuthorized(req)', '!requestIdentity.has(req)') # Only the two explicit S9/iCloud guards, now behind central guard.
assert server.count('!requestIdentity.has(req)')==2
at=server.index('function startBackgroundLoops()')
mount='''// Review candidate: no optional insecure fallback. Resource/physical adapters
// intentionally absent => denied until independently reviewed adapters exist.
const securedRoute = await mountCentralGateway(
 (req,res,url)=>dispatchRequest(req,res,url.protocol.slice(0,-1)),
 {policyFile:process.env.JARVIS_SECURITY_CONFIG,assetFile:process.env.JARVIS_PUBLIC_ASSETS,staticRoot:'/home/user/gateway/public'}
);
async function routeRequest(req,res,protocol='http') {
 try {return await securedRoute(req,res,new URL(req.url,`${protocol}://${req.headers.host}`));}
 catch {res.writeHead(400);res.end();}
}

'''
server=server[:at]+mount+server[at:]
# Small voice ownership patch based on the actual active backend, not the wider 6B backend.
backend=(J/'backend.mjs').read_text()
backend="import {requestIdentity} from './gateway-route-policy.mjs';\nimport {voiceOwners} from './voice-session-owner.mjs';\nconst voiceOwnership=voiceOwners();\n"+backend
backend=backend.replace("const space=url.searchParams.get('space')||'user';","const space=url.searchParams.get('space')||'user';\n const identity=requestIdentity.get(req);")
backend=backend.replace('return json(res,200,speechSession(space));','const session=speechSession(space);return json(res,200,identity?voiceOwnership.bind(session,identity,space):session);')
backend=backend.replace("if(action==='voice/transcribe')return json", "if(action==='voice/transcribe'&&identity)voiceOwnership.check(req.headers['x-jarvis-voice-session'],identity,space);\n   if(action==='voice/transcribe')return json")
backend=backend.replace("const data=JSON.parse((await body(req,20000)).toString());", "const data=JSON.parse((await body(req,20000)).toString());\n   if(identity)voiceOwnership.check(data.sessionId,identity,space);")
# Auth-only HTML: no Hermes panel import.
html=(G/'public/jarvis/index.html').read_text().replace('<script src="archive.js','<script src="jarvis-auth.js" defer></script><script src="archive.js',1)
# Refresh existing UI after verified human login, no fetch monkeypatch or audio edits.
app=(G/'public/jarvis/app.js').read_text()+"\ndocument.addEventListener('jarvis:session-ready',()=>void load());\n"
basehtml=html
panelhtml=html.replace('</head>','<link rel="stylesheet" href="hermes-missions.css"><script src="hermes-missions.js" defer></script></head>')
groups=[('01-central-security',[(J/n,(ROOT/n).read_bytes()) for n in ['jarvis-session-auth.mjs','hermes-server-auth.mjs','gateway-route-policy.mjs','gateway-security.mjs','gateway-security-mount.mjs']]+[(G/'server.js',server.encode())]),('02-independent-auth-client',[(G/'public/jarvis/jarvis-auth.js',(ROOT/'public/jarvis-auth.js').read_bytes()),(G/'public/jarvis/voice-router.js',(ROOT/'public/voice-router.js').read_bytes()),(G/'public/jarvis/app.js',app.encode()),(G/'public/jarvis/index.html',basehtml.encode())]),('03-voice-owner',[(J/'voice-session-owner.mjs',(ROOT/'voice-session-owner.mjs').read_bytes()),(J/'backend.mjs',backend.encode())]),('04-optional-hermes-panel',[(G/'public/jarvis/hermes-missions.js',(ROOT/'public/hermes-missions.js').read_bytes()),(G/'public/jarvis/hermes-missions.css',(ROOT/'public/hermes-missions.css').read_bytes()),(G/'public/jarvis/index.html',panelhtml.encode())])]
initial={p:p.read_bytes() if p.exists() else None for _,changes in groups for p,_ in changes};state=initial.copy();entries=[]
with tempfile.TemporaryDirectory(prefix='phase6d-overlay-') as tmp:
 root=Path(tmp)
 for p,b in initial.items():
  if b is not None:t=root/str(p).lstrip('/');t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(b)
 for name,changes in groups:
  parts=[];files=[]
  for p,after in changes:
   before=state[p];rel=str(p).lstrip('/')
   parts.extend(difflib.unified_diff((before or b'').decode().splitlines(True),after.decode().splitlines(True),fromfile='a/'+rel if before is not None else '/dev/null',tofile='b/'+rel,n=0))
   files.append({'target':str(p),'before_sha256':sha(before),'after_sha256':sha(after)});state[p]=after
  f=DEST/(name+'.patch');f.write_text(''.join(parts))
  result=subprocess.run(['patch','--batch','-p1','-d',str(root),'-i',str(f)],capture_output=True,text=True)
  if result.returncode:raise RuntimeError(result.stdout+result.stderr)
  entries.append({'lot':name,'sha256':sha(f.read_bytes()),'files':files})
 assert all((root/str(p).lstrip('/')).read_bytes()==b for p,b in state.items())
 # Syntax-check the actual candidate gateway, never import or start it.
 candidate=root/str(G/'server.js').lstrip('/');mjs=root/'candidate.mjs';mjs.write_bytes(candidate.read_bytes());subprocess.run(['node','--check',str(mjs)],check=True,capture_output=True)
 # Retain only code-only fixtures of relevant function bodies for isolated tests.
 (DEST/'candidate-backend.mjs.txt').write_text(backend)
 (DEST/'candidate-server-routing.js.txt').write_text(server[server.index('async function handleApi('):server.index('// Review candidate:')].rstrip()+'\n')
 for item in reversed(entries):
  result=subprocess.run(['patch','--batch','-R','-p1','-d',str(root),'-i',str(DEST/(item['lot']+'.patch'))],capture_output=True,text=True)
  if result.returncode:raise RuntimeError(result.stdout+result.stderr)
 assert all((root/str(p).lstrip('/')).read_bytes()==b if b is not None else not (root/str(p).lstrip('/')).exists() for p,b in initial.items())
 # Independently reverse and reapply each lot at its own boundary.
 for item in entries:
  subprocess.run(['patch','--batch','-p1','-d',str(root),'-i',str(DEST/(item['lot']+'.patch'))],check=True,capture_output=True)
  subprocess.run(['patch','--batch','-R','-p1','-d',str(root),'-i',str(DEST/(item['lot']+'.patch'))],check=True,capture_output=True)
  # The panel lot requires the auth HTML preimage: covered in full reverse above.
  if item['lot']=='03-voice-owner':break
assert all((p.read_bytes() if p.exists() else None)==b for p,b in initial.items())
manifest={'mode':'review-only','production_activation':'NO-GO-pending-resource-adapters-and-isolation','lots':entries,'dependencies':{'01-central-security':'03 ownership installed before granting voice; object routes default denied','02-independent-auth-client':'safe inert on old gateway (session 404); global cookie scope migration required on login','03-voice-owner':'identity from 01; inert under legacy unauthenticated requests','04-optional-hermes-panel':'02 auth client + existing reviewed 6B Hermes facade, not provided by central security lot'},'forward_and_reverse_byte_verified':True,'production_preimages_unchanged':True,'production_writes':0,'model_calls':0}
(DEST/'patch-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'route_method_pairs':len(matrix),'lots':len(entries),'forward_reverse':True,'production_writes':0}))
