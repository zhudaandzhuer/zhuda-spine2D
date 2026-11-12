import { semanticLandmarks } from './semanticRig.js';

const SOLVER_ROLES=new Set(['pelvis','chest','L_elbow','L_wrist','R_elbow','R_wrist','L_knee','L_ankle','R_knee','R_ankle']);
const DEFAULT_ROLES=[
  'pelvis','chest','head',
  'L_shoulder','L_elbow','L_wrist','R_shoulder','R_elbow','R_wrist',
  'L_hip','L_knee','L_ankle','R_hip','R_knee','R_ankle'
];

const LIMB_CHAINS=[
  {name:'L_arm',root:'L_shoulder',mid:'L_elbow',end:'L_wrist',upperKey:'L_upper_arm',lowerKey:'L_forearm'},
  {name:'R_arm',root:'R_shoulder',mid:'R_elbow',end:'R_wrist',upperKey:'R_upper_arm',lowerKey:'R_forearm'},
  {name:'L_leg',root:'L_hip',mid:'L_knee',end:'L_ankle',upperKey:'L_thigh',lowerKey:'L_shin'},
  {name:'R_leg',root:'R_hip',mid:'R_knee',end:'R_ankle',upperKey:'R_thigh',lowerKey:'R_shin'},
];
function pointDist(a,b){return a&&b?Math.hypot(Number(b.x)-Number(a.x),Number(b.y)-Number(a.y)):null;}
function angleRad(a,b){return a&&b?Math.atan2(Number(b.y)-Number(a.y),Number(b.x)-Number(a.x)):0;}
function rotateXY(x,y,a){const c=Math.cos(a),q=Math.sin(a);return {x:x*c-y*q,y:x*q+y*c};}
function setupSegmentsFromLandmarks(lm){const out={};for(const c of LIMB_CHAINS){const root=lm?.joints?.[c.root],mid=lm?.joints?.[c.mid],end=lm?.joints?.[c.end],a=pointDist(root,mid),b=pointDist(mid,end);if(a>1e-6)out[c.upperKey]=a;if(b>1e-6)out[c.lowerKey]=b;}return out;}

function finite(v){ return Number.isFinite(Number(v)); }
function torsoScale(lm){
  const p=lm?.joints?.pelvis,c=lm?.joints?.chest;
  if (p&&c) { const d=Math.hypot(c.x-p.x,c.y-p.y); if (d>1e-6) return d; }
  const candidates=[lm?.metrics?.shoulderWidth,lm?.metrics?.hipWidth,lm?.metrics?.leftThigh,lm?.metrics?.rightThigh].filter(v=>finite(v)&&Number(v)>1e-6).map(Number).sort((a,b)=>a-b);
  if (!candidates.length) return 1;
  return candidates[Math.floor(candidates.length/2)];
}

function swapSide(role){
  if (role.startsWith('L_')) return 'R_'+role.slice(2);
  if (role.startsWith('R_')) return 'L_'+role.slice(2);
  return role;
}


function normAngle(a){let v=Number(a)||0;while(v>180)v-=360;while(v<-180)v+=360;return v;}
export function captureRootMotion(semanticRig, setupPose, poseResult){
  const setup=semanticLandmarks(semanticRig,setupPose),cur=semanticLandmarks(semanticRig,poseResult),sp=setup.joints.pelvis,cp=cur.joints.pelvis;
  if(!sp||!cp)return null;
  const scale=torsoScale(setup);
  return {x:(cp.x-sp.x)/scale,y:(cp.y-sp.y)/scale,rotation:normAngle(cp.rotation-sp.rotation),scaleX:sp.scaleX?cp.scaleX/sp.scaleX:1,scaleY:sp.scaleY?cp.scaleY/sp.scaleY:1};
}

export function captureReferencePose(semanticRig, poseResult, {roles=DEFAULT_ROLES,label=null,setupPoseResult=null}={}){
  const lm=semanticLandmarks(semanticRig,poseResult),setupLm=setupPoseResult?semanticLandmarks(semanticRig,setupPoseResult):null;
  const origin=lm.joints.pelvis;
  if (!origin) throw new Error('Reference capture requires pelvis landmark');
  const scale=torsoScale(lm);
  const joints={};
  for (const role of roles) {
    const p=lm.joints[role]; if (!p) continue;
    joints[role]={x:(p.x-origin.x)/scale,y:(p.y-origin.y)/scale,rotation:p.rotation,scaleX:p.scaleX,scaleY:p.scaleY,confidence:p.confidence,bone:p.bone};
  }
  return {
    format:'zhuda-semantic-pose',version:1,label,
    source:{animation:poseResult?.animation||null,time:poseResult?.time||0,duration:poseResult?.duration||0,scale,origin:{x:origin.x,y:origin.y},setupSegments:setupSegmentsFromLandmarks(setupLm||lm)},
    joints,
  };
}

