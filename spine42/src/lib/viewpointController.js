import { inferSemanticRig, semanticLandmarks } from './semanticRig.js';
import { samplePose } from './poseOps.js';
import { retargetReferencePose } from './referencePose.js';
import { applyAnimationPlan } from './animationOps.js';
const INFO={
  L_upper_arm:['L_arm','upper','L_shoulder','L_elbow'],L_forearm:['L_arm','lower','L_elbow','L_wrist'],
  R_upper_arm:['R_arm','upper','R_shoulder','R_elbow'],R_forearm:['R_arm','lower','R_elbow','R_wrist'],
  L_thigh:['L_leg','upper','L_hip','L_knee'],L_shin:['L_leg','lower','L_knee','L_ankle'],
  R_thigh:['R_leg','upper','R_hip','R_knee'],R_shin:['R_leg','lower','R_knee','R_ankle'],
};
function dist(a,b){return a&&b?Math.hypot(Number(a.x)-Number(b.x),Number(a.y)-Number(b.y)):null;}
function ratioFor(spec,segment,setupLm){const x=INFO[segment];if(!x)return 1;const [chain,which,a,b]=x,f=spec?.limbLocalTargets?.chains?.[chain]?.sourceFactors?.[which];if(Number.isFinite(Number(f)))return Number(f);const A=spec?.targets?.[a],B=spec?.targets?.[b],base=dist(setupLm?.joints?.[a],setupLm?.joints?.[b]),cur=dist(A,B);return base&&cur?cur/base:1;}
function choose(controller,ratio){const variants=[...(controller?.variants||[])].sort((a,b)=>Number(a.maxRatio)-Number(b.maxRatio));for(const v of variants)if(Number(ratio)<=Number(v.maxRatio))return v.attachment;return controller.baseAttachment;}
export function applyViewpointControllers({raw,atlasText,motion,animation,manifest,timeScale=1,semanticRig=inferSemanticRig(raw)}={}){
  const meta=manifest?.metadata||{},controllers=meta.viewpointControllers||[];if(!controllers.length)return {applied:false,operations:[],controllers:[],keys:[]};const setup=samplePose(raw,atlasText,{animationName:'',time:0}),setupLm=semanticLandmarks(semanticRig,setup),controlled=new Set(controllers.map(c=>c.slot)),ops=[],keys=[];
  for(const family of meta.decomposedFamilies||[]){if(family.sourceSlot)ops.push({op:'set_slot_attachment_key',animation,slot:family.sourceSlot,time:0,name:null});for(let i=0;i<(family.slots||[]).length;i++){const slot=family.slots[i],att=family.attachments?.[i];if(slot&&att&&!controlled.has(slot))ops.push({op:'set_slot_attachment_key',animation,slot,time:0,name:att});}}
  const cache=new Map();for(const frame of motion?.frames||[]){const t=Number(frame.time||0)*Number(timeScale||1),k=Number(frame.time||0);let spec=cache.get(k);if(!spec){spec=retargetReferencePose(frame.pose,semanticRig,setup,{animation,time:t,solverTargetsOnly:false});cache.set(k,spec);}for(const c of controllers){const ratio=ratioFor(spec,c.driverSegment||c.segment,setupLm),att=choose(c,ratio);keys.push({time:t,segment:c.segment,slot:c.slot,ratio,attachment:att});}}
  for(const c of controllers){let prev=Symbol('none');for(const k of keys.filter(x=>x.slot===c.slot).sort((a,b)=>a.time-b.time)){if(k.attachment===prev)continue;ops.push({op:'set_slot_attachment_key',animation,slot:c.slot,time:k.time,name:k.attachment});prev=k.attachment;}}
  applyAnimationPlan(raw,{operations:ops});return {applied:true,operations:ops,controllers:controllers.map(c=>({segment:c.segment,slot:c.slot,baseAttachment:c.baseAttachment,variants:c.variants})),keys};
}
