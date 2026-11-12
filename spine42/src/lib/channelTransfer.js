import { deepClone, retimeAnimationNode } from './animationOps.js';

function attachmentMap(raw){
  const out=new Map();const add=(slot,name,data)=>{if(!out.has(slot))out.set(slot,new Map());out.get(slot).set(name,data);};
  if(Array.isArray(raw?.skins)) for(const skin of raw.skins) for(const [slot,atts] of Object.entries(skin?.attachments||{})) for(const [name,d] of Object.entries(atts||{}))add(slot,name,d);
  else for(const skin of Object.values(raw?.skins||{})) for(const [slot,atts] of Object.entries(skin||{})) for(const [name,d] of Object.entries(atts||{}))add(slot,name,d);
  return out;
}
function constraintNames(raw,key){
  const v=raw?.[key]; if(Array.isArray(v))return new Set(v.map(x=>x?.name).filter(Boolean)); return new Set(Object.keys(v||{}));
}
function compatibleDeform(targetRaw,deform){
  const atts=attachmentMap(targetRaw),out={};let kept=0,dropped=0;
  for(const [skin,slots] of Object.entries(deform||{})){
    for(const [slot,attachments] of Object.entries(slots||{})){
      for(const [att,frames] of Object.entries(attachments||{})){
        if(!atts.get(slot)?.has(att)){dropped++;continue;}
        (((out[skin]??={})[slot]??={})[att])=deepClone(frames);kept++;
      }
    }
  }
  return {out,kept,dropped};
}
function scaleTimes(node,factor){ if(factor!==1) retimeAnimationNode(node,factor); return node; }

export function transferCompatibleAnimationChannels(targetRaw,sourceAnimation,targetAnimationName,{timeScale=1,excludeBones=null}={}){
  const target=targetRaw.animations?.[targetAnimationName]; if(!target)throw new Error(`Target animation not found: ${targetAnimationName}`);
  const excluded=excludeBones instanceof Set?excludeBones:new Set(excludeBones||[]);
  const boneNames=new Set((targetRaw.bones||[]).map(b=>b.name)),slotNames=new Set((targetRaw.slots||[]).map(s=>s.name)),atts=attachmentMap(targetRaw);
  const report={bones:{kept:0,dropped:0},slots:{kept:0,dropped:0},constraints:{kept:0,dropped:0},deform:{kept:0,dropped:0},drawOrder:{kept:0,dropped:0}};
  for(const [bone,tls] of Object.entries(sourceAnimation?.bones||{})){
    if(!boneNames.has(bone)||excluded.has(bone)){report.bones.dropped++;continue;}
    (target.bones??={})[bone]=scaleTimes(deepClone(tls),Number(timeScale||1));report.bones.kept++;
  }
  for(const [slot,tls] of Object.entries(sourceAnimation?.slots||{})){
    if(!slotNames.has(slot)){report.slots.dropped++;continue;}
    const copy=deepClone(tls);
    if(Array.isArray(copy.attachment)) copy.attachment=copy.attachment.filter(f=>f?.name==null || atts.get(slot)?.has(f.name));
    (target.slots??={})[slot]=scaleTimes(copy,Number(timeScale||1));report.slots.kept++;
  }
  for(const key of ['ik','transform','path','physics']){
    const names=constraintNames(targetRaw,key),src=sourceAnimation?.[key];if(!src)continue;
    for(const [name,frames] of Object.entries(src)){
      const def=Array.isArray(targetRaw?.[key]) ? targetRaw[key].find(x=>x?.name===name) : null;
      const touchesExcluded=def && ([...(def.bones||[]),def.target].filter(Boolean).some(b=>excluded.has(b)));
      if(!names.has(name)||touchesExcluded){report.constraints.dropped++;continue;}
      ((target[key]??={})[name])=scaleTimes(deepClone(frames),Number(timeScale||1));report.constraints.kept++;
    }
  }
  if(sourceAnimation?.deform){const d=compatibleDeform(targetRaw,sourceAnimation.deform);if(Object.keys(d.out).length)target.deform=scaleTimes(d.out,Number(timeScale||1));report.deform.kept=d.kept;report.deform.dropped=d.dropped;}
  if(Array.isArray(sourceAnimation?.drawOrder)){
    const copy=[];for(const f of sourceAnimation.drawOrder){const offsets=(f.offsets||[]).filter(o=>slotNames.has(o.slot));if((f.offsets||[]).length&&!offsets.length){report.drawOrder.dropped++;continue;}copy.push({...deepClone(f),offsets});report.drawOrder.kept++;}
    if(copy.length)target.drawOrder=scaleTimes(copy,Number(timeScale||1));
  }
  return report;
}
