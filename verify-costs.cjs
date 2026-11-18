const {chromium} = require('/home/user/workspace/brasskapelos-wp-redesign/tooling/node_modules/playwright-core');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({executablePath: '/home/user/.cache/ms-playwright/chromium-1193/chrome-linux/chrome',
    headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 390, height: 844}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let data = {day: '2026-11-11', todayUsd: .003, totalUsd: .003, trackingSince: new Date().toISOString(),
      balance: null, billingUrl: 'https://aistudio.google.com/billing',
      google: {state: 'pending_export', today: [], message: 'En attente de l’export Google.'}};
    let online = true;
    const seen = new Set();
    await page.route('**/api/jarvis/live/costs', route => route.fulfill({contentType: 'application/json', body: JSON.stringify(data)}));
    await page.route('**/api/jarvis/live/balance', route => {
      const input = route.request().postDataJSON();
      data.balance = {amount: input.amount, currency: input.currency, remaining: input.amount, updatedAt: new Date().toISOString()};
      return route.fulfill({contentType: 'application/json', body: JSON.stringify(data)});
    });
    await page.route('**/api/jarvis/live/usage', route => {
      if (!online) return route.fulfill({status: 503, contentType: 'application/json', body: '{}'});
      const input = route.request().postDataJSON();
      const key = input.sessionId + ':' + input.sequence;
      if (!seen.has(key)) {seen.add(key); data.todayUsd += .002; if (data.balance) data.balance.remaining -= .002;}
      return route.fulfill({contentType: 'application/json', body: JSON.stringify(data)});
    });
    await page.goto('http://127.0.0.1:8787/jarvis/');
    await page.locator('#cockpitResources').click();
    await page.waitForFunction(() => document.querySelector('#voiceDailyCost').textContent.includes('0,003'));
    assert.equal(await page.locator('#voiceCreditBalance').textContent(), 'À renseigner');
    assert.equal(await page.locator('#voiceGoogleCost').textContent(), 'En attente de Google');
    await page.locator('#voiceBalanceEdit').click();
    await page.locator('#voiceBalanceForm [name=amount]').fill('15.99');
    await page.locator('#voiceBalanceForm [name=currency]').selectOption('USD');
    await page.locator('#voiceBalanceForm [type=submit]').click();
    await page.locator('#voiceBalanceDialog').waitFor({state: 'hidden'});
    assert((await page.locator('#voiceCreditBalance').textContent()).includes('15,99'));
    online = false;
    await page.evaluate(() => window.jarvisUsage.record('test-session', 1, {promptTokenCount: 100, responseTokenCount: 30}));
    await page.waitForFunction(() => document.querySelector('#voiceCostSync').textContent.includes('Connexion au suivi interrompue'));
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('jarvis-voice-usage-pending-v1')).length), 1);
    online = true;
    data.google = {state: 'ready', checkedAt: new Date().toISOString(), day: data.day, today: [{currency: 'CHF', amount: .0123}]};
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await page.waitForFunction(() => JSON.parse(localStorage.getItem('jarvis-voice-usage-pending-v1')).length === 0);
    await page.waitForFunction(() => document.querySelector('#voiceDailyCost').textContent.includes('0,005'));
    assert((await page.locator('#voiceCreditBalance').textContent()).includes('15,988'));
    assert((await page.locator('#voiceGoogleCost').textContent()).includes('0,0123'));
    await page.reload();
    await page.locator('#cockpitResources').click();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.waitForFunction(() => document.querySelector('#voiceCreditBalance').textContent.includes('15,988'));
    await page.screenshot({path: '/home/user/workspace/jarvis/data/voice-costs-mobile.png', fullPage: true});
    assert.deepEqual(errors, []);
    console.log('PASS: mobile cost/credit display, reference balance form, automatic usage updates, failed-report persistence/retry, reload and no overflow (mocked ledger).');
  } finally { await browser.close(); }
})().catch(error => {console.error(error.stack); process.exit(1);});
