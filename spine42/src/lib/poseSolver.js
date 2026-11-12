import { inferSemanticRig, semanticLandmarks } from './semanticRig.js';
import { samplePose } from './poseOps.js';
import { applyAnimationPlan } from './animationOps.js';

function norm(a){ let v=Number(a)||0; while(v>180)v-=360; while(v<-180)v+=360; return v; }
function deg(x,y){ return Math.atan2(y,x)*180/Math.PI; }
function boneMap(raw){ return new Map((raw?.bones||[]).map(b=>[b.name,b])); }
function inheritedParentMatrix(rawByBone,poseByBone,boneName){
  const bone=rawByBone.get(boneName)||{},parent=bone.parent?poseByBone.get(bone.parent)?.world:null;if(!parent)return {a:1,b:0,c:0,d:1};
  const mode=bone.inherit||'normal';if(mode==='onlyTranslation')return {a:1,b:0,c:0,d:1};
  return parent;
}

function invVec(m,x,y){ const det=m.a*m.d-m.b*m.c; if(Math.abs(det)<1e-10) throw new Error('Singular transform'); return {x:(x*m.d-y*m.b)/det,y:(y*m.a-x*m.c)/det}; }
function mulMat(p,l){ return {a:p.a*l.a+p.b*l.c,b:p.a*l.b+p.b*l.d,c:p.c*l.a+p.d*l.c,d:p.c*l.b+p.d*l.d}; }
function localMat(rotation,scaleX=1,scaleY=1,shearX=0,shearY=0){
  const rx=(rotation+shearX)*Math.PI/180, ry=(rotation+90+shearY)*Math.PI/180;
  return {a:Math.cos(rx)*scaleX,b:Math.cos(ry)*scaleY,c:Math.sin(rx)*scaleX,d:Math.sin(ry)*scaleY};
}
function solveSegment(rawByBone,parentMatrix,boneName,childName,worldDelta){
  const bone=rawByBone.get(boneName)||{},child=rawByBone.get(childName)||{};
  const dp=invVec(parentMatrix,worldDelta.x,worldDelta.y),X=Number(child.x||0),Y=Number(child.y||0),sy=Number(bone.scaleY??1);
  if(Math.abs(Number(bone.shearX||0))>1e-7||Math.abs(Number(bone.shearY||0))>1e-7) throw new Error(`Explicit segment solver does not yet support setup shear: ${boneName}`);
  const desiredLen=Math.hypot(dp.x,dp.y),scaledY=Y*sy;
  const totalSx=Math.abs(X)>1e-8?Math.sqrt(Math.max(0,desiredLen*desiredLen-scaledY*scaledY))/Math.abs(X):Number(bone.scaleX??1);
  const localOffsetAngle=Math.atan2(scaledY,X*totalSx)*180/Math.PI;
  const totalRotation=deg(dp.x,dp.y)-localOffsetAngle;
  const setupRot=Number(bone.rotation||0),setupSx=Number(bone.scaleX??1);
  const rotateOffset=norm(totalRotation-setupRot),scaleKey=setupSx?totalSx/setupSx:totalSx;
  const matrix=mulMat(parentMatrix,localMat(totalRotation,totalSx,sy,Number(bone.shearX||0),Number(bone.shearY||0)));
  return {rotateOffset,scaleKey,totalRotation,totalSx,matrix,parentLocalVector:dp,localOffsetAngle};
}

function chainRoles(side, limb){
  if (limb==='arm') return [`${side}_shoulder`,`${side}_elbow`,`${side}_wrist`];
  if (limb==='leg') return [`${side}_hip`,`${side}_knee`,`${side}_ankle`];
  throw new Error(`Unsupported limb: ${limb}`);
}

