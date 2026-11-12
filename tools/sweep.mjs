#!/usr/bin/env node
// Geometry + timing gate on the official Spine 4.2 runtime (spine-core in Node, no GPU).
//   node tools/sweep.mjs --json x.json --atlas x.atlas [--contract x.contract.json] [--fps 30] [--out report.json]
// Checks, per animation: finite vertices, triangle flips / collapses against the setup pose (tracked by
// slot+attachment identity, so attachment swaps and draw-order keys cannot confuse it), loop seam position
// and velocity, a time-stepped physics run, and real AnimationState mixes between contract animations.
// It cannot see pixels: texture edges, occlusion and whether the motion reads well still need native images.
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import * as spine from '@esotericsoftware/spine-core';

const a = {};
for (let i = 2; i < process.argv.length; i++) { const k = process.argv[i]; if (!k.startsWith('--')) throw new Error('bad arg ' + k); const n = process.argv[i + 1]; if (n === undefined || n.startsWith('--')) a[k.slice(2)] = true; else { a[k.slice(2)] = n; i++; } }
if (a.help || !a.json || !a.atlas) { console.log('Usage: sweep.mjs --json FILE --atlas FILE [--contract FILE] [--fps 30] [--loop-tol 0.05] [--out report.json]'); process.exit(a.help ? 0 : 2); }

const jsonBytes = fs.readFileSync(a.json), atlasText = fs.readFileSync(a.atlas, 'utf8');
const raw = JSON.parse(jsonBytes);
const ver = String(raw.skeleton?.spine || '');
if (!ver.startsWith('4.2')) throw new Error(`This gate is qualified for Spine 4.2 data, got "${ver}"`);
const contract = a.contract && fs.existsSync(a.contract) ? JSON.parse(fs.readFileSync(a.contract, 'utf8')) : {};
const atlas = new spine.TextureAtlas(atlasText);
const data = new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(raw);
const fps = Number(a.fps || 30), loopTol = Number(a['loop-tol'] || 0.05), EPS = 1e-7;
const meta = contract.animations || {};
const errors = [], warnings = [];

function geometry(slot, att) {
  if (att instanceof spine.MeshAttachment) { const p = new Float32Array(att.worldVerticesLength); att.computeWorldVertices(slot, 0, p.length, p, 0, 2); return { p, t: att.triangles }; }
  if (att instanceof spine.RegionAttachment) { const p = new Float32Array(8); att.computeWorldVertices(slot, p, 0, 2); return { p, t: [0, 1, 2, 2, 3, 0] }; }
  return null;
}
function areas(g) { const o = new Float64Array(g.t.length / 3); for (let i = 0, k = 0; i < g.t.length; i += 3, k++) { const A = g.t[i] * 2, B = g.t[i + 1] * 2, C = g.t[i + 2] * 2; o[k] = (g.p[B] - g.p[A]) * (g.p[C + 1] - g.p[A + 1]) - (g.p[B + 1] - g.p[A + 1]) * (g.p[C] - g.p[A]); } return o; }

