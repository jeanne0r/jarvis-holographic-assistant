"""Private read-only ownership inventory. Never reads titles/bodies/fact values.

Do not execute --approved without explicit user approval for this exact scope.
"""
import argparse,hashlib,json,os,sqlite3
from contextlib import closing
from pathlib import Path
SOURCES=[('/home/user/workspace/jarvis/data/brain.sqlite','docs','id','kind'),('/home/user/workspace/jarvis/data/voice-memory.sqlite','facts','key',None)]

def collect(sources,limit=20):
 if type(limit) is not int or not 1<=limit<=20:raise ValueError('Strict shared twenty-row cap')
 report={'mode':'read-only-metadata','content_fields_read':False,'owners_assigned':False,'limit_total':limit,'sources':[]};remaining=limit
 for path,table,key,kind in sources:
  if (table,key,kind) not in {('docs','id','kind'),('facts','key',None)}:raise ValueError('Fixed schema whitelist')
  entry={'database':str(path),'table':table,'rows':[]}
  with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
   db.execute('PRAGMA query_only=ON')
   entry['counts_by_space']=[{'space':r[0],'count':r[1]} for r in db.execute('SELECT space,count(*) FROM '+table+' GROUP BY space')]
   columns=key+',space,updated'+(',kind' if kind else '')
   for row in db.execute('SELECT '+columns+' FROM '+table+' ORDER BY updated DESC LIMIT ?',(remaining,)):
    entry['rows'].append({'id_sha256':hashlib.sha256(str(row[0]).encode()).hexdigest(),'space':row[1],'updated':row[2],**({'kind':row[3]} if kind else {})})
   remaining-=len(entry['rows'])
  report['sources'].append(entry)
 report['sample_count']=limit-remaining
 return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--approved',action='store_true');a=p.parse_args()
 if not a.approved:raise SystemExit('Approval required: two SQLite sources, metadata only, at most 20 sampled rows total, no contents or transmission.')
 report=collect(SOURCES)
 out=Path('/home/user/workspace/_private/jarvis-2/phase6d-owner-inventory')
 for folder in [out.parents[1],out.parent,out]:
  if folder.is_symlink() or (folder/'.git').exists():raise PermissionError('Private non-Git path required')
  folder.mkdir(mode=0o700,exist_ok=True)
 if out.stat().st_uid!=os.getuid() or out.stat().st_mode&0o077:raise PermissionError('Private report directory required')
 file=out/'inventory.json';fd=os.open(file,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
 print('Private metadata report written; no database changes or owner assignment.')
if __name__=='__main__':main()