function chooseElbow(start,target,l1,l2,currentMid,{bend=null}={}){
  const dx=target.x-start.x, dy=target.y-start.y;
  const rawD=Math.hypot(dx,dy);
  const minD=Math.abs(l1-l2)+1e-5, maxD=l1+l2-1e-5;
  const d=Math.min(maxD,Math.max(minD,rawD||minD));
  const ux=dx/(rawD||1), uy=dy/(rawD||1);
  const a=(l1*l1-l2*l2+d*d)/(2*d);
  const h=Math.sqrt(Math.max(0,l1*l1-a*a));
  const bx=start.x+ux*a, by=start.y+uy*a;
  const p={x:-uy,y:ux};
  const c1={x:bx+p.x*h,y:by+p.y*h};
  const c2={x:bx-p.x*h,y:by-p.y*h};
  if (bend==='positive') return c1;
  if (bend==='negative') return c2;
  const d1=Math.hypot(c1.x-currentMid.x,c1.y-currentMid.y);
  const d2=Math.hypot(c2.x-currentMid.x,c2.y-currentMid.y);
  return d1<=d2?c1:c2;
}


function ikForChain(raw,b0,b1){
  return (raw?.ik||[]).find(c=>Array.isArray(c?.bones) && c.bones.includes(b0) && c.bones.includes(b1) && c.target) || null;
}
function ikConstraintsTouching(raw,bones){const set=new Set(bones);return (raw?.ik||[]).filter(c=>Array.isArray(c?.bones)&&c.bones.some(b=>set.has(b)));}

function worldToParentLocal(poseByBone, rawByBone, boneName, world){
  const parentName=rawByBone.get(boneName)?.parent;
  if (!parentName) return {x:world.x,y:world.y};
  const p=poseByBone.get(parentName)?.world;
  if (!p) throw new Error(`Parent pose missing for ${boneName}: ${parentName}`);
  const dx=world.x-p.x, dy=world.y-p.y;
  const det=p.a*p.d-p.b*p.c;
  if (Math.abs(det)<1e-9) throw new Error(`Singular parent transform for ${boneName}`);
  return {x:(dx*p.d-dy*p.b)/det,y:(dy*p.a-dx*p.c)/det};
}

function parentWorldRotation(poseByBone, rawByBone, boneName){
  const bone=rawByBone.get(boneName)||{},parent=bone.parent;if((bone.inherit||'normal')==='onlyTranslation')return 0;
  return parent ? (poseByBone.get(parent)?.world?.rotationX ?? 0) : 0;
}

