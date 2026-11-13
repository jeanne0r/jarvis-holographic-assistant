// Incremental UTF-8 SSE decoding; no provider payload is written to disk.
export async function* sseEvents(body){
 const decoder=new TextDecoder();let pending='';
 const parse=block=>{const value=block.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trimStart()).join('\n');return !value||value==='[DONE]'?null:JSON.parse(value);};
 for await(const chunk of body){
  pending+=decoder.decode(chunk,{stream:true});pending=pending.replace(/\r\n/g,'\n');
  if(pending.length>2*1024*1024)throw Error('Événement vocal trop volumineux.');
  let boundary;while((boundary=pending.indexOf('\n\n'))!==-1){const event=parse(pending.slice(0,boundary));pending=pending.slice(boundary+2);if(event)yield event;}
 }
 pending+=decoder.decode();if(pending.trim()){const event=parse(pending);if(event)yield event;}
}
