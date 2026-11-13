const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=process.env.JARVIS_TEST_BASE||'http://127.0.0.1:8787';
function wav(seconds=8){const buffer=Buffer.alloc(44+16000*2*seconds);buffer.write('RIFF');buffer.writeUInt32LE(buffer.length-8,4);buffer.write('WAVEfmt ',8);buffer.writeUInt32LE(16,16);buffer.writeUInt16LE(1,20);buffer.writeUInt16LE(1,22);buffer.writeUInt32LE(16000,24);buffer.writeUInt32LE(32000,28);buffer.writeUInt16LE(2,32);buffer.writeUInt16LE(16,34);buffer.write('data',36);buffer.writeUInt32LE(buffer.length-44,40);for(let i=0;i<16000*seconds;i++)buffer.writeInt16LE(Math.round(1000*Math.sin(i*.1)),44+i*2);return buffer;}
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.JARVIS_TEST_CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
 try{
 const page=await browser.newPage({viewport:{width:390,height:844},permissions:['microphone']});const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(() => {
      window.voiceStats = {packets: 0, stops: 0, tracks: [], toolResponses: [], quiet:true, ends:0};
      // This VM's headless Chromium never resolves AudioWorklet.addModule, even
      // for an empty processor. Run the actual PCM source on a test clock here;
      // capture and the application's lifecycle stay real.
      const NativeContext = window.AudioContext;
      window.AudioContext = class extends NativeContext {
        constructor(...args) {
          super(...args);
          this.testProcessors = {};
          this.audioWorklet.addModule = async url => {
            const source = await (await fetch(url)).text();
            new Function('sampleRate', 'AudioWorkletProcessor', 'registerProcessor', source)(
              this.sampleRate, class {constructor() {this.port = {}; }},
              (name, Processor) => {this.testProcessors[name] = Processor;},
            );
          };
        }
      };
      window.AudioWorkletNode = function(context, name) {
        const node = context.createGain();
        node.gain.value = 0;
        const processor = new context.testProcessors[name]();
        node.port = {onmessage: null, postMessage: data => {
          if (name === 'jarvis-playback' && data.type === 'clear') window.voiceStats.stops++;
          processor.port.onmessage?.({data});
        }};
        processor.port.postMessage = data => node.port.onmessage?.({data});
        const timer = setInterval(() => processor.process([[window.voiceStats.quiet?new Float32Array(context.sampleRate / 50):Float32Array.from({length:context.sampleRate/50},(_,i)=>(window.voiceStats.amplitude??.1)*Math.sin(i*.15))]], [[new Float32Array(context.sampleRate / 50)]]), 20);
        const disconnect = node.disconnect.bind(node);
        node.disconnect = () => {clearInterval(timer); disconnect();};
        return node;
      };
      const get = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = async options => {
        const stream = await get(options);
        window.voiceStats.tracks.push(...stream.getTracks());
        return stream;
      };
    });

 await page.route('**/api/jarvis/voice/status*',route=>route.fulfill({json:{engine:'codex',configured:true}}));
 let sessions=0,transcriptions=0,delay=false;const asks=[],spoken=[],archives=[];
 await page.route('**/api/jarvis/voice/session?*',route=>route.fulfill({json:{sessionId:'00000000-0000-4000-8000-'+String(++sessions).padStart(12,'0'),engine:'codex',maxSeconds:3600}}));
 await page.route('**/api/jarvis/voice/transcribe?*',route=>{const body=route.request().postDataBuffer();assert.equal(body.toString('ascii',0,4),'RIFF');assert(body.length>6400&&body.length<1920045);transcriptions++;return route.fulfill({json:{text:'Question vocale '+transcriptions}});});
 await page.route('**/api/jarvis/ask?*',async route=>{const body=route.request().postDataJSON();asks.push(body);if(delay)await new Promise(r=>setTimeout(r,3000));await route.fulfill({json:{answer:body.question==='Nouveau fil'?'Un lien [Site](https://example.org/) et <img src=x onerror=window.unsafeAnswer=true>':'Réponse commune à '+body.question,...(body.question==='Question vocale 1'?{speech:'Texte à lire produit par Codex.'}:{}),sources:[],action:null}}).catch(()=>{});});
 await page.route('**/api/jarvis/voice/speak?*',route=>{spoken.push(route.request().postDataJSON());return route.fulfill({contentType:'audio/pcm;rate=24000',body:wav().subarray(44)});});
 await page.route('**/api/jarvis/conversations/record?*',route=>{archives.push(route.request().postDataJSON());return route.fulfill({json:{saved:true}});});
 // Audio lifecycle is tested independently of GPU rendering.
 await page.route('**/hologram.js?*',route=>route.fulfill({contentType:'text/javascript',body:''}));
 await page.goto(base+'/jarvis/');await page.waitForFunction(()=>!!window.jarvisLiveDiagnostics);await page.evaluate(()=>window.jarvisAsk('Je m’appelle Member 1.'));
 await page.locator('#liveButton').click();await page.waitForFunction(()=>document.querySelector('#liveStatus').textContent.startsWith('Je t’écoute'));await page.waitForTimeout(1200);assert.equal(transcriptions,0,'silence stays local');
 const utterance=async()=>{await page.evaluate(()=>window.voiceStats.quiet=false);await page.waitForTimeout(600);await page.evaluate(()=>window.voiceStats.quiet=true);};
 await utterance();await page.waitForFunction(()=>document.body.dataset.voice==='speaking');assert.equal(asks[1].channel,'voice');assert(asks[1].history.some(m=>m.text==='Je m’appelle Member 1.'));assert.equal(spoken[0].text,'Texte à lire produit par Codex.');
 const playingStops=await page.evaluate(()=>window.voiceStats.stops);await page.locator('#liveButton').click();await page.waitForTimeout(250);
 assert.equal(await page.evaluate(()=>window.voiceStats.stops),playingStops,'Muting during playback must not clear the output');assert.equal(await page.evaluate(()=>window.jarvisLiveDiagnostics.state),'speaking');assert(await page.evaluate(()=>window.jarvisLiveDiagnostics.outputRms>0));assert(await page.evaluate(()=>!window.voiceStats.tracks.at(-1).enabled));
 await page.locator('#liveButton').click();assert(await page.evaluate(()=>window.voiceStats.tracks.at(-1).enabled));
 const beforeEcho=await page.evaluate(()=>window.voiceStats.stops);await page.evaluate(()=>{window.voiceStats.amplitude=.01;window.voiceStats.quiet=false;});await page.waitForTimeout(350);await page.evaluate(()=>window.voiceStats.quiet=true);await page.waitForTimeout(1100);assert.equal(await page.evaluate(()=>window.voiceStats.stops),beforeEcho,'Low speaker leakage must not cut playback');assert.equal(transcriptions,1,'Weak echo must not trigger a new transcribed question');await page.evaluate(()=>window.voiceStats.amplitude=.1);
 const stops=await page.evaluate(()=>window.voiceStats.stops);await page.evaluate(()=>window.voiceStats.quiet=false);await page.waitForFunction(n=>window.voiceStats.stops>n,stops);assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'),'true');await page.evaluate(()=>window.voiceStats.quiet=true);
 await page.waitForFunction(()=>document.querySelector('#messages').textContent.includes('Réponse commune à Question vocale 2'));assert(asks[2].history.some(m=>m.text==='Question vocale 1'));assert(asks[2].history.some(m=>m.text==='Réponse commune à Question vocale 1'));
 await page.evaluate(()=>window.jarvisAsk('Question écrite après la voix'));await page.waitForFunction(()=>window.voiceStats.tracks.every(t=>t.readyState==='ended'));assert(asks.at(-1).history.some(m=>m.text==='Question vocale 2'));
 await page.locator('#liveButton').click();await page.waitForFunction(()=>document.querySelector('#liveStatus').textContent.startsWith('Je t’écoute'));delay=true;const before=asks.length;await utterance();await page.waitForFunction(()=>window.jarvisBusy());
 const pendingTranscripts=transcriptions,pendingStops=await page.evaluate(()=>window.voiceStats.stops);
 await page.evaluate(()=>{window.voiceStats.amplitude=.01;window.voiceStats.quiet=false});await page.waitForTimeout(350);await page.evaluate(()=>window.voiceStats.quiet=true);await page.waitForTimeout(850);
 assert.equal(transcriptions,pendingTranscripts,'Weak noise while thinking must not submit another question');assert.equal(await page.evaluate(()=>window.voiceStats.stops),pendingStops,'Weak noise while thinking must not cancel Codex');assert(await page.evaluate(()=>window.jarvisBusy()),'Original Codex turn remains active');await page.evaluate(()=>window.voiceStats.amplitude=.1);
 await page.locator('#cockpitWrite').click();await page.locator('#newConversation').click();await page.waitForTimeout(900);assert.equal(await page.locator('#messages').textContent(),'');assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'),'false');assert.equal(asks.length,before+1);assert.equal(spoken.length,2,'interrupted answer is not synthesized: '+JSON.stringify(spoken.map(s=>s.text)));
 delay=false;await page.evaluate(()=>window.jarvisAsk('Nouveau fil'));assert.deepEqual(asks.at(-1).history,[]);assert.equal(await page.locator('#messages a.answer-link').getAttribute('href'),'https://example.org/');assert.equal(await page.evaluate(()=>window.unsafeAnswer),undefined);assert(archives.some(a=>a.channel==='voice'&&a.user==='Question vocale 1'));assert.deepEqual(errors,[]);
 await page.locator('#cockpitSheetClose').click();
 // Dictation mode must ignore even strong microphone input until real output drain.
 await page.locator('#voiceModeToggle').click();assert.equal(await page.locator('#voiceModeToggle').textContent(),'Dictée sans coupure');
 await page.locator('#liveButton').click();await page.waitForFunction(()=>document.querySelector('#liveStatus').textContent.startsWith('À toi'));
 delay=true;const dictTranscriptions=transcriptions,dictAsks=asks.length;await utterance();await page.waitForFunction(()=>window.jarvisBusy());
 assert(await page.evaluate(()=>window.voiceStats.tracks.at(-1).enabled===false),'Dictation mutes the real microphone track during reasoning');
 await utterance();assert.equal(transcriptions,dictTranscriptions+1,'Strong noise must not retranscribe during reasoning');assert.equal(asks.length,dictAsks+1);
 await page.waitForFunction(()=>document.body.dataset.voice==='speaking');const dictStops=await page.evaluate(()=>window.voiceStats.stops);await utterance();await page.waitForTimeout(800);
 assert.equal(await page.evaluate(()=>window.voiceStats.stops),dictStops,'Dictation must never interrupt generated audio');assert.equal(transcriptions,dictTranscriptions+1);
 assert(await page.evaluate(()=>!window.voiceStats.tracks.at(-1).enabled),'Microphone stays muted during queued playback after generation completes');
 await page.waitForFunction(()=>window.voiceStats.tracks.at(-1).enabled&&document.querySelector('#liveStatus').textContent.startsWith('À toi'),{},{timeout:20000});
 delay=false;await utterance();await page.waitForFunction(()=>document.body.dataset.voice==='speaking');assert.equal(transcriptions,dictTranscriptions+2,'Microphone resumes for the next request');
 await page.locator('#voiceModeToggle').click();assert(await page.evaluate(()=>window.voiceStats.tracks.at(-1).enabled),'Natural mode can be restored during playback');
 await page.locator('#voiceModeToggle').click();await page.locator('#voiceStop').click();
 await page.reload();await page.waitForFunction(()=>!document.querySelector('#voiceModeToggle').hidden);assert.equal(await page.locator('#voiceModeToggle').textContent(),'Dictée sans coupure','Mode preference survives reload');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 // The heart mutes capture without cancelling a pending turn or generated PCM.
 await page.locator('#liveButton').click();await page.waitForFunction(()=>document.querySelector('#liveStatus').textContent.startsWith('À toi'));
 delay=true;await utterance();await page.waitForFunction(()=>window.jarvisBusy());
 const manualStops=await page.evaluate(()=>window.voiceStats.stops),manualTranscriptions=transcriptions;
 await page.locator('#liveButton').click();assert.equal(await page.locator('#liveButton').getAttribute('aria-label'),'Réactiver le micro de Jarvis');
 assert(await page.evaluate(()=>window.jarvisBusy()),'Mute must preserve the pending answer');assert.equal(await page.locator('#voiceStop').isVisible(),true);
 assert(await page.evaluate(()=>!window.voiceStats.tracks.at(-1).enabled&&window.voiceStats.tracks.at(-1).readyState==='live'),'Mute disables capture without closing the track');
 await page.waitForFunction(()=>document.body.dataset.voice==='speaking');
 await page.locator('#voiceModeToggle').click();assert(await page.evaluate(()=>!window.voiceStats.tracks.at(-1).enabled),'Switching to natural must preserve manual mute');
 await utterance();assert.equal(transcriptions,manualTranscriptions,'Muted input cannot transcribe or interrupt');assert.equal(await page.evaluate(()=>window.voiceStats.stops),manualStops,'Mute must not clear generated PCM');
 await page.waitForFunction(()=>window.jarvisLiveDiagnostics.state==='muted',{},{timeout:20000});
 assert(await page.evaluate(()=>!window.voiceStats.tracks.at(-1).enabled),'Drained output must not release manual mute');
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:'data/voice-muted-390.png'});
 await page.locator('#liveButton').click();assert(await page.evaluate(()=>window.voiceStats.tracks.at(-1).enabled),'Heart resumes capture in the same session');
 await page.locator('#liveButton').click();assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'),'false');
 const savedMessages=await page.locator('#messages').textContent();await page.locator('#voiceStop').click();
 assert(await page.locator('#voiceStop').isHidden());assert(await page.evaluate(()=>window.voiceStats.tracks.every(t=>t.readyState==='ended')),'Explicit stop closes the microphone');assert.equal(await page.locator('#messages').textContent(),savedMessages,'Ending a voice session retains the conversation');
 // Explicit stop still cancels processing and rejects a stale late response.
 await page.locator('#liveButton').click();await page.waitForFunction(()=>document.querySelector('#liveStatus').textContent.startsWith('Je t’écoute'));await utterance();await page.waitForFunction(()=>window.jarvisBusy());
 const beforeExplicitStop=spoken.length;await page.locator('#voiceStop').click();assert(!(await page.evaluate(()=>window.jarvisBusy())));await page.waitForTimeout(1000);assert.equal(spoken.length,beforeExplicitStop,'Stopped turn cannot start playback later');
 delay=false;await page.locator('#voiceModeToggle').click();
 await page.route('**/api/jarvis/ask?*',route=>route.fulfill({status:503,json:{error:'Test indisponibilité temporaire'}}));
 await page.locator('#liveButton').click();await page.waitForFunction(()=>document.querySelector('#liveStatus').textContent.startsWith('À toi'));await utterance();await page.waitForFunction(()=>document.querySelector('#liveStatus').textContent.startsWith('Réponse indisponible'));
 assert(await page.evaluate(()=>window.voiceStats.tracks.at(-1).enabled),'Dictation releases the microphone after an ask failure');await page.locator('#voiceStop').click();
 console.log('PASS: manual mute retains pending answers and PCM, track privacy, mode switches and drain preserve mute, same-session resume, explicit stop retains messages and cancels pending turns, local silence, speech-only transcription, common /ask engine and cross-channel history, exact Codex speech text, clickable safe links, weak echo rejection, barge-in without closing mic, written handoff, stale response cancellation, new-conversation reset voice archival, uninterrupted dictation through real output drain, automatic microphone resumption, live mode switching and persisted preference.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error.stack);process.exit(1)});