export function solveTwoBoneTarget(raw, semanticRig, poseResult, {side,limb,target,bend=null,time=0,animation}){
  if (!['L','R'].includes(side)) throw new Error(`Invalid side: ${side}`);
  if (!target || !Number.isFinite(Number(target.x)) || !Number.isFinite(Number(target.y))) throw new Error('Target requires finite x/y');
  const [r0,r1,r2]=chainRoles(side,limb);
  const b0=semanticRig?.roles?.[r0]?.bone, b1=semanticRig?.roles?.[r1]?.bone, b2=semanticRig?.roles?.[r2]?.bone;
  if (!b0||!b1||!b2) throw new Error(`Semantic chain missing for ${side} ${limb}: ${r0}/${r1}/${r2}`);
  const poseByBone=new Map((poseResult?.bones||[]).map(b=>[b.name,b]));
  const rawByBone=boneMap(raw);
  const p0=poseByBone.get(b0)?.world, p1=poseByBone.get(b1)?.world, p2=poseByBone.get(b2)?.world;
  if (!p0||!p1||!p2) throw new Error(`Pose chain missing runtime bones for ${side} ${limb}`);
  const l1=Math.hypot(p1.x-p0.x,p1.y-p0.y), l2=Math.hypot(p2.x-p1.x,p2.y-p1.y);
  const desired={x:Number(target.x),y:Number(target.y)};
  const constraint=limb==='leg' ? ikForChain(raw,b0,b1) : null;
  if (constraint) {
    const targetBone=constraint.target;
    const targetRaw=rawByBone.get(targetBone);
    if (!targetRaw) throw new Error(`IK target bone not found: ${targetBone}`);
    const desiredLocal=worldToParentLocal(poseByBone,rawByBone,targetBone,desired);
    const tx=desiredLocal.x-Number(targetRaw.x||0), ty=desiredLocal.y-Number(targetRaw.y||0);
    return {
      side,limb,roles:[r0,r1,r2],bones:[b0,b1,b2],target:desired,lengths:[l1,l2],control:'ik-target',constraint:constraint.name,targetBone,
      operations:[
        {op:'set_bone_key',animation,bone:targetBone,timeline:'translate',time:Number(time),values:{x:tx,y:ty}},
        {op:'set_ik_key',animation,constraint:constraint.name,time:Number(time),values:{mix:1,bendPositive:constraint.bendPositive!==false}},
      ]
    };
  }
  const mid=chooseElbow({x:p0.x,y:p0.y},desired,l1,l2,{x:p1.x,y:p1.y},{bend});
  const upperWorld=deg(mid.x-p0.x,mid.y-p0.y);
  const lowerWorld=deg(desired.x-mid.x,desired.y-mid.y);
  const parentRot=parentWorldRotation(poseByBone,rawByBone,b0);
  const upperSetup=Number(rawByBone.get(b0)?.rotation||0);
  const lowerSetup=Number(rawByBone.get(b1)?.rotation||0);
  const upperLocal=norm(upperWorld-parentRot);
  const lowerLocal=norm(lowerWorld-upperWorld);
  const upperOffset=norm(upperLocal-upperSetup);
  const lowerOffset=norm(lowerLocal-lowerSetup);
  return {
    side,limb,roles:[r0,r1,r2],bones:[b0,b1,b2],target:desired,solvedMid:mid,lengths:[l1,l2],
    angles:{upperWorld,lowerWorld,parentWorld:parentRot,upperLocal,lowerLocal,upperOffset,lowerOffset},
    operations:[
      {op:'set_bone_key',animation,bone:b0,timeline:'rotate',time:Number(time),values:{value:upperOffset}},
      {op:'set_bone_key',animation,bone:b1,timeline:'rotate',time:Number(time),values:{value:lowerOffset}},
    ]
  };
}




export function solvePelvisTarget(raw, semanticRig, poseResult, {target,time=0,animation}){
  const pelvis=semanticRig?.roles?.pelvis?.bone;if(!pelvis)throw new Error('Semantic pelvis role missing');
  const rawByBone=boneMap(raw),poseByBone=new Map((poseResult?.bones||[]).map(b=>[b.name,b])),p=poseByBone.get(pelvis)?.world;
  if(!p)throw new Error('Pelvis pose missing');
  const driver=rawByBone.get(pelvis)?.parent||pelvis,driverPose=poseByBone.get(driver)?.world;
  if(!driverPose)throw new Error(`Pelvis driver pose missing: ${driver}`);
  const delta={x:Number(target.x)-p.x,y:Number(target.y)-p.y},desiredDriver={x:driverPose.x+delta.x,y:driverPose.y+delta.y};
  const driverParent=rawByBone.get(driver)?.parent,parentPose=driverParent?poseByBone.get(driverParent)?.world:null;
  let local;
  if(parentPose){const dx=desiredDriver.x-parentPose.x,dy=desiredDriver.y-parentPose.y;local=invVec(parentPose,dx,dy);}else local=desiredDriver;
  const dr=rawByBone.get(driver)||{},tx=local.x-Number(dr.x||0),ty=local.y-Number(dr.y||0);
  const operations=[{op:'set_bone_key',animation,bone:driver,timeline:'translate',time:Number(time),values:{x:tx,y:ty}}];
  let rotateOffset=null;
  if(Number.isFinite(Number(target.rotation))){
    const pr=rawByBone.get(pelvis)||{},parentM=rawByBone.get(pelvis)?.parent?poseByBone.get(rawByBone.get(pelvis).parent)?.world:{a:1,b:0,c:0,d:1};
    const ang=Number(target.rotation)*Math.PI/180,lv=invVec(parentM,Math.cos(ang),Math.sin(ang)),localAngle=deg(lv.x,lv.y);rotateOffset=norm(localAngle-Number(pr.rotation||0));
    operations.push({op:'set_bone_key',animation,bone:pelvis,timeline:'rotate',time:Number(time),values:{value:rotateOffset}});
  }
  return {control:'pelvis-anchor',role:'pelvis',bone:pelvis,driver,target:{x:Number(target.x),y:Number(target.y),rotation:target.rotation??null},delta,operations,rotateOffset};
}

