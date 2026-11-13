(() => {
 const panel=document.querySelector('#voiceDiagnostics');if(!panel)return;
 const labels={idle:'Veille',connecting:'Connexion',listening:'Écoute',thinking:'Attente',speaking:'Lecture',error:'Erreur'};
 let last=0,pending=null,timer=0;
 function draw(data){last=performance.now();panel.dataset.state=data.state;
  panel.querySelector('[data-live-phase]').textContent=labels[data.state]||data.state;
  panel.querySelector('[data-live-input]').textContent=data.inputRms.toFixed(3);
  panel.querySelector('[data-live-output]').textContent=data.outputRms.toFixed(3);
  panel.querySelector('[data-live-transport]').textContent=({closed:'Fermé',connecting:'Ouverture',ready:'Gemini connecté',error:'Erreur'})[data.transport]||data.transport;
  panel.querySelector('[data-live-event]').textContent=data.lastEvent;
  panel.querySelector('[data-live-buffer]').textContent=Math.round(data.bufferedMs)+' ms';
  panel.querySelector('[data-live-wait]').textContent=data.waiting?'Déduite : '+data.waitSource:'—';
  panel.querySelector('[data-live-interrupt]').textContent=data.interruptions+(data.lastInterrupt?' · '+(data.lastInterrupt==='local'?'VAD local':'Gemini confirmé'):'');
  panel.querySelector('[data-live-mic-bar]').value=data.inputRms;
  panel.querySelector('[data-live-output-bar]').value=data.outputRms;
 }
 document.addEventListener('jarvis:live-diagnostics',event=>{pending=event.detail;if(performance.now()-last>=75){clearTimeout(timer);timer=0;draw(pending);}else if(!timer)timer=setTimeout(()=>{timer=0;draw(pending)},75);});
 if(window.jarvisLiveDiagnostics)draw(window.jarvisLiveDiagnostics);
})();
