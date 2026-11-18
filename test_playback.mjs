import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const code = await readFile(new URL('./public/live-pcm.js', import.meta.url), 'utf8');
function player(rate) {
  let Playback;
  const messages = [];
  const context = vm.createContext({sampleRate: rate, Float32Array,
    AudioWorkletProcessor: class {constructor() {this.port = {postMessage: data => messages.push(data)};}},
    registerProcessor: (name, processor) => {if (name === 'jarvis-playback') Playback = processor;},
  });
  vm.runInContext(code, context);
  const processor = new Playback();
  return {processor, messages,
    send: data => processor.port.onmessage({data}),
    render: (size = 128) => {
      const output = new Float32Array(size);
      processor.process([], [[output]]);
      return output;
    },
  };
}

// One continuous waveform, split at awkward packet boundaries. Resampling must
// preserve phase across every packet at both common Mac output sample rates.
for (const rate of [24000, 44100, 48000, 96000]) {
  const p = player(rate);
  const input = Float32Array.from({length: 24000}, (_, i) => .4 * Math.sin(2 * Math.PI * 440 * i / 24000));
  for (let pos = 0; pos < input.length; pos += 317)
    p.send({type: 'audio', rate: 24000, samples: input.slice(pos, pos + 317)});
  const output = p.render(Math.floor(rate * .95));
  let maxError = 0;
  for (let i = Math.ceil(rate * .005); i < output.length; i++) {
    const position = i * 24000 / rate;
    const index = Math.floor(position), fraction = position - index;
    const expected = input[index] + (input[index + 1] - input[index]) * fraction;
    maxError = Math.max(maxError, Math.abs(output[i] - expected));
  }
  assert(maxError < 1e-6, `continuous resampling ${rate} Hz: ${maxError}`);
}

// Packets arrive late in bursts, up to 60 ms of jitter. There must be one
// continuous speech region, with no gaps or repeated fades at packet boundaries.
{
  const rate = 48000;
  const p = player(rate);
  const arrivals = [];
  for (let i = 0; i < 50; i++) {
    const jitter = [0, 48 * 60, 48 * 10, 48 * 35, 0][i % 5];
    arrivals.push(Math.max(i * 960 + jitter, (arrivals.at(-1) || 0) + 1));
  }
  let packet = 0;
  const output = [];
  for (let frame = 0; frame < rate * 1.5; frame += 128) {
    while (packet < 50 && arrivals[packet] <= frame) {
      p.send({type: 'audio', rate: 24000, samples: new Float32Array(480).fill(.25)});
      if (++packet === 50) p.send({type: 'end'});
    }
    output.push(...p.render());
  }
  const first = output.findIndex(v => v >= .249);
  const last = output.findLastIndex(v => v >= .249);
  assert(first > 0 && last - first > 46000);
  assert(output.slice(first, last + 1).every(v => v >= .249), 'no crackling gaps between packets');
  assert.equal(p.processor.count, 0);
  assert(p.messages.some(m => m.type === 'drained'));
}

// An interruption discards even seconds of queued speech, with at most 4 ms
// left to fade smoothly. New speech must never include the discarded samples.
{
  const p = player(48000);
  p.send({type: 'audio', rate: 24000, samples: new Float32Array(24000 * 3).fill(.5)});
  p.render(512);
  p.send({type: 'clear'});
  assert.equal(p.processor.count, 0);
  const fade = p.render(512);
  assert(fade[0] > 0 && fade[0] < .5);
  assert(fade.subarray(192).every(v => v === 0), 'silence within 4 ms after interrupt');
  p.send({type: 'audio', rate: 24000, samples: new Float32Array(4800).fill(-.25)});
  const next = p.render(512);
  assert(next.subarray(192).every(v => v === -.25), 'old voice cannot resume after interrupt');
}

// Drain responses shorter than the startup buffer, and bound a faulty stream.
{
  const p = player(48000);
  p.send({type: 'audio', rate: 24000, samples: new Float32Array(480).fill(.2)});
  assert(p.render().every(v => v === 0));
  p.send({type: 'end'});
  assert(p.render().some(v => v > 0));
  p.render(2000);
  assert.equal(p.processor.count, 0);
  p.send({type: 'audio', rate: 24000, samples: new Float32Array(24000 * 31)});
  assert(p.messages.some(m => m.type === 'overflow'));
}
console.log('PASS: continuous PCM phase at 24/44.1/48/96 kHz, burst/jitter playback without packet gaps, interruption clears all queued speech within 4 ms, short replies, bounded queue.');

// Meters must reflect rendered samples, not the receipt of a queued packet.
{
 const p=player(48000);p.send({type:'audio',rate:24000,samples:new Float32Array(2400).fill(.3)});
 assert.equal(p.messages.filter(m=>m.type==='meter'&&m.rms>0).length,0);
 p.render(2048);assert(p.messages.some(m=>m.type==='meter'&&m.rms===0&&!m.playing),'buffered but not played = zero');
 p.send({type:'end'});const rendered=p.render(2048);const actual=Math.sqrt(rendered.reduce((sum,v)=>sum+v*v,0)/rendered.length);
 const meter=p.messages.filter(m=>m.type==='meter'&&m.playing).at(-1);assert(meter&&meter.rms>0&&meter.peak<=.301);assert(actual>.28);
 p.send({type:'clear',epoch:41});const clear=p.messages.at(-1);assert.equal(clear.epoch,41);assert.equal(clear.rms,0);assert.equal(clear.bufferedMs,0);
 p.render(4096);assert(p.messages.filter(m=>m.type==='meter').slice(-1)[0].epoch===41);
 console.log('PASS: output meter derives from rendered PCM, stays zero while buffering, and resets with an interruption epoch.');
}
// A final empty stream must acknowledge completion, including after an underrun.
{
 const p=player(48000);p.send({type:'end'});p.render(128);assert(p.messages.some(m=>m.type==='drained'&&m.ended===true));
 p.send({type:'audio',rate:24000,samples:new Float32Array(6000).fill(.2)});p.render(24000);
 const before=p.messages.length;p.send({type:'end'});p.render(512);assert(p.messages.slice(before).some(m=>m.type==='drained'&&m.ended===true),'final end re-acknowledges a previously empty queue');
}
