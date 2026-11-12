import {
  AnimationState,
  AnimationStateData,
  AtlasAttachmentLoader,
  Physics,
  Skeleton,
  SkeletonJson,
  TextureAtlas,
} from '@esotericsoftware/spine-webgl';

function normalizeAngle(value) {
  let v = Number(value) || 0;
  while (v > 180) v -= 360;
  while (v < -180) v += 360;
  return v;
}

function keyedInfo(raw, animationName) {
  const out = new Map();
  const bones = raw?.animations?.[animationName]?.bones || {};
  for (const [boneName, timelines] of Object.entries(bones)) {
    out.set(boneName, Object.fromEntries(Object.entries(timelines || {}).map(([name, frames]) => [name, Array.isArray(frames) ? frames.length : 0])));
  }
  return out;
}

function snapshotSkeleton(skeleton) {
  return skeleton.bones.map((bone, index) => ({
    index,
    name: bone.data.name,
    parent: bone.parent?.data?.name ?? null,
    children: bone.children.map(child => child.data.name),
    length: bone.data.length,
    active: bone.isActive(),
    local: {
      x: bone.x,
      y: bone.y,
      rotation: bone.rotation,
      scaleX: bone.scaleX,
      scaleY: bone.scaleY,
      shearX: bone.shearX,
      shearY: bone.shearY,
    },
    world: {
      x: bone.worldX,
      y: bone.worldY,
      rotationX: bone.getWorldRotationX(),
      rotationY: bone.getWorldRotationY(),
      scaleX: bone.getWorldScaleX(),
      scaleY: bone.getWorldScaleY(),
      a: bone.a,
      b: bone.b,
      c: bone.c,
      d: bone.d,
    },
  }));
}

export function buildPoseRuntime(raw, atlasText) {
  const atlas = new TextureAtlas(atlasText);
  const parser = new SkeletonJson(new AtlasAttachmentLoader(atlas));
  const data = parser.readSkeletonData(raw);
  return { atlas, data };
}

export function samplePoseFromData(raw, data, { animationName = '', time = 0 } = {}) {
  const setupSkeleton = new Skeleton(data);
  setupSkeleton.setToSetupPose();
  setupSkeleton.updateWorldTransform(Physics.update);
  const setup = snapshotSkeleton(setupSkeleton);

  const skeleton = new Skeleton(data);
  skeleton.setToSetupPose();
  let duration = 0;
  if (animationName) {
    const animation = data.findAnimation(animationName);
    if (!animation) throw new Error(`Animation not found: ${animationName}`);
    duration = animation.duration;
    const state = new AnimationState(new AnimationStateData(data));
    const entry = state.setAnimation(0, animationName, false);
    const clamped = Math.min(Math.max(0, Number(time) || 0), Math.max(0, duration));
    entry.trackTime = clamped;
    entry.trackLast = clamped;
    entry.animationLast = clamped;
    state.apply(skeleton);
  }
  skeleton.updateWorldTransform(Physics.update);
  const pose = snapshotSkeleton(skeleton);
  const keyed = keyedInfo(raw, animationName);

  const bones = pose.map((bone, i) => {
    const base = setup[i];
    const dx = bone.world.x - base.world.x;
    const dy = bone.world.y - base.world.y;
    const dRotation = normalizeAngle(bone.world.rotationX - base.world.rotationX);
    const dScaleX = bone.world.scaleX - base.world.scaleX;
    const dScaleY = bone.world.scaleY - base.world.scaleY;
    const distance = Math.hypot(dx, dy);
    const score = distance + Math.abs(dRotation) * 0.35 + (Math.abs(dScaleX) + Math.abs(dScaleY)) * 35;
    return {
      ...bone,
      keyed: keyed.get(bone.name) || {},
      delta: { x: dx, y: dy, distance, rotation: dRotation, scaleX: dScaleX, scaleY: dScaleY, score },
    };
  });

  const ranked = [...bones].sort((a, b) => b.delta.score - a.delta.score);
  return {
    animation: animationName || null,
    time: Math.min(Math.max(0, Number(time) || 0), Math.max(0, duration)),
    duration,
    bones,
    ranked,
  };
}

export function samplePose(raw, atlasText, options = {}) {
  const runtime = buildPoseRuntime(raw, atlasText);
  try { return samplePoseFromData(raw, runtime.data, options); }
  finally { runtime.atlas.dispose?.(); }
}

export function summarizeHierarchy(raw) {
  const bones = raw?.bones || [];
  const slots = raw?.slots || [];
  const attachmentIndex = new Map();
  const addAttachment = (skinName, slotName, name, data) => {
    if (!attachmentIndex.has(slotName)) attachmentIndex.set(slotName, []);
    const display = data?.path || data?.name || name;
    attachmentIndex.get(slotName).push({ skin:skinName, name, display, type:data?.type || 'region' });
  };
  if (Array.isArray(raw?.skins)) {
    for (const skin of raw.skins) for (const [slotName, attachments] of Object.entries(skin?.attachments || {})) for (const [name, data] of Object.entries(attachments || {})) addAttachment(skin.name || 'default', slotName, name, data);
  } else {
    for (const [skinName, skin] of Object.entries(raw?.skins || {})) for (const [slotName, attachments] of Object.entries(skin || {})) for (const [name, data] of Object.entries(attachments || {})) addAttachment(skinName, slotName, name, data);
  }
  const slotsByBone = new Map();
  for (const slot of slots) {
    if (!slotsByBone.has(slot.bone)) slotsByBone.set(slot.bone, []);
    const available = attachmentIndex.get(slot.name) || [];
    slotsByBone.get(slot.bone).push({
      name: slot.name,
      setupAttachment: slot.attachment ?? null,
      availableCount: available.length,
      attachments: available.slice(0, 32),
    });
  }
  const byName = new Map(bones.map((bone, index) => [bone.name, { ...bone, index, children: [] }]));
  for (const item of byName.values()) if (item.parent && byName.has(item.parent)) byName.get(item.parent).children.push(item.name);
  const roots = [...byName.values()].filter(item => !item.parent || !byName.has(item.parent));
  const rows = [];
  const walk = (item, depth) => {
    const boneSlots = slotsByBone.get(item.name) || [];
    const tokens = new Set();
    for (const slot of boneSlots) {
      tokens.add(slot.name);
      if (slot.setupAttachment) tokens.add(slot.setupAttachment);
      for (const a of slot.attachments.slice(0,12)) tokens.add(a.display);
    }
    rows.push({ index:item.index, name:item.name, parent:item.parent || null, depth, length:item.length || 0, children:item.children, slots:boneSlots, semanticTokens:[...tokens].slice(0,32) });
    for (const child of item.children) walk(byName.get(child), depth + 1);
  };
  for (const root of roots) walk(root, 0);
  return rows;
}