export function solveChestTarget(raw, semanticRig, poseResult, {target,time=0,animation}){
  const chest=semanticRig?.roles?.chest?.bone;
  if(!chest)throw new Error('Semantic chest role missing');
  const rawByBone=boneMap(raw),poseByBone=new Map((poseResult?.bones||[]).map(b=>[b.name,b]));
  const driver=rawByBone.get(chest)?.parent;if(!driver)throw new Error(`Chest ${chest} has no driver parent`);
  const driverPose=poseByBone.get(driver)?.world;if(!driverPose)throw new Error(`Chest driver pose missing: ${driver}`);
  const parentName=rawByBone.get(driver)?.parent,parentM=parentName?poseByBone.get(parentName)?.world:{a:1,b:0,c:0,d:1};
  if(!parentM)throw new Error(`Chest driver parent matrix missing: ${parentName}`);
  const desired={x:Number(target.x),y:Number(target.y)};
  const seg=solveSegment(rawByBone,parentM,driver,chest,{x:desired.x-driverPose.x,y:desired.y-driverPose.y});
  const operations=[
    {op:'set_bone_key',animation,bone:driver,timeline:'rotate',time:Number(time),values:{value:seg.rotateOffset}},
    {op:'set_bone_key',animation,bone:driver,timeline:'scalex',time:Number(time),values:{value:seg.scaleKey}},
  ];
  let chestOffset=null;
  if(Number.isFinite(Number(target.rotation))){
    const ang=Number(target.rotation)*Math.PI/180,lv=invVec(seg.matrix,Math.cos(ang),Math.sin(ang)),localAngle=deg(lv.x,lv.y),chestRaw=rawByBone.get(chest)||{};
    chestOffset=norm(localAngle-Number(chestRaw.rotation||0));operations.push({op:'set_bone_key',animation,bone:chest,timeline:'rotate',time:Number(time),values:{value:chestOffset}});
  }
  return {control:'chest-anchor',role:'chest',bone:chest,driver,target:desired,rotationTarget:Number.isFinite(Number(target.rotation))?Number(target.rotation):null,segment:seg,chestOffset,operations};
}

