"""Host-only broker controller. Gateway/Hermes never select executable or environment."""
import json
from .store import Jobs
class Broker:
 def __init__(self,jobs,grants,*,launch=None,authorize=None):self.jobs,self.grants,self.launch,self.authorize=jobs,grants,launch,authorize
 def call(self,service,method,args):
    if service!='gateway-human':raise PermissionError('Gateway identity required; Hermes denied')
    if set(args)-{'subject','project','key','payload','job'}:raise ValueError('Broker fields')
    subject=args.get('subject');grant=self.grants.get(subject,{})
    project=args.get('project')
    if method=='submit':
        if project not in grant.get('write',[]):raise PermissionError('Project write denied')
        payload=args.get('payload')
        if not isinstance(payload,dict) or set(payload)!={'question','context'} or not isinstance(payload['question'],str) or not 1<=len(payload['question'])<=8000:raise ValueError('Technical payload')
        # Context is data. Never accept flags, command, cwd, environment or permissions.
        ctx=payload['context']
        if not isinstance(ctx,dict) or set(ctx)-{'history','space','channel','view','application'}:raise ValueError('Context fields')
        job=self.jobs.admit(subject,project,args['key'],payload);return {'id':job,'state':self.jobs.get(subject,job)['state']}
    if method=='list':return self.jobs.list(subject,grant.get('read',[]))
    row=self.jobs.get(subject,args['job'])
    if row['project'] not in grant.get('read',[]):raise PermissionError('Project read denied')
    if method=='get':return row
    if method=='cancel':
        if row['project'] not in grant.get('write',[]):raise PermissionError('Cancel denied')
        return self.jobs.cancel(subject,row['id'])
    raise PermissionError('Broker operation denied')
 def work(self,job,*,approved=False,remote_budget_micros=0):
    # Explicit supervisor operation, never reachable through the gateway RPC.
    if approved is not True or remote_budget_micros<=0:raise PermissionError('No approved remote execution budget')
    row=self.jobs.db.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone()
    if not row or row['state']!='queued':raise PermissionError('Not a queued job; no automatic replay')
    if self.launch is None or self.authorize is None or self.authorize(dict(row)) is not True:raise PermissionError('Executor or current human authorization missing')
    with self.jobs.db:
        cursor=self.jobs.db.execute("UPDATE jobs SET state='running' WHERE id=? AND state='queued'",(job,))
        if cursor.rowcount!=1:raise PermissionError('Job cancelled or already claimed')
    try:
        result=self.launch(dict(row))
        with self.jobs.db:self.jobs.db.execute("UPDATE jobs SET state='completed',result=? WHERE id=? AND state='running'",(json.dumps(result),job))
    except Exception:
        with self.jobs.db:self.jobs.db.execute("UPDATE jobs SET state='uncertain' WHERE id=?",(job,))
        raise
