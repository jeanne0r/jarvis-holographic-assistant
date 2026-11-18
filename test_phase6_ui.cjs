const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const assert=require('node:assert/strict');const http=require('node:http');const fs=require('node:fs/promises');const path=require('node:path');
(async()=>{
 const finalMode=process.argv.includes('--final');
 const hybrid=process.argv.includes('--hybrid'),readOnly=process.argv.includes('--read-only');
 let logged=false,created=false,cancelled=false;const posts=[];const publicRoot=path.resolve('public');
 const server=http.createServer(async(req,res)=>{try{
  const url=new URL(req.url,'http://localhost');const send=(status,body)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(body))};
  if(url.pathname.startsWith('/api/jarvis/')){
   const route=url.pathname.slice('/api/jarvis/'.length);let raw='';for await(const p of req)raw+=p;
   if(req.method==='POST')posts.push({route,body:JSON.parse(raw||'{}')});
   if(route==='session'){if(req.method==='POST')logged=true;return send(logged?200:401,logged?{subject:'synthetic-user',spaces:['user'],roles:['missions.read','missions.create','missions.cancel']}:{error:'Authentication required'})}
   if(hybrid&&route==='ask'){assert.ok(logged);created=true;return send(202,{answer:'Mission DoseLab enregistrée.',speech:'Mission DoseLab enregistrée.',sources:[],sourceIds:[],action:null,mission:{mission_id:'synthetic-mission',state:'queued'}})}
   if(route==='hermes/config')return send(200,{enabled:!readOnly,readEnabled:true,syntheticOnly:true});
   if(route==='hermes/missions'&&req.method==='POST'){created=true;return send(202,{mission_id:'synthetic-mission',state:'queued'})}
   if(route==='hermes/missions')return send(200,{items:created?[{id:'synthetic-mission',state:cancelled?'cancelled':'completed',objective:'DoseLab synthétique'}]:[]});
   if(route.endsWith('/cancel')){cancelled=true;return send(202,{state:'cancelled'})}
   if(route==='hermes/availability')return send(200,{state:'unknown',fresh:false,dispatch_allowed:false});
   if(route.endsWith('/results'))return send(200,{...(finalMode?{canonical:{schema:'canonical_metadata.v1',origin:'sqlite',selection_origin:'authenticated_host_tool_receipts',mission_id:'synthetic-mission',receipt_ids:['host-receipt'],items:[{memory_id:'memory-id',revision_id:'revision-id',source_ref:'synthetic://canonical/exact',stored_validation_status:'inferred',revision_status:'inferred',observed_utc:'2023-11-14T22:15:00Z'}]}}:{}),events:[{kind:'completed',data:JSON.stringify({output:'source.ref=synthetic://doselab/correction <img src=x onerror=window.PWNED=true>'})}]});
   if(route==='hermes/missions/synthetic-mission')return send(200,{state:'completed',definition:{objective:'DoseLab synthétique'},approvals:[{state:'pending',action:'{"description":"Revue synthétique"}'}]});
   if(route==='docs')return send(200,{docs:[],total:0,counts:{},lastSync:null});
   if(hybrid&&route==='voice/status'&&!logged)return send(401,{error:'Authentication required'});
   if(route==='voice/status')return send(200,{configured:false,engine:hybrid?'hybrid':'gemini-live'});
   if(route==='live/status')return send(200,{configured:false,engine:hybrid?'hybrid':'gemini-live'});
   return send(200,{configured:false,counts:{},index:{state:'ready'},ledger:{},state:'ready',sources:[],points:[]});
  }
  let filename=path.resolve(publicRoot,'.'+url.pathname.replace(/^\/jarvis/,''));if(url.pathname==='/jarvis/')filename=path.join(publicRoot,'index.html');
  if(!filename.startsWith(publicRoot+path.sep))throw Error('path');
  const raw=await fs.readFile(filename);res.writeHead(200,{'content-type':filename.endsWith('.js')?'application/javascript':filename.endsWith('.css')?'text/css':filename.endsWith('.html')?'text/html':'application/octet-stream'});res.end(raw);
 }catch{res.writeHead(404);res.end()}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium_headless_shell-1193/chrome-linux/headless_shell',headless:true,env:{...process.env,LD_LIBRARY_PATH:'/home/user/workspace/brasskapelos-wp-redesign/tooling/sysroot/usr/lib/x86_64-linux-gnu'},args:['--no-sandbox']});
 try{
  for(const [name,width,height]of[['desktop',1366,900],['mobile',390,844]]){
   logged=false;created=false;const page=await browser.newPage({viewport:{width,height},reducedMotion:'reduce'});
   await page.route('**/*',route=>route.request().url().startsWith(origin)?route.continue():route.abort());
   await page.goto(origin+'/jarvis/',{waitUntil:'networkidle'});
   await page.locator('#hermesMissionsButton').click();await page.getByLabel('Code personnel').fill('synthetic-session-code');await page.getByRole('button',{name:'Se connecter',exact:true}).click();
   if(readOnly){
    assert.ok(await page.getByRole('button',{name:'Retrouver les cellules DoseLab X4',exact:true}).isDisabled());
    created=true;await page.getByRole('button',{name:'Actualiser',exact:true}).click();
    await page.locator('#hermesMissionList button').first().click();
   }else if(hybrid){
    await page.waitForFunction(()=>document.querySelectorAll('script[src^="codex-voice.js"]').length===1);
    await page.evaluate(()=>document.dispatchEvent(new Event('jarvis:session-ready')));
    assert.equal(await page.locator('script[src^="codex-voice.js"]').count(),1);
    await page.locator('#hermesMissionsDialog').getByRole('button',{name:'Fermer',exact:true}).click();
    const receipt=await page.evaluate(()=>window.jarvisAsk('Jarvis, demande à Hermes de vérifier la configuration DoseLab.'));
    assert.equal(receipt.mission.state,'queued');
    await page.locator('#hermesMissionsButton').click();
    await page.getByRole('button',{name:'Actualiser',exact:true}).click();
    await page.getByRole('button',{name:/Terminée · DoseLab synthétique/}).click();
   }else await page.getByRole('button',{name:'Retrouver les cellules DoseLab X4',exact:true}).click();
   await page.waitForFunction(()=>document.querySelector('#hermesMissionResult')?.textContent.includes('synthetic://doselab/correction'));
   if(finalMode){await page.waitForFunction(()=>document.querySelector('#hermesMissionCanonical')?.textContent.includes('2023-11-14T22:15:00Z'));assert.ok((await page.locator('#hermesMissionCanonical').textContent()).includes('synthetic://canonical/exact'));assert.ok((await page.locator('#hermesWorkerAvailability').textContent()).includes('indisponible'))}
   assert.equal(await page.evaluate(()=>Boolean(window.PWNED)),false);assert.equal(await page.locator('#hermesMissionResult img').count(),0);
   assert.ok(await page.getByText('Un compte approbateur distinct est requis.').isVisible());
   assert.equal(await page.getByRole('button',{name:'Autoriser cette action une fois',exact:true}).count(),0);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await page.screenshot({path:'data/'+(finalMode?'phase6d-final':process.argv.includes('--phase6d')?'phase6d':readOnly?'phase6c':hybrid?'phase6b':'phase6')+'-ui-'+name+'.png'});
   await page.locator('#hermesMissionsDialog').getByRole('button',{name:'Fermer',exact:true}).click();
   assert.ok(await page.locator('#liveButton').isVisible());
   assert.equal(await page.evaluate(()=>Object.values(localStorage).some(v=>String(v).includes('synthetic-session-code'))),false);
   assert.equal(await page.getByLabel('Code personnel').inputValue(),'');
   await page.close();
  }
  assert.ok(posts.filter(p=>p.route==='hermes/missions').every(p=>Object.keys(p.body).join()==='template'));
  assert.equal(posts.filter(p=>p.route==='live/session'||p.route==='live/tool').length,0);
  if(readOnly)assert.equal(posts.filter(p=>p.route==='hermes/missions').length,0);
  if(hybrid)assert.equal(posts.filter(p=>p.route==='ask').length,2);
  console.log('PASS '+(readOnly?'history-only panel; ':hybrid?'hybrid window.jarvisAsk → panel; ':'')+'UI Chromium desktop/mobile: existing holographic frontend, login, async synthetic mission, source text/XSS rejection, independent approval display, no overflow, microphone remains untouched. All APIs simulated locally.');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve))}
})().catch(e=>{console.error(e);process.exit(1)});
