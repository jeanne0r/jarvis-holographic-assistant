"""PREPARED root-only probe of the two actual cgroups. No service restart/GPU.
Requires separate approval. Publishes a non-secret root-owned startup receipt.
"""
import argparse,json,os,pwd,secrets,socket,stat,subprocess,sys,time,hashlib
from pathlib import Path
UNITS=['jarvis-hermes-pilot-system.service','jarvis-hermes-supervisor.service']
OUTPUT=Path('/etc/jarvis-hermes-supervisor/confinement.json')
def cmd(args):return subprocess.check_output(args,text=True,timeout=10).strip()
def verdict(observed,hooks,before,after,witness):
 return before and after and {'cgroup_inet_ingress','cgroup_inet_egress'}<=set(hooks) and observed.get('loopback',{}).get('connected') is True and observed.get('non_loopback',{}).get('connected') is False and witness is False
PROBE='''import json,socket,sys
result={}
for name,host,port in [('loopback','127.0.0.1',8797),('non_loopback',sys.argv[1],int(sys.argv[2]))]:
 s=socket.socket();s.settimeout(1)
 try:s.connect((host,port));result[name]={'connected':True,'local_port':s.getsockname()[1]}
 except OSError as e:result[name]={'connected':False,'local_port':s.getsockname()[1]}
 finally:s.close()
print(json.dumps(result))
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--approved-root-confinement-probe',action='store_true',required=True);p.parse_args()
 if os.geteuid()!=0:raise PermissionError('Root administrative probe only')
 os.umask(0o077)
 route=json.loads(cmd(['ip','-j','route','get','192.0.2.1']))[0];address=route['prefsrc']
 if address.startswith('127.') or address=='192.0.2.96':raise PermissionError('Independent non-loopback witness required')
 # Require the explicit egress table as well as effective BPF. Review its exact
 # loaded rules separately during installation; never install/alter it here.
 rules=json.loads(cmd(['nft','-j','list','table','inet','jarvis_hermes_supervisor']))
 if not rules.get('nftables'):raise PermissionError('Dedicated egress restriction absent')
 observations=[]
 for unit in UNITS:
  props=dict(line.split('=',1) for line in cmd(['systemctl','show',unit,'-p','MainPID','-p','ControlGroup','-p','ActiveState','-p','User']).splitlines())
  if props['ActiveState'] not in ({'active','activating'} if unit=='jarvis-hermes-supervisor.service' else {'active'}) or int(props['MainPID'])<=0 or not props['ControlGroup'].startswith('/system.slice/'):raise PermissionError('Actual active system cgroup required')
  account=pwd.getpwnam(props['User'])
  if account.pw_uid==0:raise PermissionError('Application identity must be non-root')
  cgroup=Path('/sys/fs/cgroup'+props['ControlGroup'])
  hooks=[r['attach_type'] for r in json.loads(cmd(['/usr/sbin/bpftool','-j','cgroup','show',str(cgroup),'effective']))]
  with socket.socket() as receiver:
   receiver.bind((address,0));receiver.listen(8);receiver.settimeout(.2);port=receiver.getsockname()[1]
   def control():
    with socket.create_connection((address,port),timeout=1) as client:peer=client.getsockname()
    accepted,_=receiver.accept();accepted.close();return True
   before=control()
   def join_cgroup():
    with (cgroup/'cgroup.procs').open('w') as f:f.write(str(os.getpid()))
    os.setgroups([]);os.setgid(account.pw_gid);os.setuid(account.pw_uid)
   result=subprocess.run([sys.executable,'-I','-c',PROBE,address,str(port)],preexec_fn=join_cgroup,capture_output=True,text=True,timeout=5,env={'PATH':'/usr/bin:/bin'})
   if result.returncode:raise PermissionError('Actual cgroup probe failed')
   observed=json.loads(result.stdout);seen=False
   try:
    connection,peer=receiver.accept();connection.close();seen=peer[1]==observed['non_loopback']['local_port']
   except socket.timeout:pass
   after=control()
  if not verdict(observed,hooks,before,after,seen):raise PermissionError('Network enforcement not demonstrated')
  unitfile=Path('/etc/systemd/system')/unit
  observations.append({'name':unit,'pid':int(props['MainPID']),'ingress_enforced':True,'egress_enforced':True,'effective_bpf_hooks':hooks,'unit_sha256':hashlib.sha256(unitfile.read_bytes()).hexdigest()})
  if cmd(['systemctl','show',unit,'-p','MainPID','--value'])!=props['MainPID']:raise PermissionError('Service changed during probe')
 parent=OUTPUT.parent;st=parent.lstat()
 if parent.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:raise PermissionError('Root-owned proof directory required')
 receipt={'probe_passed':True,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'supervisor_main_pid':observations[1]['pid'],'units':observations,'created':time.time(),'loaded_egress_sha256':hashlib.sha256(json.dumps(rules,sort_keys=True).encode()).hexdigest()}
 if OUTPUT.exists():
  old=OUTPUT.lstat()
  if OUTPUT.is_symlink() or old.st_uid!=0 or old.st_mode&0o022:raise PermissionError('Untrusted existing proof')
  previous=parent/('confinement.previous-'+str(time.time_ns())+'.json');previous.write_bytes(OUTPUT.read_bytes());previous.chmod(0o640)
 temporary=parent/('.confinement-'+secrets.token_hex(6));fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
 with os.fdopen(fd,'w') as file:json.dump(receipt,file);file.flush();os.fsync(file.fileno())
 temporary.chmod(0o644);os.replace(temporary,OUTPUT)
 print(json.dumps({'passed':True,'root_proof':str(OUTPUT),'units':UNITS,'services_restarted':False,'model_calls':0}))
if __name__=='__main__':main()
