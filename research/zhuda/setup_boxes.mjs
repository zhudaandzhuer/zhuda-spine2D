// world-space boxes of each visible region attachment in the setup pose (or at anim/time)
import fs from 'fs';
import * as spine from '@esotericsoftware/spine-core';
const [json, atlasF, anim, time] = process.argv.slice(2);
const atlas = new spine.TextureAtlas(fs.readFileSync(atlasF, 'utf8'));
for (const p of atlas.pages) p.setTexture({ getImage: () => ({ width: p.width, height: p.height }), setFilters() {}, setWraps() {}, dispose() {} });
const sd = new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(JSON.parse(fs.readFileSync(json, 'utf8')));
const sk = new spine.Skeleton(sd); sk.setToSetupPose();
if (anim) { const st = new spine.AnimationState(new spine.AnimationStateData(sd)); st.setAnimation(0, anim, false).trackTime = +time || 0; st.apply(sk); }
sk.updateWorldTransform(spine.Physics.update);
const out = {};
for (const s of sk.drawOrder) {
  const a = s.getAttachment(); if (!(a instanceof spine.RegionAttachment)) continue;
  const v = new Float32Array(8); a.computeWorldVertices(s, v, 0, 2);
  const xs = [v[0], v[2], v[4], v[6]], ys = [v[1], v[3], v[5], v[7]];
  out[s.data.name] = { att: a.name, cx: (Math.min(...xs) + Math.max(...xs)) / 2, cy: (Math.min(...ys) + Math.max(...ys)) / 2, w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys), alpha: s.color.a };
}
console.log(JSON.stringify(out));
