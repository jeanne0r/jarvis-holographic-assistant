// Isolated DOM + HTTP browser tests, all API responses synthetic. No active gateway.
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
(async()=>{
 const root=path.join(__dirname,'data/big-boss/lot-a-ready');
 const server=http.createServer((req,res)=>{const name=req.url.slice(1);if(['hermes-embedded.js','hermes-embedded.css'].includes(name)){res.setHeader('Content-Type',name.endsWith('css')?'text/css; charset=utf-8':'application/javascript; charset=utf-8');res.end(fs.readFileSync(path.join(root,name)));return}res.setHeader('Content-Type','text/html; charset=utf-8');res.end('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><div class="header-actions"></div><link rel="stylesheet" href="/hermes-embedded.css"><script defer src="/hermes-embedded.js"></script>')});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:'/home/user/.cache/ms-playwright/chromium_headless_shell-1193/chrome-linux/headless_shell',headless:true,env:{...process.env,LD_LIBRARY_PATH:'/home/user/workspace/brasskapelos-wp-redesign/tooling/sysroot/usr/lib/x86_64-linux-gnu'},args:['--no-sandbox']});
 let checks=0;
 try{
 for(const unified of [false,true])for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:900}});page.setDefaultTimeout(6000);
  let logged=false,enabled=false,denied=false,posts=[],external=[],apiPaths=[],holdResults=false,releaseResult;let reached;const waitingResult=new Promise(resolve=>reached=resolve);
  const identity={subject:'synthetic-human',spaces:['user'],roles:['missions.read','missions.cancel','missions.create']};
  const output='**Configuration actuelle**\n\n| Composant | Capacité |\n| --- | --- |\n| Cellules | 4 × 1 kg |\n\n- Vérifier les mesures\n\n```js\nconst valeur = "µg Ω é";\n```\n<img src=x onerror="window.PWNED=1">\n[attaque](javascript:alert(1))\n[documentation](https://example.org/test)\nSource : `synthetic://doselab/correction`';
  const items=[{id:'done',state:'completed',objective:'DoseLab X4 synthétique : retrouve les cellules',created:1700000000,updated:1700000065},{id:'active',state:'queued',objective:'DoseLab X4 synthétique : vérification',created:1700000100},{id:'failed',state:'failed',objective:'DoseLab synthétique : échec',created:1699999999},{id:'cancelled',state:'cancelled',objective:'DoseLab synthétique : annulée',created:1699999998}];
  await page.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url());if(url.origin!==origin){external.push(url.href);return route.abort()}
   if(!url.pathname.startsWith('/api/')){if(unified&&url.pathname==='/hermes-embedded.js')return route.fulfill({contentType:'application/javascript; charset=utf-8',body:fs.readFileSync(path.join(__dirname,'data/big-boss/lot-b-single-session/hermes-embedded.js'),'utf8')});return route.continue()}
   const sub=url.pathname.replace(unified?'/api/jarvis/':'/api/jarvis/hermes-panel/',''),method=request.method();
   const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
   apiPaths.push(sub);
   const wasHeld=sub.endsWith('/results')&&holdResults&&logged&&!denied;
   if(wasHeld){await new Promise(resolve=>{releaseResult=resolve;reached()})}
   if(method==='POST')posts.push({sub,body:request.postDataJSON()});
   if(sub==='session'){
    if(method==='POST'){logged=true;return reply(identity)}
    if(method==='DELETE'){logged=false;return reply({signedOut:true})}
    return logged?reply(identity):reply({error:'denied'},401);
   }
   if((!logged||denied)&&!wasHeld)return reply({error:'Panel denied or unavailable'},denied||401);
   if(sub==='hermes/config')return reply({enabled,readEnabled:true,textEnabled:false,voiceEnabled:false,syntheticOnly:true});
   if(sub==='hermes/availability')return reply({fresh:false,state:'unavailable',reason:'disabled'});
   if(sub==='hermes/missions')return method==='POST'?reply({mission_id:'active'},202):reply({items});
   if(sub.endsWith('/cancel')){items.find(v=>v.id==='active').state='cancelled';return reply({state:'cancelled'})}
   if(sub.endsWith('/results'))return reply({events:[{kind:'completed',data:JSON.stringify({output})}],canonical:{schema:'canonical_metadata.v1',origin:'sqlite',mission_id:url.pathname.split('/').at(-2),selection_origin:'authenticated_host_tool_receipts',receipt_ids:['receipt'],items:[{memory_id:'stable-memory',revision_id:'revision',source_ref:'synthetic://doselab/correction',stored_validation_status:'user_confirmed',revision_status:'user_confirmed',observed_utc:'2023-11-14T22:15:00Z'}]}});
   return reply({...items.find(v=>sub.endsWith('/'+v.id)),definition:{objective:'Objectif original intégral'}});
  });
  await page.goto(origin);
  await page.waitForFunction(()=>!!window.JarvisMissionView);
  const safe=await page.evaluate(()=>{
   const examples=['<svg onload=alert(1)>','[x](data:text/html,evil)','[x](javascript:alert%281%29)','**<img src=x onerror=alert(1)>**','`<script>evil</script>`'];
   return examples.every(text=>{const rendered=JarvisMissionView.markdown(text);return !rendered.querySelector('script,img,svg,iframe,a')});
  });assert.equal(safe,true);checks++;
  assert.equal(await page.evaluate(()=>JarvisMissionView.timing({created:'invalid',updated:2,state:'completed'})),'Date non fournie');checks++;
