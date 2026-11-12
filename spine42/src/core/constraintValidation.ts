import type { SpineConstraint, SpineDocument } from './spineDocument.ts';

export interface ConstraintIssue { code:string; severity:'block'|'warn'; constraint?:string; kind?:string; detail:string; }
export interface ConstraintValidationReport { ok:boolean; issues:ConstraintIssue[]; warnings:ConstraintIssue[]; ordered:Array<{kind:string;name:string;order:number}>; }

function parentMap(raw:SpineDocument){return new Map((raw.bones||[]).map(bone=>[bone.name,bone.parent||null]));}
function isSameOrDescendant(parents:Map<string,string|null>,ancestor:string,node:string){let current:string|null|undefined=node,guard=0;while(current&&guard++<2048){if(current===ancestor)return true;current=parents.get(current);}return false;}
function orderOf(constraint:SpineConstraint){return Number(constraint.order??0);}

export function validateConstraintGraph(raw:SpineDocument):ConstraintValidationReport {
  const issues:ConstraintIssue[]=[],warnings:ConstraintIssue[]=[],bones=new Set((raw.bones||[]).map(b=>b.name)),slots=new Map((raw.slots||[]).map(s=>[s.name,s])),parents=parentMap(raw),all:Array<{kind:'ik'|'transform'|'path';constraint:SpineConstraint}>=[];
  for(const constraint of raw.ik||[])all.push({kind:'ik',constraint});for(const constraint of raw.transform||[])all.push({kind:'transform',constraint});for(const constraint of raw.path||[])all.push({kind:'path',constraint});
  const orders=new Map<number,string>();
  for(const {kind,constraint} of all){
    const label=`${kind}:${constraint.name}`,order=orderOf(constraint);if(!Number.isInteger(order)||order<0)issues.push({code:'invalid_constraint_order',severity:'block',constraint:constraint.name,kind,detail:`${label} order must be a non-negative integer; got ${String(constraint.order)}`});else if(orders.has(order))issues.push({code:'duplicate_constraint_order',severity:'block',constraint:constraint.name,kind,detail:`${label} shares order ${order} with ${orders.get(order)}`});else orders.set(order,label);
    for(const bone of constraint.bones||[])if(!bones.has(bone))issues.push({code:'constraint_bone_missing',severity:'block',constraint:constraint.name,kind,detail:`${label} references missing constrained bone ${bone}`});
    let targetBone:string|null=null;if(kind==='path'){const slot=slots.get(String(constraint.target||''));if(!slot)issues.push({code:'path_target_slot_missing',severity:'block',constraint:constraint.name,kind,detail:`${label} references missing target slot ${String(constraint.target||'')}`});else targetBone=slot.bone;}else{if(!constraint.target||!bones.has(constraint.target))issues.push({code:'constraint_target_missing',severity:'block',constraint:constraint.name,kind,detail:`${label} references missing target bone ${String(constraint.target||'')}`});else targetBone=constraint.target;}
    if(targetBone)for(const constrained of constraint.bones||[])if(bones.has(constrained)&&isSameOrDescendant(parents,constrained,targetBone))issues.push({code:'constraint_dependency_cycle',severity:'block',constraint:constraint.name,kind,detail:`${label} target ${targetBone} is ${targetBone===constrained?'the constrained bone':'a descendant of '+constrained}, which creates an update dependency cycle`});
  }
  const ordered=all.map(({kind,constraint})=>({kind,name:constraint.name,order:orderOf(constraint)})).sort((a,b)=>a.order-b.order||a.kind.localeCompare(b.kind)||a.name.localeCompare(b.name));
  if(ordered.length){const max=ordered.at(-1)?.order??0;if(max>=ordered.length)warnings.push({code:'constraint_order_gap',severity:'warn',detail:`Constraint orders contain gaps (max ${max}, count ${ordered.length}); legal but harder to audit.`});}
  return {ok:issues.length===0,issues,warnings,ordered};
}
export function assertConstraintGraphSafe(raw:SpineDocument):void{const report=validateConstraintGraph(raw);if(!report.ok)throw new Error(report.issues.map(issue=>`${issue.code}: ${issue.detail}`).join('; '));}
