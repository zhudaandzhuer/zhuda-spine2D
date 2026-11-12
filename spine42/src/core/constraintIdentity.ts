import { cloneSpineDocument, type SpineDocument } from './spineDocument.ts';
import { assertConstraintGraphSafe } from './constraintValidation.ts';
import { constraintList, findConstraint, type ConstraintKind } from './constraintAuthoring.ts';
import { constraintSkinReferences, constraintTimelineReferences, type ConstraintSkinReference, type ConstraintTimelineReference } from './constraintStructure.ts';

export interface ConstraintRenameResult { kind:ConstraintKind; oldName:string; newName:string; timelineReferences:ConstraintTimelineReference[]; skinReferences:ConstraintSkinReference[]; }
export interface ConstraintSkinEditResult { kind:ConstraintKind; name:string; beforeSkinRequired:boolean; afterSkinRequired:boolean; beforeSkinNames:string[]; afterSkinNames:string[]; addedSkins:string[]; removedSkins:string[]; }

const own=(object:object,key:string)=>Object.prototype.hasOwnProperty.call(object,key);
function skinRecords(raw:SpineDocument):any[]{return Array.isArray((raw as any).skins)?(raw as any).skins:[];}
function normalizeName(value:unknown){const name=String(value??'').trim();if(!name)throw new Error('CONSTRAINT_NAME_REQUIRED');return name;}
function normalizeSkinNames(raw:SpineDocument,value:unknown):string[]{if(!Array.isArray(value))throw new Error('CONSTRAINT_SKIN_NAMES_ARRAY_REQUIRED');const names=value.map(x=>String(x??'').trim()).filter(Boolean);if(new Set(names).size!==names.length)throw new Error('CONSTRAINT_SKIN_NAMES_DUPLICATE');const available=new Set(skinRecords(raw).map(s=>String(s?.name||'default')));for(const name of names)if(!available.has(name))throw new Error(`CONSTRAINT_SKIN_MISSING: ${name}`);return names.sort();}

export function renameConstraint(raw:SpineDocument,kind:ConstraintKind,oldNameInput:unknown,newNameInput:unknown):{document:SpineDocument;result:ConstraintRenameResult}{
  const oldName=normalizeName(oldNameInput),newName=normalizeName(newNameInput);if(oldName===newName)throw new Error('CONSTRAINT_RENAME_NO_CHANGE');findConstraint(raw,kind,oldName);if(constraintList(raw,kind).some(c=>String(c.name)===newName))throw new Error(`CONSTRAINT_NAME_EXISTS: ${kind}:${newName}`);
  const timelineReferences=constraintTimelineReferences(raw,kind,oldName),skinReferences=constraintSkinReferences(raw,kind,oldName),document=cloneSpineDocument(raw),entry=findConstraint(document,kind,oldName);entry.constraint.name=newName;
  for(const ref of timelineReferences){const container=(document.animations as any)?.[ref.animation]?.[kind];if(!container||!own(container,oldName))throw new Error(`CONSTRAINT_RENAME_TIMELINE_MISSING: ${ref.animation}/${kind}/${oldName}`);if(own(container,newName))throw new Error(`CONSTRAINT_RENAME_TIMELINE_CONFLICT: ${ref.animation}/${kind}/${newName}`);container[newName]=container[oldName];delete container[oldName];}
  for(const skin of skinRecords(document)){const values=skin?.[kind];if(!Array.isArray(values)||!values.includes(oldName))continue;if(values.includes(newName))throw new Error(`CONSTRAINT_RENAME_SKIN_CONFLICT: ${skin.name||'default'}/${kind}/${newName}`);skin[kind]=values.map((value:string)=>value===oldName?newName:value);}
  assertConstraintGraphSafe(document);return{document,result:{kind,oldName,newName,timelineReferences,skinReferences}};
}

export function setConstraintSkinMembership(raw:SpineDocument,kind:ConstraintKind,name:string,{skinRequired,skinNames}:{skinRequired:boolean;skinNames:string[]}):{document:SpineDocument;result:ConstraintSkinEditResult}{
  if(typeof skinRequired!=='boolean')throw new Error('CONSTRAINT_SKIN_REQUIRED_BOOLEAN');const normalized=normalizeSkinNames(raw,skinNames);if(skinRequired&&!normalized.length)throw new Error('CONSTRAINT_SKIN_REQUIRED_NEEDS_MEMBERSHIP');if(!skinRequired&&normalized.length)throw new Error('CONSTRAINT_SKIN_DISABLED_REQUIRES_EMPTY_MEMBERSHIP');const beforeEntry=findConstraint(raw,kind,name).constraint,beforeSkinRequired=beforeEntry.skin===true,beforeSkinNames=constraintSkinReferences(raw,kind,name).map(x=>x.skin).sort();if(beforeSkinRequired===skinRequired&&JSON.stringify(beforeSkinNames)===JSON.stringify(normalized))throw new Error('CONSTRAINT_SKIN_MEMBERSHIP_NO_CHANGE');const document=cloneSpineDocument(raw),entry=findConstraint(document,kind,name).constraint;
  if(skinRequired)entry.skin=true;else delete entry.skin;
  const wanted=new Set(normalized);for(const skin of skinRecords(document)){const skinName=String(skin?.name||'default'),values=Array.isArray(skin?.[kind])?[...skin[kind]]:[],has=values.includes(name),want=wanted.has(skinName);if(want&&!has){values.push(name);skin[kind]=values;}else if(!want&&has){skin[kind]=values.filter((value:string)=>value!==name);if(!skin[kind].length)delete skin[kind];}}
  const afterSkinNames=constraintSkinReferences(document,kind,name).map(x=>x.skin).sort();if((entry.skin===true)!==skinRequired||JSON.stringify(afterSkinNames)!==JSON.stringify(normalized))throw new Error('CONSTRAINT_SKIN_MEMBERSHIP_WRITE_MISMATCH');assertConstraintGraphSafe(document);return{document,result:{kind,name,beforeSkinRequired,afterSkinRequired:skinRequired,beforeSkinNames,afterSkinNames,addedSkins:afterSkinNames.filter(x=>!beforeSkinNames.includes(x)),removedSkins:beforeSkinNames.filter(x=>!afterSkinNames.includes(x))}};
}
