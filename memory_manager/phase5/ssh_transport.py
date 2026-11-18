"""Private CT205 capability transport. No credentials leave the remote process.

Only experimental Qdrant read/upsert/query and raw synthetic embeddings are
permitted. SSH identities/host keys are controller configuration, never model data.
No listeners, daemon, shell tool or arbitrary endpoint is exposed to Hermes.
"""
import json
from pathlib import Path
import shlex
import subprocess
from ..phase2.local_model import Unavailable

COLLECTION='jarvis_knowledge_experimental_v1'
REMOTE=r'''
import json,sys,urllib.request,urllib.error
from pathlib import Path
v=json.load(sys.stdin)
allowed={('qdrant','GET','/collections/jarvis_knowledge_experimental_v1'),
 ('qdrant','PUT','/collections/jarvis_knowledge_experimental_v1/points?wait=true'),
 ('qdrant','POST','/collections/jarvis_knowledge_experimental_v1/points/query'),
 ('embedding','POST','/v1/embeddings')}
if (v['service'],v['method'],v['path']) not in allowed:raise PermissionError('Capability denied')
if len(json.dumps(v))>64000:raise ValueError('Bounded request')
if v['service']=='embedding':
 stage=Path(sys.argv[1]);key=(stage/'embedding.token').read_text().strip();headers={'Authorization':'Bearer '+key};port=6335
else:
 key=next(l.split('=',1)[1].strip().strip('"').strip("'") for l in Path('/etc/jarvis-memory.env').read_text().splitlines() if l.startswith('QDRANT__SERVICE__API_KEY='));headers={'api-key':key};port=6333
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):raise PermissionError('Redirect denied')
req=urllib.request.Request('http://127.0.0.1:'+str(port)+v['path'],method=v['method'],headers={'Content-Type':'application/json',**headers},data=None if v['body'] is None else json.dumps(v['body'],allow_nan=False).encode())
try:
 with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(req,timeout=min(15,v['timeout'])) as r:
  data=r.read(1000001)
  if len(data)>1000000:raise ValueError('Response limit')
  print(json.dumps({'ok':True,'result':json.loads(data)}))
except urllib.error.HTTPError as e:print(json.dumps({'ok':False,'http_status':e.code}))
except Exception:print(json.dumps({'ok':False,'http_status':None}))
'''


class CT205:
    def __init__(self,service,private_state,*,identity,known_hosts):
        if service not in {'embedding','qdrant'}:raise ValueError('Service denied')
        p=Path(private_state)
        if p.parent!=Path('/var/lib/jarvis-memory/phase5-a2') or not p.name.replace('-','').isalnum():raise ValueError('Pinned A2 private state required')
        self.service,self.state=service,str(p)
        self.identity,self.known_hosts=str(identity),str(known_hosts)

    def __call__(self,method,path,body=None,*,timeout=5):
        allowed={('qdrant','GET','/collections/'+COLLECTION),('qdrant','PUT','/collections/'+COLLECTION+'/points?wait=true'),
                 ('qdrant','POST','/collections/'+COLLECTION+'/points/query'),('embedding','POST','/v1/embeddings')}
        if (self.service,method,path) not in allowed:raise PermissionError('Experimental capability denied')
        if not 0<timeout<=15:raise ValueError('Request deadline')
        v={'service':self.service,'method':method,'path':path,'body':body,'timeout':timeout}
        raw=json.dumps(v,allow_nan=False)
        if len(raw)>64000:raise ValueError('Request size')
        command='pct exec 205 -- python3 -c '+shlex.quote(REMOTE)+' '+shlex.quote(self.state)
        try:
            p=subprocess.run(['ssh','-i',self.identity,'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
                '-o','UserKnownHostsFile='+self.known_hosts,'-o','ConnectTimeout=5','root@192.0.2.200',command],
                input=raw,text=True,capture_output=True,timeout=timeout)
            if p.returncode:raise Unavailable('Private capability unavailable')
            if len(p.stdout)>1000000:raise Unavailable('Response bound')
            result=json.loads(p.stdout)
            if not result.get('ok'):raise Unavailable('Private endpoint rejected or unavailable')
            return result['result']
        except (OSError,ValueError,subprocess.TimeoutExpired):raise Unavailable('Private capability unavailable') from None
