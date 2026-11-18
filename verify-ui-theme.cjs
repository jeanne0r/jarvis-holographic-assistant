const {webkit}=require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const assert=require('node:assert/strict');
const base=process.env.JARVIS_TEST_BASE||'http://127.0.0.1:8787';
(async()=>{
 const browser=await webkit.launch({headless:true});
 try{for(const viewport of [{width:375,height:667},{width:390,height:844},{width:1440,height:1000}]){
  const page=await browser.newPage({viewport,ignoreHTTPSErrors:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  // This test checks HTML sheets; GPU rendering is covered by verify-hologram.cjs.
  await page.route('**/hologram.js?*',r=>r.fulfill({contentType:'text/javascript',body:''}));
  await page.route('**/api/jarvis/conversations/record?*',r=>r.fulfill({json:{saved:true}}));
  await page.route('**/api/jarvis/ask?*',r=>r.fulfill({json:{answer:'Réponse de vérification du thème.',sources:[],action:null}}));
  await page.goto(base+'/jarvis/');
  async function checkTheme(label){
   const issues=await page.evaluate(()=>{
    const root=document.querySelector('dialog[open]')||document.body;const issues=[];
    function green(value){const matches=[...value.matchAll(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/g)];return matches.some(m=>{
     if(m[4]!==undefined&&Number(m[4])===0)return false;
     const [r,g,b]=m.slice(1,4).map(v=>Number(v)/255),max=Math.max(r,g,b),min=Math.min(r,g,b),d=max-min;
     if(d<.005)return false;let h=max===r?((g-b)/d+6)%6:max===g?(b-r)/d+2:(r-g)/d+4;h*=60;
     return h>75&&h<185&&d/(1-Math.abs(max+min-1))>.04;
    })}
    for(const el of [root,...root.querySelectorAll('*')]){
     if(!el.getClientRects().length)continue;const s=getComputedStyle(el);
     for(const prop of ['color','backgroundColor','backgroundImage','borderTopColor'])if(green(s[prop]))issues.push({element:el.id||el.className,prop,value:s[prop]});
    }
    return {green:issues,overflow:root.scrollWidth>root.clientWidth+1};
   });
   assert.deepEqual(issues.green,[],label+' green remnants');assert(!issues.overflow,label+' sheet overflow');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),label+' page overflow');
  }
  await checkTheme('home');
  await page.locator('#cockpitResources').click();await page.locator('.gateway-app-links').waitFor();
  const links=await page.locator('.gateway-app-links a').evaluateAll(nodes=>nodes.map(a=>({href:a.href,label:a.textContent,target:a.target,rel:a.rel})));
  assert.equal(links.length,8);assert(links.some(a=>a.label.includes('Allemand')));assert(links.some(a=>a.label.includes('Verbes')));
  for(const a of links){assert(a.href.startsWith(base+'/'));assert.equal(a.target,'_blank');assert(a.rel.includes('noopener'));const res=await page.request.get(a.href);assert.equal(res.status(),200,a.href)}
  await checkTheme('resources');await page.screenshot({path:`data/theme-resources-${viewport.width}.png`});
  await page.locator('#cockpitSheetClose').click();await page.locator('#cockpitWrite').click();
  await page.locator('#question').fill('Vérification du thème');await page.locator('#askButton').click();await page.getByText('Réponse de vérification du thème.',{exact:true}).waitFor();
  await checkTheme('conversation');await page.screenshot({path:`data/theme-conversation-${viewport.width}.png`});await page.locator('#cockpitSheetClose').click();
  await page.locator('[data-system=home]').click();await checkTheme('home voice sheet');await page.locator('#cockpitSheetClose').click();
  for(const id of ['noteDialog','sourcesDialog','voiceBalanceDialog','detail','map3dSourceDialog']){
   await page.evaluate(id=>document.getElementById(id).showModal(),id);await checkTheme(id);await page.evaluate(id=>document.getElementById(id).close(),id);
  }
  for(const view of ['library','atelier','memory3d']){await page.locator(`.nav[data-view=${view}]`).evaluate(el=>el.click());await checkTheme(view)}
  assert.deepEqual(errors,[]);console.log('PASS WebKit',viewport.width,': same-origin gateway links, blue theme, conversation, all static sheets and memory views, no overflow or JS errors');await page.close();
 }}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