export function solveExplicitJointChain(raw, semanticRig, poseResult, {side,limb,midTarget,endTarget,time=0,animation}){
  const [r0,r1,r2]=chainRoles(side,limb);
  const b0=semanticRig?.roles?.[r0]?.bone,b1=semanticRig?.roles?.[r1]?.bone,b2=semanticRig?.roles?.[r2]?.bone;
  if(!b0||!b1||!b2) throw new Error(`Semantic chain missing for ${side} ${limb}`);
  const poseByBone=new Map((poseResult?.bones||[]).map(b=>[b.name,b])),rawByBone=boneMap(raw);
  const p0=poseByBone.get(b0)?.world,p1=poseByBone.get(b1)?.world,p2=poseByBone.get(b2)?.world;
  if(!p0||!p1||!p2) throw new Error(`Pose chain missing runtime bones for ${side} ${limb}`);
  const mid={x:Number(midTarget.x),y:Number(midTarget.y)},end={x:Number(endTarget.x),y:Number(endTarget.y)};
  const baseL1=Math.hypot(p1.x-p0.x,p1.y-p0.y),baseL2=Math.hypot(p2.x-p1.x,p2.y-p1.y);
  const desiredL1=Math.hypot(mid.x-p0.x,mid.y-p0.y),desiredL2=Math.hypot(end.x-mid.x,end.y-mid.y);
  const parentName=rawByBone.get(b0)?.parent; const parentM=inheritedParentMatrix(rawByBone,poseByBone,b0);
  if(!parentM) throw new Error(`Parent matrix missing for ${b0}`);
  const upper=solveSegment(rawByBone,parentM,b0,b1,{x:mid.x-p0.x,y:mid.y-p0.y});
  const lower=solveSegment(rawByBone,upper.matrix,b1,b2,{x:end.x-mid.x,y:end.y-mid.y});
  const upperOffset=upper.rotateOffset,lowerOffset=lower.rotateOffset,sx0=upper.scaleKey,sx1=lower.scaleKey;
  const upperWorld=deg(mid.x-p0.x,mid.y-p0.y),lowerWorld=deg(end.x-mid.x,end.y-mid.y),parentRot=parentWorldRotation(poseByBone,rawByBone,b0);
  const operations=[
    {op:'set_bone_key',animation,bone:b0,timeline:'rotate',time:Number(time),values:{value:upperOffset}},
    {op:'set_bone_key',animation,bone:b1,timeline:'rotate',time:Number(time),values:{value:lowerOffset}},
    {op:'set_bone_key',animation,bone:b0,timeline:'scalex',time:Number(time),values:{value:sx0}},
    {op:'set_bone_key',animation,bone:b1,timeline:'scalex',time:Number(time),values:{value:sx1}},
  ];
  let terminal=null;
  if(Number.isFinite(Number(endTarget.rotation))){
    const desiredAngle=Number(endTarget.rotation)*Math.PI/180,worldDir={x:Math.cos(desiredAngle),y:Math.sin(desiredAngle)};
    const localDir=invVec(lower.matrix,worldDir.x,worldDir.y),localAngle=deg(localDir.x,localDir.y);
    const terminalRaw=rawByBone.get(b2)||{},setupRot=Number(terminalRaw.rotation||0),rotateOffset=norm(localAngle-setupRot);
    operations.push({op:'set_bone_key',animation,bone:b2,timeline:'rotate',time:Number(time),values:{value:rotateOffset}});
    const ux=Math.cos(localAngle*Math.PI/180),uy=Math.sin(localAngle*Math.PI/180);
    const wx=lower.matrix.a*ux+lower.matrix.b*uy,wy=lower.matrix.c*ux+lower.matrix.d*uy,xFactor=Math.hypot(wx,wy)||1;
    const yAngle=(localAngle+90)*Math.PI/180,vyx=Math.cos(yAngle),vyy=Math.sin(yAngle);
    const wyx=lower.matrix.a*vyx+lower.matrix.b*vyy,wyy=lower.matrix.c*vyx+lower.matrix.d*vyy,yFactor=Math.hypot(wyx,wyy)||1;
    const setupSx=Number(terminalRaw.scaleX??1),setupSy=Number(terminalRaw.scaleY??1);
    const keySx=Number.isFinite(Number(endTarget.scaleX)) ? Number(endTarget.scaleX)/(xFactor*setupSx) : 1;
    const keySy=Number.isFinite(Number(endTarget.scaleY)) ? Number(endTarget.scaleY)/(yFactor*setupSy) : 1;
    if(Number.isFinite(Number(endTarget.scaleX))||Number.isFinite(Number(endTarget.scaleY))) operations.push({op:'set_bone_key',animation,bone:b2,timeline:'scale',time:Number(time),values:{x:keySx,y:keySy}});
    terminal={desiredRotation:Number(endTarget.rotation),localAngle,rotateOffset,keyScaleX:keySx,keyScaleY:keySy,xFactor,yFactor};
  }
  const constraints=ikConstraintsTouching(raw,[b0,b1,b2]);
  for(let i=constraints.length-1;i>=0;i--){const c=constraints[i];operations.unshift({op:'set_ik_key',animation,constraint:c.name,time:Number(time),values:{mix:0,bendPositive:c.bendPositive!==false}});}
  return {side,limb,roles:[r0,r1,r2],bones:[b0,b1,b2],control:'explicit-mid-end',midTarget:mid,endTarget:end,lengths:{base:[baseL1,baseL2],desired:[desiredL1,desiredL2],scaleX:[sx0,sx1]},angles:{upperWorld,lowerWorld,parentWorld:parentRot,upperOffset,lowerOffset,upperTotalRotation:upper.totalRotation,lowerTotalRotation:lower.totalRotation},constraints:constraints.map(c=>c.name),terminal,operations};
}

