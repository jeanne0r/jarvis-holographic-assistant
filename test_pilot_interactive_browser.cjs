// Existing panel/login in a real browser, against a temporary synthetic service.
let stage='start';
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
(async()=>{const cfg=JSON.parse(fs.readFileSync(process.argv[2]));const token=fs.readFileSync(process.argv[3],'utf8');
 const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium_headless_shell-1193/chrome-linux/headless_shell',headless:true,env:{...process.env,LD_LIBRARY_PATH:'/home/user/workspace/brasskapelos-wp-redesign/tooling/sysroot/usr/lib/x86_64-linux-gnu'},args:['--no-sandbox']});
 try{const page=await browser.newPage();page.setDefaultTimeout(4000);page.on('response',r=>{if(r.url().includes('/api/'))console.log(JSON.stringify({path:new URL(r.url()).pathname,status:r.status()}))});await page.route('**/*',r=>r.request().url().startsWith(cfg.origin+'/')?r.continue():r.abort());await page.goto(cfg.origin,{waitUntil:'domcontentloaded'});
 stage='login-open';await page.getByRole('button',{name:'Connexion Jarvis',exact:true}).first().click();await page.getByLabel('Code personnel').fill(token);await page.getByRole('button',{name:'Se connecter',exact:true}).click();stage='panel-open';await page.getByRole('button',{name:'Missions Hermes',exact:true}).click();
 stage='admit';await page.getByRole('button',{name:'Retrouver les cellules DoseLab X4',exact:true}).click();await page.locator('#hermesMissionResult').filter({hasText:'En attente'}).waitFor();assert.ok((await page.locator('#hermesMissionResult').textContent()).includes('DoseLab'));
 assert.equal(await page.getByRole('button',{name:'Autoriser cette action une fois',exact:true}).count(),0);
 console.log(JSON.stringify({passed:true,real_browser_panel:true,mission_queued_only:true,windows_started:false,model_calls:0}));
 }finally{await browser.close()}})().catch(()=>{console.error('Browser acceptance failed at '+stage+'; no provider invoked.');process.exitCode=1});
