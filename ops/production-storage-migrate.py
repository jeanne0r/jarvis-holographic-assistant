"""Prepared migration command. Default only describes requirements, no data access.
Execution is forbidden until this exact patch, backup location, outage and owner map
are approved. Never use a visual profile as an owner mapping.
"""
import argparse,json,os,pathlib,stat,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from memory_manager.production.persistence import Persistence
from memory_manager.store import snapshot

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute-approved',action='store_true');p.add_argument('--approval-file');a=p.parse_args()
 if not a.execute_approved:
  print('PREPARED ONLY: approved private mapping, consistent backups, stopped writers and separate production permission required. No database opened.');return
 if not a.approval_file:raise PermissionError('Explicit private approval file required')
 fd=os.open(a.approval_file,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd)
  if not stat.S_ISREG(st.st_mode) or st.st_uid not in (0,os.getuid()) or st.st_mode&0o077 or st.st_size>1024**2:raise PermissionError('Private approved manifest')
  cfg=json.loads(os.read(fd,1024**2+1))
 finally:os.close(fd)
 if cfg.get('approved') is not True or cfg.get('writers_stopped') is not True:raise PermissionError('Approved mapping and exclusive write window required')
 for mapping in cfg.get('mapping',[]):
  if set(mapping)-{'kind','id','owner','space','project'} or mapping.get('kind') not in ('document','conversation','memory') or mapping.get('owner') not in cfg['approved_subjects'] or not mapping.get('owner') or mapping.get('space') not in cfg['approved_spaces']:raise PermissionError('Complete explicit mapping required before mutation')
 brain=pathlib.Path(cfg['brain']).resolve(strict=True);voice=pathlib.Path(cfg['voice']).resolve(strict=True);backup=pathlib.Path(cfg['backup_directory']).resolve(strict=True)
 if backup.stat().st_mode&0o077:raise PermissionError('Private approved backup directory')
 os.umask(0o077)
 # SQLite backup API includes committed WAL data. Each backup has integrity/hash checks.
 import uuid
 for db in (brain,voice):snapshot(db,backup/(db.name+'.'+uuid.uuid4().hex+'.sqlite'))
 repo=Persistence(brain,voice)
 try:
  repo.migrate()
  for mapping in cfg.get('mapping',[]):
   if set(mapping)-{'kind','id','owner','space','project'} or mapping['owner'] not in cfg['approved_subjects'] or not mapping['owner'] or mapping['space'] not in cfg['approved_spaces']:raise PermissionError('Explicit subject/scope required')
   kind=mapping['kind'];key=mapping['id']
   if kind!='memory':
    previous=repo.metadata(kind,key)
    if previous:
     if previous['owner']!=mapping['owner'] or previous['space']!=mapping['space'] or previous.get('project')!=mapping.get('project'):raise PermissionError('Ownership conflict')
     continue
   else:
    previous=repo.voice.execute('SELECT * FROM g_fact_acl WHERE space=? AND key=?',(mapping['space'],key)).fetchone()
    if previous:
     if previous['owner']!=mapping['owner']:raise PermissionError('Fact owner conflict')
     continue
   if kind=='document':repo.claim(kind,key,mapping['owner'],mapping['space'],mapping.get('project'),approved=True)
   elif kind=='conversation':
    row=repo.db.execute('SELECT space FROM conversation_sessions WHERE id=?',(key,)).fetchone()
    if not row or row['space']!=mapping['space']:raise PermissionError('Conversation source mismatch')
    repo.claim(kind,key,mapping['owner'],mapping['space'],mapping.get('project'),approved=True)
   elif kind=='memory':
    row=repo.voice.execute('SELECT 1 FROM facts WHERE space=? AND key=?',(mapping['space'],key)).fetchone()
    if not row:raise PermissionError('Fact source mismatch')
    with repo.voice:repo.voice.execute('INSERT INTO g_fact_acl VALUES(?,?,?,?,?,0)',(mapping['space'],key,mapping['owner'],1,'observed'))
   else:raise PermissionError('Auxiliary account mapping requires its verified file/resource manifest; not inferred here')
 finally:repo.close()
 print('Approved additive migration completed; no source contents printed. Auxiliary ownership not inferred.')
if __name__=='__main__':
 try:main()
 except Exception:print('Migration stopped. Inspect private state and backups before retry; no automatic restore.',file=sys.stderr);raise SystemExit(1)
