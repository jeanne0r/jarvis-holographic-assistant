// Optional, local-only head tracking. Camera permission is requested on a click.
(() => {
 const button=document.querySelector('#cameraToggle'),status=document.querySelector('#cameraStatus');if(!button)return;
 let current=null,sequence=0,workerUnavailable=false;
 const state={enabled:false,tracking:false,x:0,y:0,depth:0,inferenceMs:0};
 Object.defineProperty(window,'jarvisCamera',{get:()=>Object.freeze({...state})});
 const emit=()=>document.dispatchEvent(new CustomEvent('jarvis:camera-tracking',{detail:{...state}}));
 function label(text){status.textContent=text;}
 function stop(message='Caméra éteinte'){
  ++sequence;const s=current;current=null;
  if(s){clearTimeout(s.timer);clearTimeout(s.watchdog);s.worker?.terminate();s.detector?.close();s.stream?.getTracks().forEach(t=>t.stop());s.video.pause();s.video.srcObject=null;s.video.remove();}
  Object.assign(state,{enabled:false,tracking:false,x:0,y:0,depth:0,inferenceMs:0});emit();
  button.setAttribute('aria-pressed','false');button.textContent='Activer le regard';label(message);
 }
 async function tick(s){
  if(current!==s||document.hidden)return;
  if(s.busy||s.video.readyState<2||s.lastVideoTime===s.video.currentTime){s.timer=setTimeout(()=>tick(s),100);return;}
  s.busy=true;s.lastVideoTime=s.video.currentTime;
  try{
   s.ctx.drawImage(s.video,0,0,256,192);
   if(s.detector){
    const at=performance.now(),faces=s.detector.detectForVideo(s.canvas,at).detections;
    const box=faces.map(f=>f.boundingBox).filter(Boolean).sort((a,b)=>b.width*b.height-a.width*a.height)[0];
    s.result({type:'face',box:box?{x:(box.originX+box.width/2)/256,y:(box.originY+box.height/2)/192,width:box.width/256}:null,ms:performance.now()-at});return;
   }
   const bitmap=await createImageBitmap(s.canvas);
   if(current!==s){bitmap.close();return;}
   s.worker.postMessage({type:'frame',bitmap,timestamp:performance.now()},[bitmap]);
   s.watchdog=setTimeout(()=>{if(current===s)stop('Suivi indisponible · réessayer');},10000);
  }catch{if(current===s)stop('Suivi indisponible sur ce navigateur');}
 }
 async function fallback(s){
  if(current!==s||s.fallback)return;
  workerUnavailable=true;s.fallback=true;s.busy=false;clearTimeout(s.watchdog);s.worker?.terminate();s.worker=null;
  s.watchdog=setTimeout(()=>{if(current===s)stop('Chargement interrompu · réessayer');},30000);
  label('Chargement du suivi compatible Safari…');
  try{
   // Some WebKit versions expose OffscreenCanvas but no worker WebGL context.
   // Use a DOM canvas there, with a lower inference cadence to protect audio/UI.
   const {FilesetResolver,FaceDetector}=await import('./vendor/vision/vision.module.js');
   const files=await FilesetResolver.forVisionTasks(new URL('./vendor/vision/wasm',document.baseURI).href);
   if(current!==s)return;
   const detector=await FaceDetector.createFromOptions(files,{canvas:document.createElement('canvas'),baseOptions:{modelAssetPath:new URL('./vendor/vision/face_detector.tflite',document.baseURI).href,delegate:'CPU'},runningMode:'VIDEO',minDetectionConfidence:.65});
   if(current!==s){detector.close();return;}
   s.detector=detector;s.result({type:'ready'});
  }catch{if(current===s)stop('Suivi indisponible sur ce navigateur');}
 }
 async function start(){
  const id=++sequence;state.lastError='';
  if(!isSecureContext||!navigator.mediaDevices?.getUserMedia){label('Ouvre Jarvis en HTTPS pour la caméra');return;}
  const video=document.createElement('video');video.muted=true;video.playsInline=true;video.autoplay=true;video.className='camera-input';video.setAttribute('aria-hidden','true');document.body.append(video);
  const canvas=document.createElement('canvas');canvas.width=256;canvas.height=192;
  const s={video,canvas,ctx:canvas.getContext('2d'),busy:false,lastVideoTime:-1};current=s;
  button.setAttribute('aria-pressed','true');button.textContent='Couper la caméra';label('Autorise la caméra · analyse locale');
  try{
   let stream;
   try{stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user',width:{ideal:320},height:{ideal:240},frameRate:{ideal:15,max:15}}});}
   catch(error){
    // iOS cameras may reject the low capture-rate constraint. Inference still
    // samples at 4–8 fps even when the camera needs its native capture format.
    if(error.name!=='OverconstrainedError')throw error;
    stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user'}});
   }
   if(sequence!==id||current!==s){stream.getTracks().forEach(t=>t.stop());return;}
   s.stream=stream;video.srcObject=stream;await video.play();if(current!==s)return;
   stream.getVideoTracks().forEach(t=>t.addEventListener('ended',()=>{if(current===s)stop('Caméra déconnectée');}));
   label('Chargement du suivi local…');
   s.watchdog=setTimeout(()=>{if(current===s)stop('Chargement interrompu · réessayer');},30000);
   s.result=data=>{
    if(current!==s)return;clearTimeout(s.watchdog);
    if(data.type==='error'){fallback(s);return;}
    if(data.type==='ready'){state.enabled=true;emit();label('Cherche ton visage…');tick(s);return;}
    if(data.type!=='face')return;
    s.busy=false;state.inferenceMs=data.ms;
    if(data.box){
     s.lastSeen=performance.now();s.neutralWidth??=data.box.width;
     Object.assign(state,{tracking:true,x:Math.max(-1,Math.min(1,(.5-data.box.x)*2.4)),y:Math.max(-1,Math.min(1,(data.box.y-.5)*2.4)),depth:Math.max(-.65,Math.min(.65,(data.box.width/s.neutralWidth-1)*.6))});
     label('Visage suivi · images sur cet appareil');
    }else if(!s.lastSeen||performance.now()-s.lastSeen>700){Object.assign(state,{tracking:false,x:0,y:0,depth:0});label('Cherche ton visage…');}
    emit();s.timer=setTimeout(()=>tick(s),Math.max(s.fallback?250:100,Math.min(600,data.ms*3)));
   };
   if(!workerUnavailable&&window.Worker&&window.createImageBitmap&&window.OffscreenCanvas){
    s.worker=new Worker(new URL('./camera-worker.js?v=20261112-gaze1',document.baseURI));
    s.worker.onerror=()=>fallback(s);s.worker.onmessage=({data})=>s.result(data);s.worker.postMessage({type:'init'});
   }else fallback(s);
  }catch(error){if(current===s){state.lastError=error.name+': '+error.message;stop(error.name==='NotAllowedError'?'Caméra non autorisée':error.name==='NotFoundError'?'Aucune caméra disponible':'Caméra indisponible · réessayer');}}
 }
 button.addEventListener('click',()=>current?stop():start());
 document.addEventListener('visibilitychange',()=>{if(document.hidden&&current)stop();});
 new MutationObserver(()=>{if(current&&(document.body.dataset.screen!=='chat'||document.body.classList.contains('hud-sheet-open')))stop();}).observe(document.body,{attributes:true,attributeFilter:['data-screen','class']});
 window.addEventListener('pagehide',()=>stop());
})();
