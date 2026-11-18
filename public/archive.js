(() => {
  const key='jarvis-conversations-pending-v1';
  const spaces=new Set(['user','amelie','malik','theo','commun']);
  let pending=new Map(),sending=false,failed=false;
  const written=new Map();
  function clean(text){
    return String(text).replace(/^.*(?:password|mot de passe|passwd|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|gateway[_ -]?token|authorization|bearer\s|oauth|BEGIN .*PRIVATE KEY).*$/gim,'[Information sensible masquée]')
      .replace(/AIza[0-9A-Za-z_-]{20,}/g,'[secret masqué]')
      .replace(/\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]+|eyJ[A-Za-z0-9_.-]{20,})\b/g,'[secret masqué]')
      .replace(/[A-Za-z0-9_+/=-]{48,}/g,'[identifiant masqué]').trim();
  }
  function paint(){
    const label=document.querySelector('#archiveStatus');if(!label)return;
    label.textContent=pending.size?(failed?'Enregistrement à réessayer · ':'Enregistrement… · ')+pending.size+' échange(s) en attente sur cet appareil.':'Échanges écrits et vocaux enregistrés automatiquement · texte uniquement.';
    label.classList.toggle('error',failed);
  }
  function persist(){try{localStorage.setItem(key,JSON.stringify([...pending]));}catch{failed=true;}paint();}
  try{for(const [id,row] of JSON.parse(localStorage.getItem(key)||'[]'))if(spaces.has(row.space)&&row.id&&Number.isInteger(row.revision))pending.set(id,row);}catch{}
  async function flush(){
    if(sending||!pending.size)return;sending=true;
    try{for(const [id,row] of pending){
      const response=await fetch('/api/jarvis/conversations/record?space='+encodeURIComponent(row.space),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(row),keepalive:new Blob([JSON.stringify(row)]).size<60000,signal:AbortSignal.timeout(12000)});
      if(!response.ok)throw Error();
      if(pending.get(id)?.revision===row.revision)pending.delete(id);
      failed=false;persist();
    }}catch{failed=true;paint();}finally{sending=false;}
  }
  function record(row){
    if(!row.id||!spaces.has(row.space))return;
    const safe={...row,user:clean(row.user||''),assistant:clean(row.assistant||'')};
    pending.set(safe.channel+':'+safe.id+':'+safe.turn,safe);persist();void flush();
  }
  function uuid(){if(crypto.randomUUID)return crypto.randomUUID();const b=crypto.getRandomValues(new Uint8Array(16));b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;const h=Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');return h.slice(0,8)+'-'+h.slice(8,12)+'-'+h.slice(12,16)+'-'+h.slice(16,20)+'-'+h.slice(20);}
  function writtenRow(space){
    if(!written.has(space))written.set(space,{id:uuid(),space,channel:'written',turn:-1,revision:0,user:'',assistant:'',status:'partial'});
    return written.get(space);
  }
  window.jarvisArchive={record,
    newConversation(space){written.delete(space);},
    written(role,text,space){const row=writtenRow(space);
      if(role==='user'){row.turn++;row.revision=0;row.user=text;row.assistant='';row.status='partial';}
      else {if(row.turn<0)row.turn=0;row.assistant+=(row.assistant?'\n':'')+text;row.status='complete';}
      row.revision++;record({...row});
    },
    writtenRequest(space){const row=writtenRow(space);return {id:row.id,turn:Math.max(0,row.turn)};},
  };
  function leave(){for(const row of pending.values()){
    const body=JSON.stringify(row);if(new Blob([body]).size<60000)navigator.sendBeacon('/api/jarvis/conversations/record?space='+encodeURIComponent(row.space),new Blob([body],{type:'application/json'}));
  }}
  window.addEventListener('pagehide',leave);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)leave();else void flush();});
  window.addEventListener('online',()=>void flush());setInterval(()=>void flush(),5000);paint();void flush();
})();
