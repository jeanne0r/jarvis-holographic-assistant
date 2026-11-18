"""Explicit broker service entry point; no inference worker starts on import."""
import argparse,json,os,stat
from pathlib import Path
from .store import Jobs
from .service import Broker
from .transport import Server

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);args=parser.parse_args()
 fd=os.open(args.config,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  info=os.fstat(fd)
  if info.st_uid!=os.getuid() or info.st_mode&0o077 or not stat.S_ISREG(info.st_mode) or info.st_size>65536:raise PermissionError('Private owned broker config required')
  cfg=json.loads(os.read(fd,65537))
 finally:os.close(fd)
 if os.getuid() in (0,cfg['gateway_uid']) or os.getuid()!=cfg['broker_uid']:raise PermissionError('Distinct broker UID required')
 state=Path(cfg['state_directory']).resolve(strict=True)
 if state.stat().st_uid!=os.getuid() or state.stat().st_mode&0o077:raise PermissionError('Private state directory required')
 os.umask(0o077);jobs=Jobs(state/'jobs.sqlite');broker=Broker(jobs,cfg['project_grants'])
 # Admission/reconciliation service only. No worker/remote budget can be enabled
 # by an incoming RPC. Supervisor execution is a separate approved operation.
 server=Server(cfg['socket'],broker,cfg['credentials'],ipc_gid=cfg.get('ipc_gid'))
 try:server.serve_forever()
 finally:server.server_close();jobs.close()
if __name__=='__main__':main()
