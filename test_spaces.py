import tempfile,pathlib,subprocess,os,json,sqlite3
script=str(pathlib.Path(__file__).with_name('store.py'))
with tempfile.TemporaryDirectory() as d:
 env={**os.environ,'JARVIS_DB':d+'/test.sqlite'}
 def call(action,value,space='user',raw=False):
  p=subprocess.run(['python3',script,action,space],input=json.dumps(value).encode(),stdout=subprocess.PIPE,env=env)
  return json.loads(p.stdout)
 note=call('save',dict(title='Orbite secrète test',body='Souvenir test',status='Idée'))['data']
 assert call('list',{'space':'amelie'})['data']['total']==0
 assert call('get',{'space':'amelie','id':note['id']})['data'] is None
 assert call('move',{'space':'user','target':'amelie','id':note['id']})['ok']
 assert call('list',{'space':'user','q':'Orbite'})['data']['docs']==[]
 assert len(call('list',{'space':'amelie','q':'Orbite'})['data']['docs'])==1
 assert not call('move',{'space':'user','target':'commun','id':note['id']})['ok']
 assert not call('list',{'space':'invalid'})['ok']
 export=[{'id':'same','title':'Projet test','mapping':{'a':{'message':{'author':{'role':'user'},'content':{'parts':['Essai import']}}}}}]
 assert call('import',export,'amelie')['data']['imported']==1
 assert call('import',export,'amelie')['data']['imported']==0
 assert call('import',export,'user')['data']['imported']==1
 assert call('list',{'space':'user'})['data']['total']==1
 assert call('list',{'space':'amelie'})['data']['total']==2
 # Source refresh preserves a manually moved document.
 assert call('move',{'id':'chatgpt:amelie:same','space':'amelie','target':'commun'})['ok']
 export[0]['mapping']['a']['message']['content']['parts']=['Nouvelle version']
 assert call('import',export,'amelie')['ok']
 assert call('get',{'id':'chatgpt:amelie:same','space':'commun'})['data']['body']=='Toi: Nouvelle version'
 print('PASS: separate counts/search/details, notes, move, invalid spaces, scoped imports, deduplication, ownership preserved on refresh.')
