"""ACL join over the existing brain.sqlite schema; no knowledge duplication.

Run under the storage identity, never as an unrestricted gateway subprocess.
Unknown historical owners stay unclaimed until an approved explicit mapping.
"""
import json,re,sqlite3,time,uuid
from pathlib import Path
from ..store import snapshot
class LegacyRepository:
 def __init__(self,path):
    self.path=Path(path);self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row
 def migrate(self):
    if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='g_resource_acl'").fetchone():return {'changed':False}
    backup=snapshot(self.path,self.path.with_name(self.path.name+'.before-business-acl-'+uuid.uuid4().hex))
    with self.db:self.db.execute('CREATE TABLE g_resource_acl(kind TEXT NOT NULL,id TEXT NOT NULL,owner TEXT NOT NULL,space TEXT NOT NULL,project TEXT,version INTEGER NOT NULL,PRIMARY KEY(kind,id))')
    return {'changed':True,'backup':backup}
 def claim(self,kind,key,owner,space,project=None,*,approved=False):
    if approved is not True:raise PermissionError('Explicit owner mapping approval required')
    if kind=='document':
        row=self.db.execute('SELECT space FROM docs WHERE id=?',(key,)).fetchone()
        if not row or row['space']!=space:raise PermissionError('Source/space mismatch')
    with self.db:
        old=self.metadata(kind,key)
        if old:raise PermissionError('Existing ownership cannot be overwritten')
        self.db.execute('INSERT INTO g_resource_acl VALUES(?,?,?,?,?,1)',(kind,key,owner,space,project))
 def metadata(self,kind,key):
    row=self.db.execute('SELECT * FROM g_resource_acl WHERE kind=? AND id=?',(kind,key)).fetchone()
    return dict(row) if row else None
 def list(self,kind,query):
    if kind!='document':raise ValueError('Use the native repository for this resource kind')
    spaces=query.get('spaces',[]);projects=query.get('projects',[])
    if not spaces:return []
    placeholders=','.join('?' for _ in spaces)
    columns="d.id,d.title,d.kind,d.topic,d.status,d.source,d.updated,substr(d.body,1,240) AS preview,d.space,a.owner,a.project,a.version"
    clause=f"a.space IN ({placeholders}) AND (a.owner=? OR a.space='commun')"
    params=[*spaces,query['owner']]
    words=re.findall(r'\w+',query.get('q',''),re.UNICODE)[:20]
    if query.get('q','').strip() and not words:return []
    join="JOIN g_resource_acl a ON a.id=d.id AND a.kind='document' AND a.space=d.space"
    if words:
        match=' OR '.join('"'+word+'"' for word in words)
        rows=self.db.execute(f"SELECT {columns} FROM search JOIN docs d ON d.id=search.id {join} WHERE search MATCH ? AND {clause} ORDER BY bm25(search) LIMIT 500",[match,*params]).fetchall()
    else:rows=self.db.execute(f"SELECT {columns} FROM docs d {join} WHERE {clause} ORDER BY d.updated DESC LIMIT 1200",params).fetchall()
    return [dict(r) for r in rows if not r['project'] or r['project'] in projects]

 def get(self,kind,key):
    if kind!='document':raise ValueError('Native repository required')
    row=self.db.execute("SELECT d.*,a.owner,a.project,a.version FROM docs d JOIN g_resource_acl a ON a.kind='document' AND a.id=d.id AND a.space=d.space WHERE d.id=?",(key,)).fetchone()
    return dict(row) if row else None
 def create(self,kind,data):
    if kind!='document' or not isinstance(data.get('title'),str) or not isinstance(data.get('body'),str) or not 1<=len(data['title'])<=180 or not 1<=len(data['body'])<=30000:raise ValueError('Document schema')
    key='note:'+uuid.uuid4().hex;now=time.time()
    with self.db:
        self.db.execute('INSERT INTO docs(id,title,body,kind,topic,status,source,updated,fingerprint,space) VALUES(?,?,?,?,?,?,?,?,?,?)',(key,data['title'],data['body'],'Atelier',data.get('topic','Idées libres'),data.get('status','Idée'),'Ajouté dans Jarvis',now,None,data['space']))
        self.db.execute('INSERT INTO search(id,title,body) VALUES(?,?,?)',(key,data['title'],data['body']))
        self.db.execute('INSERT INTO g_resource_acl VALUES(?,?,?,?,?,1)',('document',key,data['owner'],data['space'],data.get('project')))
    return self.get(kind,key)
 def mutate(self,kind,key,change,guard):
    if kind!='document' or set(change)!={'target'}:raise ValueError('Document mutation schema')
    with self.db:
        cursor=self.db.execute('UPDATE g_resource_acl SET space=?,version=version+1 WHERE kind=? AND id=? AND owner=? AND version=?',(change['target'],kind,key,guard['expectedOwner'],guard['expectedVersion']))
        if cursor.rowcount!=1:raise PermissionError('Ownership/version changed')
        self.db.execute('UPDATE docs SET space=? WHERE id=?',(change['target'],key))
    return {'moved':True,'space':change['target']}
 def close(self):self.db.close()
