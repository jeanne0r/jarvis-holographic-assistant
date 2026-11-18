const {chromium}=require(process.env.PLAYWRIGHT||'/home/user/tooling/browser/node_modules/playwright');const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch();const errors=[];const out=(process.env.SHOTS||'/tmp/hermes-shots')+'/';require('node:fs').mkdirSync(out,{recursive:true});
try{
 const page=await b.newPage({viewport:{width:1440,height:900}});page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 await page.goto('http://127.0.0.1:18790/jarvis/');
 await page.locator('#hermesMissionsButton').click();await page.getByLabel('Code personnel').fill('demo');await page.getByRole('button',{name:'Se connecter'}).click();
 await page.locator('#hermesMissionsDialog[open]').waitFor();await page.waitForTimeout(600);
 await page.screenshot({path:out+'1-ouverture.png'});
 // done tab, open completed mission
 await page.getByRole('tab',{name:/Terminées/}).click();await page.locator('.hermes-card',{hasText:'configuration actuelle'}).click();
 await page.waitForFunction(()=>document.querySelector('#hermesMissionResult').textContent.includes('4 cellules'));await page.waitForTimeout(300);
 assert.match(await page.locator('#hermesResultWarning').textContent(),/1 compte rendu de mission non vérifié/);
 assert.equal(await page.locator('.hermes-source').count(),4);
 // real-source mission: measurement chips and banner
 await page.locator('.hermes-card',{hasText:'recalibrer le dosage du VSV'}).click();
 await page.waitForFunction(()=>document.querySelector('#hermesMissionResult').textContent.includes('36,2 mL'));
 assert.match(await page.locator('#hermesResultWarning').textContent(),/2 lectures réelles/);
 const chips=await page.locator('#hermesMissionResult .hermes-source-link').allTextContents();
 assert.ok(chips.includes('HA sensor.vsv_dosage · 168h')&&chips.includes('Influx sensor.vsv_dosage · 90d'),JSON.stringify(chips));
 await page.screenshot({path:out+'2c-reel.png'});
 await page.getByRole('tab',{name:/Terminées/}).click();await page.locator('.hermes-card',{hasText:'configuration actuelle'}).click();await page.waitForTimeout(300);
 await page.screenshot({path:out+'2-detail.png'});await page.screenshot({path:out+'2b-detail-full.png',fullPage:false});
 await page.locator('.hermes-source-link').first().click();await page.waitForTimeout(500);await page.screenshot({path:out+'3-source.png'});
 // archive
 await page.locator('.hermes-actions').getByRole('button',{name:'Archiver',exact:true}).click();
 assert.equal(await page.locator('#hermesMissionList .hermes-card',{hasText:'configuration actuelle'}).count(),0);
 await page.getByRole('tab',{name:/Archivées/}).click();assert.equal(await page.locator('#hermesMissionList .hermes-card').count(),1);
 await page.screenshot({path:out+'4-archivees.png'});
 await page.locator('.hermes-actions').getByRole('button',{name:'Restaurer dans la liste'}).click();assert.equal(await page.locator('#hermesMissionList .hermes-card').count(),0);
 // duplicate warning + submit
 await page.getByRole('tab',{name:/En cours/}).click();
 await page.getByLabel('Décrire une mission').fill('Quelles sont les capacités actuelles des cellules de charge du DoseLab X4, et ont-elles changé ?');
 assert.match(await page.locator('.hermes-duplicate').textContent(),/identique existe déjà/);await page.screenshot({path:out+'5-doublon.png'});
 const submit=page.getByRole('button',{name:'Confier à Hermes'});
 await page.getByLabel('Décrire une mission').fill('');assert.equal(await submit.isDisabled(),true);
 await page.getByLabel('Décrire une mission').fill('Résume les révisions DoseLab de novembre.');
 assert.equal(await page.locator('.hermes-duplicate').isHidden(),true);
 assert.equal(await page.locator('#hermesMissionsDialog input[type=checkbox]#hermesTextConsent').count(),0);   // 17.11: no consent box
 assert.match(await page.locator('#hermesReadOnlyNotice').textContent(),/ne commande jamais rien/);
 assert.equal(await submit.isDisabled(),false);await submit.click();
 await page.waitForFunction(()=>document.querySelector('.hermes-detail-head h3').textContent==='Résume les révisions DoseLab de novembre.');
 assert.match(await page.locator('#hermesMissionNotice').textContent(),/enregistrée/);
 await page.screenshot({path:out+'6-envoi.png'});
 // cancel running
 page.once('dialog',d=>d.accept());await page.locator('.hermes-card',{hasText:'Compare les deux'}).click();await page.getByRole('button',{name:'Annuler la mission'}).click();
 await page.waitForTimeout(800);
 // failed mission
 await page.getByRole('tab',{name:/Toutes/}).click();await page.locator('.hermes-card',{hasText:'tentative du 16.11'}).click();await page.waitForTimeout(400);await page.screenshot({path:out+'7-echec.png'});
 assert.equal(await page.evaluate(()=>document.querySelectorAll('#hermesMissionsDialog [style*="javascript"]').length),0);
 await page.close();
 // mobile
 const m=await b.newPage({viewport:{width:390,height:844}});m.on('pageerror',e=>errors.push(String(e)));
 await m.goto('http://127.0.0.1:18790/jarvis/');await m.locator('#hermesMissionsButton').click();
 if(await m.getByLabel('Code personnel').isVisible()){await m.getByLabel('Code personnel').fill('demo');await m.getByRole('button',{name:'Se connecter'}).click()}
 await m.locator('#hermesMissionsDialog[open]').waitFor();await m.waitForTimeout(600);await m.screenshot({path:out+'8-mobile-liste.png'});
 await m.getByRole('tab',{name:/Terminées/}).click();await m.locator('.hermes-card').first().click();await m.waitForTimeout(700);await m.screenshot({path:out+'9-mobile-detail.png'});
 assert.equal(await m.locator('.hermes-side').isHidden(),true);await m.getByRole('button',{name:'← Missions'}).click();assert.equal(await m.locator('.hermes-side').isVisible(),true);
 const overflow=await m.evaluate(()=>document.documentElement.scrollWidth>innerWidth);assert.equal(overflow,false);
 console.log(JSON.stringify({passed:true,errors}));
}catch(e){console.log('FAIL',e.message.slice(0,500),JSON.stringify(errors))}finally{await b.close()}})();
