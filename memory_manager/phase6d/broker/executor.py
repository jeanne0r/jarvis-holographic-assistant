"""One bounded launch under a distinct approved OS identity, no inherited secrets."""
import json,os,selectors,signal,stat,subprocess,time
from pathlib import Path
from .isolation import check_uid,plan

def bounded(command,payload,*,seconds=300,limit=1048576):
 if len(payload)>32000:raise ValueError('Input bound')
 proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,env={'LANG':'C.UTF-8','PATH':'/usr/bin:/bin'})
 poll=selectors.DefaultSelector();outputs={'stdout':bytearray(),'stderr':bytearray()};pending=memoryview(payload);end=time.monotonic()+seconds
 for file,name in [(proc.stdout,'stdout'),(proc.stderr,'stderr')]:os.set_blocking(file.fileno(),False);poll.register(file,selectors.EVENT_READ,name)
 os.set_blocking(proc.stdin.fileno(),False);poll.register(proc.stdin,selectors.EVENT_WRITE,'stdin')
 try:
  while poll.get_map():
   if time.monotonic()>=end:raise TimeoutError('Executor deadline')
   for key,events in poll.select(min(.2,max(0,end-time.monotonic()))):
    if key.data=='stdin':
     try:sent=os.write(key.fileobj.fileno(),pending[:4096]);pending=pending[sent:]
     except BrokenPipeError:pending=memoryview(b'')
     if not pending:poll.unregister(key.fileobj);key.fileobj.close()
    else:
     part=os.read(key.fileobj.fileno(),65536)
     if not part:poll.unregister(key.fileobj);key.fileobj.close();continue
     outputs[key.data]+=part
     if len(outputs[key.data])>limit:raise ValueError('Output quota')
  if proc.wait(timeout=max(.1,end-time.monotonic()))!=0:raise ValueError('Executor failed')
  return outputs
 finally:
  poll.close()
  if proc.poll() is None:
   try:os.killpg(proc.pid,signal.SIGKILL)
   except ProcessLookupError:pass
  proc.wait()
  for f in (proc.stdin,proc.stdout,proc.stderr):f.close()

class Executor:
 def __init__(self,root,runtime,uid,gateway_uid,provider_socket=None,schema=None,tools_socket=None):self.root,self.runtime,self.uid,self.gateway_uid,self.provider_socket,self.schema=Path(root).resolve(),runtime,uid,gateway_uid,provider_socket,schema;self.tools_socket=tools_socket
 def __call__(self,job):
  check_uid(self.uid,self.gateway_uid)
  workspace=(self.root/job['id']).resolve(strict=True)
  if workspace.parent!=self.root:raise PermissionError('Job root boundary')
  if not self.schema or not self.provider_socket:raise PermissionError('Reviewed schema/provider configuration required')
  command=plan(workspace,self.runtime,gateway_uid=self.gateway_uid,executor_uid=self.uid,proxy_socket=self.provider_socket,tools_socket=self.tools_socket)
  split=command.index('--');command[split:split]=['--ro-bind',str(Path(self.schema).resolve(strict=True)),'/runtime/answer-schema.json']
  command[-1:-1]=['--output-schema','/runtime/answer-schema.json']
  bounded(command,job['payload'].encode())
  fd=os.open(workspace/'result.json',os.O_RDONLY|os.O_NOFOLLOW)
  try:
   info=os.fstat(fd)
   if not stat.S_ISREG(info.st_mode) or info.st_size>64000 or info.st_uid!=self.uid:raise ValueError('Result file denied')
   result=json.loads(os.read(fd,64001))
  finally:os.close(fd)
  if not isinstance(result,dict) or not isinstance(result.get('answer'),str) or not isinstance(result.get('speech'),str) or not isinstance(result.get('sourceIds'),list):raise ValueError('Incomplete structured result')
  return result
