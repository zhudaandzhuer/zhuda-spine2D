import { boneKey, entityKeyToString } from './entityKey.ts';
import { buildStaticDependencyGraph, type DependencyGraph } from './dependencyGraph.ts';
import type { SpineDocument } from './spineDocument.ts';

export interface BoneSetupImpact {
  bone:string;
  affectedBones:string[];
  descendants:string[];
  slots:string[];
  attachments:Array<{skin:string;slot:string;name:string}>;
  constraints:Array<{kind:string;name:string;relationship:string}>;
  allAnimations:string[];
  directTimelineAnimations:string[];
}
function nodeKeyName(node:any){return node?.key?.name||'';}
function collectDescendants(graph:DependencyGraph,boneId:string){const seen=new Set<string>(),queue=[boneId];while(queue.length){const current=queue.shift()!;for(const edge of graph.incoming.get(current)||[]){if(edge.kind!=='parent'||seen.has(edge.from))continue;seen.add(edge.from);queue.push(edge.from);}}return [...seen];}
export function analyzeBoneSetupImpact(raw:SpineDocument,boneName:string,graph:DependencyGraph=buildStaticDependencyGraph(raw)):BoneSetupImpact{
  const boneId=entityKeyToString(boneKey(boneName));if(!graph.nodes.has(boneId))throw new Error(`Bone not found: ${boneName}`);const descendantIds=collectDescendants(graph,boneId),affectedBoneIds=[boneId,...descendantIds],affectedBones=affectedBoneIds.map(id=>nodeKeyName(graph.nodes.get(id))).filter(Boolean),slotIds=new Set<string>(),attachmentIds=new Set<string>(),constraintMap=new Map<string,{kind:string;name:string;relationship:string}>(),directAnimations=new Set<string>();
  for(const id of affectedBoneIds){for(const edge of graph.incoming.get(id)||[]){if(edge.kind==='slot-bone')slotIds.add(edge.from);if(edge.kind==='constraint-bone'||edge.kind==='constraint-target'){const node=graph.nodes.get(edge.from),key:any=node?.key;if(key?.name)constraintMap.set(edge.from,{kind:key.kind,name:key.name,relationship:edge.kind});}if(edge.kind==='timeline-owner'){const key:any=graph.nodes.get(edge.from)?.key;if(key?.animation)directAnimations.add(key.animation);}}}
  for(const slotId of slotIds){for(const edge of graph.incoming.get(slotId)||[]){if(edge.kind==='attachment-slot')attachmentIds.add(edge.from);if(edge.kind==='constraint-target-slot'){const node=graph.nodes.get(edge.from),key:any=node?.key;if(key?.name)constraintMap.set(edge.from,{kind:key.kind,name:key.name,relationship:edge.kind});}if(edge.kind==='timeline-owner'){const key:any=graph.nodes.get(edge.from)?.key;if(key?.animation)directAnimations.add(key.animation);}}}
  for(const id of constraintMap.keys())for(const edge of graph.incoming.get(id)||[])if(edge.kind==='timeline-owner'){const key:any=graph.nodes.get(edge.from)?.key;if(key?.animation)directAnimations.add(key.animation);}
  const slots=[...slotIds].map(id=>nodeKeyName(graph.nodes.get(id))).filter(Boolean).sort(),attachments=[...attachmentIds].map(id=>{const key:any=graph.nodes.get(id)?.key;return {skin:String(key?.skin||''),slot:String(key?.slot||''),name:String(key?.name||'')}}).filter(item=>item.name).sort((a,b)=>`${a.skin}/${a.slot}/${a.name}`.localeCompare(`${b.skin}/${b.slot}/${b.name}`)),constraints=[...constraintMap.values()].sort((a,b)=>`${a.kind}/${a.name}`.localeCompare(`${b.kind}/${b.name}`));
  return {bone:boneName,affectedBones:affectedBones.sort(),descendants:descendantIds.map(id=>nodeKeyName(graph.nodes.get(id))).filter(Boolean).sort(),slots,attachments,constraints,allAnimations:Object.keys(raw.animations||{}).sort(),directTimelineAnimations:[...directAnimations].sort()};
}
