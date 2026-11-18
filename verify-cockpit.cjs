const {chromium,webkit}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const assert=require('node:assert/strict');
(async()=>{const engine=process.env.JARVIS_TEST_BROWSER==='webkit'?webkit:chromium;const b=await engine.launch(engine===webkit?{headless:true}:{executablePath:'/home/user/.cache/ms-playwright/chromium-1193/chrome-linux/chrome',headless:true,args:['--no-sandbox']});try{
 for(const [name,width,height,fallback] of [['iphone',390,844,false],['iphone-short',375,667,false],['iphone-large',430,932,false],['fallback',390,844,true]].filter(row=>(!process.env.JARVIS_TEST_QUICK||row[0]==='iphone')&&(!process.env.JARVIS_TEST_CASE||row[0]===process.env.JARVIS_TEST_CASE))){
  const p=await b.newPage({viewport:{width,height},isMobile:true,hasTouch:true,deviceScaleFactor:2,ignoreHTTPSErrors:true});const errors=[];p.on('pageerror',e=>errors.push(e.message));
  if(fallback)await p.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return /webgl/.test(type)?null:get.call(this,type,...args)}});
  await p.goto((process.env.JARVIS_TEST_BASE||'https://192.0.2.16:8788')+'/jarvis/',{waitUntil:'networkidle'});await p.waitForTimeout(1200);
  assert.equal(await p.locator('#plasmaCore').count(),0);assert.equal(await p.locator('.reference-core-name').textContent(),'J.A.R.V.I.S.');assert.equal(await p.locator('#hologramCanvas').count(),1);console.log(name,'holographic scene and microphone control present');
  assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'width '+name);
  const button=await p.locator('#liveButton').boundingBox();assert(button.y>0&&button.y+button.height<height,'microphone inside viewport '+name);
  assert(await p.locator('#cockpitWrite').isVisible());assert(await p.locator('#cockpitResources').isVisible());
  await p.screenshot({path:`/home/user/workspace/jarvis/data/cockpit-${engine===webkit?'webkit-':''}${name}.png`});
  await p.locator('#cockpitResources').click();assert(await p.locator('#voiceCreditBalance').isVisible());assert(await p.locator('#voiceMemoryStatus').isVisible());await p.locator('#cockpitSheetClose').click();
  await p.locator('#cockpitWrite').click();await p.locator('#question').fill('Brouillon');await p.locator('#cockpitSheetClose').click();await p.locator('#cockpitWrite').click();assert.equal(await p.locator('#question').inputValue(),'Brouillon');await p.locator('#cockpitSheetClose').click();
  await p.locator('.system-key[data-system=home]').click();assert(await p.locator('#homeVoicePanel').isVisible());assert.equal(await p.locator('#homeStartVoice').textContent(),'Ouvrir le micro');await p.locator('#cockpitSheetClose').click();await p.locator('#cockpitWrite').click();assert.equal(await p.locator('#question').inputValue(),'Brouillon');await p.locator('#cockpitSheetClose').click();
  const asks=[];let delayed=false;
  await p.route('**/api/jarvis/conversations/record?*',route=>route.fulfill({json:{ok:true}}));
  await p.route('**/api/jarvis/ask?*',async route=>{asks.push(route.request().postDataJSON());if(delayed)await new Promise(resolve=>setTimeout(resolve,500));await route.fulfill({json:{answer:'Réponse du test',sources:[],action:null}}).catch(()=>{});});
  await p.locator('#cockpitWrite').click();assert(await p.locator('#newConversation').isVisible());
  await p.locator('#question').fill('Premier échange');await p.locator('#askButton').click();await p.waitForFunction(()=>document.querySelector('#messages').textContent.includes('Réponse du test'));
  await p.evaluate(()=>document.querySelector('#liveTranscript').textContent='Ancienne transcription');
  await p.locator('#newConversation').click();assert.equal(await p.locator('#messages').textContent(),'');assert.equal(await p.locator('#liveTranscript').textContent(),'');assert.equal(await p.locator('#question').inputValue(),'');
  assert((await p.locator('#conversationResetStatus').textContent()).includes('souvenirs conservés'));
  await p.locator('#question').fill('Deuxième échange');await p.locator('#askButton').click();await p.waitForFunction(()=>document.querySelector('#messages').textContent.includes('Réponse du test'));assert.equal(asks.length,2);assert.deepEqual(asks[1].history,[]);assert.notEqual(asks[0].archive.id,asks[1].archive.id);
  delayed=true;await p.locator('#question').fill('Question en cours');await p.locator('#askButton').click();await p.waitForFunction(()=>document.querySelector('#askButton').disabled);await p.locator('#newConversation').click();await p.waitForTimeout(650);assert.equal(await p.locator('#messages').textContent(),'');assert(await p.locator('#askButton').isEnabled());
  assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await p.locator('#cockpitSheetClose').click();
  await p.locator('.system-key[data-system=library]').click();assert(await p.locator('#cards .memory-card').first().isVisible());await p.locator('[data-view=chat]').click();assert(await p.locator('#liveButton').isVisible());
  assert.deepEqual(errors,[]);await p.close();console.log('PASS:',name,'viewport, controls, resource/memory panel, preserved draft, memory navigation.');
 }
}finally{await b.close()}})().catch(e=>{console.error(e.stack);process.exit(1)});
