// Explicit real Google test. Synthetic microphone stays in RAM; actual worklet
// source executes on a test clock because this VM's native worklet loader stalls.
if(process.env.JARVIS_REAL_GEMINI_TEST!=='1'){console.log('Real Google test skipped. Set JARVIS_REAL_GEMINI_TEST=1 explicitly (billable API calls).');process.exit(0);}
const fs=require('node:fs'),assert=require('node:assert/strict');
const{chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
(async()=>{
 for(const file of ['/home/user/gateway/.env','/home/user/workspace/_secrets/.env']){try{for(const line of fs.readFileSync(file,'utf8').split('\n')){const m=line.match(/^(GEMINI_API_KEY|GOOGLE_API_KEY)=(.*)$/);if(m)process.env[m[1]]=m[2].replace(/^['"]|['"]$/g,'');}}catch{}}
 const{speechSession,streamSpeech}=await import('./speech.mjs');const session=speechSession('user'),chunks=[];
 await streamSpeech(session.sessionId,'user','Compte lentement de un à dix.',chunk=>chunks.push(chunk));const raw=Buffer.concat(chunks).toString('base64');
 const b=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium-1193/chrome-linux/chrome',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
 try{
  const p=await b.newPage({viewport:{width:390,height:844},permissions:['microphone'],ignoreHTTPSErrors:true,reducedMotion:'reduce'});
  await p.addInitScript(({raw})=>{
   const bytes=Uint8Array.from(atob(raw),c=>c.charCodeAt(0)),view=new DataView(bytes.buffer),samples=new Float32Array(bytes.length/2);for(let i=0;i<samples.length;i++)samples[i]=view.getInt16(i*2,true)/32768;
   window.realTest={samples,position:0,feed:false,events:[],serverFrames:0,serverInterrupt:false,transcribed:false,renderedPeak:0};
   document.addEventListener('jarvis:live-diagnostics',e=>{const d=e.detail;window.realTest.events.push({at:performance.now(),...d});if(window.realTest.events.length>1500)window.realTest.events.shift();});
   const NativeSocket=window.WebSocket;window.WebSocket=class extends NativeSocket{constructor(...args){super(...args);this.addEventListener('message',async e=>{const s=typeof e.data==='string'?e.data:await e.data.text();const d=JSON.parse(s);window.realTest.serverFrames++;if(d.serverContent?.interrupted)window.realTest.serverInterrupt=true;if(d.serverContent?.inputTranscription?.text)window.realTest.transcribed=true;});}};
   const NativeContext=window.AudioContext;window.AudioContext=class extends NativeContext{constructor(...args){super(...args);this.testProcessors={};this.audioWorklet.addModule=async url=>{const source=await(await fetch(url)).text();new Function('sampleRate','AudioWorkletProcessor','registerProcessor',source)(this.sampleRate,class{constructor(){this.port={};}},(name,P)=>this.testProcessors[name]=P);};}};
   window.AudioWorkletNode=function(context,name){const node=context.createGain();node.gain.value=0;const processor=new context.testProcessors[name]();node.port={onmessage:null,postMessage:data=>processor.port.onmessage?.({data})};processor.port.postMessage=data=>node.port.onmessage?.({data});let previousTick=performance.now();const timer=setInterval(()=>{const now=performance.now(),blocks=Math.min(25,Math.max(1,Math.floor((now-previousTick)/20)));previousTick+=blocks*20;for(let block=0;block<blocks;block++){
    const input=new Float32Array(context.sampleRate/50),output=new Float32Array(input.length),test=window.realTest;
    if(name==='jarvis-pcm'&&test.feed){for(let i=0;i<input.length;i++){const pos=Math.floor((test.position+i)*24000/context.sampleRate);input[i]=test.samples[pos]||0;}test.position+=input.length;if(test.position*24000/context.sampleRate>=test.samples.length)test.feed=false;}
    processor.process([[input]],[[output]]);if(name==='jarvis-playback')for(const v of output)test.renderedPeak=Math.max(test.renderedPeak,Math.abs(v));}
   },20);const disconnect=node.disconnect.bind(node);node.disconnect=()=>{clearInterval(timer);disconnect();};return node;};
  },{raw});
  // Keep synthetic test utterances out of personal Qdrant memory.
  await p.route('**/api/jarvis/conversations/record?*',r=>r.fulfill({json:{saved:true}}));
  await p.goto((process.env.JARVIS_TEST_BASE||'http://127.0.0.1:8787')+'/jarvis/');await p.locator('#liveButton').click();
  await p.waitForFunction(()=>window.jarvisLiveDiagnostics?.transport==='ready',{},{timeout:20000}).catch(async error=>{console.log('Connection status',await p.evaluate(()=>({diag:window.jarvisLiveDiagnostics,status:document.querySelector('#liveStatus').textContent,frames:window.realTest.serverFrames})));throw error;});
  console.log('real Google connected');await p.evaluate(()=>{window.realTest.position=0;window.realTest.feed=true;});
  await p.waitForFunction(()=>window.jarvisLiveDiagnostics.inputRms>.02,{},{timeout:10000});
  await p.waitForFunction(()=>window.jarvisLiveDiagnostics.outputRms>.01&&window.jarvisLiveDiagnostics.state==='speaking',{},{timeout:25000});
  await p.waitForTimeout(1200);await p.waitForFunction(()=>window.jarvisLiveDiagnostics.outputRms>.01,{},{timeout:4000});
  console.log('real output still rendered beyond 1s');const before=await p.evaluate(()=>({diag:window.jarvisLiveDiagnostics,frames:window.realTest.serverFrames,transcribed:window.realTest.transcribed,renderedPeak:window.realTest.renderedPeak,model:document.body.dataset.voice}));
  assert(before.frames>0&&before.renderedPeak>0);assert.equal(before.diag.outputSource,'AudioWorklet · échantillons lus');
  await p.evaluate(()=>{window.realTest.position=0;window.realTest.feed=true;});
  await p.waitForFunction(()=>window.jarvisLiveDiagnostics.interruptions>0&&window.jarvisLiveDiagnostics.lastInterrupt==='server',{},{timeout:10000});
  console.log('server-confirmed interruption measured');await p.waitForFunction(()=>window.realTest.serverInterrupt,{},{timeout:10000});
  const result=await p.evaluate(()=>{const events=window.realTest.events;return {at:new Date().toISOString(),method:'Real Gemini WebSocket and generated audio; synthetic mic in RAM; actual worklet source on test clock, no physical speaker measurement.',serverFrames:window.realTest.serverFrames,serverInterrupt:window.realTest.serverInterrupt,inputTranscribed:window.realTest.transcribed,renderedPeak:window.realTest.renderedPeak,maxMic:Math.max(...events.map(e=>e.inputRms)),maxOutput:Math.max(...events.map(e=>e.outputRms)),states:[...new Set(events.map(e=>e.state))],lastEvent:window.jarvisLiveDiagnostics.lastEvent,outputSource:window.jarvisLiveDiagnostics.outputSource};});
  await p.locator('#liveButton').click();await p.waitForFunction(()=>window.jarvisLiveDiagnostics.state==='idle');
  assert.equal((await p.evaluate(()=>window.jarvisLiveDiagnostics)).outputRms,0);
  assert(result.serverInterrupt&&result.inputTranscribed&&result.maxMic>0&&result.maxOutput>0);for(const state of ['idle','connecting','listening','thinking','speaking'])assert(result.states.includes(state));
  fs.writeFileSync('/home/user/workspace/jarvis/data/real-live-reactivity.json',JSON.stringify(result,null,2),{mode:0o600});console.log(JSON.stringify(result));
 }finally{await b.close();}
})().catch(e=>{console.error(e.name+': '+e.message);process.exit(1)});