export function solvePoseTargets(raw, poseResult, spec, {semanticRig=inferSemanticRig(raw)}={}){
  const animation=spec?.animation;
  if (!animation) throw new Error('Pose target spec requires animation');
  const time=Number(spec?.time||0),targets=spec?.targets||{},solutions=[],operations=[],unsupported=[];
  const chains=[
    {side:'L',limb:'arm',mid:'L_elbow',end:'L_wrist'}, {side:'R',limb:'arm',mid:'R_elbow',end:'R_wrist'},
    {side:'L',limb:'leg',mid:'L_knee',end:'L_ankle'}, {side:'R',limb:'leg',mid:'R_knee',end:'R_ankle'},
  ];
  const consumed=new Set();
  for(const c of chains){
    const mid=targets[c.mid],end=targets[c.end];
    if(mid&&end){
      const sol=solveExplicitJointChain(raw,semanticRig,poseResult,{side:c.side,limb:c.limb,midTarget:mid,endTarget:end,time,animation});
      solutions.push({...sol,targetRoles:[c.mid,c.end]});operations.push(...sol.operations);consumed.add(c.mid);consumed.add(c.end);
    } else if(end){
      const sol=solveTwoBoneTarget(raw,semanticRig,poseResult,{side:c.side,limb:c.limb,target:end,time,animation,bend:end?.bend||null});
      solutions.push({...sol,targetRole:c.end});operations.push(...sol.operations);consumed.add(c.end);
    }
  }
  for(const role of Object.keys(targets)) if(!consumed.has(role)) unsupported.push(role);
  return {animation,time,semanticRig,solutions,operations,unsupported};
}


function explicitChainConstraintOps(raw,semanticRig,targets,{animation,time}){
  const defs=[['L','arm','L_elbow','L_wrist'],['R','arm','R_elbow','R_wrist'],['L','leg','L_knee','L_ankle'],['R','leg','R_knee','R_ankle']],seen=new Set(),ops=[];
  for(const [side,limb,mid,end] of defs){if(!targets?.[mid]||!targets?.[end])continue;const [r0,r1,r2]=chainRoles(side,limb),bones=[semanticRig?.roles?.[r0]?.bone,semanticRig?.roles?.[r1]?.bone,semanticRig?.roles?.[r2]?.bone].filter(Boolean);for(const c of ikConstraintsTouching(raw,bones)){if(seen.has(c.name))continue;seen.add(c.name);ops.push({op:'set_ik_key',animation,constraint:c.name,time:Number(time),values:{mix:0,bendPositive:c.bendPositive!==false}});}}
  return ops;
}

