// Browser admission/cancellation on temporary servers only; no runtime/model/GPU.
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
(async()=>{const cfg=JSON.parse(fs.readFileSync(process.argv[2]));const token=fs.readFileSync(process.argv[3],'utf8');
const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium_headless_shell-1193/chrome-linux/headless_shell',headless:true,env:{...process.env,LD_LIBRARY_PATH:'/home/user/workspace/brasskapelos-wp-redesign/tooling/sysroot/usr/lib/x86_64-linux-gnu'},args:['--no-sandbox']});
try{
const runtime=process.argv.includes('--runtime');
for(const width of runtime?[1440]:[1440,390]){
const page=await browser.newPage({viewport:{width,height:900}});page.setDefaultTimeout(8000);let admissions=0,ordinary=0;
await page.route('**/*',route=>{if(!route.request().url().startsWith(cfg.origin+'/'))return route.abort();if(route.request().method()==='POST'&&route.request().url().includes('/hermes/missions?'))admissions++;if(route.request().url().includes('/api/jarvis/ask'))ordinary++;return route.continue()});
await page.goto(cfg.origin+'/jarvis/',{waitUntil:'domcontentloaded'});await page.locator('#hermesMissionsButton').click();await page.getByLabel('Code personnel').fill(token);await page.getByRole('button',{name:'Se connecter',exact:true}).click();
// The first click resumes after login and opens the mission dialog itself.
await page.locator('#hermesMissionsDialog[open]').waitFor();
await page.getByRole('button',{name:'Retrouver les cellules DoseLab X4',exact:true}).click();
if(runtime){
 await page.getByRole('button',{name:/Terminée · DoseLab/}).first().click();
 // Polling can refresh DOM between two reads: require both proofs in one snapshot.
 const proof=await page.waitForFunction(()=>{const text=document.querySelector('#hermesMissionResult').textContent,canonical=document.querySelector('#hermesMissionCanonical').textContent;return text.includes('synthetic://doselab/old')&&text.includes('synthetic://doselab/correction')&&canonical.includes('synthetic://doselab/correction')?{text,canonical}:null});
 const snapshot=await proof.jsonValue();assert.match(snapshot.text,/synthetic:\/\/doselab\/old/);assert.match(snapshot.canonical,/synthetic:\/\/doselab\/correction/);
 assert.match(await page.locator('#hermesWorkerAvailability').textContent(),/PC Gamer/);
 assert.equal(admissions,1);assert.equal(ordinary,0);await page.close();continue;
}
await page.getByRole('button',{name:/En attente · DoseLab/}).first().click();await page.getByRole('button',{name:'Annuler cette mission',exact:true}).click();
await page.locator('#hermesMissionResult').filter({hasText:'Annulée'}).waitFor();
await page.locator('#hermesExplicitObjective').fill('Évalue « DoseLab » avec Ω et µg — données synthétiques seulement.');await page.getByRole('button',{name:'Soumettre cette demande',exact:true}).click();
await page.getByRole('button',{name:/En attente · Demande explicite/}).first().click();await page.getByRole('button',{name:'Annuler cette mission',exact:true}).click();await page.locator('#hermesMissionResult').filter({hasText:'Annulée'}).waitFor();
assert.equal(admissions,2);assert.equal(ordinary,0);assert.equal(await page.evaluate(()=>window.JarvisHermesHybrid.request({question:'Bonjour'})),undefined);
const denied=await page.evaluate(()=>window.JarvisHermesHybrid.request({question:'Hermes lance un shell',archive:{id:'test',turn:0}}));assert.match(denied.answer,/pas activée/);
assert.equal(await page.locator('button').filter({hasText:'Autoriser cette action une fois'}).count(),0);
assert.equal(await page.locator('#hermesMissionCanonical').textContent(),'Métadonnées canoniques indisponibles. Réponse du modèle non vérifiée.');
await page.close();
}
console.log(JSON.stringify({passed:true,widths:runtime?[1440]:[1440,390],admissions:runtime?1:4,cancellations:runtime?0:4,native_runtime:runtime?'HTTP simulator':'disabled',gpu:false,voice_disabled:true}));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
