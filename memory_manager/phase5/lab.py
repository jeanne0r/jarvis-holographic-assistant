"""Explicit laboratory runner; never provisions Qdrant or starts Hermes/Ollama.

Examples: python3 -m memory_manager.phase5.lab init --database data/phase5/lab.sqlite
Network operations additionally require --approved-services and a private 0600
configuration referencing token files, never literal credentials.
"""
import argparse
import json
import os
from pathlib import Path
from ..store import Memory, Principal
from ..phase2 import database as phase2
from ..phase2.local_model import PrivateHTTP
from ..api import server
from . import database, vector
from .api import extension

ROOT=Path(__file__).resolve().parents[2]/'data'/'phase5'


def lab_path(value):
    path=Path(value).resolve()
    if not path.is_relative_to(ROOT.resolve()) or path==ROOT.resolve():raise ValueError('Phase5 laboratory data path required')
    return path


def private_json(path):
    path=Path(path)
    if path.stat().st_mode & 0o077:raise PermissionError('0600 configuration required')
    return json.loads(path.read_text())


def credential(path):
    path=Path(path)
    if path.stat().st_mode & 0o077:raise PermissionError('0600 credential required')
    token=path.read_text().strip()
    if len(token)<32:raise ValueError('Dedicated credential required')
    return token


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['init','index','rebuild','serve'])
    p.add_argument('--database',required=True);p.add_argument('--config');p.add_argument('--approved-services',action='store_true')
    args=p.parse_args();path=lab_path(args.database)
    if args.action=='init':
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        m=Memory(path,create=True)
        try:phase2.migrate(m);database.migrate(m)
        finally:m.close()
        print(json.dumps({'created':'laboratory','network_calls':0}));return
    if not args.approved_services:raise PermissionError('Explicit service-test authorization required')
    c=private_json(args.config)
    # Force loopback tunnels, preserving SSH encryption on the physical network.
    from urllib.parse import urlsplit
    for key in ('qdrant_url','embedding_url'):
        if urlsplit(c[key]).hostname not in {'127.0.0.1','::1'}:raise ValueError('Loopback SSH endpoint required')
    qhttp=PrivateHTTP(c['qdrant_url']);qkey=credential(c['qdrant_token_file'])
    def qtransport(method,path,body=None,**kw):return qhttp(method,path,body,headers={'api-key':qkey},**kw)
    driver=vector.Qdrant(qtransport)
    embed=vector.Embeddings(PrivateHTTP(c['embedding_url'],credential(c['embedding_token_file'])),c['embedding_manifest_sha256'])
    if args.action=='serve':
        clients=private_json(c['clients_file'])
        s=server(path,clients,c.get('port',8795),extension=extension(driver,embed))
        try:s.serve_forever()
        except KeyboardInterrupt:pass
        finally:s.server_close()
    else:
        m=Memory(path)
        try:
            identity=c['index_identity'];principal=Principal(identity['owner'],frozenset(identity['scopes']),frozenset({'reader','indexer'}),'phase5-indexer')
            print(json.dumps(vector.index(m,principal,driver,embed,rebuild=args.action=='rebuild')))
        finally:m.close()


if __name__=='__main__':
    try:main()
    except (ValueError,PermissionError,KeyError,OSError):raise SystemExit('Laboratory configuration or authorization rejected; no credential details emitted')
