// Per-job private tool endpoint. Owner, space and permissions come from the host.
import net from 'node:net';
export function toolsBroker({identity,space,sessions,authority,declarations}){
 return net.createServer(socket=>{let bytes=Buffer.alloc(0),done=false;socket.setTimeout(5000,()=>socket.destroy());socket.on('error',()=>{});socket.on('data',async part=>{
  if(done)return;bytes=Buffer.concat([bytes,part]);if(bytes.length>16004)return socket.destroy();if(bytes.length<4)return;
  const size=bytes.readUInt32BE();if(size>16000)return socket.destroy();if(bytes.length<size+4)return;done=true;
  let result;try{const msg=JSON.parse(bytes.subarray(4));if(!sessions.isActive(identity,'conversation',space))throw Error('Session revoked');
   if(msg.method==='tools/list')result={tools:declarations};
   else if(msg.method==='tools/call'&&typeof msg.params?.name==='string')result={content:[{type:'text',text:JSON.stringify(await authority(identity,space,msg.params.name,msg.params.arguments||{}))}]};
   else throw Error('Tool method denied');
  }catch{result={isError:true,content:[{type:'text',text:'Tool denied'}]}}
  const raw=Buffer.from(JSON.stringify(result));if(raw.length>65536)return socket.destroy();const h=Buffer.alloc(4);h.writeUInt32BE(raw.length);socket.end(Buffer.concat([h,raw]));
 })});
}
