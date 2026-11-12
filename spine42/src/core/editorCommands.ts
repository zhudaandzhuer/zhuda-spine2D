import { CommandBus } from './commandBus.ts';
import { patchSet, type PatchOperation } from './patchSet.ts';
import { assertSpineDocument, cloneSpineDocument, type SpineDocument } from './spineDocument.ts';
import { applyAnimationPlan, cloneAnimation, createAnimation, deleteAnimation, deleteBoneKey, deleteDrawOrderKey, deleteSlotAttachmentKey, retimeAnimation, setBoneKey, setDrawOrderKey, setSlotAttachmentKey, validateAnimationAuthoring } from '../lib/animationOps.js';
import { solvePoseTargetsStaged } from '../lib/poseSolver.js';
import { assertConstraintGraphSafe } from './constraintValidation.ts';
import { applyConstraintSetupValues, type ConstraintKind } from './constraintAuthoring.ts';
import { applyConstraintStructureValues, createConstraint, deleteConstraint } from './constraintStructure.ts';
import { renameConstraint, setConstraintSkinMembership } from './constraintIdentity.ts';
import { deleteConstraintAnimationKey, setConstraintAnimationKey, type ConstraintAnimationChannel } from './constraintAnimation.ts';
import { deleteDeformKey, setDeformKey, validateDeformAuthoring, type DeformLocator } from './deformAuthoring.ts';
import { deleteTimelineKeys, moveTimelineKeys, pasteTimelineKeys, scaleTimelineKeys, type TimelineClipboard, type TimelineKeyRef } from './timelineAuthoring.ts';
import { findGraphLane, setGraphBezierHandles, setGraphKeyValue, setGraphSegmentMode, type GraphCurveMode } from './graphAuthoring.ts';
import { applySetMeshHullCountToDocument, applyCreateMeshFaceToDocument, applyDeleteMeshFaceToDocument, applyDeleteMeshVertexToDocument, applyFlipMeshEdgeToDocument, applyInsertMeshVertexInFaceToDocument, applyMoveMeshVertexToDocument, applySetMeshVertexUvToDocument, applySplitEdgeToDocument, forkLinkedMesh, type MeshLocator, type MeshVertexMoveDelta } from './meshTopology.ts';
import { batchReplaceMeshVertexInfluences, batchSetMeshBoneWeights, bindMeshVertexBone, bindUnweightedMesh, limitMeshVertexInfluences, normalizeMeshVertexWeights, pruneMeshVertexWeights, setMeshVertexBoneWeight, unbindMeshVertexBone, type WeightBatchTarget, type WeightInfluenceReplacement } from './meshWeights.ts';

export const EDITOR_COMMANDS = Object.freeze({
  SET_BONE_SETUP_TRANSFORM: 'setup.setBoneTransform',
  SET_SLOT_SETUP_ATTACHMENT: 'setup.setSlotAttachment',
  SET_CONSTRAINT_SETUP_VALUES: 'constraint.setSetupValues',
  SET_CONSTRAINT_STRUCTURE: 'constraint.setStructure',
  CREATE_CONSTRAINT: 'constraint.create',
  DELETE_CONSTRAINT: 'constraint.delete',
  RENAME_CONSTRAINT: 'constraint.rename',
  SET_CONSTRAINT_SKIN_MEMBERSHIP: 'constraint.setSkinMembership',
  SET_CONSTRAINT_KEY: 'animation.setConstraintKey',
  DELETE_CONSTRAINT_KEY: 'animation.deleteConstraintKey',
  SET_DEFORM_KEY: 'deform.setKey',
  DELETE_DEFORM_KEY: 'deform.deleteKey',
  DOPE_MOVE_KEYS: 'timeline.moveKeys',
  DOPE_SCALE_KEYS: 'timeline.scaleKeys',
  DOPE_DELETE_KEYS: 'timeline.deleteKeys',
  DOPE_PASTE_KEYS: 'timeline.pasteKeys',
  GRAPH_SET_KEY_VALUE: 'graph.setKeyValue',
  GRAPH_SET_SEGMENT_MODE: 'graph.setSegmentMode',
  GRAPH_SET_BEZIER_HANDLES: 'graph.setBezierHandles',
  CREATE_ANIMATION: 'animation.create',
  CLONE_ANIMATION: 'animation.clone',
  DELETE_ANIMATION: 'animation.delete',
  SET_BONE_KEY: 'animation.setBoneKey',
  DELETE_BONE_KEY: 'animation.deleteBoneKey',
  SET_DRAW_ORDER_KEY: 'animation.setDrawOrderKey',
  DELETE_DRAW_ORDER_KEY: 'animation.deleteDrawOrderKey',
  SET_SLOT_ATTACHMENT_KEY: 'animation.setSlotAttachmentKey',
  DELETE_SLOT_ATTACHMENT_KEY: 'animation.deleteSlotAttachmentKey',
  RETIME_ANIMATION: 'animation.retime',
  SOLVE_SEMANTIC_POSE: 'animation.solveSemanticPose',
  SPLIT_MESH_EDGE: 'mesh.splitEdge',
  MOVE_MESH_VERTEX: 'mesh.moveVertex',
  MOVE_MESH_VERTICES: 'mesh.moveVertices',
  FLIP_MESH_EDGE: 'mesh.flipEdge',
  DELETE_MESH_FACE: 'mesh.deleteFace',
  DELETE_MESH_VERTEX: 'mesh.deleteVertex',
  INSERT_MESH_FACE_VERTEX: 'mesh.insertFaceVertex',
  CREATE_MESH_FACE: 'mesh.createFace',
  SET_MESH_HULL: 'mesh.setHull',
  FORK_LINKED_MESH: 'mesh.forkLinked',
  SET_MESH_VERTEX_UV: 'mesh.setVertexUv',
  SET_MESH_VERTEX_WEIGHT: 'weights.setVertexWeight',
  NORMALIZE_MESH_VERTEX_WEIGHTS: 'weights.normalizeVertex',
  BIND_MESH_VERTEX_BONE: 'weights.bindVertexBone',
  UNBIND_MESH_VERTEX_BONE: 'weights.unbindVertexBone',
  PRUNE_MESH_VERTEX_WEIGHTS: 'weights.pruneVertex',
  LIMIT_MESH_VERTEX_INFLUENCES: 'weights.limitVertexInfluences',
  BATCH_SET_MESH_BONE_WEIGHTS: 'weights.batchSetBoneWeights',
  REPLACE_MESH_VERTEX_INFLUENCES: 'weights.replaceVertexInfluences',
  BIND_UNWEIGHTED_MESH: 'weights.bindUnweightedMesh',
} as const);

