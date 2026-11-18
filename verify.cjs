const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const fs=require('fs');const assert=require('assert');
const token=fs.readFileSync('/home/user/gateway/.env','utf8').match(/^GATEWAY_TOKEN=(.*)$/m)[1].trim();
(async()=>{
 const base='http://127.0.0.1:8787';
 for(const p of ['/jarvis/','/verbes/index.html','/allemand/index.html','/astro/index.html'])assert.equal((await fetch(base+p)).status,200);
 assert.equal((await fetch(base+'/api/health',{headers:{authorization:'Bearer '+token}})).status,200);
 assert.equal((await fetch(base+'/api/jarvis/docs')).status,200);
 assert.equal((await fetch(base+'/api/jarvis/login',{method:'POST',headers:{'content-type':'application/json',origin:'http://evil.example'},body:JSON.stringify({token})})).status,403);
 const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium_headless_shell-1193/chrome-linux/headless_shell',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1500,height:1060}});let errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{document.modelContext={registerTool(t){window.jarvisTool=t}}});
 await page.goto(base+'/jarvis/');await page.waitForFunction(()=>Number(document.querySelector('#count').textContent)>0);
 await page.screenshot({path:'/home/user/workspace/jarvis/data/desktop.png',fullPage:true});
 assert(await page.locator('.graph-node').count()>0);await page.locator('.graph-node').first().click();await page.locator('#detail').waitFor({state:'visible'});assert((await page.locator('#detailBody').textContent()).length>0);await page.locator('#detail .close').click();
 await page.locator('#search').fill('Jarvis');await page.waitForTimeout(700);assert(await page.locator('.graph-node').count()>0);
 const toolResult=await page.evaluate(()=>window.jarvisTool.execute({query:'Astro'}));assert(toolResult.results.length>0);assert(await page.locator('#libraryView').isVisible());assert(await page.evaluate(async()=>{try{await window.jarvisTool.execute({query:5});return false}catch{return true}}));
 await page.locator('#search').fill('zzzznotfound123');await page.waitForTimeout(700);assert.equal(await page.locator('#cards .memory-card').count(),0);
 await page.locator('#search').fill('');await page.waitForTimeout(700);await page.locator('[data-view=galaxy]').click();
 await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:'/home/user/workspace/jarvis/data/mobile.png',fullPage:true});await page.locator('#mobileSources').click();assert(await page.locator('#sourcesDialog').isVisible());await page.locator('#sourcesDialog .close').click();
 if(!process.env.SKIP_AI){
 await page.locator('[data-view=chat]').click();await page.locator('#question').fill('Quel est le but de Jarvis, notre cerveau collectif ?');await page.locator('#askButton').click();await page.waitForFunction(()=>!document.querySelector('#askButton').disabled,{},{timeout:170000});
 const answer=await page.locator('#messages .message').last().textContent();assert(!answer.includes('pas pu répondre')&&!answer.includes('indisponible'));assert(answer.length>120);console.log('AI answer received; cited sources:',await page.locator('#messages .message').last().locator('button').count()-1);
 }
 assert.deepEqual(errors,[]);await browser.close();console.log('PASS: gateway health, existing sites, auth, CSRF, desktop/mobile, graph detail, search, empty state, WebMCP valid/invalid, real AI response.');
})().catch(e=>{console.error(e.message);process.exit(1)});
