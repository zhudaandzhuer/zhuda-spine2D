// per-slot flipped-triangle audit with physics: node flipaudit.mjs json atlas [anim...]
import fs from 'fs';
import * as spine from '@esotericsoftware/spine-core';
const [json, atlasF, ...names] = process.argv.slice(2);
const atlas = new spine.TextureAtlas(fs.readFileSync(atlasF, 'utf8'));
for (const p of atlas.pages) p.setTexture({ getImage: () => ({ width: p.width, height: p.height }), setFilters() {}, setWraps() {}, dispose() {} });
const sd = new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(JSON.parse(fs.readFileSync(json, 'utf8')));
function tris(sk) {
  const out = {};
  for (const s of sk.drawOrder) {
    const a = s.getAttachment(); if (!(a instanceof spine.MeshAttachment)) continue;
    const v = new Float32Array(a.worldVerticesLength); a.computeWorldVertices(s, 0, a.worldVerticesLength, v, 0, 2);
    const t = a.triangles, sg = [];
    for (let i = 0; i < t.length; i += 3) { const [p, q, r] = [t[i] * 2, t[i + 1] * 2, t[i + 2] * 2];
      sg.push((v[q] - v[p]) * (v[r + 1] - v[p + 1]) - (v[r] - v[p]) * (v[q + 1] - v[p + 1])); }
    out[s.data.name + '/' + a.name] = sg;
  }
  return out;
}
const setup = new spine.Skeleton(sd); setup.setToSetupPose(); setup.updateWorldTransform(spine.Physics.update);
const ref = tris(setup);
const res = {};
for (const an of (names.length ? names : sd.animations.map((a) => a.name))) {
  const anim = sd.findAnimation(an); const sk = new spine.Skeleton(sd); sk.setToSetupPose();
  const st = new spine.AnimationState(new spine.AnimationStateData(sd)); st.setAnimation(0, an, anim.duration > 0 && an === 'idle' || an === 'run');
  sk.updateWorldTransform(spine.Physics.reset);
  const dt = 1 / 60, per = {};
  for (let t = 0; t <= anim.duration + 1e-6; t += dt) {
    st.update(dt); st.apply(sk); sk.update(dt); sk.updateWorldTransform(spine.Physics.update);
    const cur = tris(sk);
    for (const k in cur) { const r = ref[k]; if (!r) continue; let n = 0, col = 0;
      cur[k].forEach((x, i) => { if (Math.sign(x) !== Math.sign(r[i]) && Math.abs(x) > Math.max(40, 0.15 * Math.abs(r[i]))) n++; else if (Math.abs(x) < Math.abs(r[i]) * 0.04) col++; });
      if (n || col) { const e = per[k] || (per[k] = { flipFrames: 0, maxFlips: 0, worstT: 0, collapsed: 0 }); if (n) e.flipFrames++; if (n > e.maxFlips) { e.maxFlips = n; e.worstT = +t.toFixed(3); } e.collapsed = Math.max(e.collapsed, col); } }
  }
  res[an] = per;
}
console.log(JSON.stringify(res, null, 1));