export interface SetSlotSetupAttachmentPayload { slotName:string; attachmentName:string|null; skinName?:string; }
export interface SetBoneSetupTransformPayload {
  boneName: string;
  values: Partial<Record<'x'|'y'|'rotation'|'scaleX'|'scaleY'|'shearX'|'shearY'|'length',number>>;
}
export interface SetConstraintSetupValuesPayload { kind:ConstraintKind; name:string; values:Record<string,unknown>; }
export interface SetConstraintStructurePayload { kind:ConstraintKind; name:string; values:{target?:unknown;bones?:unknown;order?:unknown}; }
export interface CreateConstraintPayload { kind:ConstraintKind; name:string; target:string; bones:string[]; }
export interface DeleteConstraintPayload { kind:ConstraintKind; name:string; cascadeTimelines?:boolean; }
export interface RenameConstraintPayload { kind:ConstraintKind; oldName:string; newName:string; }
export interface SetConstraintSkinMembershipPayload { kind:ConstraintKind; name:string; skinRequired:boolean; skinNames:string[]; }
export interface SetConstraintKeyPayload { animationName:string; kind:ConstraintKind; name:string; channel:ConstraintAnimationChannel; time:number; values:Record<string,unknown>; curve?:unknown; }
export interface DeleteConstraintKeyPayload { animationName:string; kind:ConstraintKind; name:string; channel:ConstraintAnimationChannel; time:number; }
export interface SetDeformKeyPayload { animationName:string; locator:DeformLocator; time:number; offsets:number[]; curve?:unknown; }
export interface DeleteDeformKeyPayload { animationName:string; locator:DeformLocator; time:number; }
export interface DopeMoveKeysPayload { animationName:string; refs:TimelineKeyRef[]; delta:number; }
export interface DopeScaleKeysPayload { animationName:string; refs:TimelineKeyRef[]; anchor:number; factor:number; }
export interface DopeDeleteKeysPayload { animationName:string; refs:TimelineKeyRef[]; }
export interface DopePasteKeysPayload { animationName:string; clipboard:TimelineClipboard; targetTime:number; }
export interface GraphSetKeyValuePayload { animationName:string; laneId:string; keyIndex:number; value:number; }
export interface GraphSetSegmentModePayload { animationName:string; laneId:string; segmentIndex:number; mode:GraphCurveMode; }
export interface GraphSetBezierHandlesPayload { animationName:string; laneId:string; segmentIndex:number; handles:[number,number,number,number]; unified?:boolean; }

export interface CreateAnimationPayload { name: string; }
export interface CloneAnimationPayload { source: string; target: string; }
export interface DeleteAnimationPayload { name: string; }
export interface SetBoneKeyPayload { animationName: string; boneName: string; timelineName: string; time: number; values: Record<string,number>; curve?: string | number[]; }
export interface DeleteBoneKeyPayload { animationName: string; boneName: string; timelineName: string; time: number; }
export interface SetDrawOrderKeyPayload { animationName:string; time:number; offsets:Array<{slot:string;offset:number}>; }
export interface DeleteDrawOrderKeyPayload { animationName:string; time:number; }
export interface SetSlotAttachmentKeyPayload { animationName:string; slotName:string; time:number; attachmentName?:string|null; }
export interface DeleteSlotAttachmentKeyPayload { animationName:string; slotName:string; time:number; }
export interface RetimeAnimationPayload { name: string; factor: number; }
export interface SplitMeshEdgePayload { locator: MeshLocator; a:number; b:number; t?:number; }
export interface MoveMeshVertexPayload { locator: MeshLocator; vertexIndex:number; delta:MeshVertexMoveDelta; }
export interface MoveMeshVerticesPayload { locator:MeshLocator; moves:Array<{vertexIndex:number;delta:MeshVertexMoveDelta}>; }
export interface FlipMeshEdgePayload { locator:MeshLocator; a:number; b:number; }
export interface DeleteMeshFacePayload { locator:MeshLocator; triangleIndex:number; }
export interface DeleteMeshVertexPayload { locator:MeshLocator; vertexIndex:number; }
export interface InsertMeshFaceVertexPayload { locator:MeshLocator; triangleIndex:number; barycentric?:[number,number,number]; }
export interface CreateMeshFacePayload { locator:MeshLocator; indices:[number,number,number]; }
export interface SetMeshHullPayload { locator:MeshLocator; hullCount:number; }
export interface ForkLinkedMeshPayload { locator:MeshLocator; }
export interface SetMeshVertexUvPayload { locator:MeshLocator; vertexIndex:number; u:number; v:number; }
export interface SetMeshVertexWeightPayload { locator:MeshLocator; vertexIndex:number; boneIndex:number; weight:number; lockedBoneIndices?:number[]; }
export interface NormalizeMeshVertexWeightsPayload { locator:MeshLocator; vertexIndex:number; lockedBoneIndices?:number[]; }
export interface BindMeshVertexBonePayload { locator:MeshLocator; vertexIndex:number; boneIndex:number; local:{x:number;y:number}; weight?:number; lockedBoneIndices?:number[]; }
export interface UnbindMeshVertexBonePayload { locator:MeshLocator; vertexIndex:number; boneIndex:number; lockedBoneIndices?:number[]; }
export interface PruneMeshVertexWeightsPayload { locator:MeshLocator; vertexIndex:number; threshold?:number; lockedBoneIndices?:number[]; }
export interface LimitMeshVertexInfluencesPayload { locator:MeshLocator; vertexIndex:number; maxInfluences?:number; lockedBoneIndices?:number[]; }
export interface BatchSetMeshBoneWeightsPayload { locator:MeshLocator; targets:WeightBatchTarget[]; maxInfluences?:number; }
export interface ReplaceMeshVertexInfluencesPayload { locator:MeshLocator; replacements:WeightInfluenceReplacement[]; maxInfluences?:number; }
export interface BindUnweightedMeshPayload { locator:MeshLocator; replacements:WeightInfluenceReplacement[]; maxInfluences?:number; }
export interface SolveSemanticPosePayload { animationName: string; time: number; atlasText: string; semanticRig: unknown; spec: Record<string,unknown>; visualOperations?: unknown[]; refine?: { role: string; midRole: string; residualAt?: number }; maxResidual?: number; }

function validateAnimationDocument(document: SpineDocument): void {
  const result=validateAnimationAuthoring(document as any);
  if(!result?.ok)throw new Error((result?.issues||['Animation authoring validation failed']).join('; '));
}
function legacyWorkingCopy(document: SpineDocument): any { return cloneSpineDocument(document) as any; }

function stableOutsideAnimation(document: SpineDocument, animationName: string): string {
  const clone=cloneSpineDocument(document) as any;if(clone.animations)delete clone.animations[animationName];return JSON.stringify(clone);
}

function meshAttachmentPath(document:any,locator:MeshLocator):(string|number)[]{
  if(Array.isArray(document.skins)){const index=document.skins.findIndex((skin:any)=>String(skin?.name||'default')===locator.skin);if(index<0)throw new Error(`Skin not found: ${locator.skin}`);return['skins',index,'attachments',locator.slot,locator.attachment];}
  return['skins',locator.skin,locator.slot,locator.attachment];
}
function meshAttachmentValue(document:any,locator:MeshLocator):any{if(Array.isArray(document.skins)){const i=document.skins.findIndex((skin:any)=>String(skin?.name||'default')===locator.skin);if(i<0)throw new Error(`Skin not found: ${locator.skin}`);return document.skins[i].attachments[locator.slot][locator.attachment];}return document.skins?.[locator.skin]?.[locator.slot]?.[locator.attachment];}
function weightPatch(document:SpineDocument,working:any,label:string,metadata:any){const source=working.result.sourceLocator,value=meshAttachmentValue(working.document,source),operations:PatchOperation[]=[{op:'set',path:meshAttachmentPath(document,source),value}];if(working.result.layoutChanged&&Array.isArray(working.result.deformTimelines))for(const ref of working.result.deformTimelines)operations.push({op:'set',path:['animations',ref.animation,'attachments',ref.skin,ref.slot,ref.attachment,'deform'],value:ref.frames});const patch=patchSet(label,...operations);patch.metadata={...metadata,deformMigration:working.result.layoutChanged?{timelines:working.result.deformTimelines?.length||0}:null};return patch;}
function animationSubtreePatch(document: SpineDocument, animationName: string, mutate: (working:any)=>void, label:string) {
  if(!document.animations?.[animationName])throw new Error(`Animation not found: ${animationName}`);
  const working=legacyWorkingCopy(document);mutate(working);
  return patchSet(label,{op:'set',path:['animations',animationName],value:working.animations[animationName]});
}

