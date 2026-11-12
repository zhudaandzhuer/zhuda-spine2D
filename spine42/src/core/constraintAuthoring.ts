import { cloneSpineDocument, type SpineConstraint, type SpineDocument } from './spineDocument.ts';

export type ConstraintKind='ik'|'transform'|'path';
export type ConstraintFieldType='number'|'boolean'|'enum';
export type ConstraintSetupValue=number|boolean|string;
export interface ConstraintFieldSpec { key:string; label:string; type:ConstraintFieldType; defaultValue:ConstraintSetupValue; enumValues?:readonly string[]; min?:number; }
export interface ConstraintSetupEditResult { kind:ConstraintKind; name:string; index:number; before:SpineConstraint; after:SpineConstraint; changedProperties:string[]; effectiveBefore:Record<string,ConstraintSetupValue>; effectiveAfter:Record<string,ConstraintSetupValue>; }

const IK_FIELDS:ConstraintFieldSpec[]=[
  {key:'mix',label:'Mix',type:'number',defaultValue:1},
  {key:'softness',label:'Softness',type:'number',defaultValue:0,min:0},
  {key:'bendPositive',label:'Bend Positive',type:'boolean',defaultValue:true},
  {key:'compress',label:'Compress',type:'boolean',defaultValue:false},
  {key:'stretch',label:'Stretch',type:'boolean',defaultValue:false},
  {key:'uniform',label:'Uniform',type:'boolean',defaultValue:false},
];
const TRANSFORM_FIELDS:ConstraintFieldSpec[]=[
  {key:'local',label:'Local',type:'boolean',defaultValue:false},
  {key:'relative',label:'Relative',type:'boolean',defaultValue:false},
  {key:'rotation',label:'Rotation',type:'number',defaultValue:0},
  {key:'x',label:'X',type:'number',defaultValue:0},
  {key:'y',label:'Y',type:'number',defaultValue:0},
  {key:'scaleX',label:'Scale X',type:'number',defaultValue:0},
  {key:'scaleY',label:'Scale Y',type:'number',defaultValue:0},
  {key:'shearY',label:'Shear Y',type:'number',defaultValue:0},
  {key:'mixRotate',label:'Mix Rotate',type:'number',defaultValue:1},
  {key:'mixX',label:'Mix X',type:'number',defaultValue:1},
  {key:'mixY',label:'Mix Y',type:'number',defaultValue:1},
  {key:'mixScaleX',label:'Mix Scale X',type:'number',defaultValue:1},
  {key:'mixScaleY',label:'Mix Scale Y',type:'number',defaultValue:1},
  {key:'mixShearY',label:'Mix Shear Y',type:'number',defaultValue:1},
];
const PATH_FIELDS:ConstraintFieldSpec[]=[
  {key:'positionMode',label:'Position Mode',type:'enum',defaultValue:'percent',enumValues:['fixed','percent']},
  {key:'spacingMode',label:'Spacing Mode',type:'enum',defaultValue:'length',enumValues:['length','fixed','percent','proportional']},
  {key:'rotateMode',label:'Rotate Mode',type:'enum',defaultValue:'tangent',enumValues:['tangent','chain','chainScale']},
  {key:'rotation',label:'Rotation',type:'number',defaultValue:0},
  {key:'position',label:'Position',type:'number',defaultValue:0},
  {key:'spacing',label:'Spacing',type:'number',defaultValue:0},
  {key:'mixRotate',label:'Mix Rotate',type:'number',defaultValue:1},
  {key:'mixX',label:'Mix X',type:'number',defaultValue:1},
  {key:'mixY',label:'Mix Y',type:'number',defaultValue:1},
];
export const CONSTRAINT_SETUP_FIELDS:Readonly<Record<ConstraintKind,readonly ConstraintFieldSpec[]>>=Object.freeze({ik:IK_FIELDS,transform:TRANSFORM_FIELDS,path:PATH_FIELDS});

