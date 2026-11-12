import { inferSemanticRig, semanticLandmarks } from './semanticRig.js';
import { samplePose } from './poseOps.js';

const FRONT_RUN_REQUIRED=['L_shoulder','L_elbow','L_wrist','R_shoulder','R_elbow','R_wrist','pelvis','chest'];
function dist(a,b){return a&&b?Math.hypot(Number(a.x)-Number(b.x),Number(a.y)-Number(b.y)):0;}
function frameTimes(duration,frames){const n=Math.max(3,Number(frames)||13);return Array.from({length:n},(_,i)=>duration*(i/(n-1)));}

export function assessMotionSanity(raw,atlasText,{animationName,profile='front-run',frames=13,minUpperOutRatio=-.05,minForeOutRatio=-.05,frontWristSeparationRatio=.08}={}){
  if(!raw||!atlasText||!animationName)throw new Error('assessMotionSanity requires raw, atlasText, and animationName');
  if(profile!=='front-run')return {format:'zhuda-motion-sanity-report',version:1,status:'SKIPPED',profile,animation:animationName,reason:`Unsupported profile: ${profile}`};
  const rig=inferSemanticRig(raw),missing=FRONT_RUN_REQUIRED.filter(r=>!rig.roles?.[r]?.bone);
  if(missing.length)return {format:'zhuda-motion-sanity-report',version:1,status:'BLOCKED',profile,animation:animationName,sideConvention:rig.sideConvention,issues:[{code:'semantic_roles_missing',severity:'block',roles:missing}]};
  if(rig.sideConvention!=='anatomical-lr')return {format:'zhuda-motion-sanity-report',version:1,status:'BLOCKED',profile,animation:animationName,sideConvention:rig.sideConvention,issues:[{code:'side_convention_incompatible',severity:'block',expected:'anatomical-lr',actual:rig.sideConvention}]};
  const setupPose=samplePose(raw,atlasText,{animationName:'',time:0}),setup=semanticLandmarks(rig,setupPose),first=samplePose(raw,atlasText,{animationName,time:0}),duration=Number(first.duration||0),times=frameTimes(duration,frames);
  const sign={L:Math.sign(setup.joints.L_shoulder.x-setup.joints.R_shoulder.x)||1,R:Math.sign(setup.joints.R_shoulder.x-setup.joints.L_shoulder.x)||-1};
  const baseLen={
    L_upper:dist(setup.joints.L_shoulder,setup.joints.L_elbow)||1,L_fore:dist(setup.joints.L_elbow,setup.joints.L_wrist)||1,
    R_upper:dist(setup.joints.R_shoulder,setup.joints.R_elbow)||1,R_fore:dist(setup.joints.R_elbow,setup.joints.R_wrist)||1,
  };
  const torso=Math.max(1,dist(setup.joints.pelvis,setup.joints.chest)),minFrontSep=Math.max(6,torso*Number(frontWristSeparationRatio));
  const samples=[],issues=[],frontSides=[];
  for(const time of times){
    const pose=samplePose(raw,atlasText,{animationName,time}),lm=semanticLandmarks(rig,pose),j=lm.joints,dy=Math.abs(j.L_wrist.y-j.R_wrist.y);
    if(dy<minFrontSep){samples.push({time,phase:'passing',wristYSeparation:dy});continue;}
    const side=j.L_wrist.y>j.R_wrist.y?'L':'R',other=side==='L'?'R':'L',sg=sign[side],sh=j[`${side}_shoulder`],el=j[`${side}_elbow`],wr=j[`${side}_wrist`],upperLen=baseLen[`${side}_upper`],foreLen=baseLen[`${side}_fore`];
    const upperOut=sg*(el.x-sh.x),foreOut=sg*(wr.x-el.x),upperOutRatio=upperOut/upperLen,foreOutRatio=foreOut/foreLen,wristOwnSide=sg*(wr.x-sh.x)/(upperLen+foreLen);
    const row={time,phase:'front-swing',frontSide:side,otherSide:other,wristYSeparation:dy,upperOut,foreOut,upperOutRatio,foreOutRatio,wristOwnSide};samples.push(row);frontSides.push(side);
    if(upperOutRatio<Number(minUpperOutRatio))issues.push({code:'front_upper_arm_folds_inward',severity:'error',time,side,upperOut,upperOutRatio,threshold:Number(minUpperOutRatio),detail:'Front-swing shoulder→elbow moves toward the torso center before the forearm moves outward.'});
    if(foreOutRatio<Number(minForeOutRatio))issues.push({code:'front_forearm_folds_inward',severity:'error',time,side,foreOut,foreOutRatio,threshold:Number(minForeOutRatio),detail:'Front-swing elbow→wrist reverses toward the torso center.'});
  }
  const unique=new Set(frontSides);if(frontSides.length<2)issues.push({code:'insufficient_front_swing_samples',severity:'warn',count:frontSides.length});else if(unique.size<2)issues.push({code:'front_arm_does_not_alternate',severity:'error',frontSides:[...unique]});
  const errors=issues.filter(x=>x.severity==='error'||x.severity==='block');
  return {format:'zhuda-motion-sanity-report',version:1,status:errors.length?'NEEDS_REVIEW':'PASS',profile,animation:animationName,duration,frames:times.length,sideConvention:rig.sideConvention,thresholds:{minUpperOutRatio:Number(minUpperOutRatio),minForeOutRatio:Number(minForeOutRatio),minFrontWristSeparation:minFrontSep},summary:{frontSwingSamples:frontSides.length,sides:[...unique],violations:errors.length,warnings:issues.length-errors.length},issues,samples};
}
