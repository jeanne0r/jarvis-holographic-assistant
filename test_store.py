import tempfile,pathlib,subprocess,os,json,zipfile,io,sqlite3
script=str(pathlib.Path(__file__).with_name('store.py'))
with tempfile.TemporaryDirectory() as d:
 env={**os.environ,'JARVIS_DB':d+'/test.sqlite'}
 def call(action,value,raw=False):
  p=subprocess.run(['python3',script,action],input=value if raw else json.dumps(value).encode(),stdout=subprocess.PIPE,env=env)
  return json.loads(p.stdout)
 export=[{'id':'test-123','title':'Projet constellation','update_time':1700000000,'current_node':'b','mapping':{'a':{'parent':None,'message':{'author':{'role':'user'},'content':{'parts':['Une idée Jarvis']}}},'b':{'parent':'a','message':{'author':{'role':'assistant'},'content':{'parts':['Relions nos idées.']}}},'other':{'parent':'a','message':{'author':{'role':'assistant'},'content':{'parts':['Branche abandonnée']}}}}}]
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w') as z:z.writestr('conversations-1.json',json.dumps(export))
 assert call('import',b.getvalue(),True)['data']['imported']==1
 assert call('import',json.dumps(export).encode(),True)['data']['imported']==0
 doc=call('get',{'id':'chatgpt:test-123'})['data'];assert 'Branche abandonnée' not in doc['body']
 assert len(call('list',{'q':'constellation'})['data']['docs'])==1
 assert call('save',{'title':'Décision test','body':'Test persistant','status':'Décision'})['ok']
 assert not call('save',{'title':'','body':'','status':'Idée'})['ok']
 assert not call('import',b'bad json',True)['ok']
 assert call('list',{})['data']['total']==2
 print('PASS: ZIP numbered JSON, import deduplication, selected branch, search, durable note, validation, invalid import rollback.')
