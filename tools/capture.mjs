#!/usr/bin/env node
// Native Spine WebGL capture. Drives viewer/index.html in headless Chromium and saves exactly what the
// official runtime rendered. Every frame carries a verified snapshot of the renderer's real track state.
//
//   node tools/capture.mjs --json build/x.json --atlas build/x.atlas [--contract build/x.contract.json]
//        --plan plan.json --out evidence/dir
//
// plan.json:
//   { "size":[720,900], "bg":"transparent"|"#rrggbb", "frame":{x,y,width,height}?, "debug":{"bones":false,"mesh":false},
//     "shots":[ {"name":"idle_0.50","seek":{"tracks":[{"anim":"idle","time":0.5,"loop":true}],"physics":"none"}} ],
//     "plays":[ {"name":"mix_idle_nod","fps":30,"duration":2.0,"cues":[{"at":0,"anim":"idle","loop":true},{"at":0.5,"anim":"nod","mix":0.2}],
//                "physics":true,"look":{"look":[[0,0,0],[1,1,0]]}} ] }
// Exit code 1 if any shot fails verification. Never writes outside --out.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';

const KIT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function parseArgs(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) throw new Error(`Unexpected argument: ${a}`);
    const k = a.slice(2), n = argv[i + 1];
    if (n === undefined || n.startsWith('--')) o[k] = true; else { o[k] = n; i++; }
  }
  return o;
}

export async function loadPlaywright() {
  const tried = [];
  const candidates = [];
  if (process.env.PLAYWRIGHT_MODULE) candidates.push(process.env.PLAYWRIGHT_MODULE);
  const req = createRequire(path.join(KIT, 'package.json'));
  for (const name of ['playwright-core', 'playwright']) { try { candidates.push(req.resolve(name)); } catch { tried.push(`${name} (kit node_modules)`); } }
  let globalRoot = null;
  try { globalRoot = execSync('npm root -g', { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(); } catch { /* npm missing */ }
  const roots = [globalRoot, '/opt/npm-tools/node_modules', '/usr/local/lib/node_modules', '/usr/lib/node_modules'].filter(Boolean);
  for (const r of roots) for (const name of ['playwright-core', 'playwright']) { const p = path.join(r, name, 'index.mjs'); if (fs.existsSync(p)) candidates.push(p); else tried.push(p); }
  for (const c of candidates) {
    try { const m = await import(c.startsWith('/') || /^[A-Za-z]:\\/.test(c) ? pathToFileURL(c).href : c); const chromium = m.chromium || (m.default && m.default.chromium); if (chromium) return { chromium, module: c }; } catch (e) { tried.push(`${c}: ${e.message.split('\n')[0]}`); }
  }
  throw new Error('Playwright not found. Install once in the kit: `npm install --no-save playwright-core` (then `npx playwright-core install chromium`), or set PLAYWRIGHT_MODULE to a playwright(-core) index.mjs and CHROME_PATH to a Chrome/Chromium binary.\nTried: ' + tried.join('; '));
}

export async function launch(o = {}) {
  const { chromium, module } = await loadPlaywright();
  const args = o.gpu ? ['--ignore-gpu-blocklist'] : ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
  const opts = { headless: true, args };
  if (process.env.CHROME_PATH) opts.executablePath = process.env.CHROME_PATH;
  let browser;
  try { browser = await chromium.launch(opts); }
  catch (e) {
    if (opts.executablePath) throw e;
    try { browser = await chromium.launch({ ...opts, channel: 'chrome' }); }
    catch { throw new Error('No Chromium available for Playwright. Run `npx playwright-core install chromium` or set CHROME_PATH.\n' + e.message.split('\n')[0]); }
  }
  return { browser, module };
}

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json', '.atlas': 'text/plain; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml', '.css': 'text/css' };

/** Static server: /kit/* -> kit root, /p/* -> project directory. Bound to loopback only. */
export function serve(projectDir) {
  const roots = { kit: KIT, p: path.resolve(projectDir) };
  const server = http.createServer((req, res) => {
    try {
      const url = new URL(req.url, 'http://x');
      const parts = decodeURIComponent(url.pathname).split('/').filter(Boolean);
      const root = roots[parts.shift()];
      if (!root) { res.writeHead(404); return res.end('not found'); }
      const file = path.resolve(root, ...parts);
      if (!file.startsWith(root + path.sep) && file !== root) { res.writeHead(403); return res.end('forbidden'); }
      if (!fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404); return res.end('not found'); }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream', 'Cache-Control': 'no-store' });
      fs.createReadStream(file).pipe(res);
    } catch (e) { res.writeHead(500); res.end(String(e)); }
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port })));
}

