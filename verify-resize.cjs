const {chromium,webkit}=require(process.env.JARVIS_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const base=process.env.JARVIS_TEST_BASE||'http://127.0.0.1:8787';
(async()=>{
 const engine=process.env.JARVIS_TEST_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch(engine===webkit?{headless:true}:{headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox','--disable-gpu']});
 try{for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000},hasTouch:true,isMobile:width===390,reducedMotion:'reduce'});
  await page.addInitScript(()=>{window.resizeTest={players:0};window.YT={Player:class{
   constructor(target,options){resizeTest.players++;this.frame=document.createElement('iframe');this.frame.srcdoc='<p>Retained video fixture</p>';target.replaceWith(this.frame);queueMicrotask(()=>options.events.onReady({target:this}));}
   playVideo(){}pauseVideo(){}setVolume(){}getPlayerState(){return 1;}
   stopVideo(){resizeTest.stopped=true;}destroy(){resizeTest.destroyed=true;this.frame.remove();}
  }};});
  await page.goto(base+'/jarvis/');
  await page.evaluate(()=>jarvisCapabilities.execute({type:'media',action:'youtube',videoId:'M7lc1UVf-VE',title:'Resize fixture'}));
  const card=page.locator('.workspace-screen[data-content=youtube]'),grip=card.locator('.workspace-resize');
  await card.locator('iframe').evaluate(el=>{el.contentWindow.retained='same-player';});
  const before=await card.evaluate(el=>({w:el.offsetWidth,h:el.offsetHeight}));
  await grip.scrollIntoViewIfNeeded();const rect=await grip.boundingBox();
  await page.mouse.move(rect.x+20,rect.y+20);await page.mouse.down();await page.mouse.move(rect.x+110,rect.y+100,{steps:6});await page.mouse.up();
  const after=await card.evaluate(el=>({w:el.offsetWidth,h:el.offsetHeight}));
  assert(after.w>before.w+40);assert(after.h>before.h+30);
  assert.equal(await card.locator('iframe').evaluate(el=>el.contentWindow.retained),'same-player');
  await page.keyboard.press('Tab');await grip.focus();await grip.press('Home');
  assert(!(await card.evaluate(el=>el.classList.contains('workspace-sized'))));
  await grip.press('ArrowRight');const keyWidth=await card.evaluate(el=>el.offsetWidth);await grip.press('Shift+ArrowRight');assert.equal(await card.evaluate(el=>el.offsetWidth),Math.min(width-16,keyWidth+40));
  if(engine===chromium&&width===390){
   await grip.press('Home');await grip.press('ArrowRight');await page.evaluate(()=>document.activeElement?.blur());await grip.scrollIntoViewIfNeeded();const r=await grip.boundingBox(),session=await page.context().newCDPSession(page),x=r.x+r.width/2,y=r.y+r.height/2;
   await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y,force:1,radiusX:1,radiusY:1}]});await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x+55,y:Math.min(y+30,985),force:1,radiusX:1,radiusY:1}]});await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
   assert(await card.evaluate(el=>el.classList.contains('workspace-sized')));
  }
  await page.evaluate(()=>{visualViewport.dispatchEvent(new Event('resize'));});
  assert(await card.evaluate(el=>el.offsetWidth<=innerWidth-16&&el.offsetHeight<=innerHeight-16));
  if(width===390){await card.locator('.workspace-preview').tap();await page.locator('.content-minimize').tap();}else{await card.locator('.workspace-preview').click();await page.locator('.content-minimize').click();}
  assert.equal(await card.locator('iframe').evaluate(el=>el.contentWindow.retained),'same-player');
  assert.equal(await page.evaluate(()=>resizeTest.players),1);
  if(width===390)await card.locator('.workspace-dismiss').tap();else await card.locator('.workspace-dismiss').click();await page.waitForFunction(()=>resizeTest.stopped&&resizeTest.destroyed);
  console.log('PASS resize: mouse/touch, two axes, keyboard/reset, viewport bounds, retained iframe, enlarge/reduce and stop-on-close',engine.name(),width);
  await page.close();
 }}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
