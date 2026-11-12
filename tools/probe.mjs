#!/usr/bin/env node
// Read-only probe: can this machine do native capture (Playwright + Chromium + WebGL)? Prints one JSON line.
import { launch } from './capture.mjs';
try {
  const { browser, module } = await launch({});
  const page = await browser.newPage();
  await page.setContent('<canvas id="c" width="8" height="8"></canvas>');
  const gl = await page.evaluate(() => { const g = document.getElementById('c').getContext('webgl2') || document.getElementById('c').getContext('webgl'); if (!g) return null; const e = g.getExtension('WEBGL_debug_renderer_info'); return { version: g.getParameter(g.VERSION), renderer: e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'unknown', maxTexture: g.getParameter(g.MAX_TEXTURE_SIZE) }; });
  const version = browser.version();
  await browser.close();
  console.log(JSON.stringify(gl ? { ok: true, playwright: module, browser: version, webgl: gl } : { ok: false, error: 'browser launched but WebGL is unavailable' }));
} catch (e) { console.log(JSON.stringify({ ok: false, error: String(e.message || e).slice(0, 600) })); }
