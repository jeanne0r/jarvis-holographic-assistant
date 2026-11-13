// Gemini transcribes and speaks. Every answer/action comes from the common /ask brain.
(() => {
 const $=s=>document.querySelector(s),button=$('#liveButton'),status=$('#liveStatus'),clock=$('#liveClock'),stopButton=$('#voiceStop');let active=null;
 const modeButton=$('#voiceModeToggle'),modeKey='jarvis-voice-mode-v1';let mode='natural';
 try{if(localStorage.getItem(modeKey)==='dictation')mode='dictation';}catch{}
 const readyText=()=>active?.muted?'Micro en pause · touche le cœur pour reprendre.':mode==='dictation'?'À toi · parle, puis marque une pause.':'Je t’écoute. Tu peux m’interrompre.';
 function syncMic(s){
  if(active!==s)return;
  const held=Boolean(s.muted)||(mode==='dictation'&&Boolean(s.busy||s.turn||s.outputPending||Date.now()<(s.resumeAfter||0)));
  const changed=held!==Boolean(s.micHeld);if(changed){s.gate?.reset();s.chunks=[];s.bytes=0;s.strongMs=0;s.voicedMs=0;monitor.input(0,0,false);}
  s.micHeld=held;if(changed)for(const track of s.stream?.getAudioTracks()||[])track.enabled=!held;
  if(changed)document.dispatchEvent(new CustomEvent('jarvis:voice-mode',{detail:{mode,held}}));
 }
 function renderMode(){modeButton.hidden=false;modeButton.textContent=mode==='dictation'?'Dictée sans coupure':'Mode : naturel';modeButton.setAttribute('aria-pressed',String(mode==='dictation'));modeButton.title=mode==='dictation'?'Dictée : micro suspendu pendant le traitement et la réponse. Passer en mode naturel.':'Naturel : tu peux interrompre Jarvis. Passer en dictée sans coupure.';document.body.dataset.voiceMode=mode;}
 modeButton.addEventListener('click',()=>{mode=mode==='natural'?'dictation':'natural';try{localStorage.setItem(modeKey,mode)}catch{}renderMode();if(active){syncMic(active);if(!active.busy&&!active.turn)paint(active.muted?readyText():active.micHeld?'Je te réponds · micro en pause.':readyText());}document.dispatchEvent(new CustomEvent('jarvis:voice-mode',{detail:{mode,held:!!active?.micHeld}}));});
 let lastTiming={};Object.defineProperty(window,'jarvisVoiceTimings',{get:()=>({...lastTiming}),configurable:true});
 const monitor=new JarvisLiveState(data=>{document.body.dataset.voice=data.state;document.dispatchEvent(new CustomEvent('jarvis:voice-state',{detail:{state:data.state}}));document.dispatchEvent(new CustomEvent('jarvis:live-diagnostics',{detail:data}));document.dispatchEvent(new CustomEvent('jarvis:audio-level',{detail:{input:data.inputRms,output:data.outputRms,source:'rendered-pcm'}}));});
 Object.defineProperty(window,'jarvisLiveDiagnostics',{get:()=>monitor.snapshot(),configurable:true});monitor.publish(true);renderMode();
 function paint(message,error=false){
  const muted=Boolean(active?.muted);status.textContent=message;status.classList.toggle('error',error);
  button.setAttribute('aria-pressed',String(Boolean(active)&&!muted));button.setAttribute('aria-label',!active?'Ouvrir le micro de Jarvis':muted?'Réactiver le micro de Jarvis':'Mettre le micro de Jarvis en pause');button.title=!active?'Ouvrir le micro':muted?'Réactiver le micro':'Mettre le micro en pause';button.classList.toggle('listening',Boolean(active)&&!muted);
  stopButton.hidden=!active;document.body.dataset.voiceMuted=String(muted);document.body.dataset.voiceSession=active?'active':'closed';document.dispatchEvent(new CustomEvent('jarvis:voice-controls'));
 }
 function toggleMute(){
  const s=active;if(!s)return;s.muted=!s.muted;s.lastSpeech=Date.now();syncMic(s);monitor.mute(s.muted);
  paint(s.muted?'Micro en pause · la réponse continue.':s.busy?'Je réfléchis…':s.turn||s.outputPending?'Je te réponds.':readyText());
 }
 stopButton.addEventListener('click',()=>stop('Conversation vocale terminée. Le texte reste dans Conversation.'));

 function clear(s){s.epoch=(s.epoch||0)+1;s.playback?.port.postMessage({type:'clear',epoch:s.epoch});s.speaking=false;s.outputPending=false;s.outputEnded=false;monitor.clear();}
 function cancel(s){s.sequence++;s.turn?.abort();s.turn=null;if(s.busy)window.jarvisCancelAsk?.();s.busy=false;clear(s);}
 function stop(message='Micro coupé.',error=false){const s=active;active=null;if(s){cancel(s);s.abort.abort();clearInterval(s.ticker);clearTimeout(s.resumeTimer);s.stream?.getTracks().forEach(t=>t.stop());s.mic?.disconnect();s.processor?.disconnect();s.playback?.disconnect();s.ctx?.close().catch(()=>{});}clock.textContent='';monitor.stop(error);paint(message,error);}
 function wave(parts){const size=parts.reduce((n,b)=>n+b.byteLength,0),out=new ArrayBuffer(size+44),v=new DataView(out);const word=(offset,text)=>{for(let i=0;i<text.length;i++)v.setUint8(offset+i,text.charCodeAt(i));};word(0,'RIFF');v.setUint32(4,size+36,true);word(8,'WAVEfmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);v.setUint32(28,32000,true);v.setUint16(32,2,true);v.setUint16(34,16,true);word(36,'data');v.setUint32(40,size,true);let at=44;for(const p of parts){new Uint8Array(out,at,p.byteLength).set(new Uint8Array(p));at+=p.byteLength;}return out;}
 async function speak(s,text,controller,sequence){
  const pieces=String(text).match(/[\s\S]{1,3000}(?:\s|$)|[\s\S]{1,3000}/g)||[];
  for(const piece of pieces){
   const r=await fetch('/api/jarvis/voice/speak?space='+encodeURIComponent(s.space),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({sessionId:s.id,text:piece,stream:true}),signal:controller.signal});if(!r.ok){const data=await r.json();throw Error(data.error||'La réponse reste affichée ; lecture vocale indisponible.');}
   const reader=r.body.getReader();let carry=new Uint8Array(0);
   try{for(;;){const {done,value}=await reader.read();if(done)break;if(active!==s||sequence!==s.sequence){await reader.cancel();return;}const bytes=new Uint8Array(carry.length+value.length);bytes.set(carry);bytes.set(value,carry.length);const count=Math.floor(bytes.length/2),samples=new Float32Array(count),view=new DataView(bytes.buffer);for(let i=0;i<count;i++)samples[i]=view.getInt16(i*2,true)/32768;carry=bytes.slice(count*2);if(!lastTiming.firstAudioMs){lastTiming.firstAudioMs=Math.round(performance.now()-s.turnStarted);document.dispatchEvent(new CustomEvent('jarvis:voice-timing',{detail:{...lastTiming}}));}monitor.receivedAudio();s.playback.port.postMessage({type:'audio',rate:24000,samples},[samples.buffer]);}}finally{reader.releaseLock();}
  }
  if(active===s&&sequence===s.sequence){s.outputEnded=true;monitor.generationComplete();s.playback.port.postMessage({type:'end'});}
 }
 async function utterance(s,parts){
  if(active!==s||parts.length<10)return;cancel(s);const sequence=s.sequence,controller=new AbortController();s.turn=controller;s.busy=true;s.turnStarted=performance.now();lastTiming={};syncMic(s);monitor.wait('Transcription Gemini');paint('Je t’écoute · transcription…');
  try{
   const r=await fetch('/api/jarvis/voice/transcribe?space='+encodeURIComponent(s.space),{method:'POST',headers:{'content-type':'audio/wav','x-jarvis-voice-session':s.id},body:wave(parts),signal:controller.signal});const data=await r.json();if(!r.ok)throw Error(data.error||'Transcription indisponible.');if(active!==s||sequence!==s.sequence)return;
   lastTiming.transcriptionMs=Math.round(performance.now()-s.turnStarted);const text=String(data.text||'').trim();if(!text){s.busy=false;s.turn=null;syncMic(s);monitor.turnComplete();paint(readyText());return;}
   const row=document.createElement('p');row.textContent=text;$('#liveTranscript').replaceChildren(row);s.lastSpeech=Date.now();monitor.wait('Réflexion Jarvis');paint('Je réfléchis…');
   const response=await window.jarvisAsk(text,{channel:'voice',signal:controller.signal,archive:{id:s.id,turn:s.turnNumber++}});if(active!==s||sequence!==s.sequence)return;if(!response){s.busy=false;s.turn=null;syncMic(s);monitor.turnComplete();paint('Réponse indisponible · consulte la conversation.',true);return;}
   lastTiming.brainMs=Math.round(performance.now()-s.turnStarted)-lastTiming.transcriptionMs;lastTiming.codexMs=response.execution?.elapsedMs??null;s.busy=false;if(response.answer){s.outputPending=true;s.outputEnded=false;syncMic(s);paint('Je te réponds.');monitor.wait('Synthèse vocale Gemini');await speak(s,response.speech||response.answer,controller,sequence);}
   if(active===s&&sequence===s.sequence){s.turn=null;syncMic(s);monitor.turnComplete();paint(s.muted?readyText():s.micHeld?'Je te réponds · micro en pause.':readyText());}
  }catch(error){if(active===s&&sequence===s.sequence&&error.name!=='AbortError'){s.busy=false;s.turn=null;clear(s);syncMic(s);monitor.turnComplete();paint(error.message,true);}}
 }
 button.addEventListener('click',async()=>{
  if(active){toggleMute();return;}
  if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia){paint('Ouvre Jarvis en HTTPS pour utiliser le micro.',true);const link=$('#liveHttps'),url=new URL(location.href);url.protocol='https:';url.port='8788';link.href=url.href;link.hidden=false;return;}
  const s={abort:new AbortController(),space:$('#spaceSelect').value,sequence:0,epoch:0,chunks:[],bytes:0,busy:false,speaking:false,turnNumber:0,strongMs:0};active=s;monitor.connect();paint('Ouverture du micro…');
  try{
   const Context=window.AudioContext||window.webkitAudioContext;s.ctx=new Context({latencyHint:'interactive'});await s.ctx.resume();
   const r=await fetch('/api/jarvis/voice/session?space='+encodeURIComponent(s.space),{method:'POST',headers:{'content-type':'application/json'},body:'{}',signal:s.abort.signal}),session=await r.json();if(!r.ok)throw Error(session.error||'Voix indisponible.');if(active!==s)return;s.id=session.sessionId;
   const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});if(active!==s){stream.getTracks().forEach(t=>t.stop());return;}s.stream=stream;for(const track of stream.getAudioTracks())track.enabled=!s.muted;stream.getAudioTracks()[0].onended=()=>{if(active===s)stop('Le micro a été déconnecté.');};
   await s.ctx.audioWorklet.addModule('live-pcm.js?v=20261113-modes2');if(active!==s)return;
   s.mic=s.ctx.createMediaStreamSource(stream);s.processor=new AudioWorkletNode(s.ctx,'jarvis-pcm',{outputChannelCount:[1]});s.playback=new AudioWorkletNode(s.ctx,'jarvis-playback',{numberOfInputs:0,outputChannelCount:[1]});
   s.playback.port.onmessage=({data})=>{if(active!==s||data.epoch!==s.epoch)return;if(data.type==='meter'){s.speaking=data.playing;monitor.playback(data);}if(data.type==='drained'){s.speaking=false;monitor.drained();if(s.outputEnded&&data.ended){s.outputPending=false;s.lastSpeech=Date.now();s.resumeAfter=Date.now()+300;syncMic(s);clearTimeout(s.resumeTimer);s.resumeTimer=setTimeout(()=>{if(active===s){syncMic(s);if(!s.busy&&!s.turn)paint(readyText());}},320);}}if(data.type==='overflow')stop('Lecture audio instable. Réouvre le micro.',true);};s.playback.connect(s.ctx.destination);
   s.gate=new JarvisVoiceGate({tailMs:600,start:()=>{s.captureDuringPlayback=Boolean(s.speaking||monitor.snapshot().pendingAudio||s.busy||s.turn);s.voicedMs=0;s.bargeConfirmed=false;s.chunks=[];s.bytes=0;s.strongMs=0;s.lastSpeech=Date.now();if(!s.captureDuringPlayback)monitor.speechStart();},audio:buffer=>{s.chunks.push(buffer.slice(0));s.bytes+=buffer.byteLength;if(s.bytes>1900000)stop('Ta phrase est trop longue. Réouvre le micro.',true);},end:()=>{if(active===s){if(s.voicedMs<100||(s.captureDuringPlayback&&!s.bargeConfirmed)){s.chunks=[];s.bytes=0;return;}const parts=s.chunks;s.chunks=[];s.bytes=0;void utterance(s,parts);}},activity:()=>s.lastSpeech=Date.now()});
   s.processor.port.onmessage=({data})=>{if(active!==s)return;syncMic(s);if(s.micHeld){monitor.input(0,0,false);return;}const pcm=new Int16Array(data);let sum=0,square=0,peak=0;for(const x of pcm){const value=x/32768;sum+=value;square+=value*value;peak=Math.max(peak,Math.abs(value));}const length=Math.max(1,pcm.length),rms=Math.sqrt(Math.max(0,square/length-(sum/length)**2));s.gate.push(data);if(active!==s)return;
    if(s.gate.active&&(s.speaking||s.busy||s.turn)){const threshold=s.speaking?Math.max(.015,monitor.snapshot().outputRms*.2):.012;s.strongMs=rms>threshold?s.strongMs+length/16:0;if(s.strongMs>=160){s.bargeConfirmed=true;cancel(s);monitor.interrupt('local');document.dispatchEvent(new CustomEvent('jarvis:voice-interrupt',{detail:{source:'microphone'}}));s.strongMs=0;}}
    if(s.gate.active&&s.gate.quiet<120&&rms>Math.max(.003,s.gate.floor*2))s.voicedMs+=length/16;
    monitor.input(rms,peak,s.gate.active&&s.gate.quiet<120&&(!s.captureDuringPlayback||s.bargeConfirmed));
   };
   s.mic.connect(s.processor);s.processor.connect(s.ctx.destination);s.started=s.lastSpeech=Date.now();monitor.ready('Voix Gemini prête · aiguillage Gemini / Codex');syncMic(s);paint(readyText());s.ticker=setInterval(()=>{if(active!==s)return;const seconds=Math.max(0,Math.min(session.maxSeconds||3600,3600)-Math.floor((Date.now()-s.started)/1000));clock.textContent=Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0');if(!seconds)stop('Session terminée. Tu peux rouvrir le micro.');else if(!s.busy&&!s.turn&&!s.outputPending&&!s.speaking&&Date.now()-s.lastSpeech>120000)stop('Micro coupé après deux minutes sans parole.');},1000);
  }catch(error){if(active===s)stop(error.name==='NotAllowedError'?'Autorise le micro dans Safari.':error.message,true);}
 });
 for(const event of ['jarvis:spacechange','jarvis:newconversation','jarvis:writtenask'])document.addEventListener(event,()=>{if(active)stop('Micro coupé.');});
 window.addEventListener('pagehide',()=>stop());document.addEventListener('visibilitychange',()=>{if(document.hidden&&active)stop('Micro coupé lorsque tu quittes la page.');});
 if(!window.isSecureContext){const url=new URL(location.href);url.protocol='https:';url.port='8788';$('#liveHttps').href=url.href;$('#liveHttps').hidden=false;paint('Ouvre Jarvis en HTTPS pour utiliser le micro.');}
})();
