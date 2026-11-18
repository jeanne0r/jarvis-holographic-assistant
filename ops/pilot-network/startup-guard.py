"""Runs unprivileged in the final unit before the application.
Only a fresh root-owned approval matching this start can release the gate.
"""
import importlib.util,json,os,secrets,stat,subprocess,time
from pathlib import Path

def root_json(path):
 st=path.lstat()
 if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:raise PermissionError('Root-owned gate required')
 return json.loads(path.read_text())

def main():
 folder=Path('/run/jarvis-pilot-network-gate');cfg=root_json(folder/'fixture.json')
 if not time.time()<cfg['expires']<=time.time()+60:raise PermissionError('Fresh supervised start required')
 spec=importlib.util.spec_from_file_location('probe',Path(__file__).with_name('check-system-filter.py'))
 probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
 result=subprocess.run(['/usr/bin/python3','-c',probe.PROBE,cfg['ip'],str(cfg['port'])],capture_output=True,text=True,timeout=12,check=True)
 request={'nonce':secrets.token_hex(24),'session':cfg['session'],'network':json.loads(result.stdout)}
 dest=Path('/var/lib/jarvis-hermes-pilot/startup-network.json')
 fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as f:json.dump(request,f)
 deadline=min(cfg['expires'],time.time()+20)
 while time.time()<deadline:
  try:
   approved=root_json(folder/'approved.json')
   if approved.get('nonce')==request['nonce'] and approved.get('session')==cfg['session'] and time.time()<approved.get('expires',0):return
  except FileNotFoundError:pass
  time.sleep(.1)
 raise PermissionError('No verified root approval; application must not start')
if __name__=='__main__':
 try:main()
 except Exception:
  print('Final-unit network gate refused; application not started.',file=__import__('sys').stderr)
  raise SystemExit(1)
