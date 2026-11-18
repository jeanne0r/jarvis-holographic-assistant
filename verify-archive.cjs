const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium-1193/chrome-linux/chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage();let offline=true;const records=[];const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/jarvis/conversations/record?*',route=>{records.push(route.request().postDataJSON());return route.fulfill({status:offline?503:200,contentType:'application/json',body:JSON.stringify(offline?{error:'offline'}:{saved:true})});});
  await page.route('**/api/jarvis/ask?*',route=>{
   assert.match(route.request().postDataJSON().archive.id,/^[0-9a-f-]{36}$/);
   return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({answer:'Réponse de vérification.',sources:[],action:null})});
  });
  await page.goto('http://192.0.2.16:8787/jarvis/');
  await page.locator('[data-view=chat]').click();await page.locator('#question').fill('Bonjour, vérification de la mémoire écrite.');await page.locator('#question').press('Enter');
  await page.waitForFunction(()=>document.querySelector('#messages').textContent.includes('Réponse de vérification.'));
  await page.waitForFunction(()=>document.querySelector('#archiveStatus').textContent.includes('réessayer'));
  const queued=await page.evaluate(()=>JSON.parse(localStorage.getItem('jarvis-conversations-pending-v1')));
  assert.equal(queued.length,1);assert.equal(queued[0][1].assistant,'Réponse de vérification.');assert.equal(queued[0][1].space,'user');
  const id=queued[0][1].id;offline=false;await page.reload();
  await page.waitForFunction(()=>JSON.parse(localStorage.getItem('jarvis-conversations-pending-v1')||'[]').length===0);
  assert(records.some(r=>r.id===id&&r.revision===2&&r.assistant==='Réponse de vérification.'));
  offline=true;
  await page.evaluate(()=>{window.jarvisArchive.written('user','Mot de passe : fixture-secret-123','amelie');window.jarvisArchive.written('assistant','API key: fixture-key-456','amelie');});
  const privateQueue=await page.evaluate(()=>localStorage.getItem('jarvis-conversations-pending-v1'));
  assert(!privateQueue.includes('fixture-secret-123'));assert(!privateQueue.includes('fixture-key-456'));assert(privateQueue.includes('amelie'));
  assert.deepEqual(errors,[]);
  console.log('PASS: Enter archives written exchange on LAN HTTP, durable retry after reload, stable IDs, per-person scope, secrets redacted before browser storage.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