const rest = new spine.Skeleton(data); rest.setToSetupPose(); rest.updateWorldTransform(spine.Physics.none);
const baseline = new Map();
function base(slotIndex, att) {
  const key = slotIndex + ':' + att.name;
  if (!baseline.has(key)) { const rs = rest.slots[slotIndex]; const keep = rs.getAttachment(); rs.setAttachment(att); const g = geometry(rs, att); baseline.set(key, g ? areas(g) : null); rs.setAttachment(keep); }
  return baseline.get(key);
}
function inspect(sk, acc, where) {
  const snap = new Map();
  for (const slot of sk.slots) {
    const att = slot.getAttachment(); if (!att) continue;
    const g = geometry(slot, att); if (!g) continue;
    const key = slot.data.index + ':' + att.name;
    snap.set(key, g.p);
    let bad = 0; for (const v of g.p) if (!Number.isFinite(v)) bad++;
    if (bad) { acc.nonfinite += bad; if (acc.details.length < 12) acc.details.push({ ...where, slot: slot.data.name, type: 'nonfinite' }); continue; }
    const b = base(slot.data.index, att), ar = areas(g);
    for (let i = 0; i < ar.length; i++) {
      if (Math.abs(b[i]) <= EPS) continue;
      const ratio = ar[i] / b[i];
      if (ratio < 0) { acc.flips++; if (acc.details.length < 12) acc.details.push({ ...where, slot: slot.data.name, attachment: att.name, triangle: i, type: 'flip' }); }
      else if (ratio < 0.02) { acc.collapsed++; if (acc.details.length < 12) acc.details.push({ ...where, slot: slot.data.name, attachment: att.name, triangle: i, type: 'collapsed' }); }
      if (ratio > acc.maxStretch) acc.maxStretch = ratio;
    }
  }
  return snap;
}
function maxDelta(A, B) { let d = 0, changed = 0; for (const k of new Set([...A.keys(), ...B.keys()])) { const x = A.get(k), y = B.get(k); if (!x || !y || x.length !== y.length) { changed++; continue; } for (let i = 0; i < x.length; i += 2) d = Math.max(d, Math.hypot(x[i] - y[i], x[i + 1] - y[i + 1])); } return { d, changed }; }
const newAcc = () => ({ samples: 0, nonfinite: 0, flips: 0, collapsed: 0, maxStretch: 1, details: [] });
function poseAt(sk, anim, t) { sk.setToSetupPose(); anim.apply(sk, 0, t, false, [], 1, spine.MixBlend.setup, spine.MixDirection.mixIn); sk.updateWorldTransform(spine.Physics.none); }

const report = { tool: 'spine2d-master/sweep', runtime: 'spine-core 4.2.119', jsonSha256: createHash('sha256').update(jsonBytes).digest('hex'), fps,
  counts: { bones: data.bones.length, slots: data.slots.length, animations: data.animations.length, ik: data.ikConstraints.length, transform: data.transformConstraints.length, physics: data.physicsConstraints.length },
  animations: [], mixes: [], scope: 'geometry and timing only; no pixels, occlusion or performance-quality claim' };

// ---- static weight checks straight from the JSON -------------------------------------------------
let weighted = 0, maxInf = 0;
for (const skin of raw.skins || []) for (const [slotName, atts] of Object.entries(skin.attachments || {})) for (const [name, att] of Object.entries(atts)) {
  if (att.type !== 'mesh') continue;
  const nv = att.uvs.length / 2;
  if (att.vertices.length === att.uvs.length) continue;
  weighted++;
  let i = 0, v = 0;
  while (i < att.vertices.length) {
    const n = att.vertices[i++]; let sum = 0; maxInf = Math.max(maxInf, n);
    for (let k = 0; k < n; k++, i += 4) { const bi = att.vertices[i]; if (!(bi >= 0 && bi < raw.bones.length)) errors.push(`${slotName}/${name}: bone index ${bi} out of range`); sum += att.vertices[i + 3]; }
    if (Math.abs(sum - 1) > 0.01) errors.push(`${slotName}/${name}: vertex ${v} weights sum to ${sum.toFixed(3)}`);
    v++;
  }
  if (v !== nv) errors.push(`${slotName}/${name}: ${v} weighted vertices but ${nv} UVs`);
  for (const t of att.triangles) if (t >= nv) errors.push(`${slotName}/${name}: triangle index ${t} >= ${nv}`);
}
report.counts.weightedMeshes = weighted; report.counts.maxInfluences = maxInf;

