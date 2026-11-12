#!/usr/bin/env node
// Diagnostic CPU rasteriser (official spine-core for the pose, nearest-neighbour triangles for pixels).
// No browser needed.  Use it to understand rig state when native capture is unavailable -- never as delivery evidence.
//   node tools/softrender.mjs --json x.json --atlas x.atlas --out frame.png [--anim NAME --time T] [--bones 1]
import { renderSoftwareFrame } from './lib/softwareRenderFrame.mjs';
const a = {};
for (let i = 2; i < process.argv.length; i += 2) a[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
if (!a.json || !a.atlas || !a.out) { console.error('Usage: softrender.mjs --json FILE --atlas FILE --out FILE [--anim NAME] [--time T] [--bones 1]'); process.exit(2); }
const r = renderSoftwareFrame({ jsonPath: a.json, atlasPath: a.atlas, animation: a.anim || '', time: Number(a.time || 0), out: a.out, bones: !!a.bones, maxWidth: Number(a.width || 1000), maxHeight: Number(a.height || 1000) });
console.log(JSON.stringify({ ok: true, renderer: r.renderer, out: r.out, width: r.width, height: r.height, note: 'diagnostic only' }));
