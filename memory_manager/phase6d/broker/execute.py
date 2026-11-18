"""Explicit transient executor entry; no daemon, no provider fallback."""
import argparse,json,os,stat,time
from .executor import Executor

def control_file(path,allowed_owners):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  info=os.fstat(fd)
  if info.st_uid not in allowed_owners or info.st_mode&0o022 or not stat.S_ISREG(info.st_mode) or info.st_size>65536:raise PermissionError('Immutable trusted control file required')
  return json.loads(os.read(fd,65537))
 finally:os.close(fd)

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--job-file',required=True);a=p.parse_args()
 # The untrusted executor UID cannot create its own launch authority.
 cfg=control_file(a.config,{0})
 if os.getuid() in (0,cfg['gateway_uid'],cfg['broker_uid']) or os.getuid()!=cfg['executor_uid']:raise PermissionError('Distinct executor identity required')
 job=control_file(a.job_file,{0,cfg['broker_uid']})
 if job.get('approved') is not True or type(job.get('remote_budget_micros')) is not int or job['remote_budget_micros']<=0 or time.time()>=job.get('expires',0):raise PermissionError('Unexpired approved job and remote budget required')
 value=Executor(cfg['workspace_root'],cfg['runtime'],cfg['executor_uid'],cfg['gateway_uid'],provider_socket=job['provider_socket'],tools_socket=job.get('tools_socket'),schema=cfg['answer_schema'])(job['record'])
 # Supervisor must reconcile this exact ID/result; an interrupted process is
 # uncertain. This command never updates the broker DB as the executor UID.
 print(json.dumps({'job_id':job['record']['id'],'result':value,'validation':'unreviewed'}))
if __name__=='__main__':main()
