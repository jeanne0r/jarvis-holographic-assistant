"""Bounded Unix-domain RPC. File permissions + per-service credential, no TCP listener."""
import hashlib,hmac,json,os,socketserver,struct
MAX=65536
class Server(socketserver.UnixStreamServer):
 def __init__(self,path,broker,credentials,*,ipc_gid=None):
    # Never unlink or adopt an existing socket/path silently.
    self.broker,self.credentials=broker,credentials
    super().__init__(str(path),Handler)
    if ipc_gid is not None:
        if ipc_gid not in os.getgroups()+[os.getgid()]:raise PermissionError('Approved IPC membership required')
        os.chown(path,-1,ipc_gid)
    os.chmod(path,0o660 if ipc_gid is not None else 0o600)
class Handler(socketserver.BaseRequestHandler):
 def handle(self):
    self.request.settimeout(2)
    def exact(n):
        chunks=[]
        while n:
            c=self.request.recv(n)
            if not c:raise ValueError('Truncated')
            chunks.append(c);n-=len(c)
        return b''.join(chunks)
    try:
        size=struct.unpack('!I',exact(4))[0]
        if not 0<size<=MAX:raise ValueError('Frame bound')
        message=json.loads(exact(size))
        if set(message)!={'credential','method','args'}:raise ValueError('RPC envelope')
        digest=hashlib.sha256(message['credential'].encode()).hexdigest()
        identity=next((v for k,v in self.server.credentials.items() if hmac.compare_digest(k,digest)),None)
        if not identity or message['args'].get('subject') not in identity['subjects']:raise PermissionError('Service denied')
        value=self.server.broker.call(identity['service'],message['method'],message['args']);result={'ok':True,'value':value}
    except Exception:result={'ok':False,'error':'Broker operation denied'}
    raw=json.dumps(result,allow_nan=False).encode()
    if len(raw)>MAX:raw=b'{"ok":false,"error":"Response bound"}'
    self.request.sendall(struct.pack('!I',len(raw))+raw)