function constraintScopedPatch(document:SpineDocument,working:any,label:string,metadata:Record<string,unknown>){
  const operations:PatchOperation[]=[];
  for(const kind of ['ik','transform','path'] as const){
    const before=(document as any)[kind],after=(working.document as any)[kind];
    if(JSON.stringify(before)===JSON.stringify(after))continue;
    if(after===undefined)operations.push({op:'delete',path:[kind]});else operations.push({op:'set',path:[kind],value:after});
  }
  const beforeSkins=(document as any).skins,afterSkins=(working.document as any).skins;if(JSON.stringify(beforeSkins)!==JSON.stringify(afterSkins)){if(Array.isArray(beforeSkins)&&Array.isArray(afterSkins)&&beforeSkins.length===afterSkins.length){for(let i=0;i<afterSkins.length;i++)if(JSON.stringify(beforeSkins[i])!==JSON.stringify(afterSkins[i]))operations.push({op:'set',path:['skins',i],value:afterSkins[i]});}else if(afterSkins===undefined)operations.push({op:'delete',path:['skins']});else operations.push({op:'set',path:['skins'],value:afterSkins});}
  const beforeAnimations=(document as any).animations||{},afterAnimations=(working.document as any).animations||{};
  for(const animation of [...new Set([...Object.keys(beforeAnimations),...Object.keys(afterAnimations)])]){
    if(JSON.stringify(beforeAnimations[animation])===JSON.stringify(afterAnimations[animation]))continue;
    if(afterAnimations[animation]===undefined)operations.push({op:'delete',path:['animations',animation]});else operations.push({op:'set',path:['animations',animation],value:afterAnimations[animation]});
  }
  if(!operations.length)throw new Error('CONSTRAINT_COMMAND_NO_CHANGE');const patch=patchSet(label,...operations);patch.metadata=metadata;return patch;
}

