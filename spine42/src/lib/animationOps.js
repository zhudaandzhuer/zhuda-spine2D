const EPS = 1e-6;

export const BONE_TIMELINE_SPECS = {
  rotate: { props: ['value'], defaults: { value: 0 } },
  translate: { props: ['x', 'y'], defaults: { x: 0, y: 0 } },
  translatex: { props: ['value'], defaults: { value: 0 } },
  translatey: { props: ['value'], defaults: { value: 0 } },
  scale: { props: ['x', 'y'], defaults: { x: 1, y: 1 } },
  scalex: { props: ['value'], defaults: { value: 1 } },
  scaley: { props: ['value'], defaults: { value: 1 } },
  shear: { props: ['x', 'y'], defaults: { x: 0, y: 0 } },
  shearx: { props: ['value'], defaults: { value: 0 } },
  sheary: { props: ['value'], defaults: { value: 0 } },
};

export function deepClone(value) {
  return typeof structuredClone === 'function' ? structuredClone(value) : JSON.parse(JSON.stringify(value));
}

function animationMap(raw) {
  if (!raw.animations || typeof raw.animations !== 'object' || Array.isArray(raw.animations)) raw.animations = {};
  return raw.animations;
}

export function listAnimations(raw) {
  return Object.keys(raw.animations || {});
}

export function createAnimation(raw, name, { replace = false } = {}) {
  if (!name) throw new Error('Animation name is required');
  const animations = animationMap(raw);
  if (animations[name] && !replace) throw new Error(`Animation already exists: ${name}`);
  animations[name] = {};
  return animations[name];
}

export function cloneAnimation(raw, source, target, { replace = false } = {}) {
  const animations = animationMap(raw);
  if (!animations[source]) throw new Error(`Animation not found: ${source}`);
  if (animations[target] && !replace) throw new Error(`Animation already exists: ${target}`);
  animations[target] = deepClone(animations[source]);
  return animations[target];
}

export function deleteAnimation(raw, name) {
  if (!raw.animations?.[name]) throw new Error(`Animation not found: ${name}`);
  delete raw.animations[name];
}

export function ensureBone(raw, boneName) {
  const bone = (raw.bones || []).find(b => b?.name === boneName);
  if (!bone) throw new Error(`Bone not found: ${boneName}`);
  return bone;
}

export function ensureBoneTimeline(raw, animationName, boneName, timelineName) {
  ensureBone(raw, boneName);
  const spec = BONE_TIMELINE_SPECS[timelineName];
  if (!spec) throw new Error(`Unsupported bone timeline: ${timelineName}`);
  const anim = raw.animations?.[animationName];
  if (!anim) throw new Error(`Animation not found: ${animationName}`);
  anim.bones ||= {};
  anim.bones[boneName] ||= {};
  anim.bones[boneName][timelineName] ||= [];
  return anim.bones[boneName][timelineName];
}

export function clearBoneTimeline(raw, animationName, boneName, timelineName) {
  const anim = raw.animations?.[animationName];
  if (!anim) throw new Error(`Animation not found: ${animationName}`);
  if (anim.bones?.[boneName]?.[timelineName]) {
    delete anim.bones[boneName][timelineName];
    if (!Object.keys(anim.bones[boneName]).length) delete anim.bones[boneName];
    if (!Object.keys(anim.bones).length) delete anim.bones;
  }
}


export function ensureSlot(raw, slotName) {
  const slot = (raw.slots || []).find(s => s?.name === slotName);
  if (!slot) throw new Error(`Slot not found: ${slotName}`);
  return slot;
}

/**
 * @param {any} raw
 * @param {string} animationName
 * @param {string} slotName
 * @param {number} time
 * @param {string|null} [attachmentName]
 */
export function setSlotAttachmentKey(raw, animationName, slotName, time, attachmentName = null) {
  ensureSlot(raw, slotName);
  time = Number(time);
  if (!Number.isFinite(time) || time < 0) throw new Error(`Invalid key time: ${time}`);
  const anim = raw.animations?.[animationName];
  if (!anim) throw new Error(`Animation not found: ${animationName}`);
  anim.slots ||= {};
  anim.slots[slotName] ||= {};
  anim.slots[slotName].attachment ||= [];
  const frames = anim.slots[slotName].attachment;
  let frame = frames.find(f => Math.abs(Number(f.time || 0) - time) <= EPS);
  if (!frame) { frame = { time }; frames.push(frame); }
  else if (time !== 0 || ('time' in frame)) frame.time = time;
  if (attachmentName === null || attachmentName === undefined || attachmentName === '') delete frame.name;
  else frame.name = String(attachmentName);
  frames.sort((a,b) => Number(a.time || 0) - Number(b.time || 0));
  return frame;
}

