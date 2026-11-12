import type { SpineDocument } from './spineDocument.ts';
import { decodeMeshTopology, type DeformFrame, type MeshLocator, type MeshTopologyModel } from './meshTopology.ts';

export interface DeformLocator extends MeshLocator {}
export interface DeformKeyResult {
  animationName:string;
  locator:DeformLocator;
  time:number;
  created:boolean;
  fullLength:number;
  weighted:boolean;
  frame:DeformFrame;
}
export interface DeformValidationResult { ok:boolean; issues:string[]; warnings:string[]; }

const EPS=1e-6;
const clone=<T>(value:T):T=>(typeof structuredClone==='function'?structuredClone(value):JSON.parse(JSON.stringify(value))) as T;
const locatorKey=(l:DeformLocator)=>`${l.skin}/${l.slot}/${l.attachment}`;

export function deformFullLength(model:MeshTopologyModel):number {
  return model.weighted?model.vertices.reduce((sum,v)=>sum+(v.influences?.length||0)*2,0):model.vertices.length*2;
}
export function expandDeformFrame(frame:DeformFrame|undefined,length:number):number[] {
  const full=new Array(length).fill(0),values=Array.isArray(frame?.vertices)?frame!.vertices!:[],offset=Math.max(0,Math.trunc(Number(frame?.offset)||0));
  for(let i=0;i<values.length&&offset+i<length;i++){const value=Number(values[i]);if(Number.isFinite(value))full[offset+i]=value;}
  return full;
}
export function compressDeformFrame(full:number[],template:DeformFrame={}):DeformFrame {
  const out:DeformFrame={...clone(template)};delete out.vertices;delete out.offset;
  let first=0,last=full.length-1;while(first<full.length&&Math.abs(Number(full[first]||0))<1e-9)first++;while(last>=first&&Math.abs(Number(full[last]||0))<1e-9)last--;
  if(last>=first){if(first>0)out.offset=first;out.vertices=full.slice(first,last+1).map(Number);}
  return out;
}
function normalizeCurve(curve:unknown):unknown {
  if(curve===undefined||curve===null||curve===''||curve==='linear')return undefined;
  if(curve==='stepped')return 'stepped';
  let value=curve;if(typeof value==='string'){try{value=JSON.parse(value);}catch{throw new Error('DEFORM_CURVE_INVALID_JSON');}}
  if(!Array.isArray(value)||!value.length||value.length%4!==0||value.some(x=>typeof x!=='number'||!Number.isFinite(x)))throw new Error('DEFORM_CURVE_INVALID');
  return [...value];
}
function ensureDirectModel(raw:SpineDocument,locator:DeformLocator):MeshTopologyModel {
  const model=decodeMeshTopology(raw,locator);if(model.linked)throw new Error('LINKED_MESH_DEFORM_BLOCKED: fork linked mesh before Deform authoring');return model;
}
function animation(raw:SpineDocument,name:string):any {const a=(raw.animations as any)?.[name];if(!a)throw new Error(`Animation not found: ${name}`);return a;}
function deformFrames(raw:SpineDocument,animationName:string,locator:DeformLocator):DeformFrame[]|undefined {return (raw.animations as any)?.[animationName]?.attachments?.[locator.skin]?.[locator.slot]?.[locator.attachment]?.deform;}
function ensureDeformFrames(raw:any,animationName:string,locator:DeformLocator):DeformFrame[] {
  const a=animation(raw,animationName);a.attachments??={};a.attachments[locator.skin]??={};a.attachments[locator.skin][locator.slot]??={};a.attachments[locator.skin][locator.slot][locator.attachment]??={};a.attachments[locator.skin][locator.slot][locator.attachment].deform??=[];return a.attachments[locator.skin][locator.slot][locator.attachment].deform;
}
function cleanupDeformPath(raw:any,animationName:string,locator:DeformLocator):void {
  const a=raw.animations?.[animationName],skin=a?.attachments?.[locator.skin],slot=skin?.[locator.slot],node=slot?.[locator.attachment];if(!node)return;
  if(Array.isArray(node.deform)&&!node.deform.length)delete node.deform;if(!Object.keys(node).length)delete slot[locator.attachment];if(!Object.keys(slot||{}).length)delete skin[locator.slot];if(!Object.keys(skin||{}).length)delete a.attachments[locator.skin];if(a.attachments&&!Object.keys(a.attachments).length)delete a.attachments;
}
export function listDeformKeyTimes(raw:SpineDocument,animationName:string,locator:DeformLocator):number[] {const frames=deformFrames(raw,animationName,locator);return Array.isArray(frames)?frames.map(f=>Number(f?.time||0)).filter(Number.isFinite).sort((a,b)=>a-b):[];}
export function exactDeformKey(raw:SpineDocument,animationName:string,locator:DeformLocator,time:number):DeformFrame|null {const frames=deformFrames(raw,animationName,locator);if(!Array.isArray(frames))return null;const t=Number(time);return frames.find(f=>Math.abs(Number(f?.time||0)-t)<=EPS)||null;}
export function setDeformKey(raw:SpineDocument,animationName:string,locator:DeformLocator,time:number,offsets:number[],curve?:unknown):{document:SpineDocument;result:DeformKeyResult} {
  time=Number(time);if(!Number.isFinite(time)||time<0)throw new Error(`INVALID_DEFORM_TIME: ${time}`);const model=ensureDirectModel(raw,locator),length=deformFullLength(model);if(!Array.isArray(offsets)||offsets.length!==length)throw new Error(`DEFORM_LENGTH_MISMATCH: ${offsets?.length||0}/${length}`);if(offsets.some(v=>!Number.isFinite(Number(v))))throw new Error('DEFORM_NONFINITE_VALUE');
  const document=clone(raw),frames=ensureDeformFrames(document,animationName,locator);let frame=frames.find(f=>Math.abs(Number(f?.time||0)-time)<=EPS),created=false;if(!frame){frame={};frames.push(frame);created=true;}if(time>EPS||Object.prototype.hasOwnProperty.call(frame,'time'))frame.time=time;else delete frame.time;
  const normalized=normalizeCurve(curve);const next=compressDeformFrame(offsets.map(Number),frame);for(const key of Object.keys(frame))delete (frame as any)[key];Object.assign(frame,next);if(curve!==undefined){if(normalized===undefined)delete frame.curve;else frame.curve=normalized;}frames.sort((a,b)=>Number(a.time||0)-Number(b.time||0));
  return{document,result:{animationName,locator:{...locator},time,created,fullLength:length,weighted:model.weighted,frame:clone(frame)}};
}
export function deleteDeformKey(raw:SpineDocument,animationName:string,locator:DeformLocator,time:number):{document:SpineDocument;result:{animationName:string;locator:DeformLocator;time:number;deletedFrame:DeformFrame}} {
  ensureDirectModel(raw,locator);const document=clone(raw),frames=deformFrames(document,animationName,locator);if(!Array.isArray(frames))throw new Error('DEFORM_TIMELINE_NOT_FOUND');const t=Number(time),index=frames.findIndex(f=>Math.abs(Number(f?.time||0)-t)<=EPS);if(index<0)throw new Error(`DEFORM_KEY_NOT_FOUND: ${time}`);const [deletedFrame]=frames.splice(index,1);cleanupDeformPath(document,animationName,locator);return{document,result:{animationName,locator:{...locator},time:t,deletedFrame:clone(deletedFrame!)}};
}
export function validateDeformAuthoring(raw:SpineDocument):DeformValidationResult {
  const issues:string[]=[],warnings:string[]=[];const cache=new Map<string,number>();
  const lengthFor=(locator:DeformLocator)=>{const key=locatorKey(locator);if(cache.has(key))return cache.get(key)!;try{const model=decodeMeshTopology(raw,locator),len=deformFullLength(model);cache.set(key,len);return len;}catch(error){const message=(error as Error).message;if(message.includes('Attachment is not an editable mesh')){warnings.push(`${key}: non-mesh VertexAttachment Deform is preserved read-only`);cache.set(key,Infinity);return Infinity;}throw error;}};
  for(const [animationName,a] of Object.entries<any>(raw.animations||{}))for(const [skin,slots] of Object.entries<any>(a?.attachments||{}))for(const [slot,atts] of Object.entries<any>(slots||{}))for(const [attachment,node] of Object.entries<any>(atts||{})){
    const frames=node?.deform;if(frames===undefined)continue;const path=`animations.${animationName}.attachments.${skin}.${slot}.${attachment}.deform`;if(!Array.isArray(frames)){issues.push(`${path}: timeline must be an array`);continue;}let length:number;try{length=lengthFor({skin,slot,attachment});}catch(error){issues.push(`${path}: ${(error as Error).message}`);continue;}let prev=-Infinity;
    for(let i=0;i<frames.length;i++){const f=frames[i];if(!f||typeof f!=='object'||Array.isArray(f)){issues.push(`${path}[${i}]: frame must be an object`);continue;}const time=Number(f.time||0);if(!Number.isFinite(time)||time<0)issues.push(`${path}[${i}]: invalid time`);if(time+EPS<prev)issues.push(`${path}: frames are not time-sorted`);prev=time;const offset=f.offset===undefined?0:Number(f.offset);if(!Number.isInteger(offset)||offset<0)issues.push(`${path}[${i}]: invalid offset`);if(f.vertices!==undefined&&!Array.isArray(f.vertices))issues.push(`${path}[${i}].vertices: must be an array`);const values=Array.isArray(f.vertices)?f.vertices:[];if(values.some((v:any)=>typeof v!=='number'||!Number.isFinite(v)))issues.push(`${path}[${i}].vertices: nonfinite value`);if(offset+values.length>length)issues.push(`${path}[${i}]: sparse range ${offset}+${values.length} exceeds ${length}`);try{normalizeCurve(f.curve);}catch{issues.push(`${path}[${i}]: invalid curve`);}if(Object.keys(f).some(key=>!['time','offset','vertices','curve'].includes(key)))warnings.push(`${path}[${i}]: unknown frame fields preserved`);}
  }
  return{ok:issues.length===0,issues,warnings};
}