export function createEditorCommandBus(): CommandBus<SpineDocument> {
  const bus=new CommandBus<SpineDocument>();
  bus.validateWith(document=>assertSpineDocument(document));
  bus.validateWith(validateAnimationDocument);
  bus.validateWith(document=>{const result=validateDeformAuthoring(document);if(!result.ok)throw new Error(result.issues.join('; '));});
  bus.validateWith(assertConstraintGraphSafe);
  bus.register<SetConstraintSetupValuesPayload>(EDITOR_COMMANDS.SET_CONSTRAINT_SETUP_VALUES,{
    capability:'editConstraintSetup',
    createPatch(document,payload){
      const kind=String(payload.kind||'') as ConstraintKind;if(!['ik','transform','path'].includes(kind))throw new Error(`Unknown constraint kind: ${String(payload.kind)}`);
      const name=String(payload.name||'');const working=applyConstraintSetupValues(document,kind,name,payload.values||{}),result=working.result;
      const patch=patchSet(`Constraint Setup · ${kind}:${name}`,{op:'set',path:[kind,result.index],value:result.after});
      patch.metadata={constraintSetup:{kind,name,index:result.index,changedProperties:result.changedProperties,effectiveBefore:result.effectiveBefore,effectiveAfter:result.effectiveAfter}};return patch;
    }
  });
  bus.register<SetConstraintStructurePayload>(EDITOR_COMMANDS.SET_CONSTRAINT_STRUCTURE,{
    capability:'editConstraintSetup',
    createPatch(document,payload){
      const kind=String(payload.kind||'') as ConstraintKind;if(!['ik','transform','path'].includes(kind))throw new Error(`Unknown constraint kind: ${String(payload.kind)}`);
      const name=String(payload.name||''),working=applyConstraintStructureValues(document,kind,name,payload.values||{}),result=working.result;
      return constraintScopedPatch(document,working,`Constraint Structure · ${kind}:${name}`,{constraintStructure:{kind,name,changedProperties:result.changedProperties,orderChanges:result.orderChanges,timelineAnimations:result.timelineReferences.map(x=>x.animation)}});
    }
  });
  bus.register<CreateConstraintPayload>(EDITOR_COMMANDS.CREATE_CONSTRAINT,{
    capability:'editConstraintSetup',
    createPatch(document,payload){
      const kind=String(payload.kind||'') as ConstraintKind;if(!['ik','transform','path'].includes(kind))throw new Error(`Unknown constraint kind: ${String(payload.kind)}`);
      const working=createConstraint(document,kind,{name:payload.name,target:payload.target,bones:payload.bones}),result=working.result;
      return constraintScopedPatch(document,working,`Create Constraint · ${kind}:${result.name}`,{constraintCreate:{kind,name:result.name,index:result.index,order:result.order,target:result.constraint.target,bones:result.constraint.bones}});
    }
  });
  bus.register<DeleteConstraintPayload>(EDITOR_COMMANDS.DELETE_CONSTRAINT,{
    capability:'editConstraintSetup',
    createPatch(document,payload){
      const kind=String(payload.kind||'') as ConstraintKind;if(!['ik','transform','path'].includes(kind))throw new Error(`Unknown constraint kind: ${String(payload.kind)}`);
      const name=String(payload.name||''),working=deleteConstraint(document,kind,name,{cascadeTimelines:!!payload.cascadeTimelines}),result=working.result;
      return constraintScopedPatch(document,working,`Delete Constraint · ${kind}:${name}`,{constraintDelete:{kind,name,timelineAnimations:result.timelineReferences.map(x=>x.animation),removedTimelineAnimations:result.removedTimelineAnimations,skinReferences:result.skinReferences.map(x=>x.skin),removedSkinReferences:result.removedSkinReferences,orderChanges:result.orderChanges}});
    }
  });
  bus.register<RenameConstraintPayload>(EDITOR_COMMANDS.RENAME_CONSTRAINT,{
    capability:'editConstraintSetup',
    createPatch(document,payload){const kind=String(payload.kind||'') as ConstraintKind;if(!['ik','transform','path'].includes(kind))throw new Error(`Unknown constraint kind: ${String(payload.kind)}`);const working=renameConstraint(document,kind,payload.oldName,payload.newName),result=working.result;return constraintScopedPatch(document,working,`Rename Constraint · ${kind}:${result.oldName} → ${result.newName}`,{constraintRename:{kind,oldName:result.oldName,newName:result.newName,timelineAnimations:result.timelineReferences.map(x=>x.animation),skinReferences:result.skinReferences.map(x=>x.skin)}});}
  });
  bus.register<SetConstraintSkinMembershipPayload>(EDITOR_COMMANDS.SET_CONSTRAINT_SKIN_MEMBERSHIP,{
    capability:'editConstraintSetup',
    createPatch(document,payload){const kind=String(payload.kind||'') as ConstraintKind;if(!['ik','transform','path'].includes(kind))throw new Error(`Unknown constraint kind: ${String(payload.kind)}`);const name=String(payload.name||''),working=setConstraintSkinMembership(document,kind,name,{skinRequired:payload.skinRequired,skinNames:payload.skinNames||[]}),result=working.result;return constraintScopedPatch(document,working,`Constraint Skin · ${kind}:${name}`,{constraintSkin:{kind,name,beforeSkinRequired:result.beforeSkinRequired,afterSkinRequired:result.afterSkinRequired,beforeSkinNames:result.beforeSkinNames,afterSkinNames:result.afterSkinNames,addedSkins:result.addedSkins,removedSkins:result.removedSkins}});}
  });
  bus.register<SetConstraintKeyPayload>(EDITOR_COMMANDS.SET_CONSTRAINT_KEY,{
    capability:'editAnimation',
    createPatch(document,payload){const working=setConstraintAnimationKey(document,payload.animationName,payload.kind,payload.name,payload.channel,Number(payload.time),payload.values||{},payload.curve);const r=working.result;const patch=patchSet(`Constraint Key · ${r.kind}:${r.name}.${r.channel} @ ${r.time.toFixed(3)}s`,{op:'set',path:['animations',r.animationName],value:(working.document.animations as any)?.[r.animationName]});patch.metadata={constraintKey:{kind:r.kind,name:r.name,channel:r.channel,animationName:r.animationName,time:r.time,created:r.created,frame:r.frame}};return patch;}
  });
  bus.register<DeleteConstraintKeyPayload>(EDITOR_COMMANDS.DELETE_CONSTRAINT_KEY,{
    capability:'editAnimation',
    createPatch(document,payload){const working=deleteConstraintAnimationKey(document,payload.animationName,payload.kind,payload.name,payload.channel,Number(payload.time)),r=working.result;const patch=patchSet(`Delete Constraint Key · ${r.kind}:${r.name}.${r.channel} @ ${r.time.toFixed(3)}s`,{op:'set',path:['animations',r.animationName],value:(working.document.animations as any)?.[r.animationName]});patch.metadata={constraintKeyDelete:{kind:r.kind,name:r.name,channel:r.channel,animationName:r.animationName,time:r.time,deletedFrame:r.deletedFrame}};return patch;}
  });
  const dopePatch=(document:SpineDocument,animationName:string,working:{document:SpineDocument;result:any},label:string)=>{const patch=patchSet(label,{op:'set',path:['animations',animationName],value:(working.document.animations as any)?.[animationName]});patch.metadata={dope:working.result};return patch;};
  bus.register<DopeMoveKeysPayload>(EDITOR_COMMANDS.DOPE_MOVE_KEYS,{capability:'editDopeSheet',createPatch(document,payload,context){const working=moveTimelineKeys(document,payload.animationName,payload.refs,Number(payload.delta),{deformOnly:context.mode.mode==='deform'});return dopePatch(document,payload.animationName,working,`Dope Move · ${payload.refs.length} key(s)`);}});
  bus.register<DopeScaleKeysPayload>(EDITOR_COMMANDS.DOPE_SCALE_KEYS,{capability:'editDopeSheet',createPatch(document,payload,context){const working=scaleTimelineKeys(document,payload.animationName,payload.refs,Number(payload.anchor),Number(payload.factor),{deformOnly:context.mode.mode==='deform'});return dopePatch(document,payload.animationName,working,`Dope Scale · ${payload.refs.length} key(s)`);}});
  bus.register<DopeDeleteKeysPayload>(EDITOR_COMMANDS.DOPE_DELETE_KEYS,{capability:'editDopeSheet',createPatch(document,payload,context){const working=deleteTimelineKeys(document,payload.animationName,payload.refs,{deformOnly:context.mode.mode==='deform'});return dopePatch(document,payload.animationName,working,`Dope Delete · ${payload.refs.length} key(s)`);}});
  bus.register<DopePasteKeysPayload>(EDITOR_COMMANDS.DOPE_PASTE_KEYS,{capability:'editDopeSheet',createPatch(document,payload,context){const working=pasteTimelineKeys(document,payload.animationName,payload.clipboard,Number(payload.targetTime),{deformOnly:context.mode.mode==='deform'});return dopePatch(document,payload.animationName,working,`Dope Paste · ${payload.clipboard?.records?.length||0} key(s)`);}});
  const graphScope=(document:SpineDocument,animationName:string,laneId:string,mode:string)=>{const lane=findGraphLane(document,animationName,laneId);if(mode==='deform'&&lane.channelKind!=='deform')throw new Error(`GRAPH_DEFORM_SCOPE_BLOCKED: ${lane.label}`);if(mode==='animate'&&lane.channelKind==='deform')throw new Error(`GRAPH_DEFORM_REQUIRES_DEFORM_MODE: ${lane.label}`);return lane;};
  const graphPatch=(working:{document:SpineDocument;result:any},animationName:string,label:string)=>{const patch=patchSet(label,{op:'set',path:['animations',animationName],value:(working.document.animations as any)?.[animationName]});patch.metadata={graph:working.result};return patch;};
  bus.register<GraphSetKeyValuePayload>(EDITOR_COMMANDS.GRAPH_SET_KEY_VALUE,{capability:'editGraph',createPatch(document,payload,context){graphScope(document,payload.animationName,payload.laneId,context.mode.mode);const working=setGraphKeyValue(document,payload.animationName,payload.laneId,Number(payload.keyIndex),Number(payload.value));return graphPatch(working,payload.animationName,`Graph Value · ${payload.laneId} · k${payload.keyIndex}`);}});
  bus.register<GraphSetSegmentModePayload>(EDITOR_COMMANDS.GRAPH_SET_SEGMENT_MODE,{capability:'editGraph',createPatch(document,payload,context){graphScope(document,payload.animationName,payload.laneId,context.mode.mode);const working=setGraphSegmentMode(document,payload.animationName,payload.laneId,Number(payload.segmentIndex),payload.mode);return graphPatch(working,payload.animationName,`Graph Curve · ${payload.mode} · s${payload.segmentIndex}`);}});
  bus.register<GraphSetBezierHandlesPayload>(EDITOR_COMMANDS.GRAPH_SET_BEZIER_HANDLES,{capability:'editGraph',createPatch(document,payload,context){graphScope(document,payload.animationName,payload.laneId,context.mode.mode);const working=setGraphBezierHandles(document,payload.animationName,payload.laneId,Number(payload.segmentIndex),payload.handles,{unified:!!payload.unified});return graphPatch(working,payload.animationName,`Graph Bezier · s${payload.segmentIndex}`);}});
  bus.register<SetDeformKeyPayload>(EDITOR_COMMANDS.SET_DEFORM_KEY,{
    capability:'editDeform',
    createPatch(document,payload){const working=setDeformKey(document,payload.animationName,payload.locator,Number(payload.time),payload.offsets||[],payload.curve),r=working.result;const patch=patchSet(`Deform Key · ${r.locator.slot}/${r.locator.attachment} @ ${r.time.toFixed(3)}s`,{op:'set',path:['animations',r.animationName],value:(working.document.animations as any)?.[r.animationName]});patch.metadata={deformKey:{...r,frame:r.frame}};return patch;}
  });
  bus.register<DeleteDeformKeyPayload>(EDITOR_COMMANDS.DELETE_DEFORM_KEY,{
    capability:'editDeform',
    createPatch(document,payload){const working=deleteDeformKey(document,payload.animationName,payload.locator,Number(payload.time)),r=working.result;const patch=patchSet(`Delete Deform Key · ${r.locator.slot}/${r.locator.attachment} @ ${r.time.toFixed(3)}s`,{op:'set',path:['animations',r.animationName],value:(working.document.animations as any)?.[r.animationName]});patch.metadata={deformKeyDelete:r};return patch;}
  });
  bus.register<SetSlotSetupAttachmentPayload>(EDITOR_COMMANDS.SET_SLOT_SETUP_ATTACHMENT,{
    capability:'editSetup',
    createPatch(document,payload){
      const slotName=String(payload.slotName||''),index=(document.slots||[]).findIndex(slot=>slot.name===slotName);
      if(index<0)throw new Error(`Slot not found: ${slotName}`);
      if(payload.attachmentName!==null&&(typeof payload.attachmentName!=='string'||!payload.attachmentName.trim()))throw new Error('attachmentName must be a nonempty string or null');
      const name=payload.attachmentName,skinName=String(payload.skinName||'default');
      if(name!==null){
        const skins:any=document.skins,attachments=Array.isArray(skins)?skins.find(s=>String(s?.name||'default')===skinName)?.attachments:skins?.[skinName];
        if(!attachments?.[slotName]?.[name])throw new Error(`Setup attachment not found: ${skinName}/${slotName}/${name}`);
      }
      const field:(string|number)[]=['slots',index,'attachment'];
      const operation:PatchOperation=name===null?{op:'delete',path:field}:{op:'set',path:field,value:name};
      const patch=patchSet(`Setup Attachment · ${slotName} → ${name??'(hidden)'}`,operation);
      patch.metadata={slotSetupAttachment:{slotName,skinName,before:document.slots?.[index]?.attachment??null,after:name}};
      return patch;
    }
  });
  bus.register<SetBoneSetupTransformPayload>(EDITOR_COMMANDS.SET_BONE_SETUP_TRANSFORM,{
    capability:'editSetup',
    createPatch(document,payload){
      const index=document.bones.findIndex(bone=>bone.name===payload.boneName);if(index<0)throw new Error(`Bone not found: ${payload.boneName}`);
      const bone=document.bones[index] as Record<string,unknown>,operations:PatchOperation[]=[];
      for(const [property,value] of Object.entries(payload.values)){
        if(!Number.isFinite(Number(value)))throw new Error(`Invalid ${payload.boneName}.${property}: ${String(value)}`);
        if(Number(value)===(property==='scaleX'||property==='scaleY'?1:0)&&!Object.prototype.hasOwnProperty.call(bone,property))continue;
        operations.push({op:'set',path:['bones',index,property],value:Number(value)});
      }
      return patchSet(`Setup Pose · ${payload.boneName}`,...operations);
    }
  });
  bus.register<CreateAnimationPayload>(EDITOR_COMMANDS.CREATE_ANIMATION,{
    capability:'editAnimation',
    createPatch(document,payload){
      const name=String(payload.name||'').trim();if(!name)throw new Error('Animation name is required');
      const working=legacyWorkingCopy(document);createAnimation(working,name);
      if(document.animations)return patchSet(`建立動畫 · ${name}`,{op:'set',path:['animations',name],value:working.animations[name]});
      return patchSet(`建立動畫 · ${name}`,{op:'set',path:['animations'],value:working.animations});
    }
  });
  bus.register<CloneAnimationPayload>(EDITOR_COMMANDS.CLONE_ANIMATION,{
    capability:'editAnimation',
    createPatch(document,payload){
      const source=String(payload.source||''),target=String(payload.target||'').trim();if(!source||!target)throw new Error('Clone source and target are required');
      const working=legacyWorkingCopy(document);cloneAnimation(working,source,target);
      return patchSet(`複製動畫 · ${source} → ${target}`,{op:'set',path:['animations',target],value:working.animations[target]});
    }
  });
  bus.register<DeleteAnimationPayload>(EDITOR_COMMANDS.DELETE_ANIMATION,{
    capability:'editAnimation',
    createPatch(document,payload){
      const name=String(payload.name||'');if(!document.animations?.[name])throw new Error(`Animation not found: ${name}`);
      const working=legacyWorkingCopy(document);deleteAnimation(working,name);
      return patchSet(`刪除動畫 · ${name}`,{op:'delete',path:['animations',name]});
    }
  });
  bus.register<SetBoneKeyPayload>(EDITOR_COMMANDS.SET_BONE_KEY,{
    capability:'editAnimation',
    createPatch(document,payload){
      return animationSubtreePatch(document,payload.animationName,working=>setBoneKey(working,payload.animationName,payload.boneName,payload.timelineName,payload.time,payload.values,{curve:payload.curve}),`寫入 Key · ${payload.boneName}.${payload.timelineName} @ ${Number(payload.time).toFixed(3)}s`);
    }
  });
  bus.register<DeleteBoneKeyPayload>(EDITOR_COMMANDS.DELETE_BONE_KEY,{
    capability:'editAnimation',
    createPatch(document,payload){
      return animationSubtreePatch(document,payload.animationName,working=>{if(!deleteBoneKey(working,payload.animationName,payload.boneName,payload.timelineName,payload.time))throw new Error(`Key not found: ${payload.boneName}.${payload.timelineName} @ ${payload.time}`);},`刪除 Key · ${payload.boneName}.${payload.timelineName} @ ${Number(payload.time).toFixed(3)}s`);
    }
  });
  bus.register<SetDrawOrderKeyPayload>(EDITOR_COMMANDS.SET_DRAW_ORDER_KEY,{
    capability:'editAnimation',
    createPatch(document,payload){
      const animationName=String(payload.animationName||''),time=Number(payload.time),offsets=Array.isArray(payload.offsets)?payload.offsets.map(x=>({slot:String(x?.slot||''),offset:Number(x?.offset)})):[];
      return animationSubtreePatch(document,animationName,working=>setDrawOrderKey(working,animationName,time,offsets),`Draw Order Key · ${animationName} @ ${time.toFixed(3)}s`);
    }
  });
  bus.register<DeleteDrawOrderKeyPayload>(EDITOR_COMMANDS.DELETE_DRAW_ORDER_KEY,{
    capability:'editAnimation',
    createPatch(document,payload){
      const animationName=String(payload.animationName||''),time=Number(payload.time);
      return animationSubtreePatch(document,animationName,working=>{if(!deleteDrawOrderKey(working,animationName,time))throw new Error(`Draw order key not found: ${animationName} @ ${time}`);},`Delete Draw Order Key · ${animationName} @ ${time.toFixed(3)}s`);
    }
  });
  bus.register<SetSlotAttachmentKeyPayload>(EDITOR_COMMANDS.SET_SLOT_ATTACHMENT_KEY,{
    capability:'editAnimation',
    createPatch(document,payload){
      const animationName=String(payload.animationName||''),slotName=String(payload.slotName||''),time=Number(payload.time),attachmentName=payload.attachmentName==null?null:String(payload.attachmentName);
      return animationSubtreePatch(document,animationName,working=>setSlotAttachmentKey(working,animationName,slotName,time,attachmentName),`Attachment Key · ${animationName} · ${slotName} @ ${time.toFixed(3)}s`);
    }
  });
  bus.register<DeleteSlotAttachmentKeyPayload>(EDITOR_COMMANDS.DELETE_SLOT_ATTACHMENT_KEY,{
    capability:'editAnimation',
    createPatch(document,payload){
      const animationName=String(payload.animationName||''),slotName=String(payload.slotName||''),time=Number(payload.time);
      return animationSubtreePatch(document,animationName,working=>{if(!deleteSlotAttachmentKey(working,animationName,slotName,time))throw new Error(`Attachment key not found: ${animationName}.${slotName} @ ${time}`);},`Delete Attachment Key · ${animationName} · ${slotName} @ ${time.toFixed(3)}s`);
    }
  });
  bus.register<RetimeAnimationPayload>(EDITOR_COMMANDS.RETIME_ANIMATION,{
    capability:'editAnimation',
    createPatch(document,payload){
      const factor=Number(payload.factor);if(!Number.isFinite(factor)||factor<=0||factor>100)throw new Error(`Invalid retime factor: ${payload.factor}`);
      return animationSubtreePatch(document,payload.name,working=>retimeAnimation(working,payload.name,factor),`Retiming · ${payload.name} × ${factor}`);
    }
  });
  bus.register<SetMeshVertexWeightPayload>(EDITOR_COMMANDS.SET_MESH_VERTEX_WEIGHT,{
    capability:'editWeights',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},vertexIndex=Number(payload.vertexIndex),boneIndex=Number(payload.boneIndex),weight=Number(payload.weight);if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const working=setMeshVertexBoneWeight(document,locator,vertexIndex,boneIndex,weight,payload.lockedBoneIndices||[]);return weightPatch(document,working,`Set Weight · ${locator.slot}/${locator.attachment} · v${vertexIndex} · b${boneIndex}`,{meshWeight:{kind:'set',locator,sourceLocator:working.result.sourceLocator,vertexIndex,boneIndex,weight,layoutChanged:false}});}
  });
  bus.register<NormalizeMeshVertexWeightsPayload>(EDITOR_COMMANDS.NORMALIZE_MESH_VERTEX_WEIGHTS,{
    capability:'editWeights',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},vertexIndex=Number(payload.vertexIndex),working=normalizeMeshVertexWeights(document,locator,vertexIndex,payload.lockedBoneIndices||[]);return weightPatch(document,working,`Normalize Weights · ${locator.slot}/${locator.attachment} · v${vertexIndex}`,{meshWeight:{kind:'normalize',locator,sourceLocator:working.result.sourceLocator,vertexIndex,lockedBoneIndices:payload.lockedBoneIndices||[]}});}
  });
  bus.register<BindMeshVertexBonePayload>(EDITOR_COMMANDS.BIND_MESH_VERTEX_BONE,{
    capability:'editWeights',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},vertexIndex=Number(payload.vertexIndex),boneIndex=Number(payload.boneIndex),working=bindMeshVertexBone(document,locator,vertexIndex,boneIndex,payload.local,Number(payload.weight??.1),payload.lockedBoneIndices||[]);return weightPatch(document,working,`Bind Weight · ${locator.slot}/${locator.attachment} · v${vertexIndex} · b${boneIndex}`,{meshWeight:{kind:'bind',locator,sourceLocator:working.result.sourceLocator,vertexIndex,boneIndex,layoutChanged:working.result.layoutChanged,deformTimelines:working.result.deformTimelines.length}});}
  });
  bus.register<UnbindMeshVertexBonePayload>(EDITOR_COMMANDS.UNBIND_MESH_VERTEX_BONE,{
    capability:'editWeights',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},vertexIndex=Number(payload.vertexIndex),boneIndex=Number(payload.boneIndex),working=unbindMeshVertexBone(document,locator,vertexIndex,boneIndex,payload.lockedBoneIndices||[]);return weightPatch(document,working,`Unbind Weight · ${locator.slot}/${locator.attachment} · v${vertexIndex} · b${boneIndex}`,{meshWeight:{kind:'unbind',locator,sourceLocator:working.result.sourceLocator,vertexIndex,boneIndex,layoutChanged:true}});}
  });
  bus.register<PruneMeshVertexWeightsPayload>(EDITOR_COMMANDS.PRUNE_MESH_VERTEX_WEIGHTS,{
    capability:'editWeights',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},vertexIndex=Number(payload.vertexIndex),threshold=Number(payload.threshold??.01),working=pruneMeshVertexWeights(document,locator,vertexIndex,threshold,payload.lockedBoneIndices||[]);return weightPatch(document,working,`Prune Weights · ${locator.slot}/${locator.attachment} · v${vertexIndex}`,{meshWeight:{kind:'prune',locator,sourceLocator:working.result.sourceLocator,vertexIndex,threshold,layoutChanged:working.result.layoutChanged}});}
  });
  bus.register<LimitMeshVertexInfluencesPayload>(EDITOR_COMMANDS.LIMIT_MESH_VERTEX_INFLUENCES,{
    capability:'editWeights',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},vertexIndex=Number(payload.vertexIndex),maxInfluences=Number(payload.maxInfluences??4),working=limitMeshVertexInfluences(document,locator,vertexIndex,maxInfluences,payload.lockedBoneIndices||[]);return weightPatch(document,working,`Limit Influences · ${locator.slot}/${locator.attachment} · v${vertexIndex} · ${maxInfluences}`,{meshWeight:{kind:'limit',locator,sourceLocator:working.result.sourceLocator,vertexIndex,maxInfluences,layoutChanged:working.result.layoutChanged}});}
  });
  bus.register<BindUnweightedMeshPayload>(EDITOR_COMMANDS.BIND_UNWEIGHTED_MESH,{
    capability:'editWeights',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},working=bindUnweightedMesh(document,locator,payload.replacements||[],Number(payload.maxInfluences??8));return weightPatch(document,working,`Bind Mesh · ${locator.slot}/${locator.attachment} · ${working.result.vertexIndices.length} vertices`,{meshWeight:{kind:'bindMesh',locator,sourceLocator:working.result.sourceLocator,vertexIndices:working.result.vertexIndices,boneIndices:working.result.changedBoneIndices}});}
  });
  bus.register<ReplaceMeshVertexInfluencesPayload>(EDITOR_COMMANDS.REPLACE_MESH_VERTEX_INFLUENCES,{
    capability:'editWeights',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},working=batchReplaceMeshVertexInfluences(document,locator,payload.replacements||[],Number(payload.maxInfluences??8));return weightPatch(document,working,`Replace Weights · ${locator.slot}/${locator.attachment} · ${working.result.vertexIndices.length} vertices`,{meshWeight:{kind:'replaceRows',locator,sourceLocator:working.result.sourceLocator,vertexIndices:working.result.vertexIndices,boneIndices:working.result.changedBoneIndices,layoutChanged:working.result.layoutChanged}});}
  });
  bus.register<BatchSetMeshBoneWeightsPayload>(EDITOR_COMMANDS.BATCH_SET_MESH_BONE_WEIGHTS,{
    capability:'editWeights',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},working=batchSetMeshBoneWeights(document,locator,payload.targets||[],Number(payload.maxInfluences??8));return weightPatch(document,working,`Paint Weights · ${locator.slot}/${locator.attachment} · ${working.result.vertexIndices.length} vertices`,{meshWeight:{kind:'batch',locator,sourceLocator:working.result.sourceLocator,vertexIndices:working.result.vertexIndices,boneIndices:working.result.changedBoneIndices,layoutChanged:working.result.layoutChanged}});}
  });
  bus.register<SetMeshVertexUvPayload>(EDITOR_COMMANDS.SET_MESH_VERTEX_UV,{
    capability:'editMeshTopology',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')};if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const vertexIndex=Number(payload.vertexIndex),u=Number(payload.u),v=Number(payload.v);if(!Number.isInteger(vertexIndex))throw new Error('Vertex index must be an integer');const working=applySetMeshVertexUvToDocument(document,locator,vertexIndex,u,v),source=working.result.model.sourceLocator;let value:any;if(Array.isArray((working.document as any).skins)){const i=(working.document as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===source.skin);value=(working.document as any).skins[i].attachments[source.slot][source.attachment];}else value=(working.document as any).skins[source.skin][source.slot][source.attachment];const patch=patchSet(`Set Mesh UV · ${locator.slot}/${locator.attachment} · v${vertexIndex}`,{op:'set',path:meshAttachmentPath(document,source),value});patch.metadata={meshUv:{locator,sourceLocator:source,vertexIndex,before:working.result.before,after:working.result.after}};return patch;}
  });
  bus.register<ForkLinkedMeshPayload>(EDITOR_COMMANDS.FORK_LINKED_MESH,{
    capability:'editMeshTopology',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')};if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const working=forkLinkedMesh(document,locator),operations:PatchOperation[]=[];let childValue:any;if(Array.isArray((working.document as any).skins)){const i=(working.document as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===locator.skin);childValue=(working.document as any).skins[i].attachments[locator.slot][locator.attachment];}else childValue=(working.document as any).skins[locator.skin][locator.slot][locator.attachment];operations.push({op:'set',path:meshAttachmentPath(document,locator),value:childValue});for(const animation of [...new Set(working.result.copiedTimelines.map(ref=>ref.animation))])operations.push({op:'set',path:['animations',animation],value:(working.document.animations as any)?.[animation]});const patch=patchSet(`Fork Linked Mesh · ${locator.skin}/${locator.slot}/${locator.attachment}`,...operations);patch.metadata={meshFork:{locator,sourceLocator:working.result.sourceLocator,timelineSource:working.result.timelineSource,copiedAnimations:[...new Set(working.result.copiedTimelines.map(ref=>ref.animation))],timelineTypes:working.result.inheritedTimelineTypes,sourceDependentsBefore:working.result.sourceDependentsBefore,sourceDependentsAfter:working.result.sourceDependentsAfter}};return patch;}
  });
  bus.register<MoveMeshVerticesPayload>(EDITOR_COMMANDS.MOVE_MESH_VERTICES,{
    capability:'editMeshTopology',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')};if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const moves=Array.isArray(payload.moves)?payload.moves:[];if(!moves.length)throw new Error('Mesh vertex batch move is empty');const seen=new Set<number>();let workingDocument=document,last:any=null;for(const move of moves){const vertexIndex=Number(move.vertexIndex);if(!Number.isInteger(vertexIndex)||seen.has(vertexIndex))throw new Error(`Invalid or duplicate batch vertex index: ${move.vertexIndex}`);seen.add(vertexIndex);const step=applyMoveMeshVertexToDocument(workingDocument,locator,vertexIndex,move.delta);workingDocument=step.document;last=step.result;}const source=last.model.sourceLocator;let value:any;if(Array.isArray((workingDocument as any).skins)){const i=(workingDocument as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===source.skin);value=(workingDocument as any).skins[i].attachments[source.slot][source.attachment];}else value=(workingDocument as any).skins[source.skin][source.slot][source.attachment];const patch=patchSet(`Move Mesh Vertices · ${locator.slot}/${locator.attachment} · ${moves.length}`,{op:'set',path:meshAttachmentPath(document,source),value});patch.metadata={meshVertexBatchMove:{locator,sourceLocator:source,count:moves.length,indices:[...seen]}};return patch;}
  });
  bus.register<MoveMeshVertexPayload>(EDITOR_COMMANDS.MOVE_MESH_VERTEX,{
    capability:'editMeshTopology',
    createPatch(document,payload){
      const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')};if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const vertexIndex=Number(payload.vertexIndex);if(!Number.isInteger(vertexIndex))throw new Error(`Mesh vertex index must be an integer: ${payload.vertexIndex}`);const working=applyMoveMeshVertexToDocument(document,locator,vertexIndex,payload.delta),source=working.result.model.sourceLocator;let value:any;if(Array.isArray((working.document as any).skins)){const i=(working.document as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===source.skin);value=(working.document as any).skins[i].attachments[source.slot][source.attachment];}else value=(working.document as any).skins[source.skin][source.slot][source.attachment];const patch=patchSet(`Move Mesh Vertex · ${locator.slot}/${locator.attachment} · v${vertexIndex}`,{op:'set',path:meshAttachmentPath(document,source),value});patch.metadata={meshVertexMove:{locator,sourceLocator:source,vertexIndex,vertexId:working.result.vertexId,weighted:working.result.model.weighted}};return patch;
    }
  });
  bus.register<FlipMeshEdgePayload>(EDITOR_COMMANDS.FLIP_MESH_EDGE,{
    capability:'editMeshTopology',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')};if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const a=Number(payload.a),b=Number(payload.b);if(!Number.isInteger(a)||!Number.isInteger(b))throw new Error('Flip edge indices must be integers');const working=applyFlipMeshEdgeToDocument(document,locator,a,b),source=working.result.model.sourceLocator;let value:any;if(Array.isArray((working.document as any).skins)){const i=(working.document as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===source.skin);value=(working.document as any).skins[i].attachments[source.slot][source.attachment];}else value=(working.document as any).skins[source.skin][source.slot][source.attachment];const patch=patchSet(`Flip Mesh Edge · ${locator.slot}/${locator.attachment} · ${a}-${b}`,{op:'set',path:meshAttachmentPath(document,source),value});patch.metadata={meshFlip:{locator,sourceLocator:source,edge:[a,b],opposite:working.result.opposite,triangleIndices:working.result.triangleIndices,triangles:working.result.model.triangles.length/3}};return patch;}
  });
  bus.register<SetMeshHullPayload>(EDITOR_COMMANDS.SET_MESH_HULL,{
    capability:'editMeshTopology',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},hullCount=Number(payload.hullCount);if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const working=applySetMeshHullCountToDocument(document,locator,hullCount),source=working.result.model.sourceLocator;let value:any;if(Array.isArray((working.document as any).skins)){const i=(working.document as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===source.skin);value=(working.document as any).skins[i].attachments[source.slot][source.attachment];}else value=(working.document as any).skins[source.skin][source.slot][source.attachment];const patch=patchSet(`Set Mesh Hull · ${locator.slot}/${locator.attachment} · ${hullCount}`,{op:'set',path:meshAttachmentPath(document,source),value});patch.metadata={meshHull:{locator,sourceLocator:source,before:working.result.before,after:working.result.after,vertices:working.result.model.vertices.length}};return patch;}
  });
  bus.register<CreateMeshFacePayload>(EDITOR_COMMANDS.CREATE_MESH_FACE,{
    capability:'editMeshTopology',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')},indices=(payload.indices||[]).map(Number) as [number,number,number];if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const working=applyCreateMeshFaceToDocument(document,locator,indices),source=working.result.model.sourceLocator;let value:any;if(Array.isArray((working.document as any).skins)){const i=(working.document as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===source.skin);value=(working.document as any).skins[i].attachments[source.slot][source.attachment];}else value=(working.document as any).skins[source.skin][source.slot][source.attachment];const patch=patchSet(`Create Mesh Face · ${locator.slot}/${locator.attachment} · ${indices.join('-')}`,{op:'set',path:meshAttachmentPath(document,source),value});patch.metadata={meshCreateFace:{locator,sourceLocator:source,triangleIndex:working.result.triangleIndex,indices:working.result.indices,triangles:working.result.model.triangles.length/3}};return patch;}
  });
  bus.register<InsertMeshFaceVertexPayload>(EDITOR_COMMANDS.INSERT_MESH_FACE_VERTEX,{
    capability:'editMeshTopology',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')};if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const triangleIndex=Number(payload.triangleIndex);if(!Number.isInteger(triangleIndex))throw new Error('Triangle index must be an integer');const barycentric=(payload.barycentric||[1/3,1/3,1/3]).map(Number) as [number,number,number],working=applyInsertMeshVertexInFaceToDocument(document,locator,triangleIndex,barycentric),source=working.result.model.sourceLocator,operations:PatchOperation[]=[];let value:any;if(Array.isArray((working.document as any).skins)){const i=(working.document as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===source.skin);value=(working.document as any).skins[i].attachments[source.slot][source.attachment];}else value=(working.document as any).skins[source.skin][source.slot][source.attachment];operations.push({op:'set',path:meshAttachmentPath(document,source),value});for(const ref of working.result.migratedDeforms)operations.push({op:'set',path:['animations',ref.animation,'attachments',ref.skin,ref.slot,ref.attachment,'deform'],value:ref.frames});const patch=patchSet(`Insert Mesh Vertex · ${locator.slot}/${locator.attachment} · f${triangleIndex}`,...operations);patch.metadata={meshFaceInsert:{locator,sourceLocator:source,triangleIndex,sourceIndices:working.result.sourceIndices,barycentric:working.result.barycentric,insertIndex:working.result.insertIndex,newVertexId:working.result.newVertexId,vertices:working.result.model.vertices.length,triangles:working.result.model.triangles.length/3,deformTimelines:working.result.migratedDeforms.length}};return patch;}
  });
  bus.register<DeleteMeshVertexPayload>(EDITOR_COMMANDS.DELETE_MESH_VERTEX,{
    capability:'editMeshTopology',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')};if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const vertexIndex=Number(payload.vertexIndex);if(!Number.isInteger(vertexIndex))throw new Error('Vertex index must be an integer');const working=applyDeleteMeshVertexToDocument(document,locator,vertexIndex),source=working.result.model.sourceLocator,operations:PatchOperation[]=[];let value:any;if(Array.isArray((working.document as any).skins)){const i=(working.document as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===source.skin);value=(working.document as any).skins[i].attachments[source.slot][source.attachment];}else value=(working.document as any).skins[source.skin][source.slot][source.attachment];operations.push({op:'set',path:meshAttachmentPath(document,source),value});for(const ref of working.result.migratedDeforms)operations.push({op:'set',path:['animations',ref.animation,'attachments',ref.skin,ref.slot,ref.attachment,'deform'],value:ref.frames});const patch=patchSet(`Delete Mesh Vertex · ${locator.slot}/${locator.attachment} · v${vertexIndex}`,...operations);patch.metadata={meshDeleteVertex:{locator,sourceLocator:source,vertexIndex,removedVertexId:working.result.removedVertexId,vertices:working.result.model.vertices.length,triangles:working.result.model.triangles.length/3,removedTriangles:working.result.removedTriangles,deformTimelines:working.result.migratedDeforms.length}};return patch;}
  });
  bus.register<DeleteMeshFacePayload>(EDITOR_COMMANDS.DELETE_MESH_FACE,{
    capability:'editMeshTopology',
    createPatch(document,payload){const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')};if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const triangleIndex=Number(payload.triangleIndex);if(!Number.isInteger(triangleIndex))throw new Error('Triangle index must be an integer');const working=applyDeleteMeshFaceToDocument(document,locator,triangleIndex),source=working.result.model.sourceLocator;let value:any;if(Array.isArray((working.document as any).skins)){const i=(working.document as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===source.skin);value=(working.document as any).skins[i].attachments[source.slot][source.attachment];}else value=(working.document as any).skins[source.skin][source.slot][source.attachment];const patch=patchSet(`Delete Mesh Face · ${locator.slot}/${locator.attachment} · f${triangleIndex}`,{op:'set',path:meshAttachmentPath(document,source),value});patch.metadata={meshDeleteFace:{locator,sourceLocator:source,triangleIndex,removed:working.result.removed,triangles:working.result.model.triangles.length/3}};return patch;}
  });
  bus.register<SplitMeshEdgePayload>(EDITOR_COMMANDS.SPLIT_MESH_EDGE,{
    capability:'editMeshTopology',
    createPatch(document,payload){
      const locator={skin:String(payload.locator?.skin||'default'),slot:String(payload.locator?.slot||''),attachment:String(payload.locator?.attachment||'')};if(!locator.slot||!locator.attachment)throw new Error('Mesh locator is incomplete');const a=Number(payload.a),b=Number(payload.b),t=Number(payload.t??.5);if(!Number.isInteger(a)||!Number.isInteger(b))throw new Error(`Mesh edge indices must be integers: ${payload.a}, ${payload.b}`);
      const working=applySplitEdgeToDocument(document,locator,a,b,t),source=working.result.model.sourceLocator,operations:PatchOperation[]=[{op:'set',path:meshAttachmentPath(document,source),value:(()=>{let node:any=working.document;if(Array.isArray((working.document as any).skins)){const i=(working.document as any).skins.findIndex((skin:any)=>String(skin?.name||'default')===source.skin);return (working.document as any).skins[i].attachments[source.slot][source.attachment];}return (working.document as any).skins[source.skin][source.slot][source.attachment];})()}];
      for(const ref of working.result.migratedDeforms)operations.push({op:'set',path:['animations',ref.animation,'attachments',ref.skin,ref.slot,ref.attachment,'deform'],value:ref.frames});
      const patch=patchSet(`Split Mesh Edge · ${locator.slot}/${locator.attachment} · ${a}-${b}`,...operations);patch.metadata={meshSplit:{locator,sourceLocator:source,a,b,t,insertIndex:working.result.insertIndex,newVertexId:working.result.newVertexId,vertexCount:working.result.model.vertices.length,deformTimelines:working.result.migratedDeforms.length}};return patch;
    }
  });
  bus.register<SolveSemanticPosePayload>(EDITOR_COMMANDS.SOLVE_SEMANTIC_POSE,{
    capability:'editAnimation',
    createPatch(document,payload){
      const animationName=String(payload.animationName||'');if(!document.animations?.[animationName])throw new Error(`Animation not found: ${animationName}`);
      const time=Number(payload.time);if(!Number.isFinite(time)||time<0)throw new Error(`Invalid semantic solve time: ${payload.time}`);
      const working=legacyWorkingCopy(document),beforeOutside=stableOutsideAnimation(document,animationName);
      if(payload.visualOperations?.length)applyAnimationPlan(working,{operations:payload.visualOperations as any[]});
      let solved:any=solvePoseTargetsStaged(working,String(payload.atlasText||''),payload.spec as any,{semanticRig:payload.semanticRig as any});
      const refineAt=Number(payload.refine?.residualAt??1.5);
      if(solved?.residual?.maxDistance>refineAt&&payload.refine?.role&&payload.refine?.midRole){
        const natural=solved.solutions?.find((item:any)=>item.targetRole===payload.refine!.role&&item.solvedMid);
        if(natural?.solvedMid){
          const originalTargets=(payload.spec as any)?.targets||{},refinedSpec={...(payload.spec as any),targets:{[payload.refine.midRole]:natural.solvedMid,[payload.refine.role]:originalTargets[payload.refine.role]}};
          const refined:any=solvePoseTargetsStaged(working,String(payload.atlasText||''),refinedSpec,{semanticRig:payload.semanticRig as any});
          solved={...refined,operations:[...(solved.operations||[]),...(refined.operations||[])],refinedFromNatural:true};
        }
      }
      const maxResidual=Number(payload.maxResidual??2.5);if(Number(solved?.residual?.maxDistance??Infinity)>maxResidual)throw new Error(`Semantic pose residual too high: ${Number(solved?.residual?.maxDistance).toFixed(3)}px`);
      if(stableOutsideAnimation(working,animationName)!==beforeOutside)throw new Error('Semantic command escaped animation scope');
      const patch=patchSet(`Semantic Pose · ${animationName} @ ${time.toFixed(3)}s`,{op:'set',path:['animations',animationName],value:working.animations[animationName]});
      patch.metadata={solved,visualOperationCount:payload.visualOperations?.length||0};return patch;
    }
  });
  return bus;
}
