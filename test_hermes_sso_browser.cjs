// Actual common login -> signed server relay -> private ACL. Synthetic data only.
const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const cfg=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium_headless_shell-1193/chrome-linux/headless_shell',headless:true,env:{...process.env,LD_LIBRARY_PATH:'/home/user/workspace/brasskapelos-wp-redesign/tooling/sysroot/usr/lib/x86_64-linux-gnu'},args:['--no-sandbox']});
 let checks=0;
 try{for(const width of [1440,390]){
  const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage();page.setDefaultTimeout(7000);
  let logins=0,privateLogins=0,exposed=0,admissions=0;
  await page.route('**/*',route=>{
   const req=route.request();if(!req.url().startsWith(cfg.origin+'/'))return route.abort();
   if(req.method()==='POST'&&req.url().endsWith('/api/jarvis/session'))logins++;
   if(req.url().includes('/hermes-panel/session'))privateLogins++;
   if(req.headers()['x-jarvis-human-assertion']||req.headers().authorization)exposed++;
   if(req.method()==='POST'&&req.url().includes('/hermes/missions'))admissions++;
   return route.continue();
  });
  await page.goto(cfg.origin+'/jarvis/');
  await page.getByRole('button',{name:'Connexion Jarvis',exact:true}).click();
  assert.equal(await page.getByLabel('Code personnel').count(),1);checks++;
  await page.getByLabel('Code personnel').fill(cfg.syntheticCredential);
  await page.getByRole('button',{name:'Se connecter',exact:true}).click();
  await page.locator('#jarvisAccountDialog').evaluate(el=>el.open?null:null);
  await page.locator('#hermesMissionsButton').filter({hasText:'Missions Hermes'}).click();
  await page.locator('#hermesMissionList button').first().waitFor();
  assert.equal(logins,1);assert.equal(privateLogins,0);assert.equal(exposed,0);assert.equal(admissions,0);checks+=4;
  const cookies=await context.cookies();assert.equal(cookies.filter(c=>c.name==='JarvisSession').length,1);assert.equal(cookies.some(c=>c.name==='JarvisHermesSession'),false);checks+=2;
  assert.equal(await page.evaluate(()=>localStorage.getItem('JarvisSession')),null);checks++;
  assert.match(await page.locator('#hermesMissionList').textContent(),/Démonstration/);checks++;
  await page.getByRole('button',{name:'Fermer',exact:true}).filter({visible:true}).first().click().catch(()=>page.locator('#hermesMissionsDialog button').first().click());
  // The general account remains available independently from the mission panel.
  await page.getByRole('button',{name:'Compte Jarvis',exact:true}).click();
  await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),page.getByRole('button',{name:'Déconnexion',exact:true}).click()]);
  const status=await page.evaluate(async()=>{const r=await fetch('/api/jarvis/hermes-panel/hermes/missions?space=user');return r.status});
  assert.equal(status,401);checks++;
  await context.close();
 }
 console.log(JSON.stringify({passed:true,checks,widths:[1440,390],single_login_real_http:true,private_passwords:0,gpu_calls:0,production_modified:false}));
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
