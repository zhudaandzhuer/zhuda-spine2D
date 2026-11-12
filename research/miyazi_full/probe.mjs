// pickup probe: where the apple inside the held-apple hand lands at the grab time vs the apple on the floor.
// args: json atlas time px py   (px,py = held-apple centre in canvas px; converted with origin gx,gy)
import fs from 'fs';
import * as spine from '@esotericsoftware/spine-core';
const [json, atlasF, time, px, py, gx, gy] = process.argv.slice(2);
const atlas = new spine.TextureAtlas(fs.readFileSync(atlasF, 'utf8'));
for (const p of atlas.pages) p.setTexture({ getImage: () => ({ width: p.width, height: p.height }), setFilters() {}, setWraps() {}, dispose() {} });
const sd = new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(JSON.parse(fs.readFileSync(json, 'utf8')));
const sk = new spine.Skeleton(sd); sk.setToSetupPose(); sk.updateWorldTransform(spine.Physics.none);
const hand = sk.findBone('hand_far');
const pt = new spine.Vector2(+px - +gx, +gy - +py);
hand.worldToLocal(pt);
const box = (name) => { const s = sk.findSlot(name); const a = s.getAttachment(); if (!a) return null; const v = new Float32Array(8); a.computeWorldVertices(s, v, 0, 2); return { cx: (v[0] + v[4]) / 2, cy: (v[1] + v[5]) / 2 }; };
const st = new spine.AnimationState(new spine.AnimationStateData(sd));
st.setAnimation(0, 'pickup', false).trackTime = +time - 0.001; st.apply(sk); sk.updateWorldTransform(spine.Physics.none);
const ground = box('apple');
const w = new spine.Vector2(pt.x, pt.y); hand.localToWorld(w);
const knee = {}; for (const s of ['far', 'near']) { const b = sk.findBone('shin_' + s); knee[s] = [b.worldX, b.worldY]; }
console.log(JSON.stringify({ held: [w.x, w.y], ground, knee, hip: [sk.findBone('hip').worldX, sk.findBone('hip').worldY] }));