function mirroredReferencePoint(reference,role,mirror){const p=reference?.joints?.[role];if(!p)return null;return {x:mirror?-Number(p.x):Number(p.x),y:Number(p.y),rotation:Number.isFinite(Number(p.rotation))?(mirror?180-Number(p.rotation):Number(p.rotation)):null,scaleX:Number(p.scaleX),scaleY:Number(p.scaleY)};}
function buildLimbLocalTargets(reference,targetLm,{mirror=false}={}){
  const sourceBase=reference?.source?.setupSegments;if(!sourceBase||!Object.keys(sourceBase).length)return null;
  const rp=mirroredReferencePoint(reference,'pelvis',mirror),rc=mirroredReferencePoint(reference,'chest',mirror);if(!rp||!rc)return null;const srcTorsoAngle=angleRad(rp,rc),srcScale=Number(reference?.source?.scale||1),chains={};
  for(const c of LIMB_CHAINS){const sr=mirroredReferencePoint(reference,c.root,mirror),sm=mirroredReferencePoint(reference,c.mid,mirror),se=mirroredReferencePoint(reference,c.end,mirror);if(!sr||!sm||!se)continue;const trRole=mirror?swapSide(c.root):c.root,tmRole=mirror?swapSide(c.mid):c.mid,teRole=mirror?swapSide(c.end):c.end,tr=targetLm.joints[trRole],tm=targetLm.joints[tmRole],te=targetLm.joints[teRole];if(!tr||!tm||!te)continue;
    const v1={x:sm.x-sr.x,y:sm.y-sr.y},v2={x:se.x-sm.x,y:se.y-sm.y},cur1=Math.hypot(v1.x,v1.y)*srcScale,cur2=Math.hypot(v2.x,v2.y)*srcScale,base1=Number(sourceBase[c.upperKey]||cur1||1),base2=Number(sourceBase[c.lowerKey]||cur2||1),factor1=base1>1e-6?cur1/base1:1,factor2=base2>1e-6?cur2/base2:1,tbase1=pointDist(tr,tm),tbase2=pointDist(tm,te);if(!(tbase1>1e-6&&tbase2>1e-6))continue;
    const u1=rotateXY(v1.x/Math.max(1e-9,Math.hypot(v1.x,v1.y)),v1.y/Math.max(1e-9,Math.hypot(v1.x,v1.y)),-srcTorsoAngle),u2=rotateXY(v2.x/Math.max(1e-9,Math.hypot(v2.x,v2.y)),v2.y/Math.max(1e-9,Math.hypot(v2.x,v2.y)),-srcTorsoAngle);
    const endRotationLocal=Number.isFinite(se.rotation)?normAngle(se.rotation-srcTorsoAngle*180/Math.PI):null;
    chains[mirror?swapSide(c.name):c.name]={rootRole:trRole,midRole:tmRole,endRole:teRole,upper:{x:u1.x*tbase1*factor1,y:u1.y*tbase1*factor1},lower:{x:u2.x*tbase2*factor2,y:u2.y*tbase2*factor2},endRotationLocal,endScaleX:Number.isFinite(se.scaleX)?se.scaleX:null,endScaleY:Number.isFinite(se.scaleY)?se.scaleY:null,sourceFactors:{upper:factor1,lower:factor2},targetBase:{upper:tbase1,lower:tbase2}};
  }
  return {sourceTorsoAngle:srcTorsoAngle,chains};
}

export function retargetReferencePose(reference, targetSemanticRig, targetSetupPose, {animation,time=0,roles=null,solverTargetsOnly=true,mirror=false,templateAnimation=null}={}){
  if (reference?.format!=='zhuda-semantic-pose') throw new Error('Unsupported reference pose format');
  if (!animation) throw new Error('Retarget requires target animation name');
  const targetLm=semanticLandmarks(targetSemanticRig,targetSetupPose);
  const setupPelvis=targetLm.joints.pelvis;
  if (!setupPelvis) throw new Error('Target rig requires pelvis landmark');
  const scale=torsoScale(targetLm);
  const rm=reference.rootMotion||{};
  const origin={x:setupPelvis.x+(mirror?-Number(rm.x||0):Number(rm.x||0))*scale,y:setupPelvis.y+Number(rm.y||0)*scale};
  const include=roles?new Set(roles):null;
  const targets={};
  for (const [srcRole,p] of Object.entries(reference.joints||{})) {
    const role=mirror?swapSide(srcRole):srcRole;
    if (include && !include.has(role)) continue;
    if (solverTargetsOnly && !SOLVER_ROLES.has(role)) continue;
    if (!targetSemanticRig?.roles?.[role]) continue;
    const nx=mirror?-Number(p.x):Number(p.x), ny=Number(p.y);
    targets[role]={x:origin.x+nx*scale,y:origin.y+ny*scale};
    if(Number.isFinite(Number(p.rotation))) targets[role].rotation=mirror ? 180-Number(p.rotation) : Number(p.rotation);
    if(Number.isFinite(Number(p.scaleX))) targets[role].scaleX=Number(p.scaleX);
    if(Number.isFinite(Number(p.scaleY))) targets[role].scaleY=Number(p.scaleY);
  }
  if(targets.pelvis){
    targets.pelvis.rotation=setupPelvis.rotation+(mirror?-Number(rm.rotation||0):Number(rm.rotation||0));
    targets.pelvis.scaleX=setupPelvis.scaleX*Number(rm.scaleX||1); targets.pelvis.scaleY=setupPelvis.scaleY*Number(rm.scaleY||1);
  }
  const limbLocalTargets=buildLimbLocalTargets(reference,targetLm,{mirror});
  return {animation,time:Number(time),targets,limbLocalTargets,templateAnimation:templateAnimation||null,visualState:reference.visualState||null,meta:{referenceLabel:reference.label||null,sourceScale:reference.source?.scale||null,targetScale:scale,scaleRatio:scale/(reference.source?.scale||scale),mirror,rootMotion:rm}};
}

