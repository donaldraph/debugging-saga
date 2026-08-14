/* Live click-through of debugging-saga: both modes, real browser, real API,
   real audio playback. Fails loudly on any broken step. */
const puppeteer = require('puppeteer-core');

const SITE = 'https://d1haw8tkljqm0i.cloudfront.net';
const ok = (msg) => console.log('PASS  ' + msg);

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: 'new',
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1000, height: 1500 });
  const jsErrors = [];
  page.on('pageerror', (e) => jsErrors.push(String(e)));

  const waitForResult = async () => {
    await page.waitForFunction(
      () => !document.getElementById('result').hidden, { timeout: 60000 });
  };
  const readResult = () => page.evaluate(() => ({
    title: document.getElementById('saga-title').textContent,
    credits: document.getElementById('credits').textContent,
    paragraphs: document.querySelectorAll('#saga-text p').length,
    words: document.getElementById('saga-text').textContent.split(/\s+/).length,
    audioSrc: (document.getElementById('player').src || '').slice(0, 60),
    audioNoteHidden: document.getElementById('audio-note').hidden,
  }));

  // ---- Mode 1: showcase ----
  await page.goto(SITE, { waitUntil: 'networkidle2' });
  await page.waitForSelector('.card', { timeout: 15000 });
  const cards = await page.$$eval('.card .card-title', (els) => els.map((e) => e.textContent));
  if (cards.length !== 4) throw new Error('expected 4 cards, got ' + cards.length);
  ok('4 showcase cards rendered from the live API');

  await page.click('.card[data-id="five-token-throttle"]');
  const pills = await page.$$('.pill');
  for (const p of pills) {
    if ((await p.evaluate((e) => e.textContent)) === 'Epic fantasy') await p.click();
  }
  const disabledBefore = await page.$eval('#generate', (b) => b.disabled);
  if (disabledBefore) throw new Error('Dramatize still disabled after selections');
  ok('Dramatize enabled after picking story + tone');

  await page.click('#generate');
  await waitForResult();
  const r1 = await readResult();
  if (!r1.title || r1.words < 150) throw new Error('saga too short: ' + JSON.stringify(r1));
  if (!r1.credits.includes('narrated by Brian')) throw new Error('bad credits: ' + r1.credits);
  if (!r1.audioSrc.includes('dsg-audio-dev')) throw new Error('no audio src: ' + r1.audioSrc);
  ok(`showcase epic generated: "${r1.title}" (${r1.words} words, ${r1.paragraphs}p)`);
  ok('credits: ' + r1.credits);

  // Real playback: wait for metadata, play 3s, confirm the clock moved.
  await page.evaluate(() => new Promise((res, rej) => {
    const a = document.getElementById('player');
    if (a.readyState >= 1) return res();
    a.addEventListener('loadedmetadata', res, { once: true });
    a.addEventListener('error', () => rej(new Error('audio load error')), { once: true });
    setTimeout(() => rej(new Error('audio metadata timeout')), 20000);
  }));
  const dur = await page.$eval('#player', (a) => a.duration);
  if (!(dur > 30)) throw new Error('audio too short: ' + dur + 's');
  await page.$eval('#player', (a) => a.play());
  await new Promise((r) => setTimeout(r, 3000));
  const t = await page.$eval('#player', (a) => a.currentTime);
  if (!(t > 1)) throw new Error('audio did not advance: ' + t);
  ok(`audio really plays: duration ${dur.toFixed(1)}s, advanced to ${t.toFixed(1)}s`);
  await page.$eval('#player', (a) => a.pause());

  // The truth toggle shows the real excerpt.
  await page.click('#truth summary');
  const truth = await page.$eval('#truth-text', (e) => e.textContent);
  if (!truth.includes('5.76 BILLION')) throw new Error('truth text wrong');
  ok('truth toggle shows the real build-log excerpt');
  await page.screenshot({ path: '/tmp/e2e_showcase.png', fullPage: true });

  // ---- Mode 2: bring your own bug ----
  await page.click('#again');
  await page.click('#mode-own');
  await page.type('#own-text',
    'Our nightly job failed for a week. The alert email went to a mailbox ' +
    'nobody reads because the on-call rotation config still listed an ' +
    'engineer who left in 2024. The fix was one line: update the rotation. ' +
    'The real fix was admitting nobody had tested the alerting path since he left.');
  const count = await page.$eval('#char-count', (e) => e.textContent);
  if (Number(count) < 100) throw new Error('char counter not counting: ' + count);
  ok('char counter live: ' + count + ' chars');

  for (const p of await page.$$('.pill')) {
    if ((await p.evaluate((e) => e.textContent)) === 'Greek tragedy') await p.click();
  }
  await page.click('#generate');
  await waitForResult();
  const r2 = await readResult();
  if (!r2.title || r2.words < 150) throw new Error('own-bug saga too short: ' + JSON.stringify(r2));
  if (!r2.credits.includes('narrated by Amy')) throw new Error('bad credits: ' + r2.credits);
  if (!r2.audioSrc.includes('dsg-audio-dev')) throw new Error('no audio src: ' + r2.audioSrc);
  ok(`own-bug tragedy generated: "${r2.title}" (${r2.words} words)`);
  ok('credits: ' + r2.credits);
  await page.screenshot({ path: '/tmp/e2e_ownbug.png', fullPage: true });

  if (jsErrors.length) throw new Error('page JS errors: ' + jsErrors.join(' | '));
  ok('zero page JS errors across both flows');

  await browser.close();
  console.log('ALL PASS');
})().catch((e) => { console.error('FAIL  ' + e.message); process.exit(1); });
