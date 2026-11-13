import assert from 'node:assert/strict';import {EventEmitter} from 'node:events';import {PassThrough,Writable} from 'node:stream';import {CodexWorker} from './codex-worker.mjs';
let threads=0,starts=0,interrupts=0,spawnCount=0;const calls=[];
function spawnImpl(_exe,args){spawnCount++;assert(args.includes('app-server'));const child=new EventEmitter();child.stdout=new PassThrough();child.pid=undefined;const output=x=>child.stdout.write(JSON.stringify(x)+'\n');const event=(method,params)=>output({method,params});child.stdin=new Writable({write(chunk,_,cb){const x=JSON.parse(chunk.toString());calls.push(x);cb();queueMicrotask(()=>{
 if(x.method==='initialize')output({id:x.id,result:{}});
 if(x.method==='thread/start')output({id:x.id,result:{thread:{id:'thread-'+(++threads)},model:'gpt-6.1-sol'}});
 if(x.method==='turn/start'){starts++;const text=JSON.parse(x.params.input[0].text),threadId=x.params.threadId,turn={id:'turn-'+starts};output({id:x.id,result:{turn}});event('turn/started',{threadId,turn});if(text.question==='pending')return;
 event('item/completed',{threadId,item:{type:'agentMessage',phase:'commentary',text:'Do not read commentary as JSON'}});
 event('item/completed',{threadId,item:{type:'agentMessage',phase:'final_answer',text:JSON.stringify({answer:text.question,speech:text.question,sourceIds:[],action:{type:'none'}})}});event('turn/completed',{threadId,turn:{...turn,status:'completed'}});
 }
 if(x.method==='turn/interrupt'){interrupts++;output({id:x.id,result:{}});event('turn/completed',{threadId:x.params.threadId,turn:{id:x.params.turnId,status:'interrupted'}})}
 if(x.method==='thread/unsubscribe')output({id:x.id,result:{}});
 })}});return child}
const worker=new CodexWorker('member1',{spawnImpl,learningStore:async action=>action==='list'?[]:{saved:0},explicitMemory:async()=>[]});
try{
 const results=await Promise.all([worker.answer('one',[],{space:'member1'}),worker.answer('two',[],{space:'member1'})]);assert.deepEqual(results.map(r=>r.answer),['one','two']);assert.equal(spawnCount,1);assert.equal(threads,2);assert.equal(worker.jobs.size,0);
 const controller=new AbortController();const pending=worker.answer('pending',[],{space:'member1'},controller.signal);while(starts<3)await new Promise(r=>setImmediate(r));controller.abort();await assert.rejects(pending,{name:'AbortError'});assert.equal(interrupts,1);assert.equal(starts,3,'Aborted actions must never replay');
 const already=new AbortController();already.abort();await assert.rejects(worker.answer('never-started',[],{},already.signal),{name:'AbortError'});assert.equal(threads,3);
 assert.equal((await worker.answer('after interruption',[],{})).answer,'after interruption');assert(calls.filter(c=>c.method==='thread/start').every(c=>c.params.ephemeral&&c.params.sandbox==='workspace-write'&&c.params.approvalPolicy==='never'));
 console.log('PASS: warm process reuse, isolated ephemeral threads, concurrent response routing, final-message parsing, abort propagation without action replay, recovery and sandbox policy.');
}finally{worker.close()}
