import json,os,pathlib,socket,urllib.request,urllib.parse
SECRET=pathlib.Path('/home/user/workspace/_secrets/jarvis-qdrant.env')
def call(path,data=None,timeout=15):
 config=dict(line.split('=',1) for line in SECRET.read_text().splitlines() if '=' in line and not line.startswith('#'))
 url=urllib.parse.urlsplit(config['JARVIS_SEMANTIC_URL'])
 # FritzBox maintains the DHCP hostname; prefer IPv4 for the guest firewall rule.
 host=socket.gethostbyname(url.hostname)
 target=urllib.parse.urlunsplit((url.scheme,f'{host}:{url.port}',path,'',''))
 req=urllib.request.Request(target,headers={'x-jarvis-key':config['QDRANT__SERVICE__API_KEY'],'content-type':'application/json'},data=None if data is None else json.dumps(data).encode())
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
