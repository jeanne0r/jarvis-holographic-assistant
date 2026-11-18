const {chromium,webkit}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');const assert=require('node:assert/strict');
(async()=>{const isWebkit=process.env.JARVIS_TEST_BROWSER==='webkit',engine=isWebkit?webkit:chromium;const b=await engine.launch(isWebkit?{headless:true}:{executablePath:'/home/user/.cache/ms-playwright/chromium-1193/chrome-linux/chrome',headless:true,args:['--no-sandbox']});try{
 const sizes=isWebkit?[['iphone-webkit',390,844]]:[['large',1920,1080],['4k',3840,2160],['iphone',390,844]];
 for(const [name,width,height] of sizes){const p=await b.newPage({viewport:{width,height},ignoreHTTPSErrors:true,isMobile:width<761,hasTouch:width<761});const errors=[];p.on('pageerror',e=>errors.push(e.message));const base=process.env.JARVIS_TEST_BASE||'https://192.0.2.16:8788';
 await p.goto(base+'/jarvis/',{waitUntil:'networkidle'});assert(await p.locator('#liveButton').isVisible());assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await p.screenshot({path:`/home/user/workspace/jarvis/data/reference-${name}.png`});
 await p.locator('.system-key[data-system=memory3d]').click();await p.waitForFunction(()=>document.querySelector('#map3dPoint').options.length>1,{}, {timeout:30000});
 assert(await p.locator('#memory3dCanvas').isVisible());assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 const id=await p.locator('#map3dPoint').evaluate(e=>e.options[1].value);await p.locator('#map3dPoint').selectOption(id);assert.notEqual(await p.locator('#map3dTitle').textContent(),'Chaque point vient de Qdrant.');
 await p.locator('#memory3dCanvas').focus();await p.keyboard.press('ArrowRight');await p.locator('#map3dZoomIn').click();await p.screenshot({path:`/home/user/workspace/jarvis/data/memory3d-${name}.png`,fullPage:width<761});
 if(await p.locator('#map3dSource').isVisible()){await p.locator('#map3dSource').click();await p.waitForFunction(()=>document.querySelector('#map3dSourceBody').textContent!=='Chargement de la source…');assert((await p.locator('#map3dSourceBody').textContent()).length>0);await p.locator('#map3dSourceClose').click();}
 await p.locator('#spaceSelect').selectOption('amelie');await p.waitForFunction(()=>!document.querySelector('#map3dRefresh').disabled);assert.equal(await p.locator('#map3dTitle').textContent(),'Chaque point vient de Qdrant.');assert.equal(await p.locator('#map3dSource').isVisible(),false);
 await p.locator('#map3dBack').click();assert(await p.locator('#liveButton').isVisible());assert.deepEqual(errors,[]);await p.close();console.log('PASS',name,'cockpit, no overflow, actual Qdrant 3D, point selection, source reading, space reset, return to voice.');
 }
}finally{await b.close()}})().catch(e=>{console.error(e.stack);process.exit(1)});
