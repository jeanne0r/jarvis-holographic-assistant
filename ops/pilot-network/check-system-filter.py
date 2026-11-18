"""Prepared root-only check. Never starts the pilot, Windows or a model.
Creates one transient probe unit and empty TCP fixtures for at most 20 seconds.
"""
import argparse,errno,json,os,socket,subprocess,threading,time,uuid

PROBE=r'''
import errno,json,socket,sys,time
ip,port=sys.argv[1],int(sys.argv[2])
def check(host):
 with socket.socket() as client:
  client.settimeout(2);client.bind(('127.0.0.1' if host=='127.0.0.1' else ip,0))
  local_port=client.getsockname()[1]
  try:
   client.connect((host,port));return {'connected':True,'local_port':local_port}
  except OSError as e:return {'connected':False,'errno':e.errno,'timed_out':isinstance(e,TimeoutError),'local_port':local_port}
print(json.dumps({'loopback':check('127.0.0.1'),'non_loopback':check(ip)}),flush=True)
time.sleep(5)
'''
def verdict(observed,hooks,controls,witness):
 denied=observed['non_loopback']
 return (observed['loopback'].get('connected') is True and denied.get('connected') is False
         and (denied.get('errno') in [errno.EPERM,errno.EACCES] or denied.get('timed_out') is True)
         and {'cgroup_inet_ingress','cgroup_inet_egress'}<=set(hooks)
         and controls and witness['loopback_seen'] and not witness['non_loopback_seen'])

def main():
 p=argparse.ArgumentParser();p.add_argument('--approved-root-probe',action='store_true');a=p.parse_args()
 if not a.approved_root_probe or os.geteuid()!=0:raise SystemExit('Explicit approval and root required; nothing started')
 route=json.loads(subprocess.check_output(['ip','-j','route','get','192.0.2.1']))[0]
 ip=route.get('prefsrc')
 if not ip or ip.startswith('127.'):raise SystemExit('No non-loopback source address; refuse inconclusive check')
 unit='jarvis-pilot-netcheck-'+uuid.uuid4().hex[:10]+'.service'
 sockets=[];process=None;stop=threading.Event();accepted=set();lock=threading.Lock()
 def serve(s):
  s.settimeout(.2)
  while not stop.is_set():
   try:
    c,peer=s.accept()
    with lock:accepted.add((s.getsockname()[0],peer[0],peer[1]))
    c.close()
   except socket.timeout:pass
   except OSError:break
 try:
  # Distinct exact binds: no wildcard/public listener, no payload or application.
  for host in ['127.0.0.1',ip]:
   s=socket.socket();s.bind((host,0 if not sockets else sockets[0].getsockname()[1]));s.listen(4);sockets.append(s)
   threading.Thread(target=serve,args=(s,),daemon=True).start()
  port=sockets[0].getsockname()[1]
  def controls():
   keys=[]
   for host in ['127.0.0.1',ip]:
    with socket.create_connection((host,port),timeout=1) as client:
     keys.append((host,*client.getsockname()))
   for _ in range(20):
    with lock:
     if all(k in accepted for k in keys):return True
    time.sleep(.02)
   return False
  before=controls()
  if not before:raise RuntimeError('Unconfined witnesses unavailable; no probe started')
  props=['User=nobody','Group=nogroup','NoNewPrivileges=yes','CapabilityBoundingSet=',
   'AmbientCapabilities=','PrivateTmp=yes','PrivateDevices=yes','ProtectHome=yes',
   'ProtectSystem=strict','RestrictAddressFamilies=AF_INET AF_UNIX',
   'IPAddressDeny=any','IPAddressAllow=localhost','TasksMax=32','MemoryMax=384M',
   'RuntimeMaxSec=15s','TimeoutStopSec=2s','KillMode=control-group']
  command=['systemd-run','--system','--quiet','--pipe','--wait','--collect','--unit',unit]
  for prop in props:command+=['--property',prop]
  process=subprocess.Popen(command+['/usr/bin/python3','-c',PROBE,ip,str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  attached=[]
  for _ in range(40):
   cg=subprocess.run(['systemctl','show',unit,'-p','ControlGroup','--value'],capture_output=True,text=True).stdout.strip()
   if cg:
    result=subprocess.run(['/usr/sbin/bpftool','-j','cgroup','show','/sys/fs/cgroup'+cg,'effective'],capture_output=True,text=True)
    if result.returncode==0:
     attached=json.loads(result.stdout)
     if attached:break
   if process.poll() is not None:break
   time.sleep(.1)
  out,err=process.communicate(timeout=20)
  if process.returncode:raise RuntimeError('Transient probe failed: '+err[-1500:])
  observed=json.loads(out.strip());hooks={r.get('attach_type') for r in attached}
  after=controls()
  with lock:
   witness={'loopback_seen':('127.0.0.1','127.0.0.1',observed['loopback']['local_port']) in accepted,
            'non_loopback_seen':(ip,ip,observed['non_loopback']['local_port']) in accepted}
  ok=verdict(observed,hooks,before and after,witness)
  print(json.dumps({'passed':ok,'network':observed,'effective_bpf_hooks':sorted(hooks),
   'unconfined_controls_before':before,'unconfined_controls_after':after,
   'receiver_witness':witness,'pilot_started':False}))
  if not ok:raise SystemExit('NO-GO: enforcement not demonstrated; no pilot restart')
 finally:
  subprocess.run(['systemctl','stop',unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  if process and process.poll() is None:process.kill();process.communicate()
  stop.set()
  for s in sockets:s.close()
if __name__=='__main__':main()