export function deleteSlotAttachmentKey(raw, animationName, slotName, time) {
  const frames = raw.animations?.[animationName]?.slots?.[slotName]?.attachment;
  if (!Array.isArray(frames)) return false;
  time = Number(time);
  const index = frames.findIndex(f => Math.abs(Number(f.time || 0) - time) <= EPS);
  if (index < 0) return false;
  frames.splice(index, 1);
  if (!frames.length) {
    delete raw.animations[animationName].slots[slotName].attachment;
    if (!Object.keys(raw.animations[animationName].slots[slotName]).length) delete raw.animations[animationName].slots[slotName];
    if (!Object.keys(raw.animations[animationName].slots).length) delete raw.animations[animationName].slots;
  }
  return true;
}


export function ensureIkConstraint(raw, constraintName) {
  const constraint = (raw.ik || []).find(c => c?.name === constraintName);
  if (!constraint) throw new Error(`IK constraint not found: ${constraintName}`);
  return constraint;
}

export function setIkKey(raw, animationName, constraintName, time, values = {}, { curve } = {}) {
  ensureIkConstraint(raw, constraintName);
  time = Number(time);
  if (!Number.isFinite(time) || time < 0) throw new Error(`Invalid key time: ${time}`);
  const anim = raw.animations?.[animationName];
  if (!anim) throw new Error(`Animation not found: ${animationName}`);
  anim.ik ||= {};
  anim.ik[constraintName] ||= [];
  const frames = anim.ik[constraintName];
  let frame = frames.find(f => Math.abs(Number(f.time || 0) - time) <= EPS);
  if (!frame) { frame = { time }; frames.push(frame); }
  else if (time !== 0 || ('time' in frame)) frame.time = time;
  for (const prop of ['mix', 'softness']) {
    if (values[prop] !== undefined) {
      const v = Number(values[prop]);
      if (!Number.isFinite(v)) throw new Error(`Invalid IK ${prop}: ${values[prop]}`);
      frame[prop] = v;
    }
  }
  for (const prop of ['bendPositive', 'compress', 'stretch']) {
    if (values[prop] !== undefined) frame[prop] = !!values[prop];
  }
  const normalizedCurve = normalizeCurve(curve);
  if (curve !== undefined) {
    if (normalizedCurve === undefined) delete frame.curve;
    else frame.curve = normalizedCurve;
  }
  frames.sort((a,b) => Number(a.time || 0) - Number(b.time || 0));
  return frame;
}

export function deleteIkKey(raw, animationName, constraintName, time) {
  const frames = raw.animations?.[animationName]?.ik?.[constraintName];
  if (!Array.isArray(frames)) return false;
  time = Number(time);
  const index = frames.findIndex(f => Math.abs(Number(f.time || 0) - time) <= EPS);
  if (index < 0) return false;
  frames.splice(index, 1);
  if (!frames.length) {
    delete raw.animations[animationName].ik[constraintName];
    if (!Object.keys(raw.animations[animationName].ik).length) delete raw.animations[animationName].ik;
  }
  return true;
}

export function setDrawOrderKey(raw, animationName, time, offsets = []) {
  time = Number(time);
  if (!Number.isFinite(time) || time < 0) throw new Error(`Invalid key time: ${time}`);
  const anim = raw.animations?.[animationName];
  if (!anim) throw new Error(`Animation not found: ${animationName}`);
  if (!Array.isArray(offsets)) throw new Error('Draw-order offsets must be an array');
  const slotIndex = new Map((raw.slots || []).map((slot, index) => [slot?.name, index]));
  const seen = new Set();
  const normalized = offsets.map(item => {
    const slot = String(item?.slot || '');
    if (!slotIndex.has(slot)) throw new Error(`Slot not found: ${slot}`);
    if (seen.has(slot)) throw new Error(`Duplicate draw-order slot: ${slot}`);
    seen.add(slot);
    const offset = Number(item?.offset);
    if (!Number.isInteger(offset)) throw new Error(`Draw-order offset for ${slot} must be an integer`);
    const target = slotIndex.get(slot) + offset;
    if (target < 0 || target >= slotIndex.size) throw new Error(`Draw-order offset for ${slot} is out of range`);
    return { slot, offset, sourceIndex: slotIndex.get(slot) };
  }).sort((a,b) => a.sourceIndex - b.sourceIndex).map(({slot,offset}) => ({slot,offset}));
  anim.drawOrder ||= [];
  let frame = anim.drawOrder.find(f => Math.abs(Number(f.time || 0) - time) <= EPS);
  if (!frame) { frame = { time }; anim.drawOrder.push(frame); }
  else if (time !== 0 || ('time' in frame)) frame.time = time;
  if (normalized.length) frame.offsets = normalized;
  else delete frame.offsets;
  anim.drawOrder.sort((a,b) => Number(a.time || 0) - Number(b.time || 0));
  return frame;
}