function own(object:object,key:string){return Object.prototype.hasOwnProperty.call(object,key);}
export function constraintList(raw:SpineDocument,kind:ConstraintKind):SpineConstraint[]{return (raw[kind]||[]) as SpineConstraint[];}
export function findConstraint(raw:SpineDocument,kind:ConstraintKind,name:string):{index:number;constraint:SpineConstraint}{const list=constraintList(raw,kind),index=list.findIndex(c=>String(c?.name||'')===String(name));if(index<0)throw new Error(`Constraint not found: ${kind}:${name}`);return{index,constraint:list[index]!};}
export function constraintFieldSpec(kind:ConstraintKind,key:string):ConstraintFieldSpec {const spec=CONSTRAINT_SETUP_FIELDS[kind]?.find(field=>field.key===key);if(!spec)throw new Error(`CONSTRAINT_SETUP_FIELD_BLOCKED: ${kind}.${key}`);return spec;}
export function effectiveConstraintValue(kind:ConstraintKind,constraint:SpineConstraint,key:string):ConstraintSetupValue {
  const spec=constraintFieldSpec(kind,key);if(own(constraint,key))return constraint[key] as ConstraintSetupValue;
  if(kind==='transform'&&key==='mixY')return Number(own(constraint,'mixX')?constraint.mixX:1);
  if(kind==='transform'&&key==='mixScaleY')return Number(own(constraint,'mixScaleX')?constraint.mixScaleX:1);
  if(kind==='path'&&key==='mixY')return Number(own(constraint,'mixX')?constraint.mixX:1);
  return spec.defaultValue;
}
export function effectiveConstraintValues(kind:ConstraintKind,constraint:SpineConstraint):Record<string,ConstraintSetupValue>{return Object.fromEntries(CONSTRAINT_SETUP_FIELDS[kind].map(spec=>[spec.key,effectiveConstraintValue(kind,constraint,spec.key)]));}
function normalizeEnum(spec:ConstraintFieldSpec,value:unknown):string{const raw=String(value??''),match=spec.enumValues?.find(item=>item.toLowerCase()===raw.toLowerCase());if(!match)throw new Error(`INVALID_CONSTRAINT_ENUM: ${spec.key}=${raw}; expected ${(spec.enumValues||[]).join('|')}`);return match;}
export function normalizeConstraintSetupValue(kind:ConstraintKind,key:string,value:unknown):ConstraintSetupValue {const spec=constraintFieldSpec(kind,key);if(spec.type==='boolean'){if(typeof value!=='boolean')throw new Error(`INVALID_CONSTRAINT_BOOLEAN: ${kind}.${key}=${String(value)}`);return value;}if(spec.type==='enum')return normalizeEnum(spec,value);const n=Number(value);if(!Number.isFinite(n))throw new Error(`INVALID_CONSTRAINT_NUMBER: ${kind}.${key}=${String(value)}`);if(spec.min!==undefined&&n<spec.min)throw new Error(`CONSTRAINT_VALUE_BELOW_MIN: ${kind}.${key}=${n} < ${spec.min}`);return n;}
export function applyConstraintSetupValues(raw:SpineDocument,kind:ConstraintKind,name:string,values:Record<string,unknown>):{document:SpineDocument;result:ConstraintSetupEditResult}{
  if(!values||typeof values!=='object'||Array.isArray(values)||!Object.keys(values).length)throw new Error('CONSTRAINT_SETUP_VALUES_EMPTY');
  const {index,constraint}=findConstraint(raw,kind,name),before=structuredClone(constraint),effectiveBefore=effectiveConstraintValues(kind,constraint),after=structuredClone(constraint),changedProperties:string[]=[];
  for(const [key,input] of Object.entries(values)){const normalized=normalizeConstraintSetupValue(kind,key,input),current=effectiveConstraintValue(kind,after,key);if(Object.is(current,normalized))continue;(after as any)[key]=normalized;changedProperties.push(key);}
  const document=cloneSpineDocument(raw),list=constraintList(document,kind);list[index]=after;const effectiveAfter=effectiveConstraintValues(kind,after);
  return{document,result:{kind,name,index,before,after,changedProperties:changedProperties.sort(),effectiveBefore,effectiveAfter}};
}
