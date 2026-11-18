"""The sole remote connector; TLS host/path fixed, no redirects or env proxy."""
import http.client,ipaddress,json,socket,ssl
class HTTPSProvider:
 def __init__(self,api_key):self.api_key=api_key
 def __call__(self,host,path,body):
  if host!='api.openai.com' or path!='/v1/responses':raise PermissionError('Fixed provider only')
  addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
  ips=[r[4][0] for r in addresses]
  if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):raise PermissionError('Provider resolved to non-public network')
  conn=http.client.HTTPSConnection(host,443,timeout=60,context=ssl.create_default_context())
  conn._create_connection=lambda address,timeout,source_address=None:socket.create_connection((ips[0],443),timeout,source_address)
  try:
   conn.request('POST',path,json.dumps(body).encode(),{'Authorization':'Bearer '+self.api_key,'Content-Type':'application/json'})
   response=conn.getresponse()
   if 300<=response.status<400:raise PermissionError('No provider redirects')
   raw=response.read(4*1024*1024+1)
   if len(raw)>4*1024*1024:raise ValueError('Provider reply bound')
   return {'status':response.status,'type':response.getheader('Content-Type','application/json'),'body':raw.decode('utf8','strict')}
  finally:conn.close()