export function deleteDrawOrderKey(raw, animationName, time) {
  const frames = raw.animations?.[animationName]?.drawOrder;
  if (!Array.isArray(frames)) return false;
  time = Number(time);
  const index = frames.findIndex(f => Math.abs(Number(f.time || 0) - time) <= EPS);
  if (index < 0) return false;
  frames.splice(index, 1);
  if (!frames.length) delete raw.animations[animationName].drawOrder;
  return true;
}

function normalizeCurve(curve) {
  if (curve === undefined || curve === null || curve === '' || curve === 'linear') return undefined;
  if (curve === 'stepped') return 'stepped';
  if (typeof curve === 'string') {
    try { curve = JSON.parse(curve); } catch { throw new Error('Curve must be linear, stepped, or a JSON numeric array'); }
  }
  if (!Array.isArray(curve) || !curve.length || curve.length % 4 !== 0 || curve.some(v => typeof v !== 'number' || !Number.isFinite(v))) {
    throw new Error('Bezier curve must be a numeric array whose length is a multiple of 4');
  }
  return [...curve];
}

export function setBoneKey(raw, animationName, boneName, timelineName, time, values = {}, { curve } = {}) {
  time = Number(time);
  if (!Number.isFinite(time) || time < 0) throw new Error(`Invalid key time: ${time}`);
  const spec = BONE_TIMELINE_SPECS[timelineName];
  if (!spec) throw new Error(`Unsupported bone timeline: ${timelineName}`);
  const frames = ensureBoneTimeline(raw, animationName, boneName, timelineName);
  let frame = frames.find(f => Math.abs(Number(f.time || 0) - time) <= EPS);
  if (!frame) { frame = { time }; frames.push(frame); }
  else if (time === 0 && !('time' in frame)) { /* keep compact Spine zero-time form */ }
  else frame.time = time;

  for (const prop of spec.props) {
    if (values[prop] !== undefined) {
      const v = Number(values[prop]);
      if (!Number.isFinite(v)) throw new Error(`Invalid ${timelineName}.${prop}: ${values[prop]}`);
      frame[prop] = v;
    }
  }
  const normalizedCurve = normalizeCurve(curve);
  if (curve !== undefined) {
    if (normalizedCurve === undefined) delete frame.curve;
    else frame.curve = normalizedCurve;
  }
  frames.sort((a, b) => Number(a.time || 0) - Number(b.time || 0));
  return frame;
}

export function deleteBoneKey(raw, animationName, boneName, timelineName, time) {
  const frames = raw.animations?.[animationName]?.bones?.[boneName]?.[timelineName];
  if (!Array.isArray(frames)) return false;
  time = Number(time);
  const index = frames.findIndex(f => Math.abs(Number(f.time || 0) - time) <= EPS);
  if (index < 0) return false;
  frames.splice(index, 1);
  if (!frames.length) clearBoneTimeline(raw, animationName, boneName, timelineName);
  return true;
}

export function retimeAnimationNode(node, factor) {
  if (Array.isArray(node)) { for (const item of node) retimeAnimationNode(item, factor); return; }
  if (!node || typeof node !== 'object') return;
  for (const [key, value] of Object.entries(node)) {
    if (key === 'time' && typeof value === 'number') node[key] = value * factor;
    else if (key === 'curve' && Array.isArray(value)) {
      for (let i = 0; i + 2 < value.length; i += 4) {
        if (typeof value[i] === 'number') value[i] *= factor;
        if (typeof value[i + 2] === 'number') value[i + 2] *= factor;
      }
    } else retimeAnimationNode(value, factor);
  }
}

export function retimeAnimation(raw, name, factor) {
  factor = Number(factor);
  if (!Number.isFinite(factor) || factor <= 0) throw new Error(`Invalid retime factor: ${factor}`);
  const anim = raw.animations?.[name];
  if (!anim) throw new Error(`Animation not found: ${name}`);
  retimeAnimationNode(anim, factor);
  return anim;
}

