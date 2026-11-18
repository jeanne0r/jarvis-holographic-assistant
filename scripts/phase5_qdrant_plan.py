"""Print a reviewable plan only. NO HTTP execution, credentials or destructive API."""
import json

COLLECTION='jarvis_knowledge_experimental_v1'
PLAN={
 'mode':'plan_only','executed_requests':0,'requires_human_approval':True,
 'backup':[
  {'method':'POST','path':'/collections/jarvis_memory_v1/snapshots','effect':'creates snapshot file only; requires CT205 authorization'},
  {'method':'GET','path':'/collections/jarvis_memory_v1/snapshots/<returned-name>','effect':'private backup download, exclusive destination; SHA256 + bytes manifest'},
 ],
 'provision':{'precondition':'GET target returns 404; otherwise verify and STOP, never overwrite',
  'method':'PUT','path':'/collections/'+COLLECTION,'body':{'vectors':{'size':384,'distance':'Cosine','on_disk':True},'on_disk_payload':True,
     'hnsw_config':{'on_disk':True},'optimizers_config':{'default_segment_number':2}}},
 'restore_verification':{'target':'separate isolated Qdrant 1.20.0 with private volume; never CT205 production',
  'steps':['verify archive SHA256 and bytes against manifest','ensure free disk >=2x restored collection size plus snapshot archive',
           'start isolated Qdrant with snapshot import, without force, target must be absent',
           'compare count, vector schema and payload indexes with backup-time metadata',
           'controlled synthetic query in isolated target; do not export personal payloads','record result; stop isolated instance, retain private backup']},
 'prohibited':['PUT/DELETE points in jarvis_memory_v1','global prune','restore over existing collection','force restore','public network exposure'],
 'rollback':'disable phase5 extension/client; stop lab and tunnels only; retain existing snapshots/collections/data for review'
}
if __name__=='__main__':print(json.dumps(PLAN,ensure_ascii=False,indent=2))
