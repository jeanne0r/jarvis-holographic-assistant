"""Apply and restore only temporary code copies. Never executes the gateway."""
import hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
from .prepare_embedded_panel import ROOT

def check(bundle):
 bundle=Path(bundle).resolve();manifest=json.loads((bundle/'manifest.json').read_text())
 def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
 for name,h in manifest['files'].items():
  if sha(bundle/name)!=h:raise ValueError('Artifact fingerprint mismatch')
 with tempfile.TemporaryDirectory() as tmp:
  tmp=Path(tmp);copy=tmp/'copy';backup=tmp/'backup';copy.mkdir();backup.mkdir()
  originals={'server.js':Path('/home/user/gateway/server.js'),'public/index.html':Path('/home/user/workspace/jarvis/public/index.html'),'public/jarvis/index.html':Path('/home/user/gateway/public/jarvis/index.html'),'memory_manager/phase6/interactive.py':ROOT/'memory_manager/phase6/interactive.py'}
  for name,source in originals.items():
   target=copy/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
   saved=backup/name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,saved)
  for name in ['gateway.patch','frontend.patch','frontend-source.patch','pilot.patch']:
   patch=bundle/'patches'/name
   subprocess.run(['git','apply','--check',str(patch)],cwd=copy,check=True,capture_output=True)
   subprocess.run(['git','apply',str(patch)],cwd=copy,check=True,capture_output=True)
  assert sha(copy/'server.js')==sha(bundle/'gateway/server.js')
  assert sha(copy/'public/index.html')==sha(bundle/'frontend/index.html')
  assert sha(copy/'public/jarvis/index.html')==sha(bundle/'frontend/index.html')
  assert sha(copy/'memory_manager/phase6/interactive.py')==sha(bundle/'pilot-release/memory_manager/phase6/interactive.py')
  additions={'hermes-embedded-relay.mjs':bundle/'gateway/hermes-embedded-relay.mjs','hermes-embedded-contract.mjs':bundle/'gateway/hermes-embedded-contract.mjs','public/jarvis/hermes-embedded.js':bundle/'frontend/hermes-embedded.js','public/jarvis/hermes-embedded.css':bundle/'frontend/hermes-embedded.css'}
  for name,source in additions.items():shutil.copyfile(source,copy/name)
  # Restore exact old bytes and remove only additions created in this copy.
  for name in originals:shutil.copyfile(backup/name,copy/name)
  for name in additions:(copy/name).unlink()
  for name in originals:assert sha(copy/name)==sha(backup/name)
  # Relocated private release must validate its derived runtime manifest.
  result=subprocess.run(['/usr/bin/python3','-c','from scripts.prepare_interactive_pilot import verify_manifest; assert verify_manifest()'],cwd=bundle/'pilot-release',env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1'},check=True,capture_output=True)
  return {'passed':True,'artifact_hashes_verified':True,'patches_apply_on_copy':True,'restored_bytes_equal':True,'new_files_removed_on_copy':True,'relocated_runtime_manifest_verified':True,'gateway_executed':False,'production_modified':False}
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('bundle');a=p.parse_args();print(json.dumps(check(a.bundle)))
