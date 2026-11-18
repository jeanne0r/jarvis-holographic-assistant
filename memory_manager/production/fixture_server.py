"""Offline test helper: creates only synthetic files in an empty temporary directory."""
import hashlib,os,pathlib,sys
from .test_persistence import fixture
from .persistence import Persistence
from .storage_service import Storage
from .storage_main import Server
root=pathlib.Path(sys.argv[1]).resolve(strict=True)
if list(root.iterdir()):raise PermissionError('Empty fixture directory required')
os.umask(0o077);brain=root/'brain.sqlite';voice=root/'voice.sqlite';fixture(brain,voice)
repo=Persistence(brain,voice);repo.migrate()
policy={u:{'permissions':['storage.read','storage.write'],'spaces':['user'],'write_spaces':['user'],'project_read':['dose'],'project_write':['dose']} for u in ['alice','bob']}
service=Storage(repo,policy,staging=root)
server=Server(root/'storage.sock',service,{hashlib.sha256(b's'*43).hexdigest():{'service':'gateway-storage','subjects':['alice','bob']}},ipc_gid=os.getgid())
print('fixture-ready',flush=True)
try:server.serve_forever()
finally:server.server_close();repo.close()
