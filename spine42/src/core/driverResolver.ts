import { assessSemanticContext } from '../lib/contextInfluence.js';
import { inferSemanticRig } from '../lib/semanticRig.js';

const assessSemanticContextAny = assessSemanticContext as (...args:any[])=>any;
const inferSemanticRigAny = inferSemanticRig as (...args:any[])=>any;

export interface ContextDriverOptions {
  skinName?: string;
  animationName?: string;
  time?: number;
  activeSlots?: unknown[] | null;
}
export type DriverResolutionStatus = 'PRIMARY' | 'FALLBACK' | 'BLOCKED';
export interface DriverCandidateScore { bone: string; source: 'primary'|'fallback'; score: number; status: 'PASS'|'BLOCKED'; components: Record<string,number>; }
export interface DriverRoleResolution {
  role: string;
  status: DriverResolutionStatus;
  primaryBone: string | null;
  selectedBone: string | null;
  reason: string;
  guard: any;
  score: number;
  candidates: DriverCandidateScore[];
}
export interface ContextDriverResolution {
  rig: any;
  primaryRig: any;
  fallbackRig: any | null;
  primaryContext: any;
  fallbackContext: any | null;
  roles: Record<string, DriverRoleResolution>;
  blocked: DriverRoleResolution[];
  fallbackBones: string[];
}

const LIMB_GROUPS = [
  ['L_shoulder','L_elbow','L_wrist','L_hand'],
  ['R_shoulder','R_elbow','R_wrist','R_hand'],
  ['L_hip','L_knee','L_ankle','L_foot'],
  ['R_hip','R_knee','R_ankle','R_foot'],
] as const;
const clone = <T>(value:T):T => (typeof structuredClone==='function'?structuredClone(value):JSON.parse(JSON.stringify(value))) as T;

function scoreDriverCandidate(bone:string|undefined|null,mapping:any,guard:any,source:'primary'|'fallback',animationName:string):DriverCandidateScore|null{
  if(!bone||!guard)return null;const direct=Math.max(0,Number(guard.directWeight||0)),effective=Math.max(0,Number(guard.effectiveWeight||0)),constraintCount=(guard.constraintChains||[]).length,confidence=Math.max(0,Math.min(1,Number(mapping?.confidence||0)));
  const components={visible:guard.status==='PASS'?45:-60,direct:Math.min(20,direct*3),effective:Math.min(15,effective*1.5),timeline:guard.timelineParticipation?10:0,constraint:Math.min(10,constraintCount*5),confidence:confidence*10,primary:source==='primary'?4:0,helperPenalty:0};
  if(/^run_/i.test(bone)&&!/^run(?:_|$)/i.test(String(animationName||''))&&guard.status!=='PASS')components.helperPenalty=-50;
  const score=Object.values(components).reduce((sum,value)=>sum+Number(value||0),0);return{bone,source,status:guard.status==='PASS'?'PASS':'BLOCKED',score:Number(score.toFixed(3)),components};
}
function rankedCandidates(primary:any,pGuard:any,fallback:any,fGuard:any,animationName:string):DriverCandidateScore[]{return [scoreDriverCandidate(primary?.bone,primary,pGuard,'primary',animationName),scoreDriverCandidate(fallback?.bone,fallback,fGuard,'fallback',animationName)].filter(Boolean).sort((a:any,b:any)=>b.score-a.score) as DriverCandidateScore[];}


