const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
(async()=>{
 const cfg=JSON.parse(fs.readFileSync(process.argv[2]));const token=fs.readFileSync(process.argv[3],'utf8');
 const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium_headless_shell-1193/chrome-linux/headless_shell',headless:true,env:{...process.env,LD_LIBRARY_PATH:'/home/user/workspace/brasskapelos-wp-redesign/tooling/sysroot/usr/lib/x86_64-linux-gnu'},args:['--no-sandbox']});
 try{
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:900}});page.setDefaultTimeout(6000);
   let calls=[],outside=[];
   await page.route('**/*',route=>{const u=route.request().url();if(u.startsWith(cfg.origin+'/')){calls.push(u);return route.continue()}outside.push(u);return route.abort()});
   await page.addInitScript(()=>localStorage.setItem('jarvis-space','amelie'));
   await page.goto(cfg.origin+'/jarvis/',{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>document.querySelector('#spaceSelect')?.value==='amelie');
   await page.evaluate(()=>{window.PROFILE_CHANGES=0;document.addEventListener('jarvis:spacechange',()=>window.PROFILE_CHANGES++)});
   await page.getByRole('button',{name:'Connexion missions',exact:true}).first().click();
   await page.getByLabel('Code personnel').fill(token);await page.getByRole('button',{name:'Se connecter',exact:true}).click();
   await page.locator('#hermesMissionsDialog[open]').waitFor();
   await page.getByRole('button',{name:/Terminée · DoseLab/}).click();
   await page.locator('#hermesMissionResult').filter({hasText:'synthetic://doselab/'}).waitFor();
   assert.ok((await page.locator('#hermesMissionResult').textContent()).includes('2099-01-01'));
   assert.equal(await page.evaluate(()=>window.PWNED),undefined);
   assert.match(await page.locator('#hermesMissionCanonical').textContent(),/indisponibles/);
   assert.equal(await page.locator('#spaceSelect').inputValue(),'amelie');assert.equal(await page.evaluate(()=>window.PROFILE_CHANGES),0);
   assert.equal(await page.getByRole('button',{name:'Retrouver les cellules DoseLab X4',exact:true}).isVisible(),false);
   assert.equal(await page.getByRole('button',{name:'Autoriser cette action une fois',exact:true}).count(),0);
   assert.equal(calls.some(u=>/127\.0\.0\.1:(8796|8797)/.test(u)),false);
   assert.equal(await page.evaluate(()=>localStorage.getItem('JarvisHermesSession')),null);
   const button=page.getByRole('button',{name:/En attente · DoseLab/});
   if(await button.count()){
    await button.click();await page.getByRole('button',{name:'Annuler cette mission',exact:true}).click();
    await page.locator('#hermesMissionResult').filter({hasText:'Annulée'}).waitFor();
   }
   await page.getByRole('button',{name:'Compte missions',exact:true}).click();
   await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),page.getByRole('button',{name:'Déconnexion',exact:true}).click()]);
   const status=await page.evaluate(async()=>{const r=await fetch('/api/jarvis/hermes-panel/session');return r.status});assert.equal(status,401);
   await page.close();
  }
  console.log(JSON.stringify({passed:true,desktop_and_mobile_chromium:true,real_frontend:true,visual_profile_unchanged:true,result_text_not_rewritten:true,unsafe_html_inert:true,upstream:'synthetic SQLite and real bridge',windows_started:false,model_calls:0}));
 }finally{await browser.close()}
})().catch(e=>{console.error(String(e));process.exitCode=1});
