const {chromium} = require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const assert = require('node:assert/strict');
const base = 'http://127.0.0.1:8787';
(async () => {
  for (const origin of [null, 'http://evil.example']) {
    const response = await fetch(base + '/api/jarvis/live/session', {
      method: 'POST', headers: origin ? {origin} : {}, body: '{}',
    });
    assert.equal(response.status, 403);
  }
  const lan = await fetch('http://192.0.2.16:8787/api/jarvis/live/session', {
    method: 'POST', headers: {origin: 'http://192.0.2.16:8787'}, body: '{}',
  });
  assert.equal(lan.status, 400);
  const browser = await chromium.launch({
    executablePath: '/home/user/.cache/ms-playwright/chromium-1193/chrome-linux/chrome',
    headless: true, ignoreDefaultArgs: ['--mute-audio'], args: ['--no-sandbox', '--disable-features=AudioServiceOutOfProcess', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
  });
  try {
    const page = await browser.newPage({viewport: {width: 390, height: 844}, permissions: ['microphone']});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      window.voiceStats = {packets: 0, stops: 0, tracks: [], toolResponses: [], histories:[], quiet:false, ends:0};
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
        const timer = setInterval(() => processor.process([[window.voiceStats.quiet?new Float32Array(context.sampleRate / 50):Float32Array.from({length:context.sampleRate/50},(_,i)=>.1*Math.sin(i*.15))]], [[new Float32Array(context.sampleRate / 50)]]), 20);
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
      class Socket {
        static OPEN = 1;
        constructor() { this.readyState = 0; this.bufferedAmount = 0; window.liveSocket = this;
          setTimeout(() => { this.readyState = 1; this.onopen?.(); }, 10); }
        send(raw) {
          const data = JSON.parse(raw);
          if(data.clientContent)window.voiceStats.histories.push(data.clientContent);
          if (data.setup) setTimeout(() => this.emit({setupComplete: {}}), 10);
          if (data.realtimeInput?.audio) window.voiceStats.packets++;
          if(data.realtimeInput?.audioStreamEnd)window.voiceStats.ends++;
          if (data.toolResponse) window.voiceStats.toolResponses.push(data.toolResponse);
        }
        emit(data) { this.onmessage?.({data: JSON.stringify(data)}); }
        close() { this.readyState = 3; }
      }
      window.WebSocket = Socket;
    });
    await page.route('**/api/jarvis/live/session?*', route => route.fulfill({
      status: 200, contentType: 'application/json', body: JSON.stringify({
        token: 'auth_tokens/mock', usageSessionId:'00000000-0000-4000-8000-000000000001', setup: {model: 'models/mock'}, maxSeconds: 600,
        websocketUrl: 'wss://generativelanguage.googleapis.com/test',
      }),
    }));
    await page.route('**/api/jarvis/live/tool', async route => {
      assert.equal(route.request().postDataJSON().name, 'consulter_home_assistant');
      await new Promise(resolve => setTimeout(resolve, 150));
      await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({connected: true, states: [{state: '25.1', unit: '°C'}]})});
    });
    const archives = [];
    await page.route('**/api/jarvis/conversations/record?*', route => {archives.push(route.request().postDataJSON());return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({saved:true})});});
    await page.route('**/api/jarvis/ask?*',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({answer:'Je retiens le sujet du jardin.',sources:[],action:null})}));
    await page.goto(base + '/jarvis/');
    await page.evaluate(()=>window.jarvisAsk('On parle du jardin.'));
    if(!await page.locator('#liveButton').isVisible())await page.locator('[data-view=chat]').click();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.equal(await page.locator('.reactor-controls #liveButton').count(),0);
    assert.equal(await page.locator('.reference-core-name').evaluate(e=>e.closest('button')?.id),'liveButton');
    await page.locator('#liveButton').click();
    await page.waitForFunction(() => document.querySelector('#liveStatus').textContent.startsWith('Je t’écoute'), {}, {timeout: 10000}).catch(async e => {
      const status = await page.locator('#liveStatus').textContent();
      const capture = await page.evaluate(() => ({tracks: window.voiceStats.tracks.length, socket: !!window.liveSocket, states: window.voiceStats.tracks.map(t=>t.readyState)}));
      throw Error(e.message + ' Status: ' + status + ' Capture: ' + JSON.stringify(capture));
    });
    await page.waitForFunction(() => window.voiceStats.packets > 3);
    assert((await page.evaluate(()=>window.voiceStats.histories)).some(h=>h.turnComplete===false&&h.turns.some(t=>t.parts[0].text==='On parle du jardin.')));
    await page.evaluate(()=>window.voiceStats.quiet=true);await page.waitForFunction(()=>window.voiceStats.ends>0);const packetsAtSilence=await page.evaluate(()=>window.voiceStats.packets);await page.waitForTimeout(250);assert.equal(await page.evaluate(()=>window.voiceStats.packets),packetsAtSilence);await page.evaluate(()=>window.voiceStats.quiet=false);await page.waitForFunction(n=>window.voiceStats.packets>n,packetsAtSilence);
    assert.equal((await page.locator('#liveButton').textContent()).trim(),'J.A.R.V.I.S.');
    assert.equal(await page.locator('#liveButton').getAttribute('aria-label'),'Couper le micro de Jarvis');
    await page.locator('#immersionButton').click();
    assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'),'true');
    assert.equal(await page.locator('#cinemaChannel').textContent(),'À votre écoute');
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'),'true');
    assert.equal(await page.locator('body').getAttribute('data-voice'), 'listening');
    await page.locator('.system-key[data-system=memory3d]').click();await page.locator('#memory3dCanvas').waitFor({state:'visible'});assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'),'true');assert(await page.locator('#hudMicShortcut').isVisible());await page.locator('#map3dBack').click();assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'),'true');
    const packetsBeforePanel=await page.evaluate(()=>window.voiceStats.packets);
    await page.locator('#cockpitResources').click();
    assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'),'true');
    await page.waitForFunction(before=>window.voiceStats.packets>before+3,packetsBeforePanel);
    await page.locator('#cockpitSheetClose').click();
    assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'),'true');

    await page.evaluate(() => {
      const data = btoa(String.fromCharCode(...new Uint8Array(24000 * 2)));
      window.liveSocket.emit({serverContent: {
        inputTranscription: {text: 'Bonjour Jarvis'}, outputTranscription: {text: 'Salut !'},
        modelTurn: {parts: [{inlineData: {mimeType: 'audio/pcm;rate=24000', data}}]},
      }});
    });
    await page.waitForFunction(() => document.querySelector('#liveTranscript').textContent.includes('Salut'));
    await page.evaluate(() => window.liveSocket.emit({serverContent: {interrupted: true}}));
    await page.waitForFunction(() => window.voiceStats.stops > 0);
    assert.equal(await page.locator('body').getAttribute('data-voice'), 'listening');
    assert((await page.evaluate(()=>window.jarvisHistory())).some(m=>m.text==='Salut !'));
    await page.locator('.system-key[data-system=library]').click();
    assert(await page.locator('#hudMicShortcut').isVisible());
    if(!await page.locator('#liveButton').isVisible())await page.locator('[data-view=chat]').click();
    await page.waitForTimeout(150);
    assert(archives.some(r=>r.channel==='voice'&&r.space==='user'&&r.user==='Bonjour Jarvis'&&r.assistant==='Salut !'&&r.status==='interrupted'));
    await page.evaluate(() => {window.liveSocket.emit({serverContent:{inputTranscription:{text:'Quelle est la température ?'}}});window.liveSocket.emit({toolCall: {functionCalls: [{id: 'ha-read', name: 'consulter_home_assistant', args: {query: 'aquarium'}}]}});window.liveSocket.emit({serverContent:{turnComplete:true}});});
    await page.waitForFunction(() => window.voiceStats.toolResponses.length === 1);
    assert.equal(await page.evaluate(() => window.voiceStats.toolResponses[0].functionResponses[0].response.states[0].state), '25.1');
    await page.evaluate(()=>window.liveSocket.emit({serverContent:{outputTranscription:{text:'Il fait 25,1 °C.'},turnComplete:true}}));
    await page.waitForTimeout(200);assert(archives.some(r=>r.user==='Quelle est la température ?'&&r.assistant==='Il fait 25,1 °C.'&&r.status==='complete'));
    await page.evaluate(() => {
      window.liveSocket.emit({toolCall: {functionCalls: [{id: 'ha-cancel', name: 'consulter_home_assistant', args: {query: 'frigo'}}]}});
      window.liveSocket.emit({toolCallCancellation: {ids: ['ha-cancel']}, serverContent: {interrupted: true}});
    });
    await page.waitForTimeout(350);
    assert.equal(await page.evaluate(() => window.voiceStats.toolResponses.length), 1);
    await page.locator('#spaceSelect').selectOption('amelie');
    await page.waitForFunction(() => window.voiceStats.tracks.every(t => t.readyState === 'ended'));
    assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'), 'false');
    await page.locator('#liveButton').click();
    await page.waitForFunction(() => document.querySelector('#liveStatus').textContent.startsWith('Je t’écoute'), {}, {timeout: 10000}).catch(async e => {
      const status = await page.locator('#liveStatus').textContent();
      const capture = await page.evaluate(() => ({tracks: window.voiceStats.tracks.length, socket: !!window.liveSocket, states: window.voiceStats.tracks.map(t=>t.readyState)}));
      throw Error(e.message + ' Status: ' + status + ' Capture: ' + JSON.stringify(capture));
    });
    await page.locator('#liveButton').click();
    await page.waitForFunction(() => window.voiceStats.tracks.every(t => t.readyState === 'ended'));
    assert.equal(await page.locator('#liveStatus').textContent(), 'Micro coupé.');
    assert.equal(await page.locator('body').getAttribute('data-voice'), 'idle');
    await page.locator('#liveButton').click();await page.waitForFunction(()=>document.querySelector('#liveStatus').textContent.startsWith('Je t’écoute'));
    await page.locator('#cockpitWrite').click();await page.locator('#newConversation').click();
    await page.waitForFunction(()=>window.voiceStats.tracks.every(t=>t.readyState==='ended'));assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'),'false');assert.equal(await page.locator('#liveTranscript').textContent(),'');await page.locator('#cockpitSheetClose').click();
    await page.route('**/api/jarvis/live/session?*', route => route.fulfill({status: 503, contentType: 'application/json',
      body: JSON.stringify({error: 'La clé Gemini du serveur est invalide.'})}));
    await page.locator('#liveButton').click();
    await page.waitForFunction(() => document.querySelector('#liveStatus').textContent.includes('invalide'));
    assert.equal(await page.locator('#liveButton').getAttribute('aria-pressed'), 'false');
    assert.equal(await page.locator('body').getAttribute('data-voice'), 'error');
    assert.deepEqual(errors, []);
    await page.screenshot({path: '/home/user/workspace/jarvis/data/gemini-mobile.png', fullPage: true});
    const httpPage = await browser.newPage();
    await httpPage.goto('http://192.0.2.16:8787/jarvis/');
    if(!await httpPage.locator('#liveButton').isVisible())await httpPage.locator('[data-view=chat]').click();
    assert.equal(await httpPage.locator('#liveHttps').getAttribute('href'), 'https://192.0.2.16:8788/jarvis/');
    console.log('PASS: origin/TLS, mobile layout, real microphone capture; capture/playback worklets on test clock and mocked Google; interruption clears queued audio, automatic transcript archival, cleanup, invalid key, HTTPS link.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e.stack); process.exit(1); });