export function resolveContextualSemanticRig(raw:any, primaryRig:any, options:ContextDriverOptions={}):ContextDriverResolution {
  const primaryContext=assessSemanticContextAny(raw,primaryRig,options),unsafeBones=[...new Set((primaryContext.blocked||[]).map((item:any)=>item.boneName).filter(Boolean))] as string[];
  let fallbackRig:any|null=null,fallbackContext:any|null=null;
  if(unsafeBones.length){fallbackRig=inferSemanticRigAny(raw,{excludeBones:unsafeBones});fallbackContext=assessSemanticContextAny(raw,fallbackRig,options);}
  const rig=clone(primaryRig),roles:Record<string,DriverRoleResolution>={};
  const grouped=new Set<string>();
  for(const group of LIMB_GROUPS){
    for(const role of group)grouped.add(role);
    const primaryBlocked=group.some(role=>primaryContext.roles?.[role]?.status==='BLOCKED');
    const fallbackUsable=!!fallbackRig&&group.every(role=>fallbackRig.roles?.[role]?.bone&&fallbackContext?.roles?.[role]?.status==='PASS');
    for(const role of group){
      const primary=primaryRig.roles?.[role],pGuard=primaryContext.roles?.[role];
      if(!primaryBlocked&&primary&&pGuard?.status==='PASS'){const candidates=rankedCandidates(primary,pGuard,fallbackRig?.roles?.[role],fallbackContext?.roles?.[role],options.animationName||'');roles[role]={role,status:'PRIMARY',primaryBone:primary.bone,selectedBone:primary.bone,reason:'primary-visible-driver',guard:pGuard,score:candidates.find(c=>c.bone===primary.bone)?.score||0,candidates};}
      else if(fallbackUsable){const fallback=fallbackRig.roles[role],guard=fallbackContext.roles[role],candidates=rankedCandidates(primary,pGuard,fallback,guard,options.animationName||'');rig.roles[role]=clone(fallback);roles[role]={role,status:'FALLBACK',primaryBone:primary?.bone||null,selectedBone:fallback.bone,reason:'contextual-visible-fallback',guard,score:candidates.find(c=>c.bone===fallback.bone)?.score||0,candidates};}
      else {const guard=fallbackContext?.roles?.[role]||pGuard,candidates=rankedCandidates(primary,pGuard,fallbackRig?.roles?.[role],fallbackContext?.roles?.[role],options.animationName||'');roles[role]={role,status:'BLOCKED',primaryBone:primary?.bone||null,selectedBone:null,reason:guard?.code||'no-safe-context-driver',guard,score:candidates[0]?.score||0,candidates};delete rig.roles[role];}
    }
  }
  for(const [role,primary] of Object.entries<any>(primaryRig.roles||{})){
    if(grouped.has(role))continue;const pGuard=primaryContext.roles?.[role];if(pGuard?.status==='PASS'){const candidates=rankedCandidates(primary,pGuard,fallbackRig?.roles?.[role],fallbackContext?.roles?.[role],options.animationName||'');roles[role]={role,status:'PRIMARY',primaryBone:primary.bone,selectedBone:primary.bone,reason:'primary-visible-driver',guard:pGuard,score:candidates.find(c=>c.bone===primary.bone)?.score||0,candidates};}
    else if(fallbackRig?.roles?.[role]?.bone&&fallbackContext?.roles?.[role]?.status==='PASS'){const fallback=fallbackRig.roles[role],guard=fallbackContext.roles[role],candidates=rankedCandidates(primary,pGuard,fallback,guard,options.animationName||'');rig.roles[role]=clone(fallback);roles[role]={role,status:'FALLBACK',primaryBone:primary?.bone||null,selectedBone:fallback.bone,reason:'contextual-visible-fallback',guard,score:candidates.find(c=>c.bone===fallback.bone)?.score||0,candidates};}
    else{const candidates=rankedCandidates(primary,pGuard,fallbackRig?.roles?.[role],fallbackContext?.roles?.[role],options.animationName||'');roles[role]={role,status:'BLOCKED',primaryBone:primary?.bone||null,selectedBone:null,reason:pGuard?.code||'no-safe-context-driver',guard:pGuard,score:candidates[0]?.score||0,candidates};delete rig.roles[role];}
  }
  rig.boneToRoles={};for(const [role,mapping] of Object.entries<any>(rig.roles||{}))(rig.boneToRoles[mapping.bone]||=[]).push(role);
  rig.missing=Object.entries(roles).filter(([,value])=>value.status==='BLOCKED').map(([role])=>role);rig.contextResolved=true;
  const blocked=Object.values(roles).filter(value=>value.status==='BLOCKED');return {rig,primaryRig,fallbackRig,primaryContext,fallbackContext,roles,blocked,fallbackBones:unsafeBones};
}
