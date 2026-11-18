// Local camera frames come from a Google sample portrait, never a physical camera.
// Fetch once to data/camera-test-portrait.jpg from
// https://storage.googleapis.com/mediapipe-assets/portrait.jpg before this check.
const {chromium,webkit}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.JARVIS_TEST_BASE||'http://127.0.0.1:8790';
(async()=>{
 const engine=process.env.JARVIS_TEST_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch(engine===webkit?{headless:true}:{headless:true,executablePath:'/home/user/.cache/ms-playwright/chromium-1193/chrome-linux/chrome',args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},reducedMotion:engine===webkit?'reduce':'no-preference'}),errors=[],external=[];
  page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message)});if(process.env.JARVIS_CAMERA_DEBUG)page.on('console',m=>console.log(m.type(),m.text().slice(0,300)));page.on('request',r=>{if(!r.url().startsWith(base)&&!r.url().startsWith('data:'))external.push(r.url())});
  const portrait=fs.readFileSync('data/camera-test-portrait.jpg').toString('base64');
  await page.addInitScript(({portrait,isWebkit})=>{
   window.cameraTest={calls:0,stops:0,offset:0,blank:false,deny:false,zoom:1};
   if(isWebkit){
    Object.defineProperty(HTMLMediaElement.prototype,'srcObject',{set(s){this.testStream=s},get(){return this.testStream},configurable:true});
    Object.defineProperty(HTMLMediaElement.prototype,'readyState',{get(){return 2},configurable:true});
    Object.defineProperty(HTMLMediaElement.prototype,'currentTime',{get(){return performance.now()/1000},configurable:true});
    HTMLMediaElement.prototype.play=()=>Promise.resolve();HTMLMediaElement.prototype.pause=()=>{};
    const original=CanvasRenderingContext2D.prototype.drawImage;CanvasRenderingContext2D.prototype.drawImage=function(source,...args){return original.call(this,source instanceof HTMLVideoElement?window.cameraTest.frame:source,...args)};
   }
   const getUserMedia=async options=>{
    window.cameraTest.calls++;
    if(window.cameraTest.deny)throw new DOMException('Denied','NotAllowedError');
    if(window.cameraTest.calls===1)throw new DOMException('Unsupported capture format','OverconstrainedError');
    if(options.audio!==false)throw Error('Camera must never request microphone');
    const image=new Image();image.src='data:image/jpeg;base64,'+portrait;await image.decode();
    const c=document.createElement('canvas');c.width=256;c.height=192;const ctx=c.getContext('2d');
    const draw=()=>{ctx.fillStyle='#111';ctx.fillRect(0,0,256,192);if(!window.cameraTest.blank)ctx.drawImage(image,window.cameraTest.offset+128*(1-window.cameraTest.zoom),44*(1-window.cameraTest.zoom),256*window.cameraTest.zoom,192*window.cameraTest.zoom)};draw();
    const timer=setInterval(draw,80);
    let stream;
    if(isWebkit){
     // Linux WebKit cannot play canvas.captureStream in this headless VM.
     // Exercise the real controller and WASM against injected video frames.
     const track={stop(){},addEventListener(){}};stream={getTracks:()=>[track],getVideoTracks:()=>[track]};window.cameraTest.frame=c;
    }else stream=c.captureStream(12);
    stream.getTracks().forEach(t=>{const stop=t.stop.bind(t);t.stop=()=>{window.cameraTest.stops++;clearInterval(timer);stop()}});
    return stream;
   };
   Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia},configurable:true});
  },{portrait,isWebkit:engine===webkit});
  await page.goto(base+'/jarvis/',{waitUntil:'domcontentloaded'});await page.waitForTimeout(250);
  assert.equal(await page.evaluate(()=>window.cameraTest.calls),0,'no camera permission on page load');
  await page.locator('#cameraToggle').click();if(process.env.JARVIS_CAMERA_DEBUG)console.log('Started',await page.evaluate(()=>({state:window.jarvisCamera,label:document.querySelector('#cameraStatus').textContent,calls:window.cameraTest.calls,getMedia:String(navigator.mediaDevices.getUserMedia).slice(0,170)})));
  await page.waitForFunction(()=>window.jarvisCamera?.tracking,{},{timeout:60000}).catch(async e=>{console.log('Camera diagnostic',await page.evaluate(()=>({state:window.jarvisCamera,label:document.querySelector('#cameraStatus').textContent,video:!!document.querySelector('video'),calls:window.cameraTest.calls,error:window.jarvisCamera.lastError})));throw e});
  assert.equal(await page.evaluate(()=>window.cameraTest.calls),2,'unsupported camera constraints retry with native format');
  console.log('face detected');assert(await page.evaluate(()=>window.jarvisCamera.enabled));
  const x=await page.evaluate(()=>window.jarvisCamera.x);
  await page.evaluate(()=>window.cameraTest.offset=45);
  await page.waitForFunction(x=>window.jarvisCamera.x<x-.2,x,{timeout:20000});console.log('face moved');
  if(engine===webkit)await page.emulateMedia({reducedMotion:'no-preference'});
  await page.waitForFunction(()=>window.jarvisHologram?.cameraTracking&&window.jarvisHologram.gazeX<-.15,{},{timeout:20000});
  await page.evaluate(()=>{window.cameraTest.offset=0;window.cameraTest.zoom=1.35;});
  await page.waitForFunction(()=>window.jarvisHologram.coreScale>1.10,{},{timeout:20000});
  await page.evaluate(()=>window.cameraTest.zoom=.70);
  await page.waitForFunction(()=>window.jarvisHologram.coreScale<.85,{},{timeout:20000});
  await page.evaluate(()=>window.cameraTest.zoom=1);
  await page.waitForFunction(()=>Math.abs(window.jarvisHologram.coreScale-1)<.06,{},{timeout:20000});
  console.log('proximity enlargement, shrinkage and return to baseline');
  if(engine===webkit)await page.emulateMedia({reducedMotion:'reduce'});
  await page.evaluate(()=>window.cameraTest.blank=true);
  await page.waitForFunction(()=>!window.jarvisCamera.tracking,{},{timeout:20000});
  console.log('face lost');assert.equal((await page.evaluate(()=>window.jarvisCamera)).x,0,'missing face recenters');
  await page.locator('#cameraToggle').click();assert.equal(await page.evaluate(()=>window.jarvisCamera.enabled),false);assert.equal(await page.evaluate(()=>window.cameraTest.stops),1);
  await page.evaluate(()=>{window.cameraTest.blank=false;});await page.locator('#cameraToggle').click();console.log('Restart camera',await page.evaluate(()=>({label:document.querySelector('#cameraStatus').textContent,state:window.jarvisCamera,calls:window.cameraTest.calls,video:document.querySelector('video')?.readyState})));await page.waitForFunction(()=>window.jarvisCamera.tracking,{},{timeout:60000});
  await page.locator('#cockpitWrite').click();await page.waitForFunction(()=>!window.jarvisCamera.enabled);
  assert.equal(await page.evaluate(()=>window.cameraTest.stops),2,'leaving hologram releases camera');
  await page.locator('#cockpitSheetClose').click();await page.evaluate(()=>window.cameraTest.deny=true);await page.locator('#cameraToggle').click();await page.waitForFunction(()=>document.querySelector('#cameraStatus').textContent==='Caméra non autorisée');
  assert.equal(await page.locator('#cameraToggle').getAttribute('aria-pressed'),'false');
  assert.deepEqual(errors,[]);assert.deepEqual(external,[],'no image/provider/CDN upload or external request');
  console.log('PASS '+(engine===webkit?'WebKit':'Chromium')+': actual local WASM face detection, camera video lifecycle, face-driven 3D perspective, lost-face recentering, cleanup and permission denial; no external network requests.');
 }finally{await browser.close()}
})();