export function maxTime(node) {
  let max = 0;
  if (Array.isArray(node)) for (const item of node) max = Math.max(max, maxTime(item));
  else if (node && typeof node === 'object') {
    if (typeof node.time === 'number') max = Math.max(max, node.time);
    for (const value of Object.values(node)) max = Math.max(max, maxTime(value));
  }
  return max;
}

function checkCurve(curve, path, issues) {
  if (curve === undefined) return;
  if (curve === 'stepped') return;
  if (!Array.isArray(curve) || !curve.length || curve.length % 4 !== 0 || curve.some(v => typeof v !== 'number' || !Number.isFinite(v))) {
    issues.push(`${path}: invalid curve`);
  }
}

export function validateAnimationAuthoring(raw) {
  const issues = [];
  const warnings = [];
  const version = String(raw?.skeleton?.spine || '');
  if (!version.startsWith('4.2')) warnings.push(`Skeleton version is not 4.2-compatible: ${version || '(missing)'}`);
  const boneNames = new Set((raw.bones || []).map(b => b?.name).filter(Boolean));
  const ikNames = new Set((raw.ik || []).map(c => c?.name).filter(Boolean));
  const transformNames = new Set((raw.transform || []).map(c => c?.name).filter(Boolean));
  const pathNames = new Set((raw.path || []).map(c => c?.name).filter(Boolean));
  const slotNames = new Set((raw.slots || []).map(s => s?.name).filter(Boolean));
  const slotIndex = new Map((raw.slots || []).map((slot, index) => [slot?.name, index]));
  const animations = raw.animations || {};
  for (const [animName, anim] of Object.entries(animations)) {
    for (const [boneName, timelines] of Object.entries(anim.bones || {})) {
      if (!boneNames.has(boneName)) issues.push(`animations.${animName}.bones.${boneName}: bone not found`);
      for (const [timelineName, frames] of Object.entries(timelines || {})) {
        const spec = BONE_TIMELINE_SPECS[timelineName];
        if (!spec) { warnings.push(`animations.${animName}.bones.${boneName}.${timelineName}: authoring validator does not model this timeline`); continue; }
        if (!Array.isArray(frames)) { issues.push(`animations.${animName}.bones.${boneName}.${timelineName}: timeline must be an array`); continue; }
        let prev = -Infinity;
        for (let i = 0; i < frames.length; i++) {
          const frame = frames[i];
          if (!frame || typeof frame !== 'object' || Array.isArray(frame)) { issues.push(`animations.${animName}.bones.${boneName}.${timelineName}[${i}]: frame must be an object`); continue; }
          const t = Number(frame.time || 0);
          if (!Number.isFinite(t) || t < 0) issues.push(`animations.${animName}.bones.${boneName}.${timelineName}[${i}]: invalid time`);
          if (t + EPS < prev) issues.push(`animations.${animName}.bones.${boneName}.${timelineName}: frames are not time-sorted`);
          prev = t;
          for (const prop of spec.props) if (frame[prop] !== undefined && (typeof frame[prop] !== 'number' || !Number.isFinite(frame[prop]))) issues.push(`animations.${animName}.bones.${boneName}.${timelineName}[${i}].${prop}: must be finite number`);
          checkCurve(frame.curve, `animations.${animName}.bones.${boneName}.${timelineName}[${i}]`, issues);
        }
      }
    }
    for (const [slotName, timelines] of Object.entries(anim.slots || {})) {
      if (!slotNames.has(slotName)) issues.push(`animations.${animName}.slots.${slotName}: slot not found`);
      const frames = timelines?.attachment;
      if (frames !== undefined) {
        if (!Array.isArray(frames)) issues.push(`animations.${animName}.slots.${slotName}.attachment: timeline must be an array`);
        else {
          let prev = -Infinity;
          for (let i=0;i<frames.length;i++) {
            const frame=frames[i];
            if (!frame || typeof frame !== 'object' || Array.isArray(frame)) { issues.push(`animations.${animName}.slots.${slotName}.attachment[${i}]: frame must be an object`); continue; }
            const t=Number(frame.time || 0);
            if (!Number.isFinite(t) || t < 0) issues.push(`animations.${animName}.slots.${slotName}.attachment[${i}]: invalid time`);
            if (t + EPS < prev) issues.push(`animations.${animName}.slots.${slotName}.attachment: frames are not time-sorted`);
            prev=t;
          }
        }
      }
    }
    for (const [constraintName, frames] of Object.entries(anim.ik || {})) {
      if (!ikNames.has(constraintName)) issues.push(`animations.${animName}.ik.${constraintName}: IK constraint not found`);
      if (!Array.isArray(frames)) { issues.push(`animations.${animName}.ik.${constraintName}: timeline must be an array`); continue; }
      let prev = -Infinity;
      for (let i=0;i<frames.length;i++) {
        const frame=frames[i];
        if (!frame || typeof frame !== 'object' || Array.isArray(frame)) { issues.push(`animations.${animName}.ik.${constraintName}[${i}]: frame must be an object`); continue; }
        const t=Number(frame.time || 0);
        if (!Number.isFinite(t) || t < 0) issues.push(`animations.${animName}.ik.${constraintName}[${i}]: invalid time`);
        if (t + EPS < prev) issues.push(`animations.${animName}.ik.${constraintName}: frames are not time-sorted`);
        prev=t;
        for (const prop of ['mix','softness']) if (frame[prop] !== undefined && (typeof frame[prop] !== 'number' || !Number.isFinite(frame[prop]))) issues.push(`animations.${animName}.ik.${constraintName}[${i}].${prop}: must be finite number`);
        for (const prop of ['bendPositive','compress','stretch']) if (frame[prop] !== undefined && typeof frame[prop] !== 'boolean') issues.push(`animations.${animName}.ik.${constraintName}[${i}].${prop}: must be boolean`);
        checkCurve(frame.curve, `animations.${animName}.ik.${constraintName}[${i}]`, issues);
      }
    }
    for (const [constraintName, frames] of Object.entries(anim.transform || {})) {
      if (!transformNames.has(constraintName)) issues.push(`animations.${animName}.transform.${constraintName}: Transform constraint not found`);
      if (!Array.isArray(frames)) { issues.push(`animations.${animName}.transform.${constraintName}: timeline must be an array`); continue; }
      let prev=-Infinity;for(let i=0;i<frames.length;i++){const frame=frames[i];if(!frame||typeof frame!=='object'||Array.isArray(frame)){issues.push(`animations.${animName}.transform.${constraintName}[${i}]: frame must be an object`);continue;}const t=Number(frame.time||0);if(!Number.isFinite(t)||t<0)issues.push(`animations.${animName}.transform.${constraintName}[${i}]: invalid time`);if(t+EPS<prev)issues.push(`animations.${animName}.transform.${constraintName}: frames are not time-sorted`);prev=t;for(const prop of ['mixRotate','mixX','mixY','mixScaleX','mixScaleY','mixShearY'])if(frame[prop]!==undefined&&(typeof frame[prop]!=='number'||!Number.isFinite(frame[prop])||frame[prop]<0||frame[prop]>1))issues.push(`animations.${animName}.transform.${constraintName}[${i}].${prop}: must be finite 0..1`);checkCurve(frame.curve,`animations.${animName}.transform.${constraintName}[${i}]`,issues);}
    }
    for (const [constraintName, node] of Object.entries(anim.path || {})) {
      if (!pathNames.has(constraintName)) issues.push(`animations.${animName}.path.${constraintName}: Path constraint not found`);
      if (!node || typeof node!=='object' || Array.isArray(node)) { issues.push(`animations.${animName}.path.${constraintName}: node must be an object`); continue; }
      for(const [channel,frames] of Object.entries(node)){if(!['position','spacing','mix'].includes(channel)){warnings.push(`animations.${animName}.path.${constraintName}.${channel}: unsupported Path timeline channel`);continue;}if(!Array.isArray(frames)){issues.push(`animations.${animName}.path.${constraintName}.${channel}: timeline must be an array`);continue;}let prev=-Infinity;for(let i=0;i<frames.length;i++){const frame=frames[i];if(!frame||typeof frame!=='object'||Array.isArray(frame)){issues.push(`animations.${animName}.path.${constraintName}.${channel}[${i}]: frame must be an object`);continue;}const t=Number(frame.time||0);if(!Number.isFinite(t)||t<0)issues.push(`animations.${animName}.path.${constraintName}.${channel}[${i}]: invalid time`);if(t+EPS<prev)issues.push(`animations.${animName}.path.${constraintName}.${channel}: frames are not time-sorted`);prev=t;if(channel==='position'||channel==='spacing'){if(frame.value!==undefined&&(typeof frame.value!=='number'||!Number.isFinite(frame.value)))issues.push(`animations.${animName}.path.${constraintName}.${channel}[${i}].value: must be finite number`);}else for(const prop of ['mixRotate','mixX','mixY'])if(frame[prop]!==undefined&&(typeof frame[prop]!=='number'||!Number.isFinite(frame[prop])||frame[prop]<0||frame[prop]>1))issues.push(`animations.${animName}.path.${constraintName}.mix[${i}].${prop}: must be finite 0..1`);checkCurve(frame.curve,`animations.${animName}.path.${constraintName}.${channel}[${i}]`,issues);}}
    }
    if (anim.drawOrder !== undefined) {
      if (!Array.isArray(anim.drawOrder)) issues.push(`animations.${animName}.drawOrder: timeline must be an array`);
      else {
        let prev=-Infinity;
        for (let i=0;i<anim.drawOrder.length;i++) {
          const frame=anim.drawOrder[i];
          if (!frame || typeof frame !== 'object' || Array.isArray(frame)) { issues.push(`animations.${animName}.drawOrder[${i}]: frame must be an object`); continue; }
          const t=Number(frame.time || 0);
          if (!Number.isFinite(t) || t < 0) issues.push(`animations.${animName}.drawOrder[${i}]: invalid time`);
          if (t + EPS < prev) issues.push(`animations.${animName}.drawOrder: frames are not time-sorted`);
          prev=t;
          if (frame.offsets !== undefined) {
            if (!Array.isArray(frame.offsets)) issues.push(`animations.${animName}.drawOrder[${i}].offsets: must be an array`);
            else {
              const seen=new Set();
              for (let ii=0;ii<frame.offsets.length;ii++) {
                const item=frame.offsets[ii]; const slot=item?.slot;
                if (!slotNames.has(slot)) issues.push(`animations.${animName}.drawOrder[${i}].offsets[${ii}]: slot not found`);
                if (seen.has(slot)) issues.push(`animations.${animName}.drawOrder[${i}].offsets[${ii}]: duplicate slot`);
                seen.add(slot);
                if (!Number.isInteger(item?.offset)) issues.push(`animations.${animName}.drawOrder[${i}].offsets[${ii}].offset: must be integer`);
                else if (slotIndex.has(slot)) {
                  const target=slotIndex.get(slot)+item.offset;
                  if (target<0 || target>=slotIndex.size) issues.push(`animations.${animName}.drawOrder[${i}].offsets[${ii}]: target index out of range`);
                }
              }
            }
          }
        }
      }
    }
  }
  return { ok: issues.length === 0, issues, warnings };
}