const sha = (f) => createHash('sha256').update(fs.readFileSync(f)).digest('hex');

function verifySeek(req, snap) {
  const problems = [];
  if (!snap.frozen) problems.push('renderer not frozen');
  for (const t of req.tracks || []) {
    const got = (snap.tracks || []).find((x) => x.track === (t.track || 0));
    if (!got) { problems.push(`track ${t.track || 0} empty`); continue; }
    if (got.animation !== t.anim) problems.push(`track ${t.track || 0}: animation ${got.animation} != ${t.anim}`);
    // Compare animation time: a physics pre-roll legitimately advances trackTime by whole loops.
    const want = t.time || 0, dur = got.duration || 0;
    let diff = Math.abs(got.trackTime - want);
    if (t.loop && dur > 0) { const a = ((got.animationTime % dur) + dur) % dur, b = ((want % dur) + dur) % dur; diff = Math.min(Math.abs(a - b), dur - Math.abs(a - b)); }
    if (diff > 2e-3) problems.push(`track ${t.track || 0}: time ${got.trackTime} (animation time ${got.animationTime}) != ${want}`);
  }
  return problems;
}

async function main() {
  const a = parseArgs(process.argv.slice(2));
  if (a.help || !a.json || !a.atlas || !a.plan || !a.out) {
    console.log('Usage: node tools/capture.mjs --json FILE --atlas FILE [--contract FILE] --plan plan.json --out DIR [--gpu]');
    process.exit(a.help ? 0 : 2);
  }
  const json = path.resolve(a.json), atlas = path.resolve(a.atlas), out = path.resolve(a.out);
  const dir = path.dirname(json);
  if (path.dirname(atlas) !== dir) throw new Error('json and atlas must be in the same directory');
  const contract = a.contract ? path.resolve(a.contract) : null;
  if (contract && path.dirname(contract) !== dir) throw new Error('contract must sit next to the json');
  const plan = JSON.parse(fs.readFileSync(a.plan, 'utf8'));
  fs.mkdirSync(out, { recursive: true });
  const [W, H] = plan.size || [720, 900];
  const { server, port } = await serve(dir);
  const { browser, module } = await launch({ gpu: !!a.gpu });
  const receipt = { tool: 'spine2d-master/capture', renderer: 'spine-webgl-4.2.119 (headless Chromium)', playwright: module, size: [W, H], assets: { json: sha(json), atlas: sha(atlas) }, shots: [], plays: [], ok: true };
  try {
    const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    const q = new URLSearchParams({ json: `/p/${path.basename(json)}`, atlas: `/p/${path.basename(atlas)}`, ui: '0' });
    if (contract) q.set('contract', `/p/${path.basename(contract)}`);
    await page.goto(`http://127.0.0.1:${port}/kit/viewer/index.html?${q}`);
    await page.waitForFunction(() => window.spk && (window.spk.ready || window.spk.error), null, { timeout: 60000 });
    const err = await page.evaluate(() => window.spk.error);
    if (err) throw new Error('Viewer failed: ' + err);
    receipt.info = await page.evaluate(() => window.spk.info());
    const viewOpts = { bg: plan.bg || 'transparent', bones: !!(plan.debug && plan.debug.bones), mesh: !!(plan.debug && plan.debug.mesh) };
    if (plan.frame) viewOpts.frame = plan.frame;
    if (plan.pad != null) viewOpts.pad = plan.pad;
    await page.evaluate((v) => window.spk.view(v), viewOpts);
    const save = async (file) => {
      const dataUrl = await page.evaluate(() => window.spk.png());
      fs.writeFileSync(file, Buffer.from(dataUrl.split(',')[1], 'base64'));
    };
    for (const shot of plan.shots || []) {
      const file = path.join(out, `${shot.name}.png`);
      const row = { name: shot.name, file: path.basename(file), requested: shot.seek, label: shot.label || shot.name };
      try {
        if (shot.view) await page.evaluate((v) => window.spk.view(v), shot.view);
        const snap = await page.evaluate((s) => window.spk.seek(s), shot.seek);
        const problems = verifySeek(shot.seek, snap);
        await save(file);
        const after = await page.evaluate(() => window.spk.snapshot());
        if (JSON.stringify(after.tracks) !== JSON.stringify(snap.tracks)) problems.push('track state drifted during capture');
        row.tracks = snap.tracks; row.status = problems.length ? 'FAILED' : 'VERIFIED'; row.problems = problems;
        if (shot.view) await page.evaluate((v) => window.spk.view(v), viewOpts);
      } catch (e) { row.status = 'FAILED'; row.problems = [String(e.message || e)]; }
      if (row.status !== 'VERIFIED') receipt.ok = false;
      receipt.shots.push(row);
    }
    for (const play of plan.plays || []) {
      const fps = play.fps || 30, n = Math.round((play.duration || 1) * fps), dt = 1 / fps;
      const sub = path.join(out, play.name);
      fs.mkdirSync(sub, { recursive: true });
      const row = { name: play.name, dir: play.name, fps, frames: [], cues: play.cues, status: 'VERIFIED', problems: [] };
      try {
        let snap = await page.evaluate((p) => window.spk.begin(p), { cues: play.cues, physics: play.physics, look: play.look, startX: play.startX, facing: play.facing });
        for (let i = 0; i <= n; i++) {
          const file = path.join(sub, `frame-${String(i).padStart(4, '0')}.png`);
          await save(file);
          row.frames.push({ file: path.basename(file), clock: snap.clock, tracks: snap.tracks.map((t) => ({ track: t.track, animation: t.animation, trackTime: +t.trackTime.toFixed(4), mixingFrom: t.mixingFrom, mixTime: +t.mixTime.toFixed(4), mixDuration: t.mixDuration })) });
          if (Math.abs(snap.clock - i * dt) > 1e-3) row.problems.push(`frame ${i}: clock ${snap.clock}`);
          if (i < n) snap = await page.evaluate((d) => window.spk.advance(d), dt);
        }
        row.events = snap.events;
      } catch (e) { row.problems.push(String(e.message || e)); }
      if (row.problems.length) { row.status = 'FAILED'; receipt.ok = false; }
      receipt.plays.push(row);
    }
    if (errors.length) { receipt.pageErrors = errors; receipt.ok = false; }
  } finally {
    await browser.close();
    server.close();
  }
  fs.writeFileSync(path.join(out, 'capture.json'), JSON.stringify(receipt, null, 2));
  const bad = receipt.shots.filter((s) => s.status !== 'VERIFIED').length + receipt.plays.filter((s) => s.status !== 'VERIFIED').length;
  console.log(JSON.stringify({ ok: receipt.ok, out, shots: receipt.shots.length, plays: receipt.plays.length, failed: bad, visual_verdict: 'NOT_EVALUATED (open the images)' }));
  process.exit(receipt.ok ? 0 : 1);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch((e) => { console.error(String(e.stack || e)); process.exit(1); });