// ---- per animation --------------------------------------------------------------------------------
const sk = new spine.Skeleton(data);
for (const anim of data.animations) {
  const row = { name: anim.name, duration: anim.duration, loop: !!(meta[anim.name] && meta[anim.name].loop), ...newAcc() };
  const n = Math.max(1, Math.ceil(anim.duration * fps));
  let first, last;
  for (let i = 0; i <= n; i++) { const t = anim.duration * i / n; poseAt(sk, anim, t); const s = inspect(sk, row, { time: +t.toFixed(4) }); row.samples++; if (i === 0) first = new Map([...s].map(([k, v]) => [k, Float32Array.from(v)])); if (i === n) last = s; }
  if (row.loop && anim.duration > 0) {
    const seam = maxDelta(first, last);
    const h = Math.min(1 / 120, anim.duration / 8);
    poseAt(sk, anim, h); const p1 = new Map([...inspect(sk, newAcc(), {})].map(([k, v]) => [k, Float32Array.from(v)]));
    poseAt(sk, anim, anim.duration - h); const p2 = inspect(sk, newAcc(), {});
    // velocity leaving the start vs arriving at the end
    let vj = 0, vmax = 0, vjKey = null;
    for (const [k, s0] of first) { const s1 = p1.get(k), e0 = p2.get(k), e1 = last.get(k); if (!s1 || !e0 || !e1 || s1.length !== e0.length) continue; for (let i = 0; i < s0.length; i += 2) { const vx0 = (s1[i] - s0[i]) / h, vy0 = (s1[i + 1] - s0[i + 1]) / h, vx1 = (e1[i] - e0[i]) / h, vy1 = (e1[i + 1] - e0[i + 1]) / h; const dv = Math.hypot(vx0 - vx1, vy0 - vy1); if (dv > vj) { vj = dv; vjKey = k; } vmax = Math.max(vmax, Math.hypot(vx0, vy0), Math.hypot(vx1, vy1)); } }
    row.seam = { positionPx: +seam.d.toFixed(4), attachmentChanges: seam.changed, velocityJumpPxPerS: +vj.toFixed(2), speedAtSeamPxPerS: +vmax.toFixed(2), worstSlot: vjKey == null ? null : (data.slots[+String(vjKey).split(':')[0]] || {}).name || String(vjKey) };
    if (seam.d > loopTol || seam.changed) errors.push(`${anim.name}: loop does not close (${seam.d.toFixed(3)} px, ${seam.changed} attachment changes)`);
    else if (vj > Math.max(12, vmax * 0.35)) warnings.push(`${anim.name}: velocity jump at loop seam ${vj.toFixed(1)} px/s (visible hitch risk)`);
  }
  if (data.physicsConstraints.length && anim.duration > 0) {
    const ps = new spine.Skeleton(data); ps.setToSetupPose();
    const st = new spine.AnimationState(new spine.AnimationStateData(data)); st.setAnimation(0, anim.name, true);
    const acc = newAcc(); const dt = 1 / 60, steps = Math.ceil(Math.max(2, anim.duration * 2) / dt); let drift = 0;
    st.apply(ps); ps.updateWorldTransform(spine.Physics.reset);
    for (let i = 0; i < steps; i++) { st.update(dt); st.apply(ps); ps.update(dt); ps.updateWorldTransform(spine.Physics.update); const s = inspect(ps, acc, { physicsTime: +(i * dt).toFixed(3) }); if (i % 6 === 0) { poseAt(sk, anim, st.getCurrent(0).getAnimationTime()); const ref = inspect(sk, newAcc(), {}); drift = Math.max(drift, maxDelta(s, ref).d); } }
    row.physics = { steps, nonfinite: acc.nonfinite, flips: acc.flips, collapsed: acc.collapsed, maxOffsetFromKeyedPosePx: +drift.toFixed(2), details: acc.details.slice(0, 4) };
    if (acc.nonfinite) errors.push(`${anim.name}: physics produced non-finite vertices`);
    if (acc.flips) warnings.push(`${anim.name}: ${acc.flips} triangle flips while physics runs`);
  }
  // Gait: animations.<name> = {speed: px/s, feet: [bone, ...]} in the contract.  The clip is authored in place and the
  // controller moves the skeleton at `speed`, so while a foot is on the ground its bone must travel backwards at exactly
  // -speed.  Reported per foot: stance share, worst slip speed and the distance the planted foot skates per stance.
  const gm = meta[anim.name];
  if (gm && gm.speed && Array.isArray(gm.feet) && anim.duration > 0) {
    const N = 240, dt = anim.duration / N, feet = [];
    for (const name of gm.feet) {
      const bone = sk.findBone(name);
      if (!bone) { errors.push(`${anim.name}: gait foot bone '${name}' not found`); continue; }
      const xs = [], ys = [];
      for (let i = 0; i <= N; i++) { poseAt(sk, anim, i * dt); xs.push(bone.worldX); ys.push(bone.worldY); }
      const ground = Math.min(...ys), tolY = gm.contactHeight != null ? gm.contactHeight : 1.5;
      let worst = 0, skate = 0, run = 0, stance = 0;
      for (let i = 0; i < N; i++) {
        const down = ys[i] <= ground + tolY && ys[i + 1] <= ground + tolY;
        if (!down) { skate = Math.max(skate, Math.abs(run)); run = 0; continue; }
        stance++;
        const v = (xs[i + 1] - xs[i]) / dt + gm.speed * (gm.facing === 'left' ? -1 : 1);      // world velocity of the planted foot
        worst = Math.max(worst, Math.abs(v)); run += v * dt;
      }
      skate = Math.max(skate, Math.abs(run));
      feet.push({ foot: name, stanceShare: +(stance / N).toFixed(3), worstSlipPxPerS: +worst.toFixed(2), skatePxPerStance: +skate.toFixed(2) });
      if (skate > (gm.maxSkate != null ? gm.maxSkate : 3)) errors.push(`${anim.name}: foot '${name}' skates ${skate.toFixed(1)} px while planted (speed ${gm.speed} px/s)`);
      if (stance === 0) warnings.push(`${anim.name}: foot '${name}' never touches the ground`);
    }
    row.gait = { speed: gm.speed, feet };
  }
  if (row.nonfinite) errors.push(`${anim.name}: ${row.nonfinite} non-finite vertex values`);
  if (row.flips) errors.push(`${anim.name}: ${row.flips} flipped triangle samples (first: ${JSON.stringify(row.details[0])})`);
  if (row.collapsed) warnings.push(`${anim.name}: ${row.collapsed} near-collapsed triangle samples`);
  row.maxStretch = +row.maxStretch.toFixed(2); row.details = row.details.slice(0, 6);
  report.animations.push(row);
}