function resolveLimbLocalTargets(semanticRig,poseResult,limbLocalTargets,targets){
  if(!limbLocalTargets?.chains)return targets;const lm=semanticLandmarks(semanticRig,poseResult),pelvis=lm.joints.pelvis,chest=lm.joints.chest;if(!pelvis||!chest)return targets;const torsoAngle=Math.atan2(chest.y-pelvis.y,chest.x-pelvis.x),out={...targets};
  const rot=(v)=>{const c=Math.cos(torsoAngle),s=Math.sin(torsoAngle);return {x:v.x*c-v.y*s,y:v.x*s+v.y*c}};
  for(const c of Object.values(limbLocalTargets.chains)){const root=lm.joints[c.rootRole];if(!root)continue;const u=rot(c.upper),l=rot(c.lower),mid={x:root.x+u.x,y:root.y+u.y},end={x:mid.x+l.x,y:mid.y+l.y};out[c.midRole]={...(out[c.midRole]||{}),...mid};out[c.endRole]={...(out[c.endRole]||{}),...end};if(Number.isFinite(Number(c.endRotationLocal)))out[c.endRole].rotation=torsoAngle*180/Math.PI+Number(c.endRotationLocal);if(Number.isFinite(Number(c.endScaleX)))out[c.endRole].scaleX=Number(c.endScaleX);if(Number.isFinite(Number(c.endScaleY)))out[c.endRole].scaleY=Number(c.endScaleY);}
  return out;
}

export function solvePoseTargetsStaged(raw, atlasText, spec, {semanticRig=inferSemanticRig(raw)}={}){
  const allOperations=[],solutions=[]; const animation=spec?.animation,time=Number(spec?.time||0);let targets={...(spec?.targets||{})};
  if(!animation) throw new Error('Pose target spec requires animation');
  let pose=samplePose(raw,atlasText,{animationName:animation,time});
  if(targets.pelvis){
    const pelvis=solvePelvisTarget(raw,semanticRig,pose,{target:targets.pelvis,time,animation});
    applyAnimationPlan(raw,{operations:pelvis.operations});allOperations.push(...pelvis.operations);solutions.push(pelvis);
    pose=samplePose(raw,atlasText,{animationName:animation,time});
  }
  if(targets.chest){
    const torso=solveChestTarget(raw,semanticRig,pose,{target:targets.chest,time,animation});
    applyAnimationPlan(raw,{operations:torso.operations}); allOperations.push(...torso.operations);solutions.push(torso);
    pose=samplePose(raw,atlasText,{animationName:animation,time});
  }
  const handoffOps=explicitChainConstraintOps(raw,semanticRig,targets,{animation,time});
  if(handoffOps.length){applyAnimationPlan(raw,{operations:handoffOps});allOperations.push(...handoffOps);solutions.push({control:'constraint-handoff',operations:handoffOps,constraints:handoffOps.map(o=>o.constraint)});pose=samplePose(raw,atlasText,{animationName:animation,time});}
  targets=resolveLimbLocalTargets(semanticRig,pose,spec?.limbLocalTargets,targets);
  const limbTargets=Object.fromEntries(Object.entries(targets).filter(([k])=>k!=='chest'&&k!=='pelvis'));
  if(Object.keys(limbTargets).length){
    const limb=solvePoseTargets(raw,pose,{...spec,targets:limbTargets},{semanticRig});
    applyAnimationPlan(raw,{operations:limb.operations}); allOperations.push(...limb.operations);solutions.push(...limb.solutions);
    pose=samplePose(raw,atlasText,{animationName:animation,time});
  }
  return {animation,time,semanticRig,solutions,operations:allOperations,unsupported:[],pose,resolvedTargets:targets,residual:poseResiduals(semanticRig,pose,targets)};
}

export function poseResiduals(semanticRig, poseResult, targets){
  const lm=semanticLandmarks(semanticRig,poseResult);
  const out={}; let max=0,sum=0,count=0;
  for (const [role,t] of Object.entries(targets||{})) {
    const p=lm.joints[role];
    if (!p) { out[role]={missing:true}; continue; }
    const distance=Math.hypot(p.x-Number(t.x),p.y-Number(t.y));
    out[role]={distance,actual:{x:p.x,y:p.y},target:{x:Number(t.x),y:Number(t.y)}};
    max=Math.max(max,distance); sum+=distance; count++;
  }
  return {roles:out,maxDistance:max,meanDistance:count?sum/count:0,count};
}
