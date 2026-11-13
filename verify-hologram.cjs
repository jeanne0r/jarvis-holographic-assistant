const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
const base=process.env.JARVIS_TEST_BASE||'http://127.0.0.1:8790';
(async()=>{
 const engine=process.env.JARVIS_TEST_BROWSER==='webkit'?webkit:chromium;
 const b=await engine.launch(engine===webkit?{headless:true}:{headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 try{
  const cases=[['desktop',1440,1000,false],['macbook',1280,800,false],['iphone',390,844,false],['iphone-short',375,667,false],['landscape',844,390,false],['4k',3840,2160,false],['fallback',390,844,true]];
  for(const[name,width,height,fallback]of cases.filter(row=>!process.env.JARVIS_TEST_CASE||process.env.JARVIS_TEST_CASE===row[0])){
   const p=await b.newPage({viewport:{width,height},deviceScaleFactor:1,ignoreHTTPSErrors:true});const errors=[];p.on('pageerror',e=>errors.push(e.message));
   if(fallback)await p.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return /webgl/.test(type)?null:get.call(this,type,...args);}});
   await p.route('**/api/jarvis/conversations/record?*',r=>r.fulfill({json:{saved:true}}));
   const asks=[];await p.route('**/api/jarvis/ask?*',r=>{asks.push(r.request().postDataJSON());return r.fulfill({json:{answer:'Le test est réussi.',sources:[],action:null}})});
   await p.goto(base+'/jarvis/',{waitUntil:'networkidle'});await p.waitForTimeout(600);
   assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow '+name);
   const mic=await p.locator('#liveButton').boundingBox();assert(mic&&mic.width>=44&&mic.height>=44&&mic.y>=0&&mic.y+mic.height<=height,'microphone bounds '+name);
   assert(await p.locator('#cockpitWrite').isVisible());assert(await p.locator('#cockpitResources').isVisible());
   const ready=await p.evaluate(()=>window.jarvisHologram?.ready);
   if(engine===chromium&&!fallback){await p.waitForFunction(()=>window.jarvisHologram?.ready,{},{timeout:20000});}
   if(fallback){assert(!ready);assert(await p.locator('.holo-fallback').isVisible());}
   if(await p.evaluate(()=>window.jarvisHologram?.ready)){
    const n=await p.evaluate(()=>window.jarvisHologram.frames);await p.waitForFunction(n=>window.jarvisHologram.frames>n,n,{timeout:15000});
    await p.evaluate(()=>document.dispatchEvent(new CustomEvent('jarvis:voice-state',{detail:{state:'thinking'}})));await p.waitForFunction(()=>window.jarvisHologram.state==='thinking');
    await p.evaluate(()=>document.dispatchEvent(new CustomEvent('jarvis:voice-state',{detail:{state:'speaking'}})));await p.waitForFunction(()=>window.jarvisHologram.state==='speaking');
    await p.evaluate(()=>document.dispatchEvent(new CustomEvent('jarvis:voice-state',{detail:{state:'idle'}})));
   }
   await p.screenshot({path:`data/hologram-${engine===webkit?'webkit-':''}${name}.png`});
   await p.locator('#cockpitResources').click();assert(await p.locator('#voiceCreditBalance').isVisible());assert(await p.locator('#voiceMemoryStatus').isVisible());
   if(await p.evaluate(()=>window.jarvisHologram?.ready)){await p.waitForTimeout(100);assert((await p.evaluate(()=>window.jarvisHologram)).paused);}
   await p.locator('#cockpitSheetClose').click();
   await p.locator('#cockpitWrite').click();await p.locator('#question').fill('Texte');await p.locator('#question').press('Alt+Enter');assert.equal(await p.locator('#question').inputValue(),'Texte\n');assert.equal(asks.length,0);await p.locator('#question').press('Enter');await p.waitForFunction(()=>document.querySelector('#messages').textContent.includes('Le test est réussi.'));assert.equal(asks.length,1);await p.locator('#newConversation').click();assert.equal(await p.locator('#messages').textContent(),'');await p.locator('#cockpitSheetClose').click();
   await p.locator('.system-key[data-system=home]').click();assert(await p.locator('#homeVoicePanel').isVisible());await p.locator('#cockpitSheetClose').click();
   await p.locator('.system-key[data-system=library]').click();await p.locator('#cards .memory-card').first().waitFor();await p.locator('[data-view=chat]').click();assert(await p.locator('#liveButton').isVisible());
   await p.locator('.system-key[data-system=memory3d]').click();await p.locator('#memory3dCanvas').waitFor({state:'visible'});await p.locator('#map3dBack').click();
   await p.locator('#immersionButton').click();assert.equal(await p.locator('#immersionButton').getAttribute('aria-pressed'),'true');await p.keyboard.press('Escape');assert.equal(await p.locator('#immersionButton').getAttribute('aria-pressed'),'false');
   await p.emulateMedia({reducedMotion:'reduce'});if(await p.evaluate(()=>window.jarvisHologram?.ready))await p.waitForFunction(()=>window.jarvisHologram.reducedMotion&&window.jarvisHologram.paused,{},{timeout:15000});await p.waitForTimeout(100);const f=await p.evaluate(()=>window.jarvisHologram?.frames);await p.waitForTimeout(350);assert.equal(await p.evaluate(()=>window.jarvisHologram?.frames),f,'reduced motion stops render loop');
   assert.deepEqual(errors,[]);console.log('PASS',name,JSON.stringify(await p.evaluate(()=>window.jarvisHologram)));await p.close();
  }
 }finally{await b.close();}
})().catch(e=>{console.error(e.stack);process.exit(1)});
