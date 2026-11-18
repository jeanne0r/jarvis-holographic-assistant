"""Approved installation's root boot hook; no GPU, missions, gateway restart.
Root configuration pins code and the single dedicated UID egress table.
"""
import argparse,hashlib,importlib.util,json,os,stat,subprocess
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--approved-installed-profile',action='store_true',required=True);p.parse_args()
 if os.geteuid()!=0:raise PermissionError('Root installed boot hook only')
 config=Path('/etc/jarvis-hermes-supervisor/boot.json');st=config.lstat()
 if config.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:raise PermissionError('Root approved boot policy required')
 cfg=json.loads(config.read_text());source=Path('/opt/jarvis-hermes-supervisor/ops/pilot-network/install-system-pilot.py')
 if source.is_symlink() or source.stat().st_uid!=0 or source.stat().st_mode&0o022 or hashlib.sha256(source.read_bytes()).hexdigest()!=cfg['coordinatorSha256']:raise PermissionError('Reviewed startup coordinator required')
 policy=Path('/etc/jarvis-hermes-supervisor/egress.nft')
 if policy.is_symlink() or policy.stat().st_uid!=0 or policy.stat().st_mode&0o022 or hashlib.sha256(policy.read_bytes()).hexdigest()!=cfg['egressFileSha256']:raise PermissionError('Pinned dedicated UID network policy required')
 def run(args,check=True):return subprocess.run(args,check=check,text=True,capture_output=True,timeout=45)
 rules=run(['nft','-j','list','table','inet','jarvis_hermes_supervisor'],False)
 if rules.returncode:
  run(['nft','-f',str(policy)]);rules=run(['nft','-j','list','table','inet','jarvis_hermes_supervisor'])
 def normalized(value):
  if isinstance(value,dict):return {k:normalized(v) for k,v in value.items() if k not in {'handle','packets','bytes','metainfo'}}
  if isinstance(value,list):return [normalized(v) for v in value]
  return value
 digest=hashlib.sha256(json.dumps(normalized(json.loads(rules.stdout)),sort_keys=True).encode()).hexdigest()
 if digest!=cfg['egressRulesSha256']:raise PermissionError('Loaded network rules differ; no alteration or weaker fallback')
 spec=importlib.util.spec_from_file_location('approved_coordinator',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.verify_layout()
 state=run(['systemctl','show','jarvis-hermes-pilot-system.service','-p','ActiveState','--value']).stdout.strip()
 if state not in {'active','inactive','failed'}:raise PermissionError('Ambiguous private service')
 if state!='active':module.supervised_start()
 print(json.dumps({'passed':True,'gateway_restarted':False,'model_calls':0}))
if __name__=='__main__':main()