// ---- real mixes between track-0 animations ---------------------------------------------------------
const track0 = data.animations.filter((x) => !(meta[x.name] && (meta[x.name].track || 0) !== 0) && x.duration > 0).slice(0, 10);
const mix = contract.mix && contract.mix.default != null ? contract.mix.default : 0.2;
for (const from of track0) for (const to of track0) {
  if (from === to || mix <= 0) continue;
  const acc = newAcc();
  for (const phase of [0.15, 0.5, 0.85]) {
    const ms = new spine.Skeleton(data); ms.setToSetupPose();
    const sd = new spine.AnimationStateData(data); sd.defaultMix = mix;
    const st = new spine.AnimationState(sd);
    const e = st.setAnimation(0, from.name, true); e.trackTime = from.duration * phase;
    st.apply(ms); ms.updateWorldTransform(spine.Physics.none);
    st.setAnimation(0, to.name, true);
    const dt = 1 / 60;
    for (let i = 0; i <= Math.ceil(mix / dt) + 2; i++) { st.update(dt); st.apply(ms); ms.updateWorldTransform(spine.Physics.none); inspect(ms, acc, { from: from.name, to: to.name, phase, step: i }); acc.samples++; }
  }
  if (acc.nonfinite || acc.flips) { report.mixes.push({ from: from.name, to: to.name, ...acc, details: acc.details.slice(0, 3) }); errors.push(`mix ${from.name} -> ${to.name}: ${acc.flips} flips, ${acc.nonfinite} non-finite`); }
}
report.mixPairsChecked = track0.length * Math.max(0, track0.length - 1);

report.errors = errors; report.warnings = warnings; report.ok = errors.length === 0;
if (a.out) { fs.mkdirSync(path.dirname(path.resolve(a.out)), { recursive: true }); fs.writeFileSync(a.out, JSON.stringify(report, null, 1)); }
console.log(JSON.stringify({ ok: report.ok, errors, warnings, counts: report.counts, animations: report.animations.map((r) => ({ name: r.name, duration: +r.duration.toFixed(3), loop: r.loop, flips: r.flips, collapsed: r.collapsed, maxStretch: r.maxStretch, seam: r.seam, gait: r.gait, physics: r.physics && { flips: r.physics.flips, maxOffsetPx: r.physics.maxOffsetFromKeyedPosePx } })), mixPairsChecked: report.mixPairsChecked }, null, 1));
process.exit(report.ok ? 0 : 1);
