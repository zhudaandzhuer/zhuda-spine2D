import { inferSemanticRig } from './semanticRig.js';
import { samplePose } from './poseOps.js';
import { createAnimation, applyAnimationPlan } from './animationOps.js';
import { captureReferencePose, captureRootMotion, captureAnimationVisualState, retargetReferencePose, visualStateOperations } from './referencePose.js';
import { solvePoseTargetsStaged } from './poseSolver.js';
import { transferCompatibleAnimationChannels } from './channelTransfer.js';

export function makePortableReferenceMotion(motion,{keepVisualState=false,keepChannels=false,keepSourceAnimation=false}={}){
  if(motion?.format!=='zhuda-semantic-motion') throw new Error('Expected zhuda-semantic-motion');
  const out=structuredClone(motion);
  if(!keepChannels) delete out.channels;
  for(const frame of out.frames||[]) if(!keepVisualState && frame?.pose) delete frame.pose.visualState;
  if(!keepSourceAnimation && out.source) out.source.animation=null;
  out.portable={visualState:!!keepVisualState,channels:!!keepChannels,sourceAnimation:!!keepSourceAnimation};
  return out;
}

export function captureReferenceMotion(raw, atlasText, {animationName,frames=13,times=null,label=null,semanticRig=inferSemanticRig(raw)}={}){
  if(!animationName) throw new Error('captureReferenceMotion requires animationName');
  const first=samplePose(raw,atlasText,{animationName,time:0}),duration=first.duration,setupPose=samplePose(raw,atlasText,{animationName:'',time:0});
  const count=Math.max(2,Math.round(Number(frames)||13));
  const sampleTimes=Array.isArray(times)&&times.length ? times.map(Number) : Array.from({length:count},(_,i)=>duration*i/(count-1));
  const out=[];
  for(const t of sampleTimes){
    const pose=samplePose(raw,atlasText,{animationName,time:t});
    const ref=captureReferencePose(semanticRig,pose,{label:`${label||animationName}@${t.toFixed(4)}`,setupPoseResult:setupPose});
    ref.rootMotion=captureRootMotion(semanticRig,setupPose,pose);
    ref.visualState=captureAnimationVisualState(raw,animationName,t);
    out.push({time:t,pose:ref});
  }
  return {format:'zhuda-semantic-motion',version:1,label:label||animationName,source:{animation:animationName,duration,semantic:{sideConvention:semanticRig?.sideConvention||'unknown',warnings:[...(semanticRig?.warnings||[])]}},channels:structuredClone(raw.animations?.[animationName]||{}),frames:out};
}


function primaryControlBones(raw,rig){
  const set=new Set();
  for(const role of ['pelvis','chest','head','L_shoulder','L_elbow','L_wrist','L_hand','R_shoulder','R_elbow','R_wrist','R_hand','L_hip','L_knee','L_ankle','L_foot','R_hip','R_knee','R_ankle','R_foot']){
    const b=rig?.roles?.[role]?.bone;if(b)set.add(b);
  }
  const by=new Map((raw?.bones||[]).map(b=>[b.name,b]));
  for(const role of ['pelvis','chest']){const b=rig?.roles?.[role]?.bone,p=by.get(b)?.parent;if(p)set.add(p);}
  return set;
}

export function retargetReferenceMotion(raw, atlasText, motion, {animation,replace=true,mirror=false,timeScale=1,semanticRig=inferSemanticRig(raw)}={}){
  if(motion?.format!=='zhuda-semantic-motion') throw new Error('Unsupported motion reference format');
  if(!animation) throw new Error('retargetReferenceMotion requires animation');
  createAnimation(raw,animation,{replace});
  const channelTransfer=motion.channels?transferCompatibleAnimationChannels(raw,motion.channels,animation,{timeScale,excludeBones:primaryControlBones(raw,semanticRig)}):null;
  const setup=samplePose(raw,atlasText,{animationName:'',time:0});
  const reports=[],operations=[];
  for(const frame of motion.frames||[]){
    const targetTime=Number(frame.time||0)*Number(timeScale||1),reference=frame.pose;
    const spec=retargetReferencePose(reference,semanticRig,setup,{animation,time:targetTime,mirror,templateAnimation:null});
    const visualOps=visualStateOperations(raw,animation,targetTime,spec.visualState);
    if(visualOps.length){applyAnimationPlan(raw,{operations:visualOps});operations.push(...visualOps);}
    const solved=solvePoseTargetsStaged(raw,atlasText,spec,{semanticRig});
    operations.push(...solved.operations);
    reports.push({sourceTime:Number(frame.time||0),targetTime,residual:solved.residual,resolvedTargets:structuredClone(solved.resolvedTargets||{}),operations:visualOps.length+solved.operations.length});
  }
  return {animation,duration:(motion.source?.duration||0)*Number(timeScale||1),frames:reports,operations,semanticRig,channelTransfer};
}
