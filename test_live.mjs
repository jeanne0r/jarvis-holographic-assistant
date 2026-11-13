import assert from 'node:assert/strict';
import {readFile, mkdtemp, rm} from 'node:fs/promises';
import vm from 'node:vm';

const originalFetch = globalThis.fetch;
const originalKey = process.env.GEMINI_API_KEY;
const originalGoogleKey = process.env.GOOGLE_API_KEY;
const originalBrainDb = process.env.JARVIS_DB;
const originalMemoryDb = process.env.JARVIS_VOICE_MEMORY_DB;
const originalLedger = process.env.JARVIS_USAGE_DB;
const testDir = await mkdtemp(new URL('./data/usage-test-', import.meta.url).pathname);
process.env.JARVIS_USAGE_DB = testDir + '/usage.sqlite';
process.env.JARVIS_VOICE_MEMORY_DB = testDir + '/memory.sqlite';
process.env.JARVIS_DB = testDir + '/brain.sqlite';
try {
  delete process.env.GEMINI_API_KEY;
  delete process.env.GOOGLE_API_KEY;
  const live = await import('./live.mjs?test=missing');
  assert.equal(live.liveStatus().configured, false);
  await assert.rejects(live.createLiveSession(), e => e.status === 503);
  process.env.GEMINI_API_KEY = 'test-key-never-returned';
  let calls = 0;
  globalThis.fetch = async (url, options) => {
    calls++;
    assert.equal(new URL(url).hostname, 'generativelanguage.googleapis.com');
    assert(!url.includes(process.env.GEMINI_API_KEY));
    const request = JSON.parse(options.body);
    assert.equal(request.uses, 1);
    assert.equal(request.bidiGenerateContentSetup.generationConfig.responseModalities[0], 'AUDIO');
    assert.deepEqual(request.bidiGenerateContentSetup.tools[0].functionDeclarations.map(t=>t.name), ['consulter_home_assistant','commandes_home_assistant','piloter_home_assistant','memoire_jarvis','chercher_souvenirs','web_jarvis','medias_jarvis','trajet_jarvis','evolution_jarvis']);
    assert.equal(request.bidiGenerateContentSetup.realtimeInputConfig.activityHandling, 'START_OF_ACTIVITY_INTERRUPTS');
    assert.deepEqual(request.bidiGenerateContentSetup.contextWindowCompression,{triggerTokens:'3072',slidingWindow:{targetTokens:'2048'}});
    assert.equal(request.bidiGenerateContentSetup.realtimeInputConfig.turnCoverage,'TURN_INCLUDES_ONLY_ACTIVITY');
    assert(Date.parse(request.expireTime) - Date.now() <= 600000);
    return {ok: true, json: async () => ({name: 'auth_tokens/test-only'})};
  };
  const session = await live.createLiveSession();
  assert(!JSON.stringify(session).includes(process.env.GEMINI_API_KEY));
  await assert.rejects(live.liveTool({sessionId: 'unknown', name: 'consulter_home_assistant', args: {query: ''}}), e => e.status === 403);
  await assert.rejects(live.liveTool({sessionId: session.usageSessionId, name: 'turn_on', args: {}}), e => e.status === 400);
  assert.deepEqual(Object.keys(session.setup), ['model']);
  const tokenFetch = globalThis.fetch;
  const savedHaUrl = process.env.HOME_ASSISTANT_URL, savedHaToken = process.env.HOME_ASSISTANT_TOKEN;
  process.env.HOME_ASSISTANT_URL = 'http://127.0.0.1:1'; process.env.HOME_ASSISTANT_TOKEN = 'mock';
  let commands = 0;
  globalThis.fetch = async (url, options) => ({ok: true, json: async () => {
    if (url.pathname === '/api/services') return [{domain: 'light', services: {turn_off: {fields: {}}}}];
    if (options.method === 'POST') { commands++; return []; }
    return [{entity_id: 'light.tv', state: 'off', attributes: {}}];
  }});
  const tool = (callId, name, args) => live.liveTool({sessionId: session.usageSessionId, callId, name, args});
  await tool('read', 'consulter_home_assistant', {query: 'tv'});
  await tool('services', 'commandes_home_assistant', {domain: 'light'});
  const command = {domain: 'light', service: 'turn_off', entity_ids: ['light.tv']};
  await Promise.all([tool('action', 'piloter_home_assistant', command), tool('action', 'piloter_home_assistant', command)]);
  assert.equal(commands, 1, 'duplicate Google call IDs execute only once');
  await assert.rejects(tool('action', 'piloter_home_assistant', {...command, entity_ids: ['light.other']}));
  assert.equal(commands, 1);
  await assert.rejects(tool('bad-memory', 'memoire_jarvis', {action:'memoriser', key:'inconnu', fact:'Lumière inventée', entity_id:'light.unknown'}));
  assert.equal((await tool('memory', 'memoire_jarvis', {action:'memoriser', key:'Coin lecture', fact:'Le coin lecture désigne la TV.', entity_id:'light.tv'})).saved, true);
  assert.equal((await tool('recall', 'memoire_jarvis', {action:'consulter', key:'Coin lecture'})).memories[0].entity_id, 'light.tv');
  const learned = await tool('alias-read', 'consulter_home_assistant', {query:'coin lecture'});
  assert.equal(learned.states[0].entity_id, 'light.tv');
  globalThis.fetch = tokenFetch;
  if (savedHaUrl === undefined) delete process.env.HOME_ASSISTANT_URL; else process.env.HOME_ASSISTANT_URL = savedHaUrl;
  if (savedHaToken === undefined) delete process.env.HOME_ASSISTANT_TOKEN; else process.env.HOME_ASSISTANT_TOKEN = savedHaToken;

  const nextSession = await live.createLiveSession();
  const recalled = await live.liveTool({sessionId:nextSession.usageSessionId, callId:'recall-new-session', name:'memoire_jarvis', args:{action:'consulter',key:'Coin lecture'}});
  assert.equal(recalled.memories[0].fact, 'Le coin lecture désigne la TV.');
  for (let i = 0; i < 2; i++) await live.createLiveSession();
  await assert.rejects(live.createLiveSession(), e => e.status === 429);
  assert.equal(calls, 4);

  const invalid = await import('./live.mjs?test=invalid');
  globalThis.fetch = async () => ({ok: false, status: 400, json: async () => ({error: {
    message: 'API key not valid. ' + process.env.GEMINI_API_KEY,
    details: [{reason: 'API_KEY_INVALID'}],
  }})});
  await assert.rejects(invalid.createLiveSession(), e => e.status === 503 &&
    e.message.includes('invalide') && !e.message.includes(process.env.GEMINI_API_KEY));
  const offline = await import('./live.mjs?test=offline');
  globalThis.fetch = async () => { throw Error('sensitive upstream details'); };
  await assert.rejects(offline.createLiveSession(), e => e.status === 503 && !e.message.includes('sensitive'));

  const worklet = await readFile(new URL('./public/live-pcm.js', import.meta.url), 'utf8');
  for (const rate of [16000, 24000, 44100, 48000]) {
    let Processor;
    const packets = [];
    const context = vm.createContext({sampleRate: rate,
      AudioWorkletProcessor: class { constructor() { this.port = {postMessage: packet => packets.push(packet)}; } },
      registerProcessor: (name, p) => {if (name === 'jarvis-pcm') Processor = p;},
    });
    vm.runInContext(worklet, context);
    const processor = new Processor();
    const input = new Float32Array(rate).fill(0.5);
    for (let i = 0; i < input.length; i += 128) processor.process([[input.subarray(i, i + 128)]]);
    assert.equal(packets.length, 50, `20 ms packets for ${rate} Hz`);
    for (const packet of packets) {
      assert.equal(packet.byteLength, 640);
      assert(new Int16Array(packet).every(x => Math.abs(x - 16384) <= 1));
    }
  }
  console.log('PASS: ephemeral credentials, native audio configuration, rate limits, redacted failures, PCM resampling at 16/24/44.1/48 kHz.');
} finally {
  globalThis.fetch = originalFetch;
  if (originalKey === undefined) delete process.env.GEMINI_API_KEY; else process.env.GEMINI_API_KEY = originalKey;
  if (originalGoogleKey === undefined) delete process.env.GOOGLE_API_KEY; else process.env.GOOGLE_API_KEY = originalGoogleKey;
  if (originalLedger === undefined) delete process.env.JARVIS_USAGE_DB; else process.env.JARVIS_USAGE_DB = originalLedger;
  if (originalMemoryDb === undefined) delete process.env.JARVIS_VOICE_MEMORY_DB; else process.env.JARVIS_VOICE_MEMORY_DB = originalMemoryDb;
  if (originalBrainDb === undefined) delete process.env.JARVIS_DB; else process.env.JARVIS_DB = originalBrainDb;
  await rm(testDir, {recursive: true, force: true});
}
