"""Opt-in extension of the existing authenticated API; no worker/model loop."""
import re
from ..phase2.bridge import Bridge
from ..phase2.validation import loads
from .evidence import ObservedTools,metadata
from .heartbeat import observe,status

READS={'memory.search','memory.knowledge','memory.history','memory.project','memory.experiences','memory.contradictions'}
def extension(hosts_by_actor,*,next_dispatch=None,searcher=None):
 # Trusted host configuration, never fields accepted from an HTTP request.
 hosts=dict(hosts_by_actor)
 def handle(memory,principal,request,url,query):
    match=re.fullmatch(r'/v1/missions/([a-zA-Z0-9-]+)/(canonical|tools/read)',url.path)
    if match:
        if query:raise ValueError('No client metadata selectors')
        mid,action=match.groups();Bridge(memory,principal).get(mid)
        if action=='canonical' and request.command=='GET':
            principal.require('reader');principal.require('mission_worker')
            receipts=[r[0] for r in memory.db.execute('SELECT id FROM p6d_receipts WHERE mission_id=? ORDER BY created DESC,id LIMIT 20',(mid,))]
            return 200,{'projection':metadata(memory,principal,mid,receipts) if receipts else None,'validation':'unreviewed'},'application/json'
        if action=='tools/read' and request.command=='POST':
            size=int(request.headers.get('Content-Length',0))
            if not 0<size<=8000 or request.headers.get('Transfer-Encoding'):raise ValueError('Bounded tool call required')
            body=loads(request.rfile.read(size))
            if set(body)!={'name','arguments'} or body['name'] not in READS:raise PermissionError('Read tool only')
            if principal.actor not in hosts:raise PermissionError('No host-bound tool adapter')
            result,receipt=ObservedTools(memory,hosts[principal.actor],principal,mid,searcher=searcher).call(body['name'],body['arguments'])
            return 200,{'result':result,'receipt_id':receipt},'application/json'
        raise PermissionError('Operation denied')
    match=re.fullmatch(r'/v1/workers/([a-zA-Z0-9_-]+)/(heartbeat|status)',url.path)
    if match:
        if query:raise ValueError('No heartbeat overrides')
        worker,action=match.groups()
        if action=='status' and request.command=='GET':return 200,status(memory,principal,worker),'application/json'
        if action=='heartbeat' and request.command=='POST':
            principal.require('worker_reporter')
            size=int(request.headers.get('Content-Length',0))
            if not 0<size<=1024 or request.headers.get('Transfer-Encoding'):raise ValueError('Heartbeat body bound')
            body=loads(request.rfile.read(size))
            if set(body)!={'epoch','sequence','state'}:raise ValueError('Heartbeat fields')
            observe(memory,principal,worker,body['epoch'],body['sequence'],body['state'])
            return 200,status(memory,principal,worker),'application/json'
        raise PermissionError('Operation denied')
    return next_dispatch(memory,principal,request,url,query) if next_dispatch else None
 return handle
