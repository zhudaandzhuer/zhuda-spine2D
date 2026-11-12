import type { JsonValue } from './spineDocument.ts';

export type PatchPath = readonly (string | number)[];
export type PatchOperation =
  | { op: 'set'; path: PatchPath; value: unknown }
  | { op: 'delete'; path: PatchPath }
  | { op: 'splice'; path: PatchPath; index: number; deleteCount: number; items?: unknown[] };
export interface PatchSet { label: string; operations: PatchOperation[]; metadata?: Record<string,unknown>; }

const clone = <T>(value: T): T => (typeof structuredClone === 'function' ? structuredClone(value) : JSON.parse(JSON.stringify(value))) as T;
function parentAt(root: unknown, path: PatchPath): { parent: any; key: string | number } {
  if (!path.length) throw new Error('Patch path cannot target document root.');
  let parent: any = root;
  for (let i=0;i<path.length-1;i++) {
    const key=path[i]!;
    if (parent == null || typeof parent !== 'object') throw new Error(`Patch path is not traversable at ${path.slice(0,i+1).join('.')}`);
    parent=parent[key as any];
  }
  return { parent, key:path[path.length-1]! };
}
function valueAt(root: unknown, path: PatchPath): { exists: boolean; value: unknown } {
  if (!path.length) return { exists:true, value:root };
  const {parent,key}=parentAt(root,path);if(parent==null||typeof parent!=='object')return {exists:false,value:undefined};
  return { exists:Object.prototype.hasOwnProperty.call(parent,key), value:parent[key as any] };
}
export function applyPatchSet<T>(document: T, patchSet: PatchSet, { cloneDocument=true } = {}): { document: T; inverse: PatchSet } {
  const root:any=cloneDocument?clone(document):document,inverse:PatchOperation[]=[];
  for (const operation of patchSet.operations) {
    if(operation.op==='set'){
      const previous=valueAt(root,operation.path),{parent,key}=parentAt(root,operation.path);if(parent==null||typeof parent!=='object')throw new Error(`Cannot set ${operation.path.join('.')}`);
      parent[key as any]=clone(operation.value);inverse.unshift(previous.exists?{op:'set',path:[...operation.path],value:clone(previous.value)}:{op:'delete',path:[...operation.path]});
    } else if(operation.op==='delete') {
      const previous=valueAt(root,operation.path);if(!previous.exists)continue;const {parent,key}=parentAt(root,operation.path);if(Array.isArray(parent)&&typeof key==='number')parent.splice(key,1);else delete parent[key as any];inverse.unshift({op:'set',path:[...operation.path],value:clone(previous.value)});
    } else {
      const target=valueAt(root,operation.path).value;if(!Array.isArray(target))throw new Error(`Splice target is not an array: ${operation.path.join('.')}`);
      const index=Math.max(0,Math.min(target.length,Math.trunc(operation.index))),deleteCount=Math.max(0,Math.trunc(operation.deleteCount)),items=clone(operation.items||[]),deleted=target.splice(index,deleteCount,...items);inverse.unshift({op:'splice',path:[...operation.path],index,deleteCount:items.length,items:clone(deleted)});
    }
  }
  return {document:root as T,inverse:{label:`Undo ${patchSet.label}`,operations:inverse}};
}
export function patchSet(label: string, ...operations: PatchOperation[]): PatchSet { return {label,operations}; }
