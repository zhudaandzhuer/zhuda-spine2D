import { inferSemanticRig, semanticLandmarks } from './semanticRig.js';
import { retargetReferencePose } from './referencePose.js';
import { retargetReferenceMotion, makePortableReferenceMotion } from './motionRetarget.js';

const REQUIRED=['pelvis','chest','head','L_shoulder','L_elbow','L_wrist','R_shoulder','R_elbow','R_wrist','L_hip','L_knee','L_ankle','R_hip','R_knee','R_ankle'];
const SEGMENTS=[
  ['L_shoulder','L_elbow','L_upper_arm'],['L_elbow','L_wrist','L_forearm'],
  ['R_shoulder','R_elbow','R_upper_arm'],['R_elbow','R_wrist','R_forearm'],
  ['L_hip','L_knee','L_thigh'],['L_knee','L_ankle','L_shin'],
  ['R_hip','R_knee','R_thigh'],['R_knee','R_ankle','R_shin'],
];

function attachmentMap(raw){
  const out=new Map();const add=(slot,name)=>{if(!out.has(slot))out.set(slot,new Set());out.get(slot).add(name);};
  if(Array.isArray(raw?.skins)) for(const skin of raw.skins) for(const [slot,atts] of Object.entries(skin?.attachments||{})) for(const name of Object.keys(atts||{})) add(slot,name);
  else for(const skin of Object.values(raw?.skins||{})) for(const [slot,atts] of Object.entries(skin||{})) for(const name of Object.keys(atts||{})) add(slot,name);
  return out;
}
function targetSlots(raw){ return new Set((raw?.slots||[]).map(s=>s.name)); }
function setupAttachments(raw){ return new Map((raw?.slots||[]).map(s=>[s.name,s.attachment??null])); }
function dist(a,b){return a&&b?Math.hypot(a.x-b.x,a.y-b.y):null;}
function clamp01(x){return Math.max(0,Math.min(1,x));}

function semanticCoverage(rig){
  const present=REQUIRED.filter(r=>rig?.roles?.[r]?.bone),missing=REQUIRED.filter(r=>!rig?.roles?.[r]?.bone);
  return {required:REQUIRED.length,present:present.length,coverage:present.length/REQUIRED.length,missing};
}

function visualCompatibility(raw,motion){
  const slots=targetSlots(raw),atts=attachmentMap(raw),setup=setupAttachments(raw);
  let totalFrames=0,totalStates=0,existingSlots=0,visibleStates=0,compatibleVisible=0;
  const missingVisible=new Map(),missingAttachment=new Map(),hiddenTargetSetup=new Map();
  for(const frame of motion?.frames||[]){
    const vs=frame?.pose?.visualState;if(!vs)continue;totalFrames++;
    for(const [slot,name] of Object.entries(vs.slots||{})){
      totalStates++;
      if(slots.has(slot)) existingSlots++;
      if(name!=null){
        visibleStates++;
        if(!slots.has(slot)){missingVisible.set(slot,(missingVisible.get(slot)||0)+1);continue;}
        if(atts.get(slot)?.has(name))compatibleVisible++;
        else missingAttachment.set(`${slot}:${name}`,(missingAttachment.get(`${slot}:${name}`)||0)+1);
      } else if(slots.has(slot) && setup.get(slot)!=null){
        hiddenTargetSetup.set(slot,(hiddenTargetSetup.get(slot)||0)+1);
      }
    }
  }
  const list=m=>[...m.entries()].sort((a,b)=>b[1]-a[1]).map(([name,frames])=>({name,frames}));
  return {
    frames:totalFrames,
    slotCoverage:totalStates?existingSlots/totalStates:1,
    visibleAttachmentCoverage:visibleStates?compatibleVisible/visibleStates:1,
    missingVisibleSlots:list(missingVisible),
    missingAttachments:list(missingAttachment),
    targetSetupSlotsHiddenByReference:list(hiddenTargetSetup),
  };
}

