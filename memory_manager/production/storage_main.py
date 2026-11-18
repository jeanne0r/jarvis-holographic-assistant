"""Explicit storage daemon entry. Provisioning/migration never occurs at import/start."""
import argparse,hashlib,hmac,json,os,socketserver,stat,struct
from .persistence import Persistence
from .storage_service import Storage
MAX=4*1024**2
class Server(socketserver.UnixStreamServer):
 def __init__(self,path,storage,credentials,*,ipc_gid=None):
  self.storage,self.credentials=storage,credentials
  super().__init__(str(path),Handler)
  if ipc_gid is not None:
   if ipc_gid not in os.getgroups()+[os.getgid()]:raise PermissionError('Approved IPC membership')
   os.chown(path,-1,ipc_gid)
  os.chmod(path,0o660 if ipc_gid is not None else 0o600)
class Handler(socketserver.BaseRequestHandler):
 def handle(self):
  self.request.settimeout(30)
  def exact(n):
   data=b''
   while len(data)<n:
    part=self.request.recv(n-len(data))
    if not part:raise ValueError('Short frame')
    data+=part
   return data
  try:
   size=struct.unpack('!I',exact(4))[0]
   if not 1<=size<=MAX:raise ValueError('Bound')
   m=json.loads(exact(size))
   if set(m)!={'credential','method','args'}:raise ValueError('Envelope')
   digest=hashlib.sha256(m['credential'].encode()).hexdigest()
   id=next((v for k,v in self.server.credentials.items() if hmac.compare_digest(k,digest)),None)
   if not id or m['args'].get('subject') not in id['subjects']:raise PermissionError('Service credential')
   out={'ok':True,'value':self.server.storage.call(id['service'],m['method'],m['args'])}
  except Exception:out={'ok':False,'error':'Storage denied'}
  raw=json.dumps(out,ensure_ascii=False,allow_nan=False).encode()
  if len(raw)>MAX:raw=b'{"ok":false,"error":"Response bound"}'
  self.request.sendall(struct.pack('!I',len(raw))+raw)
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
 fd=os.open(a.config,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd)
  if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or st.st_mode&0o077 or st.st_size>131072:raise PermissionError('Private config')
  cfg=json.loads(os.read(fd,131073))
 finally:os.close(fd)
 if os.getuid() in (0,cfg['gateway_uid']) or os.getuid()!=cfg['storage_uid']:raise PermissionError('Distinct storage identity')
 os.umask(0o077);repo=Persistence(cfg['brain'],cfg['voice'])
 # Explicit migration/backup is a separate approval. Missing schema fails startup.
 for db,table in [(repo.db,'g_resource_acl'),(repo.voice,'g_fact_acl')]:
  if not db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():raise PermissionError('Approved migration required')
 index_reader=None
 if cfg.get('index'):
  from .projection import qdrant_reader
  index_reader=qdrant_reader(**cfg['index'])
 service=Storage(repo,cfg['policy'],staging=cfg['staging'],json_files=cfg.get('json_files'),sync_sources=cfg.get('sync_sources'),index_reader=index_reader)
 server=Server(cfg['socket'],service,cfg['credentials'],ipc_gid=cfg.get('ipc_gid'))
 try:server.serve_forever()
 finally:server.server_close();repo.close()
if __name__=='__main__':main()
