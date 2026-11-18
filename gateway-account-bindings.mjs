import {fridgeView} from './gateway-fridge-format.mjs';
// Known native JSON formats are served by the storage identity, not legacy globals.
export function accountBindings({rpcFor,accountIds,upstreams={}}){
 return {
  ...upstreams,
  '/api/mirror/tasks':({identity,method,data})=>{
   const id=accountIds[identity.subject]?.tasks;if(!id)throw Error('Task account not bound');
   const rpc=rpcFor(identity);return rpc(method==='GET'?'tasks.list':'tasks.change',{subject:identity.subject,space:identity.space||identity.defaultSpace,id,action:method,data});
  },
  '/api/fridge/stock':async({identity,parameters})=>{
   const id=accountIds[identity.subject]?.fridge;if(!id)throw Error('Fridge account not bound');
   return fridgeView(await rpcFor(identity)('fridge.list',{space:identity.space||identity.defaultSpace,id}),parameters);
  },
 };
}
