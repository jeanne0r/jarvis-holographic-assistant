const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium-1193/chrome-linux/chrome',headless:true,args:['--no-sandbox']});try{
 for(const [name,width,height] of [['desktop',1440,1080],['macbook',1280,800],['mobile',390,844]]){
  const p=await browser.newPage({viewport:{width,height},ignoreHTTPSErrors:true});const errors=[];p.on('pageerror',e=>errors.push(e.message));
  let requests=0;await p.route('**/api/jarvis/ask?*',r=>{requests++;return r.fulfill({contentType:'application/json',body:JSON.stringify({answer:'Bonjour, à votre service.',sources:[]})})});
  await p.route('**/api/jarvis/conversations/record?*',r=>r.fulfill({contentType:'application/json',body:'{"saved":true}'}));
  await p.goto('https://192.0.2.16:8788/jarvis/',{waitUntil:'networkidle'});
  assert(await p.locator('#liveButton').isVisible());assert.equal(await p.locator('#graph').count(),0);assert.equal(await p.locator('.graph-node').count(),0);
  assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no horizontal overflow '+name);
  await p.waitForTimeout(850);
  assert.equal(await p.locator('#cinemaMemoryCount').textContent(),await p.locator('#count').textContent());
  assert.equal(await p.locator('#cinemaPerson').textContent(),await p.locator('#profileName').textContent());
  await p.locator('#immersionButton').click();assert.equal(await p.locator('#immersionButton').getAttribute('aria-pressed'),'true');assert(await p.locator('#liveButton').isVisible());assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'immersive overflow '+name);
  await p.keyboard.press('Escape');assert.equal(await p.locator('#immersionButton').getAttribute('aria-pressed'),'false');
  await p.screenshot({path:`/home/user/workspace/jarvis/data/jarvis-hud-${name}.png`,fullPage:true});
  await p.locator('#cockpitWrite').click();await p.locator('#cockpitSheet[open]').waitFor();
  await p.locator('#question').fill('Bonjour');await p.locator('#question').press('Alt+Enter');assert.equal(await p.locator('#question').inputValue(),'Bonjour\n');assert.equal(requests,0);
  await p.locator('#question').press('Enter');await p.getByText('Bonjour, à votre service.',{exact:true}).waitFor();assert.equal(requests,1);
  {await p.locator('#cockpitSheetClose').click();await p.locator('#cockpitResources').click();assert(await p.locator('#voiceDailyCost').isVisible());assert(await p.locator('#voiceMemoryStatus').isVisible());await p.locator('#cockpitSheetClose').click();}
  await p.locator('.system-key[data-system=library]').click();await p.locator('#cards .memory-card').first().waitFor();await p.locator('#cards .memory-card').first().click();await p.locator('#detail[open]').waitFor();await p.locator('#detail .close').click();
  await p.locator('[data-view=atelier]').click();assert(await p.locator('#libraryView').isVisible());await p.locator('[data-view=chat]').click();assert(await p.locator('#liveButton').isVisible());
  await p.emulateMedia({reducedMotion:'reduce'});assert.equal(await p.locator('.holo-wave i').first().evaluate(e=>getComputedStyle(e).animationName),'none');
  assert.deepEqual(errors,[]);await p.close();console.log('PASS:',name,'layout, default console, 3D scene, immersion/Escape, mirrored live readings, no constellation, Enter/AltEnter, memory detail, navigation, reduced motion.');
 }
}finally{await browser.close()}})().catch(e=>{console.error(e.stack);process.exit(1)});