await page.getByRole('button',{name:'Connexion missions',exact:true}).first().click();
  await page.getByLabel('Code personnel').fill('synthetic-only-not-a-real-secret');await page.getByRole('button',{name:'Se connecter',exact:true}).click();
  await page.locator('#hermesMissionsDialog[open]').waitFor();await page.locator('#hermesMissionList button').first().waitFor();
  assert.equal(await page.locator('#hermesMissionList button').count(),2);assert.equal(await page.locator('#hermesMissionList button').first().getAttribute('data-state'),'queued');checks+=2;
  assert.equal(await page.getByRole('button',{name:'Retrouver les cellules DoseLab X4',exact:true}).isVisible(),false);checks++;
  await page.locator('#hermesMissionList button[data-state=completed]').click();await page.locator('#hermesMissionResult table').waitFor();
  assert.equal(await page.locator('#hermesMissionResult strong').textContent(),'Configuration actuelle');
  assert.equal(await page.locator('#hermesMissionResult img, #hermesMissionResult script, #hermesMissionResult a[href^="javascript:"]').count(),0);assert.equal(await page.evaluate(()=>window.PWNED),undefined);checks+=3;
  assert.match(await page.locator('#hermesMissionResult pre code').textContent(),/µg Ω é/);
  assert.equal(await page.locator('#hermesSourcesDetails').getAttribute('open'),null);
  assert.match(await page.locator('#hermesMissionCanonical').textContent(),/synthetic:\/\/doselab\/correction/);
  assert.equal(await page.locator('#hermesMissionObjective').textContent(),'Objectif original intégral');
  assert.match(await page.locator('#hermesOriginalResult').textContent(),/synthetic:\/\/doselab\/correction/);
  await page.locator('#hermesMissionResult').getByRole('button',{name:'Source liée'}).click();
  assert.equal(await page.locator('#hermesSourcesDetails').getAttribute('open'),'');
  await page.locator('#hermesSourcesDetails summary').click();checks+=6;
  await page.getByLabel('Masquer les démonstrations').check();await page.waitForFunction(()=>document.querySelector('#hermesMissionList').textContent.includes('Aucune mission dans cette vue'));
  await page.getByLabel('Masquer les démonstrations').uncheck();await page.getByLabel('Tout l’historique').check();await page.waitForFunction(()=>document.querySelectorAll('#hermesMissionList button').length===4);checks++;
  enabled=true;await page.getByRole('button',{name:'Actualiser',exact:true}).click();await page.getByRole('button',{name:'Retrouver les cellules DoseLab X4',exact:true}).waitFor();
  assert.equal(posts.filter(v=>v.sub==='hermes/missions').length,0);
  if(unified)assert.equal(await page.locator('#hermesMissionsDialog #jarvisAccountButton').count(),0);checks++;
  await page.locator('#hermesMissionList button[data-state=queued]').click();await page.getByRole('button',{name:'Annuler cette mission',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#hermesMissionList button[data-state=queued]'));
  assert.equal(posts.filter(v=>v.sub.endsWith('/cancel')).length,1);checks++;
  assert.equal(await page.locator('#hermesMissionsDialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);checks++;
  assert.equal(await page.locator('#hermesMissionResult').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);checks++;
  if(width===390&&!unified)await page.screenshot({path:path.join(root,'mobile.png'),fullPage:true});
  holdResults=true;await page.locator('#hermesMissionList button[data-state=completed]').click();await waitingResult;
  denied=width===390?403:401;await page.getByRole('button',{name:'Actualiser',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#hermesMissionList').textContent==='');
  releaseResult();await page.waitForTimeout(100);
  assert.equal(await page.locator('#hermesMissionResult').textContent(),'');assert.equal(await page.locator('#hermesMissionCanonical').textContent(),'');
  assert.equal(await page.locator('#hermesMissionObjective').textContent(),'');assert.equal(await page.locator('#hermesMissionEvents').textContent(),'');checks+=4;
  assert.equal(apiPaths.some(value=>/(^|\/)(voice|live|ask)(\/|$)/.test(value)),false);checks++;
  assert.equal(external.length,0);assert.equal(await page.evaluate(()=>localStorage.getItem('JarvisHermesSession')),null);checks+=2;
  await page.close();
 }
 console.log(JSON.stringify({passed:true,checks,widths:[1440,390],api:'simulated',auth_modes:['existing-private','shared-session-laboratory'],model_calls:0,production_modified:false}));
 }finally{await browser.close();await new Promise(r=>server.close(r))}
})().catch(error=>{console.error(error);process.exitCode=1});