function geometryDemand(motion,targetRig,targetSetup){
  const lm=semanticLandmarks(targetRig,targetSetup),base={};
  for(const [a,b,name] of SEGMENTS)base[name]=dist(lm.joints[a],lm.joints[b]);
  const ratios={};for(const [, ,name] of SEGMENTS)ratios[name]=[];
  const extremes=[];
  for(let i=0;i<(motion?.frames||[]).length;i++){
    const f=motion.frames[i],spec=retargetReferencePose(f.pose,targetRig,targetSetup,{animation:'__feasibility__',time:f.time,solverTargetsOnly:false}),factorMap={};
    for(const c of Object.values(spec?.limbLocalTargets?.chains||{})){const side=String(c.rootRole||'')[0];if(!['L','R'].includes(side))continue;if(c.rootRole.endsWith('_shoulder')){factorMap[`${side}_upper_arm`]=c.sourceFactors?.upper;factorMap[`${side}_forearm`]=c.sourceFactors?.lower;}else if(c.rootRole.endsWith('_hip')){factorMap[`${side}_thigh`]=c.sourceFactors?.upper;factorMap[`${side}_shin`]=c.sourceFactors?.lower;}}
    for(const [a,b,name] of SEGMENTS){
      const A=spec.targets[a],B=spec.targets[b],bl=base[name];if(!bl)continue;
      const ratio=Number.isFinite(Number(factorMap[name]))?Number(factorMap[name]):(A&&B?dist(A,B)/bl:null);if(!Number.isFinite(ratio))continue;ratios[name].push(ratio);
      if(ratio<0.55||ratio>1.35)extremes.push({frame:i,time:Number(f.time||0),segment:name,ratio});
    }
  }
  const summary={};
  for(const [name,arr] of Object.entries(ratios)) summary[name]=arr.length?{min:Math.min(...arr),max:Math.max(...arr),mean:arr.reduce((s,x)=>s+x,0)/arr.length}:null;
  return {segments:summary,extremes,extremeRatioCount:extremes.length};
}

function artProfile(raw,rig){
  const slots=(raw?.slots||[]),atts=attachmentMap(raw),byBone=new Map((raw?.bones||[]).map(b=>[b.name,b]));
  const ancestors=(bone,root)=>{let cur=bone,seen=new Set();while(cur&&byBone.has(cur)&&!seen.has(cur)){if(cur===root)return true;seen.add(cur);cur=byBone.get(cur).parent;}return false;};
  const families={};
  for(const side of ['L','R']){
    for(const [kind,rootRole] of [['arm',`${side}_shoulder`],['leg',`${side}_hip`]]){
      const root=rig?.roles?.[rootRole]?.bone;if(!root){families[`${side}_${kind}`]={slots:0,attachments:0};continue;}
      const limbSlots=slots.filter(s=>ancestors(s.bone,root));
      let count=0;for(const s of limbSlots)count+=atts.get(s.name)?.size||0;
      families[`${side}_${kind}`]={slots:limbSlots.length,attachments:count,names:limbSlots.map(s=>s.name)};
    }
  }
  return {families};
}


function canonicalPartFromSlot(name){
  const m=String(name).match(/(?:^|_)run_([LR])_(upper|fore|hand|thigh|shin|foot)(?:_slot)?$/i) || String(name).match(/^run_([LR])_(upper|fore|hand|thigh|shin|foot)_slot$/i);
  if(!m)return null;
  const map={upper:'upper_arm',fore:'forearm',hand:'hand',thigh:'thigh',shin:'shin',foot:'foot'};
  return `${m[1].toUpperCase()}_${map[m[2].toLowerCase()]}`;
}
function limbFamilyForSegment(segment){const m=String(segment).match(/^([LR])_(upper_arm|forearm|thigh|shin)$/);if(!m)return null;return `${m[1]}_${m[2]==='thigh'||m[2]==='shin'?'leg':'arm'}`;}
function visualTopologyGaps(geometry,art,{severeRatio=.42}={}){
  const gaps=[];
  for(const [segment,stats] of Object.entries(geometry?.segments||{})){
    if(!stats||Number(stats.min)>=severeRatio)continue;const family=limbFamilyForSegment(segment),profile=family?art?.families?.[family]:null;
    const segmentedSlots=Number(profile?.slots||0);if(segmentedSlots>=3)continue;
    const side=String(segment)[0],requiredParts=family?.endsWith('_leg')?[`${side}_thigh`,`${side}_shin`,`${side}_foot`]:[`${side}_upper_arm`,`${side}_forearm`,`${side}_hand`];gaps.push({segment,family,minRatio:Number(stats.min),maxRatio:Number(stats.max),segmentedSlots,attachmentCount:Number(profile?.attachments||0),requiredParts,recommendation:'foreshortened_attachment_or_weighted_mesh'});
  }
  return gaps;
}
function kinematicDryRun(raw,atlasText,motion,semanticRig,{threshold=.05}={}){
  if(!atlasText)return {status:'UNKNOWN',threshold,maxResidual:null,meanResidual:null,frames:0,errors:[]};
  try{
    const clone=structuredClone(raw),portable=makePortableReferenceMotion(motion),report=retargetReferenceMotion(clone,atlasText,portable,{animation:'__feasibility_dry_run__',replace:true,semanticRig});
    const residuals=(report.frames||[]).map(f=>Number(f?.residual?.maxDistance||0)),means=(report.frames||[]).map(f=>Number(f?.residual?.meanDistance||0));
    const maxResidual=residuals.length?Math.max(...residuals):0,meanResidual=means.length?means.reduce((a,b)=>a+b,0)/means.length:0;
    return {status:maxResidual<=threshold?'READY':'BLOCKED',threshold,maxResidual,meanResidual,frames:residuals.length,errors:[]};
  }catch(error){return {status:'BLOCKED',threshold,maxResidual:null,meanResidual:null,frames:0,errors:[error?.message||String(error)]};}
}

