import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';import vm from 'node:vm';
const ctx=vm.createContext({Int16Array,Math});vm.runInContext(await readFile('public/voice-gate.js','utf8'),ctx);
let audio=[],ends=0,activities=0;const gate=new ctx.JarvisVoiceGate({audio:b=>audio.push(b),end:()=>ends++,activity:()=>activities++});
const frame=level=>Int16Array.from({length:320},(_,i)=>Math.round(level*32767*Math.sin(i*.2))).buffer;
for(let i=0;i<200;i++)gate.push(frame(0));assert.equal(audio.length,0,'four seconds of silence stay local');
for(let i=0;i<100;i++)gate.push(frame(.001));assert.equal(audio.length,0,'quiet background stays local');
gate.push(frame(.2));gate.push(frame(0));assert.equal(audio.length,0,'a single click does not start a stream');
gate.push(frame(.08));assert.equal(audio.length,0);gate.push(frame(.08));assert(audio.length>=2,'onset preserved with preceding buffer');assert(activities>0);
const voiceStart=audio.length;for(let i=0;i<10;i++)gate.push(frame(.08));assert.equal(audio.length,voiceStart+10,'speech flows continuously');
for(let i=0;i<60;i++)gate.push(frame(0));assert.equal(ends,1,'one stream-end per pause');const stopped=audio.length;
for(let i=0;i<200;i++)gate.push(frame(0));assert.equal(audio.length,stopped);assert.equal(ends,1);
gate.push(frame(.08));gate.push(frame(.08));assert(audio.length>stopped,'user speech resumes without reopening microphone');
let whispers=0;const quiet=new ctx.JarvisVoiceGate({audio:()=>whispers++,end:()=>{}});quiet.push(frame(.007));quiet.push(frame(.007));assert(whispers>0,'quiet voiced onset is retained');
console.log('PASS: silence/background suppression, click rejection, retained onset, uninterrupted speech, one stream end, resumption, soft speech.');
let fastEnds=0;const fast=new ctx.JarvisVoiceGate({tailMs:600,audio:()=>{},end:()=>fastEnds++});fast.push(frame(.08));fast.push(frame(.08));for(let i=0;i<29;i++)fast.push(frame(0));assert.equal(fastEnds,0);fast.push(frame(0));assert.equal(fastEnds,1,'Codex speech completes after 600 ms silence, preserving the legacy default');

fast.push(frame(.08));fast.push(frame(.08));fast.reset();assert.equal(fast.active,false);assert.equal(fast.history.length,0);assert.equal(fast.attack,0);
