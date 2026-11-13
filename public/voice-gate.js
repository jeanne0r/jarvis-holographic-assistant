// Suppress quiet microphone packets locally; keep a short onset buffer and a
// tail so Google's speech detector and barge-in remain available. No recording.
(() => {
 class JarvisVoiceGate {
  constructor({audio,end,activity=()=>{},start=()=>{},tailMs=900}) {
   this.tailMs=tailMs;this.audio=audio;this.end=end;this.activity=activity;this.start=start;
   this.history=[];this.active=false;this.attack=0;this.quiet=0;this.floor=.0008;
  }
  reset() {this.history=[];this.active=false;this.attack=0;this.quiet=0;}
  push(buffer) {
   const samples=new Int16Array(buffer);if(!samples.length)return;
   let sum=0,squares=0;
   for(const v of samples){const x=v/32768;sum+=x;squares+=x*x;}
   const rms=Math.sqrt(Math.max(0,squares/samples.length-(sum/samples.length)**2));
   const ms=samples.length/16,threshold=Math.max(.0035,this.floor*3.5);
   if(!this.active){
    this.history.push(buffer.slice(0));while(this.history.length>12)this.history.shift();
    if(rms>threshold)this.attack+=ms;else{this.attack=0;if(rms<Math.max(.006,this.floor*2))this.floor=this.floor*.97+rms*.03;}
    if(this.attack<40)return;
    this.active=true;this.quiet=0;this.start();this.activity();
    for(const part of this.history)this.audio(part);this.history=[];return;
   }
   this.audio(buffer);
   if(rms>threshold*.65){this.quiet=0;this.activity();}
   else this.quiet+=ms;
   if(this.quiet>=this.tailMs){this.active=false;this.attack=0;this.history=[];this.end();}
  }
 }
 globalThis.JarvisVoiceGate=JarvisVoiceGate;
})();
