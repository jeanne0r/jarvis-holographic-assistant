// Standalone login, deliberately without Hermes UI and without any live backend.
const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs/promises');
(async()=>{
 let logged=false;const server=http.createServer(async(req,res)=>{
  if(req.url==='/jarvis-auth.js'){res.setHeader('content-type','application/javascript; charset=utf-8');return res.end(await fs.readFile('public/jarvis-auth.js'))}
  if(req.url==='/api/jarvis/session'){
   let raw='';for await(const p of req)raw+=p;
   if(req.method==='POST'){assert.equal(JSON.parse(raw).token,'synthetic-session-code');logged=true}
   if(req.method==='DELETE')logged=false;
   res.writeHead(logged||req.method==='DELETE'?200:401,{'content-type':'application/json'});
   return res.end(JSON.stringify(logged?{subject:'alice',spaces:['user'],roles:['voice']}:{signedOut:true}))
  }
  res.setHeader('content-type','text/html; charset=utf-8');res.end('<!doctype html><meta name="viewport" content="width=device-width"><body><button id="liveButton">Micro existant</button><script>window.readyCount=0;document.addEventListener("jarvis:session-ready",()=>readyCount++)</script><script src="/jarvis-auth.js"></script></body>')
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium_headless_shell-1193/chrome-linux/headless_shell',headless:true,env:{...process.env,LD_LIBRARY_PATH:'/home/user/workspace/brasskapelos-wp-redesign/tooling/sysroot/usr/lib/x86_64-linux-gnu'},args:['--no-sandbox']});
 try{for(const width of [1366,390]){
  logged=false;const page=await browser.newPage({viewport:{width,height:844}});await page.route('**/*',r=>r.request().url().startsWith(origin)?r.continue():r.abort());
  await page.goto(origin);await page.locator('#jarvisAccountButton').click();await page.getByLabel('Code personnel').fill('synthetic-session-code');await page.getByRole('button',{name:'Se connecter',exact:true}).click();
  await page.waitForFunction(()=>JarvisAuth.identity()?.subject==='alice'&&!document.querySelector('#jarvisAccountDialog').open);assert.equal(await page.evaluate(()=>readyCount),1);
  assert.equal(await page.locator('#hermesMissionsDialog').count(),0);assert.ok(await page.locator('#liveButton').isVisible());
  assert.equal(await page.getByLabel('Code personnel').inputValue(),'');assert.equal(await page.evaluate(()=>Object.values(localStorage).some(x=>x.includes('synthetic-session-code'))),false);
  await page.locator('#jarvisAccountButton').click();await page.getByRole('button',{name:'Déconnexion',exact:true}).click();await page.waitForFunction(()=>window.JarvisAuth?.identity()===null);await page.close();
 }}finally{await browser.close();await new Promise(r=>server.close(r))}
 console.log(JSON.stringify({passed:true,standalone_auth_without_hermes:true,desktop_mobile:true,secret_not_persisted:true,real_provider_calls:0}));
})().catch(e=>{console.error(e);process.exit(1)});
