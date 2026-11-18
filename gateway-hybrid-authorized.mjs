// Preserve the existing hybrid classifier/public engine; replace only trusted dependencies.
import {hybridAnswer} from './hybrid-brain.mjs';
import {scopedMemoryStore} from './gateway-tool-authority.mjs';
export function authorizedHybrid({acl,sessions,tools,toolDeclarations,memoryStore,broker,dependencies={}}){
 return async({identity,question,context,signal})=>{
  if(!sessions.isActive(identity,'conversation',context.space))throw Error('Conversation denied');
  const configured=typeof dependencies==='function'?dependencies(identity):dependencies;
  return hybridAnswer(question,[],context,signal,{
   ...configured,memoryStore:scopedMemoryStore(identity,context.space,acl,memoryStore,sessions),
   tools:async()=>({tools:toolDeclarations,call:(name,args)=>tools(identity,context.space,name,args)}),
   codex:(q,s,c,abort)=>broker.answer({question:q,sources:s,context:c,identity,signal:abort}),
  });
 };
}
