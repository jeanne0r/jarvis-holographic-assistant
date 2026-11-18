// Permissions are rechecked against the server session before EVERY tool effect.
import {createHash} from 'node:crypto';
export function toolAuthority({sessions,acl,memory,handlers,physicalApprovals}){
 const reads={consulter_home_assistant:'physical.status',commandes_home_assistant:'physical.status',chercher_souvenirs:'memory.read',web_jarvis:'web.read',trajet_jarvis:'maps.read'};
 return async(identity,space,name,args={})=>{
  const demand=p=>{if(!sessions.isActive(identity,p,space))throw Object.assign(Error('Tool denied'),{status:403})};
  const targetSpace=args.shared?'commun':space;
  if(!identity.spaces.includes(targetSpace)||!acl.spaces(identity,name==='memoire_jarvis'&&args.action!=='consulter').includes(targetSpace))throw Error('Tool space denied');
  if(name==='memoire_jarvis'){
   const read=args.action==='consulter';if(!['consulter','memoriser','oublier'].includes(args.action))throw Error('Memory operation');
   demand(read?'memory.read':'memory.write');
   if(read)return memory.list(identity,'memory',{space:targetSpace});
   if(args.action==='oublier')return memory.mutate(identity,'memory',args.key,{delete:true});
   return memory.create(identity,'memory',{space:targetSpace,key:args.key,fact:args.fact,status:'inferred'});
  }
  const physical=name==='piloter_home_assistant'||name==='medias_jarvis'&&args.target&&args.target!=='ici';
  if(physical){
   demand(name==='piloter_home_assistant'?'physical.ha.control':'physical.media.control');
   const fingerprint=createHash('sha256').update(JSON.stringify([name,identity.subject,space,args])).digest('hex');
   if(!physicalApprovals||!await physicalApprovals.consume({subject:identity.subject,fingerprint,permission:name==='piloter_home_assistant'?'physical.ha.control':'physical.media.control'}))throw Error('Exact physical approval required');
  }else demand(name==='medias_jarvis'?'media.browser':reads[name]||'__denied__');
  if(typeof handlers[name]!=='function')throw Error('Tool unavailable');
  return handlers[name](args,{identity,space,allowedSpaces:acl.spaces(identity)});
 };
}
export function scopedMemoryStore(identity,space,acl,store,sessions){
 return async(action,data={})=>{
  const write=action!=='list';const target=data.shared?'commun':data.space||space;
  if(!sessions.isActive(identity,write?'memory.write':'memory.read',target)||!acl.spaces(identity,write).includes(target))throw Error('Memory denied');
  if(!['list','save','save_correction','forget'].includes(action))throw Error('Memory operation denied');
  if(write){
   if(typeof store.metadata!=='function')throw Error('Legacy fact ownership adapter required');
   const prior=await store.metadata(data.key,target);if(prior&&!acl.resource(identity,prior,true))throw Error('Fact owner denied');
  }
  const result=await store(action,{...data,space:target,include_common:target==='commun'?false:acl.spaces(identity).includes('commun'),actor:identity.subject});
  if(action==='list'){if(!Array.isArray(result))throw Error('Fact list schema');return result.filter(r=>acl.resource(identity,r)&&acl.spaces(identity).includes(r.space))}
  return result;
 };
}
