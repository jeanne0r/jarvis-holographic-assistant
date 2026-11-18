const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');const fs=require('fs'),assert=require('assert');
const token=fs.readFileSync('/home/user/gateway/.env','utf8').match(/^GATEWAY_TOKEN=(.*)$/m)[1].trim();
(async()=>{const base='http://127.0.0.1:8787';const headers={authorization:'Bearer '+token,'content-type':'application/json'};
assert.equal((await fetch(base+'/api/health',{headers})).status,200);
const docs=await (await fetch(base+'/api/jarvis/docs?space=user',{headers})).json();const id=docs.docs[0].id;
assert.equal((await fetch(base+'/api/jarvis/doc?space=amelie&id='+encodeURIComponent(id),{headers})).status,404);
const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium_headless_shell-1193/chrome-linux/headless_shell',args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1400,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{await page.goto(base+'/jarvis/');await page.waitForFunction(()=>Number(document.querySelector('#count').textContent)>0);
await page.locator('#spaceSelect').selectOption('amelie');await page.waitForFunction(()=>document.querySelector('#count').textContent==='0');assert.equal(await page.locator('.graph-node').count(),0);await page.reload();assert.equal(await page.locator('#spaceSelect').inputValue(),'amelie');
await page.locator('#spaceSelect').selectOption('user');await page.waitForFunction(()=>Number(document.querySelector('#count').textContent)>0);
await page.locator('#recent .memory-card').first().click();await page.locator('#detail').waitFor({state:'visible'});await page.locator('#moveTarget').selectOption('amelie');await page.locator('#moveForm button').click();await page.locator('#detail').waitFor({state:'hidden'});await page.locator('#spaceSelect').selectOption('amelie');await page.waitForFunction(()=>document.querySelector('#count').textContent==='1');
await page.setViewportSize({width:390,height:844});assert(await page.locator('#spaceSelect').isVisible());assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:'/home/user/workspace/jarvis/data/spaces-mobile.png',fullPage:true});
await page.locator('#recent .memory-card').first().click();await page.locator('#moveTarget').selectOption('user');await page.locator('#moveForm button').click();await page.locator('#detail').waitFor({state:'hidden'});await page.waitForFunction(()=>document.querySelector('#count').textContent==='0');assert.deepEqual(errors,[]);
console.log('PASS: gateway health, scoped API details, switching, empty space, saved selection, moving out/back, mobile layout.');
}finally{await fetch(base+'/api/jarvis/move?space=amelie',{method:'POST',headers,body:JSON.stringify({id,target:'user'})});await browser.close()}
})().catch(e=>{console.error(e.message);process.exit(1)});
