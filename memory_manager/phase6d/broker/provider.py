"""Fixed-origin provider policy and durable conservative cost reservation.

No remote call is made by constructing this object. Default budget is zero.
The trusted host supplies a forwarding implementation and approved price ceilings.
"""
import json,math,sqlite3,time
class Provider:
 def __init__(self,path,job,models,*,budget_micros=0,forward=None,authorized=None):
    self.db=sqlite3.connect(path);self.db.execute('CREATE TABLE IF NOT EXISTS provider_reservations(id INTEGER PRIMARY KEY,job TEXT NOT NULL,month TEXT NOT NULL,micros INTEGER NOT NULL,created REAL NOT NULL)');self.db.commit()
    self.job,self.models,self.budget,self.forward,self.authorized=job,dict(models),budget_micros,forward,authorized
 def request(self,method,path,body):
    if method!='POST' or path!='/v1/responses' or not isinstance(body,dict):raise PermissionError('Provider path denied')
    if self.budget<=0 or not self.forward or not self.authorized or self.authorized(self.job) is not True:raise PermissionError('Remote budget/authority unavailable')
    if body.get('model') not in self.models or any(t.get('type') not in {'function','custom'} for t in body.get('tools',[])):raise PermissionError('Model or paid hosted tool denied')
    def text_only(value):
     if isinstance(value,dict):
      if any(k in value for k in ['image_url','image','audio','file_url','file_id']) or value.get('type') in {'input_image','input_audio','input_file','image_generation'}:raise PermissionError('Text-only provider profile')
      for item in value.values():text_only(item)
     elif isinstance(value,list):
      for item in value:text_only(item)
    text_only(body)
    raw=json.dumps(body,allow_nan=False).encode()
    if len(raw)>65536:raise ValueError('Provider context bound')
    model=self.models[body['model']];maximum=body.get('max_output_tokens',2048)
    if type(maximum) is not int or not 1<=maximum<=model['output_limit']:raise ValueError('Output token bound')
    safe={**body,'max_output_tokens':maximum,'store':False}
    if min(model['input_micros_per_token'],model['output_micros_per_token'])<=0:raise ValueError('Approved conservative CHF price ceilings required')
    reservation=math.ceil((len(raw)+4096)*model['input_micros_per_token']+maximum*model['output_micros_per_token']);month=time.strftime('%Y-%m',time.gmtime())
    self.db.execute('BEGIN IMMEDIATE')
    try:
        used=self.db.execute('SELECT COALESCE(sum(micros),0) FROM provider_reservations WHERE month=?',(month,)).fetchone()[0]
        if used+reservation>self.budget:raise PermissionError('Hard monthly CHF cap')
        self.db.execute('INSERT INTO provider_reservations(job,month,micros,created) VALUES(?,?,?,?)',(self.job,month,reservation,time.time()));self.db.commit()
    except Exception:self.db.rollback();raise
    # Failure never refunds an uncertain request or triggers a paid retry.
    return self.forward('api.openai.com','/v1/responses',safe)
 def close(self):self.db.close()