export function compareLandmarksToReference(reference, targetSemanticRig, poseResult, targetSetupPose, {roles=null,mirror=false}={}){
  const desired=retargetReferencePose(reference,targetSemanticRig,targetSetupPose,{animation:'__qa__',time:poseResult?.time||0,roles,solverTargetsOnly:false,mirror});
  const actual=semanticLandmarks(targetSemanticRig,poseResult);
  const residuals={}; let sum=0,max=0,count=0;
  for (const [role,t] of Object.entries(desired.targets)) {
    const p=actual.joints[role]; if (!p) { residuals[role]={missing:true}; continue; }
    const d=Math.hypot(p.x-t.x,p.y-t.y); residuals[role]={distance:d,actual:{x:p.x,y:p.y},target:t}; sum+=d;max=Math.max(max,d);count++;
  }
  return {count,meanDistance:count?sum/count:0,maxDistance:max,residuals,meta:desired.meta};
}

export const REFERENCE_DEFAULT_ROLES=[...DEFAULT_ROLES];


function defaultSlotAttachments(raw){
  return Object.fromEntries((raw?.slots||[]).map(s=>[s.name,s.attachment ?? null]));
}

export function captureAnimationVisualState(raw, animationName='', time=0){
  const slots=defaultSlotAttachments(raw); const anim=raw?.animations?.[animationName]; const t=Number(time)||0;
  for (const [slotName,timelines] of Object.entries(anim?.slots||{})) {
    const frames=timelines?.attachment; if(!Array.isArray(frames)) continue;
    let chosen=null;
    for (const f of frames) { const ft=Number(f?.time||0); if(ft<=t+1e-8) chosen=f; else break; }
    if (chosen) slots[slotName]=chosen.name ?? null;
  }
  let drawOrder=null;
  for (const f of anim?.drawOrder||[]) { const ft=Number(f?.time||0); if(ft<=t+1e-8) drawOrder=f; else break; }
  return {sourceAnimation:animationName||null,time:t,slots,drawOrder:drawOrder?{offsets:(drawOrder.offsets||[]).map(o=>({slot:o.slot,offset:Number(o.offset||0)}))}:null};
}

function availableAttachments(raw){
  const out=new Map(); const add=(slot,name)=>{if(!out.has(slot))out.set(slot,new Set());out.get(slot).add(name);};
  if(Array.isArray(raw?.skins)) for(const skin of raw.skins) for(const [slot,atts] of Object.entries(skin?.attachments||{})) for(const name of Object.keys(atts||{})) add(slot,name);
  else for(const skin of Object.values(raw?.skins||{})) for(const [slot,atts] of Object.entries(skin||{})) for(const name of Object.keys(atts||{})) add(slot,name);
  return out;
}

export function visualStateOperations(raw, animation, time, visualState){
  if(!visualState) return [];
  const slotNames=new Set((raw?.slots||[]).map(s=>s.name)); const atts=availableAttachments(raw); const ops=[];
  for(const [slot,name] of Object.entries(visualState.slots||{})) {
    if(!slotNames.has(slot)) continue;
    if(name!=null && atts.has(slot) && !atts.get(slot).has(name)) continue;
    ops.push({op:'set_slot_attachment_key',animation,slot,time:Number(time)||0,name:name??null});
  }
  if(visualState.drawOrder?.offsets?.length){
    const offsets=visualState.drawOrder.offsets.filter(o=>slotNames.has(o.slot)).map(o=>({slot:o.slot,offset:Number(o.offset||0)}));
    if(offsets.length) ops.push({op:'set_draw_order_key',animation,time:Number(time)||0,offsets});
  }
  return ops;
}
