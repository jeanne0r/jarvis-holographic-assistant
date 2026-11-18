// Independent human login. No Hermes dependency, storage token, fetch monkeypatch or audio.
(()=>{
 let identity=null,readyPromise,pending=[];
 const make=(tag,text,parent)=>{const e=document.createElement(tag);if(text)e.textContent=text;parent?.append(e);return e};
 const button=make('button','Connexion Jarvis',document.body);button.id='jarvisAccountButton';button.type='button';button.hidden=true;
 const dialog=make('dialog',null,document.body);dialog.id='jarvisAccountDialog';
 const close=make('button','Fermer',dialog);close.type='button';close.onclick=()=>dialog.close();
 const form=make('form',null,dialog);make('label','Code personnel',form);
 const input=make('input',null,form);input.type='password';input.autocomplete='one-time-code';input.setAttribute('aria-label','Code personnel');input.required=true;
 const submit=make('button','Se connecter',form);submit.type='submit';
 const status=make('p','',dialog);status.setAttribute('role','status');
 const logout=make('button','Déconnexion',dialog);logout.type='button';logout.hidden=true;
 function publish(id){identity=id;form.hidden=!!id;logout.hidden=!id;button.textContent=id?'Compte Jarvis':'Connexion Jarvis';button.hidden=false;document.dispatchEvent(new CustomEvent(id?'jarvis:session-ready':'jarvis:session-ended'));}
 async function request(path,options={}){
  const response=await fetch('/api/jarvis/'+path,{...options,credentials:'same-origin'});
  let body;try{body=await response.json()}catch{throw Error('Réponse indisponible')}
  if(response.status===401&&identity)publish(null);
  if(!response.ok)throw Object.assign(Error(response.status===401?'Connexion requise':body.error||'Requête refusée'),{status:response.status});return body;
 }
 async function load(){try{const r=await fetch('/api/jarvis/session',{credentials:'same-origin'});if(r.status===404)return null;if(r.ok){publish(await r.json());return identity}publish(null);return null}catch{publish(null);return null}}
 const open=async()=>{await readyPromise;if(identity){dialog.showModal();return identity}dialog.showModal();return new Promise(resolve=>pending.push(resolve))};
 button.onclick=()=>{void open()};
 dialog.addEventListener('close',()=>{input.value='';for(const resolve of pending.splice(0))resolve(identity)});
 form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{await request('session',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({token:input.value})});input.value='';await load();dialog.close()}catch(error){status.textContent=error.message;input.value=''}finally{submit.disabled=false}};
 logout.onclick=async()=>{try{await request('session',{method:'DELETE'});publish(null);dialog.close();location.reload()}catch(error){status.textContent=error.message}};
 globalThis.JarvisAuth=Object.freeze({request,open,ready:()=>readyPromise,identity:()=>identity});
 readyPromise=load();
})();