function buildArtPlan(visual,geometry,topologyGaps=[]){
  const required=new Set();
  for(const x of visual.missingVisibleSlots||[]){const p=canonicalPartFromSlot(x.name);if(p)required.add(p);}
  const viewNeeds=[];
  for(const gap of topologyGaps||[]){for(const part of gap.requiredParts||[gap.segment])required.add(part);viewNeeds.push({...gap});}
  for(const [segment,s] of Object.entries(geometry.segments||{})){
    if(!s)continue;
    if(s.min<0.55 && !(topologyGaps||[]).some(g=>g.segment===segment)) viewNeeds.push({segment,minRatio:s.min,maxRatio:s.max,recommendation:'foreshortened_attachment_or_weighted_mesh'});
    else if(s.max>1.35) viewNeeds.push({segment,minRatio:s.min,maxRatio:s.max,recommendation:'extended_attachment_or_weighted_mesh'});
  }
  return {requiredParts:[...required].sort(),viewpointNeeds:viewNeeds,needsNewArt:required.size>0||viewNeeds.length>0};
}

export function assessRetargetFeasibility(raw,motion,targetSetup,{semanticRig=inferSemanticRig(raw),atlasText=null,kinematicThreshold=.05}={}){
  const semantic=semanticCoverage(semanticRig),visual=visualCompatibility(raw,motion),geometry=geometryDemand(motion,semanticRig,targetSetup),art=artProfile(raw,semanticRig),topologyGaps=visualTopologyGaps(geometry,art);
  const sourceConvention=motion?.source?.semantic?.sideConvention||'unknown',targetConvention=semanticRig?.sideConvention||'unknown',viewpointMismatch=sourceConvention!=='unknown'&&targetConvention!=='unknown'&&sourceConvention!==targetConvention;
  const kinematic=semantic.coverage<1||viewpointMismatch?{status:'BLOCKED',threshold:kinematicThreshold,maxResidual:null,meanResidual:null,frames:0,errors:[semantic.coverage<1?'semantic mapping incomplete':`side convention mismatch: ${sourceConvention} -> ${targetConvention}`]}:kinematicDryRun(raw,atlasText,motion,semanticRig,{threshold:kinematicThreshold});
  const flags=[];
  if(semantic.coverage<1)flags.push({code:'missing_semantic_role',severity:'block',detail:semantic.missing});
  if(viewpointMismatch)flags.push({code:'viewpoint_side_convention_mismatch',severity:'block',source:sourceConvention,target:targetConvention});
  if(kinematic.status==='BLOCKED')flags.push({code:'kinematic_solver_residual',severity:'block',detail:kinematic});
  if(visual.missingVisibleSlots.length)flags.push({code:'missing_visible_slots',severity:'art',detail:visual.missingVisibleSlots.slice(0,20)});
  if(visual.missingAttachments.length)flags.push({code:'missing_attachments',severity:'art',detail:visual.missingAttachments.slice(0,20)});
  if(visual.visibleAttachmentCoverage<0.9)flags.push({code:'low_visual_state_coverage',severity:'art',value:visual.visibleAttachmentCoverage});
  if(topologyGaps.length)flags.push({code:'monolithic_limb_extreme_foreshortening',severity:'art',count:topologyGaps.length,detail:topologyGaps});
  if(geometry.extremeRatioCount)flags.push({code:'extreme_foreshortening',severity:'warn',count:geometry.extremeRatioCount,detail:geometry.extremes.slice(0,30)});
  const hiddenCritical=visual.targetSetupSlotsHiddenByReference.filter(x=>/hand|leg/i.test(x.name));
  if(hiddenCritical.length&&visual.missingVisibleSlots.length)flags.push({code:'reference_hides_target_limbs_without_replacement',severity:'art',detail:hiddenCritical.slice(0,20)});
  const block=flags.some(f=>f.severity==='block'),needsArt=flags.some(f=>f.severity==='art');
  const kinematicStatus=semantic.coverage<1||viewpointMismatch?'BLOCKED':kinematic.status;
  const visualStatus=needsArt?'NEEDS_ART':'READY';
  const score=clamp01(semantic.coverage*.30 + visual.slotCoverage*.15 + visual.visibleAttachmentCoverage*.20 + (kinematicStatus==='READY'?.25:kinematicStatus==='UNKNOWN'?.12:0) + (topologyGaps.length?0:.10));
  const status=block?'BLOCKED':needsArt?'NEEDS_ART':'READY';
  const artPlan=buildArtPlan(visual,geometry,topologyGaps);
  return {status,kinematicStatus,visualStatus,sourceConvention,targetConvention,score,semantic,kinematic,visual,geometry,art,topologyGaps,artPlan,flags,recommendation:status==='READY'?'retarget':status==='NEEDS_ART'?'add_or_map_art_before_retarget':'repair_rig_or_semantic_mapping'};
}

