// Ownership layer, independent of model and audio transport.
export function voiceOwners({now=()=>Date.now(),ttl=3600000,limit=100}={}){
 const owners=new Map();
 const denied=()=>Object.assign(Error('Voice session owner denied'),{status:403});
 function principal(id){if(!id||id.kind!=='human'||!id.subject||!id.sessionHandle)throw denied()}
 return {
  bind(session,id,space){principal(id);for(const[k,v]of owners)if(v.expires<=now())owners.delete(k);if(owners.size>=limit)throw Object.assign(Error('Voice capacity'),{status:429});if(owners.has(session.sessionId))throw denied();owners.set(session.sessionId,{subject:id.subject,handle:id.sessionHandle,space,expires:now()+ttl});return session},
  check(sessionId,id,space){principal(id);const owner=owners.get(sessionId);if(!owner||owner.expires<=now()||owner.subject!==id.subject||owner.handle!==id.sessionHandle||owner.space!==space)throw denied()},
 };
}
