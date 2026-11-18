"""C2 only: one local private dry-run. Never prints source content or calls a model."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid
from memory_manager.phase5c.local_review import review


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approved-c2',action='store_true',required=True);p.parse_args()
    root=Path(__file__).resolve().parents[1];private=root/'data/phase5c'
    # An approval cannot silently be spent again on twenty other sources.
    guard=private/'c2-20261114-reserved.json'
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:8]
    folder=private/('c2-'+ident)
    with os.fdopen(os.open(guard,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:json.dump({'folder':str(folder),'maximum_sources':20},f)
    result=review('/home/user/workspace/jarvis/data/brain.sqlite',folder)
    (root/'docs/JARVIS_2_PHASE5C_C2_SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    try:main()
    except Exception as exc:print(json.dumps({'failed':True,'error_class':type(exc).__name__,'private_content_omitted':True}));raise SystemExit(1)
