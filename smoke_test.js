// Headless-browser smoke test for the generated report (docs/index.html).
//
// Serves docs/ locally and drives the app through its main flows: the care
// checklist, the header sub menu, the Plant Gallery grid, the two-axis
// slideshow (sideways = plants, up/down = photo history), deep links, and
// the detail view's photo lightbox.
//
// Requires playwright and a Chromium binary (not needed to build the report):
//   npm install playwright   # or use a preinstalled browser via CHROMIUM_PATH
//   node smoke_test.js
//
// Exits non-zero on any failed check or page error.

const { chromium } = require('playwright');
const http = require('http');
const path = require('path');
const fs = require('fs');
const os = require('os');

const DOCS = path.join(__dirname, 'docs');
const PORT = 8931;
const SHOTS = process.env.SCRATCH || os.tmpdir();
const MIME = {'.html':'text/html','.png':'image/png','.jpeg':'image/jpeg','.jpg':'image/jpeg','.json':'application/json','.js':'text/javascript'};

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0].split('#')[0]);
  if (p === '/') p = '/index.html';
  const f = path.join(DOCS, p);
  fs.readFile(f, (err, data) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, {'Content-Type': MIME[path.extname(f)] || 'application/octet-stream'});
    res.end(data);
  });
});

let failures = 0;
function check(label, ok) {
  console.log(`${ok ? 'PASS' : 'FAIL'}: ${label}`);
  if (!ok) failures++;
}

(async () => {
  await new Promise(r => server.listen(PORT, r));
  const browser = await chromium.launch(
    process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}
  );
  const page = await browser.newPage({ viewport: { width: 390, height: 780 }, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => {
    // The browser's automatic /favicon.ico request 404s; ignore it.
    if (m.type() === 'error' && !m.text().includes('404')) errors.push(m.text());
  });

  await page.goto(`http://localhost:${PORT}/`);
  await page.waitForSelector('.row');

  // Sub menu opens and navigates to the gallery.
  await page.click('#menu-btn');
  await page.waitForSelector('#menu-pop:not(.hidden)');
  await page.click('#menu-gallery');
  await page.waitForSelector('#gallery-view:not(.hidden)');
  await page.waitForSelector('.gal-card');
  check('menu → gallery view with cards', (await page.locator('.gal-card').count()) > 0);
  check('gallery sets #gallery hash', await page.evaluate(() => location.hash === '#gallery'));
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(SHOTS, 'smoke-gallery.png') });

  // Find a plant with photo history (its slideshow shows a position marker).
  const multi = await page.evaluate(() => {
    const p = P.filter(p => (p.photos || []).length > 1)
      .sort((a, b) => (a.nickname || a.name).localeCompare(b.nickname || b.name))[0];
    return p ? (p.nickname || p.name) : null;
  });
  if (multi) {
    await page.click(`.gal-card:has-text("${multi}")`);
    await page.waitForSelector('#lightbox.show');
    const cap = () => page.textContent('#lb-cap');
    check('slideshow opens on newest (1/N)', (await cap()).includes('1/'));
    check('older-photo chevron shown', await page.evaluate(() =>
      !document.getElementById('lb-down').classList.contains('hidden')));

    await page.keyboard.press('ArrowDown');
    check('ArrowDown → older photo (2/N)', (await cap()).includes('2/'));
    await page.keyboard.press('ArrowUp');
    check('ArrowUp → back to newest', (await cap()).includes('1/'));

    // After a history dive, moving sideways lands on the next plant's newest.
    await page.keyboard.press('ArrowDown');
    const before = await cap();
    await page.keyboard.press('ArrowRight');
    const after = await cap();
    check('ArrowRight → different plant, newest photo',
      after !== before && !after.includes('2/'));

    // Touch swipes: up = older, sideways = change plant.
    const swipes = await page.evaluate(() => {
      const lb = document.getElementById('lightbox');
      const capEl = document.getElementById('lb-cap');
      const fire = (type, x, y) => lb.dispatchEvent(new PointerEvent(type,
        {pointerId: 7, pointerType: 'touch', clientX: x, clientY: y, bubbles: true}));
      const out = [capEl.textContent];
      fire('pointerdown', 300, 400); fire('pointermove', 220, 400); fire('pointerup', 180, 400);
      out.push(capEl.textContent);   // swipe left → next/prev plant
      fire('pointerdown', 200, 500); fire('pointermove', 200, 430); fire('pointerup', 200, 380);
      out.push(capEl.textContent);   // swipe up → older photo (if any)
      return out;
    });
    check('swipe left changes plant', swipes[1] !== swipes[0]);

    await page.keyboard.press('Escape');
    check('Escape closes slideshow', await page.evaluate(() =>
      !document.getElementById('lightbox').classList.contains('show')));
    await page.keyboard.press('Escape');
    check('Escape returns to list', await page.evaluate(() =>
      !document.getElementById('list-view').classList.contains('hidden')));
  } else {
    console.log('SKIP: no plant with photo history');
  }

  // Deep links.
  const page2 = await browser.newPage({ viewport: { width: 390, height: 780 } });
  await page2.goto(`http://localhost:${PORT}/#gallery`);
  await page2.waitForSelector('#gallery-view:not(.hidden)');
  check('#gallery deep link works', true);

  // Detail view's single-photo lightbox keeps no slideshow chrome.
  const anyId = await page2.evaluate(() => (P.find(p => (p.photos || []).length) || {}).id);
  if (anyId) {
    const page3 = await browser.newPage({ viewport: { width: 390, height: 780 } });
    await page3.goto(`http://localhost:${PORT}/#${anyId}`);
    await page3.waitForSelector('.plant-photo');
    await page3.click('.plant-photo');
    await page3.waitForSelector('#lightbox.show');
    check('detail lightbox has no slideshow chrome', await page3.evaluate(() =>
      document.getElementById('lb-next').classList.contains('hidden')
      && document.getElementById('lb-down').classList.contains('hidden')
      && document.getElementById('lb-cap').classList.contains('hidden')));
  }

  check('no page errors', errors.length === 0);
  if (errors.length) console.log('errors:', errors);

  await browser.close();
  server.close();
  console.log(failures ? `${failures} check(s) FAILED` : 'All checks passed');
  process.exit(failures ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
