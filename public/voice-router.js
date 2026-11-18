// Speech uses /ask; authentication retry changes only script loading, never audio.
(()=>{
 let loaded=false,loading=false,retry=false;
 async function load(){
  if(loaded){return}if(loading){retry=true;return}loading=true;
  try{
   const response=await fetch('/api/jarvis/voice/status');if(!response.ok)throw Error();
   const info=await response.json(),script=document.createElement('script');
   script.src=info.engine==='gemini-live'?'live.js?v=20261113-mute1':'codex-voice.js?v=20261113-mute1';
   script.onerror=()=>{document.querySelector('#liveStatus').textContent='La voix n’a pas pu être chargée. Recharge la page.';};
   loaded=true;document.head.append(script);
  }catch{document.querySelector('#liveStatus').textContent='Connexion à Jarvis indisponible. Connecte-toi ou recharge la page.';}
  finally{loading=false;if(retry){retry=false;void load()}}
 }
 document.addEventListener('jarvis:session-ready',()=>void load());void load();
})();
