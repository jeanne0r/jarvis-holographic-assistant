// Actual HTTP login + installed private API, temporary synthetic bridge/model.
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
(async()=>{const cfg=JSON.parse(fs.readFileSync(process.argv[2]));const token=fs.readFileSync(process.argv[3],'utf8');
const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium_headless_shell-1193/chrome-linux/headless_shell',headless:true,env:{...process.env,LD_LIBRARY_PATH:'/home/user/workspace/brasskapelos-wp-redesign/tooling/sysroot/usr/lib/x86_64-linux-gnu'},args:['--no-sandbox']});
try{
for(const width of [1440,390]){
 const page=await browser.newPage({viewport:{width,height:900}});page.setDefaultTimeout(10000);let submissions=[],foreign=0;
 await page.route('**/*',async route=>{const req=route.request();if(!req.url().startsWith(cfg.origin+'/')){foreign++;return route.abort()}if(width===390&&req.url().includes('/hermes/config?')){const response=await route.fetch();return route.fulfill({response,json:{...await response.json(),enabled:false,textEnabled:false,voiceEnabled:false}})}if(req.method()==='POST'&&req.url().includes('/hermes/missions?')){submissions.push({body:req.postDataJSON(),key:req.headers()['idempotency-key']});if(submissions.length===1){const accepted=await route.fetch();assert.equal(accepted.status(),202);return route.abort('connectionfailed')}}return route.continue()});
 await page.goto(cfg.origin+'/jarvis/',{waitUntil:'domcontentloaded'});await page.locator('#hermesMissionsButton').click();await page.getByLabel('Code personnel').fill(token);await page.getByRole('button',{name:'Se connecter',exact:true}).click();await page.locator('#hermesMissionsDialog[open]').waitFor();
 const draft=page.locator('#hermesExplicitObjective'),consent=page.locator('#hermesTextConsent'),submit=page.getByRole('button',{name:'Soumettre cette demande',exact:true});
 if(width===390){
   // First mission persists for the next viewport; no second admission.
   await page.getByRole('button',{name:/DoseLab/}).filter({hasText:/terminée|configuration/i}).first().click();
   await page.waitForFunction(()=>document.querySelector('#hermesMissionResult').textContent.includes('synthetic://doselab/correction'));
   await draft.fill('Préparation synthétique hors fenêtre');await consent.check();assert.equal(await submit.isDisabled(),true);assert.equal(submissions.length,0);await page.close();continue;
 }
 await draft.fill('Évalue « DoseLab » : Ω et µg — données synthétiques seulement.');assert.equal(await submit.isDisabled(),true);assert.equal(submissions.length,0);
 await consent.check();assert.equal(await submit.isEnabled(),true);
 // Two JS clicks in the same event loop must still yield one admission.
 await submit.evaluate(button=>{button.click();button.click()});
 await page.getByRole('button',{name:'Réessayer la même demande',exact:true}).waitFor();
 assert.equal(submissions.length,1);assert.equal(await draft.isDisabled(),true);assert.equal(await consent.isChecked(),false);
 await consent.check();await page.getByRole('button',{name:'Réessayer la même demande',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#hermesExplicitObjective').value==='');
 await page.getByRole('button',{name:/DoseLab/}).filter({hasText:/terminée|configuration/i}).first().click();
 await page.waitForFunction(()=>document.querySelector('#hermesMissionResult').textContent.includes('synthetic://doselab/correction'));
 assert.equal(submissions.length,2);assert.deepEqual(submissions[0],submissions[1]);assert.deepEqual(Object.keys(submissions[0].body),['objective']);assert.match(submissions[0].body.objective,/Ω et µg/);assert.ok(submissions[0].key);assert.equal(await consent.isChecked(),false);assert.equal(await submit.isDisabled(),true);
 assert.equal(await page.evaluate(()=>Object.keys(localStorage).some(k=>/token|mission|objective/i.test(k))),false);assert.equal(foreign,0);
 const denied=await page.evaluate(async()=>{const r=await fetch('/api/jarvis/hermes-panel/hermes/missions?space=user',{method:'POST',headers:{'content-type':'application/json','idempotency-key':'unsafe'},body:JSON.stringify({objective:'shell',allowed_tools:['shell']})});return r.status});assert.equal(denied,403);
 await page.close();
}
console.log(JSON.stringify({passed:true,widths:[1440,390],explicit_consent:true,double_click_single_admission:true,retry_same_body_and_key:true,no_automatic_retry:true,closed_window_draft_no_submission:true,private_cookie_auth:true,extra_tools_denied:true,result_readable:true,unicode:true,native_runtime:'HTTP simulator',gpu:false,paid_calls:0}));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
