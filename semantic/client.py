"""Authenticated semantic service client; credentials come from the environment."""
import json,os,urllib.request

def call(path,data=None,timeout=15):
 base=os.environ.get('JARVIS_SEMANTIC_URL','').rstrip('/')
 key=os.environ.get('QDRANT__SERVICE__API_KEY','')
 if not base or not key:raise RuntimeError('Semantic memory is not configured')
 req=urllib.request.Request(base+path,headers={'x-jarvis-key':key,'content-type':'application/json'},data=None if data is None else json.dumps(data).encode())
 with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)
