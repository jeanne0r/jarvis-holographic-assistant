"""Per-job Unix endpoint around the fixed-origin budgeted provider."""
import json,os,socketserver,struct
class Server(socketserver.UnixStreamServer):
 def __init__(self,path,provider):self.provider=provider;super().__init__(str(path),Handler);os.chmod(path,0o600)
class Handler(socketserver.BaseRequestHandler):
 def handle(self):
  self.request.settimeout(60)
  def exact(n):
   out=b''
   while len(out)<n:
    part=self.request.recv(n-len(out))
    if not part:raise ValueError('Truncated')
    out+=part
   return out
  try:
   size=struct.unpack('!I',exact(4))[0]
   if not 0<size<=65536:raise ValueError('Bound')
   data=json.loads(exact(size))
   if set(data)!={'method','path','body'}:raise ValueError('Envelope')
   result=self.server.provider.request(data['method'],data['path'],data['body'])
  except Exception:result={'status':503,'type':'application/json','body':'{"error":"Provider denied; no fallback"}'}
  raw=json.dumps(result).encode()
  if len(raw)>4*1024*1024:raw=b'{"status":503,"body":"Provider response bound"}'
  self.request.sendall(struct.pack('!I',len(raw))+raw)
