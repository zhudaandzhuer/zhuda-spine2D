#!/usr/bin/env node
// Rasterise an SVG whose parts are marked with data-part="name" into one full-canvas transparent PNG per part
// (document order = draw order, back to front) plus keyart.png with everything visible.
//   node tools/raster_svg.mjs --svg art/character.svg --out .work/raster [--scale 1]
// Cropping / manifest writing is done by `spk art` (Python); this step only renders.
import fs from 'node:fs';
import path from 'node:path';
import { launch } from './capture.mjs';

const a = {};
for (let i = 2; i < process.argv.length; i += 2) a[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
if (!a.svg || !a.out) { console.error('Usage: raster_svg.mjs --svg FILE --out DIR [--scale 1]'); process.exit(2); }
const svg = fs.readFileSync(a.svg, 'utf8');
const scale = Number(a.scale || 1);
const vb = /viewBox="\s*([-\d.]+)[ ,]+([-\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)\s*"/.exec(svg);
if (!vb) throw new Error('SVG root needs a viewBox="0 0 W H" (W,H = canvas pixels)');
const W = Math.round(Number(vb[3])), H = Math.round(Number(vb[4]));
fs.mkdirSync(a.out, { recursive: true });
const { browser } = await launch({});
try {
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: scale });
  await page.setContent(`<!doctype html><html><head><style>html,body{margin:0;background:transparent}svg{display:block;width:${W}px;height:${H}px}</style></head><body>${svg}</body></html>`);
  const names = await page.evaluate(() => [...document.querySelectorAll('[data-part]')].map((e) => e.getAttribute('data-part')));
  if (!names.length) throw new Error('No elements with data-part="name" found');
  if (new Set(names).size !== names.length) throw new Error('Duplicate data-part names: ' + names.filter((n, i) => names.indexOf(n) !== i).join(', '));
  const shot = (file) => page.screenshot({ path: file, omitBackground: true, clip: { x: 0, y: 0, width: W, height: H } });
  // key art = setup pose: parts flagged data-hidden (alternate attachments) are not shown
  await page.evaluate(() => { for (const e of document.querySelectorAll('[data-part]')) e.style.display = e.hasAttribute('data-hidden') ? 'none' : ''; });
  await shot(path.join(a.out, '_keyart.png'));
  for (const n of names) {
    await page.evaluate((name) => { for (const e of document.querySelectorAll('[data-part]')) e.style.display = e.getAttribute('data-part') === name ? '' : 'none'; }, n);
    await shot(path.join(a.out, `${n}.png`));
  }
  const hidden = await page.evaluate(() => [...document.querySelectorAll('[data-part][data-hidden]')].map((e) => e.getAttribute('data-part')));
  const pads = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('[data-part]')].map((e) => [e.getAttribute('data-part'), Number(e.getAttribute('data-pad') || 2)])));
  fs.writeFileSync(path.join(a.out, '_parts.json'), JSON.stringify({ canvas: [W * scale, H * scale], scale, parts: names, hidden, pads }, null, 1));
  console.log(JSON.stringify({ ok: true, parts: names.length, canvas: [W * scale, H * scale] }));
} finally { await browser.close(); }