export function applyAnimationPlan(raw, plan) {
  for (const [index, op] of (plan.operations || []).entries()) {
    try {
      switch (op.op) {
        case 'create_animation': createAnimation(raw, op.name, { replace: !!op.replace }); break;
        case 'clone_animation': cloneAnimation(raw, op.source, op.target, { replace: !!op.replace }); break;
        case 'delete_animation': deleteAnimation(raw, op.name); break;
        case 'retime_animation': retimeAnimation(raw, op.name, op.factor); break;
        case 'clear_bone_timeline': clearBoneTimeline(raw, op.animation, op.bone, op.timeline); break;
        case 'set_bone_key': setBoneKey(raw, op.animation, op.bone, op.timeline, op.time, op.values || {}, { curve: op.curve }); break;
        case 'delete_bone_key': deleteBoneKey(raw, op.animation, op.bone, op.timeline, op.time); break;
        case 'set_slot_attachment_key': setSlotAttachmentKey(raw, op.animation, op.slot, op.time, op.name ?? null); break;
        case 'delete_slot_attachment_key': deleteSlotAttachmentKey(raw, op.animation, op.slot, op.time); break;
        case 'set_ik_key': setIkKey(raw, op.animation, op.constraint, op.time, op.values || {}, { curve: op.curve }); break;
        case 'delete_ik_key': deleteIkKey(raw, op.animation, op.constraint, op.time); break;
        case 'set_draw_order_key': setDrawOrderKey(raw, op.animation, op.time, op.offsets || []); break;
        case 'delete_draw_order_key': deleteDrawOrderKey(raw, op.animation, op.time); break;
        default: throw new Error(`Unknown operation: ${op.op}`);
      }
    } catch (error) {
      throw new Error(`Plan operation #${index + 1} (${op.op || 'unknown'}) failed: ${error.message}`);
    }
  }
  return raw;
}
