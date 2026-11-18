import argparse
import json
from .store import Memory, snapshot

parser = argparse.ArgumentParser(description='Isolated experimental memory administration')
parser.add_argument('action', choices=['init', 'backup'])
parser.add_argument('--database', required=True)
parser.add_argument('--destination')
args = parser.parse_args()
if args.action == 'init':
    Memory(args.database, create=True).close()
    print(json.dumps({'initialized': True, 'schema': 1}))
else:
    if not args.destination:
        parser.error('--destination required')
    print(json.dumps(snapshot(args.database, args.destination)))
