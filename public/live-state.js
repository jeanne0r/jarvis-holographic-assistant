// Measured voice lifecycle. No timers fabricate speech or Gemini thinking.
(() => {
 class JarvisLiveState {
  constructor(emit=()=>{}) {this.emit=emit;this.pendingLocal=false;this.data={state:'idle',muted:false,transport:'closed',inputRms:0,inputPeak:0,outputRms:0,outputPeak:0,bufferedMs:0,inputSpeech:false,playing:false,waiting:false,pendingAudio:false,waitSource:'',lastEvent:'micro fermé',interruptions:0,serverInterruptions:0,lastInterrupt:'',outputSource:'AudioWorklet · échantillons lus'};this.lastPublish=-Infinity;}
  snapshot(){return {...this.data};}
  publish(force=false){
   const d=this.data,old=d.state;
   d.state=d.transport==='error'?'error':d.transport==='closed'?'idle':d.transport!=='ready'?'connecting':d.inputSpeech?'listening':d.playing?'speaking':d.waiting||d.pendingAudio?'thinking':d.muted?'muted':'listening';
   const time=performance.now();if(force||old!==d.state||time-this.lastPublish>=40){this.lastPublish=time;this.emit(this.snapshot());}
  }
  connect(){Object.assign(this.data,{transport:'connecting',lastEvent:'ouverture de la voix'});this.publish(true);}
  ready(source='Gemini · setupComplete'){Object.assign(this.data,{transport:'ready',lastEvent:source});this.publish(true);}
  input(rms,peak,speech){Object.assign(this.data,{inputRms:rms,inputPeak:peak,inputSpeech:speech});this.publish();}
  mute(muted){Object.assign(this.data,{muted,inputRms:0,inputPeak:0,inputSpeech:false,lastEvent:muted?'micro en pause':'micro réactivé'});this.publish(true);}
  speechStart(){Object.assign(this.data,{inputSpeech:true,waiting:false,waitSource:'',lastEvent:'parole · VAD local'});this.publish(true);}
  wait(source='fin de parole locale'){Object.assign(this.data,{inputSpeech:false,waiting:true,waitSource:source,lastEvent:source==='outil Gemini'?'Gemini · toolCall':source});this.publish(true);}
  receivedAudio(){Object.assign(this.data,{pendingAudio:true,lastEvent:'Gemini · audio reçu'});this.publish();}
  playback({rms=0,peak=0,playing=false,bufferedMs=0}){Object.assign(this.data,{outputRms:rms,outputPeak:peak,playing,bufferedMs,pendingAudio:bufferedMs>0||playing});if(playing){this.data.waiting=false;this.data.waitSource='';this.data.lastEvent='AudioWorklet · lecture';}this.publish();}
  clear(){Object.assign(this.data,{outputRms:0,outputPeak:0,playing:false,bufferedMs:0,pendingAudio:false});this.publish(true);}
  interrupt(source){if(source==='local'){this.data.interruptions++;this.pendingLocal=true;}else{if(!this.pendingLocal)this.data.interruptions++;this.pendingLocal=false;this.data.serverInterruptions++;}Object.assign(this.data,{outputRms:0,outputPeak:0,playing:false,bufferedMs:0,pendingAudio:false,waiting:false,waitSource:'',lastEvent:source==='server'?'Gemini · interrupted':'interruption · VAD local',lastInterrupt:source});this.publish(true);}
  generationComplete(){this.data.lastEvent='Gemini · generationComplete';this.publish(true);}
  turnComplete(waitingForTool=false){this.data.lastEvent='Gemini · turnComplete';this.data.waiting=waitingForTool;if(waitingForTool)this.data.waitSource='outil Gemini';else this.data.waitSource='';this.publish(true);}
  drained(){Object.assign(this.data,{outputRms:0,outputPeak:0,playing:false,bufferedMs:0,pendingAudio:false,lastEvent:'AudioWorklet · file vidée'});this.publish(true);}
  stop(error=false){this.pendingLocal=false;Object.assign(this.data,{transport:error?'error':'closed',muted:false,inputRms:0,inputPeak:0,outputRms:0,outputPeak:0,inputSpeech:false,playing:false,pendingAudio:false,waiting:false,waitSource:'',bufferedMs:0,lastEvent:error?'connexion interrompue':'micro fermé'});this.publish(true);}
 }
 window.JarvisLiveState=JarvisLiveState;
})();
