import { validateSemanticMotionSpec } from './semanticMotionSpec.js';
const EPS=1e-5;
function finite(v){return Number.isFinite(Number(v));}
function framesFor(spec,op){
  const frames=spec.frames||[];
  if(op.index!==undefined){const i=Number(op.index);if(!Number.isInteger(i)||i<0||i>=frames.length)throw new Error(`Invalid frame index: ${op.index}`);return [frames[i]];}
  if(op.time!==undefined){const t=Number(op.time),f=frames.find(x=>Math.abs(Number(x.time)-t)<=EPS);if(!f)throw new Error(`No semantic frame at time ${t}`);return [f];}
  if(op.from!==undefined||op.to!==undefined){const a=op.from===undefined?-Infinity:Number(op.from),b=op.to===undefined?Infinity:Number(op.to);return frames.filter(f=>Number(f.time)>=a-EPS&&Number(f.time)<=b+EPS);}
  return frames;
}
function numberProps(obj,src,props,mode){for(const p of props)if(src[p]!==undefined){const v=Number(src[p]);if(!finite(v))throw new Error(`Invalid ${p}: ${src[p]}`);obj[p]=mode==='offset'?Number(obj[p]??(p.startsWith('scale')?1:0))+v:v;}}
export function applySemanticMotionEditPlan(spec,plan,{clone=true}={}){
  const out=clone?structuredClone(spec):spec,ops=plan?.operations;if(!Array.isArray(ops))throw new Error('Motion edit plan requires operations[]');const report=[];
  for(const op of ops){switch(op.op){
    case 'offset_joint':{if(!op.role)throw new Error('offset_joint requires role');const fs=framesFor(out,op);for(const f of fs){const j=f.joints?.[op.role];if(!j)throw new Error(`Joint ${op.role} missing at ${f.time}`);numberProps(j,op,['x','y','rotation','scaleX','scaleY'],'offset');}report.push({op:op.op,role:op.role,frames:fs.length});break;}
    case 'set_joint':{if(!op.role)throw new Error('set_joint requires role');const fs=framesFor(out,op);for(const f of fs){f.joints ||= {};f.joints[op.role] ||= {x:0,y:0};numberProps(f.joints[op.role],op,['x','y','rotation','scaleX','scaleY'],'set');}report.push({op:op.op,role:op.role,frames:fs.length});break;}
    case 'offset_root':{const fs=framesFor(out,op);for(const f of fs){f.root ||= {};numberProps(f.root,op,['x','y','rotation','scaleX','scaleY'],'offset');}report.push({op:op.op,frames:fs.length});break;}
    case 'set_root':{const fs=framesFor(out,op);for(const f of fs){f.root ||= {};numberProps(f.root,op,['x','y','rotation','scaleX','scaleY'],'set');}report.push({op:op.op,frames:fs.length});break;}
    case 'retime':{const factor=Number(op.factor);if(!finite(factor)||factor<=0)throw new Error('retime factor must be > 0');for(const f of out.frames||[])f.time=Number(f.time)*factor;out.duration=Number(out.duration)*factor;report.push({op:op.op,factor,duration:out.duration});break;}
    case 'rename':{if(!op.name)throw new Error('rename requires name');out.name=String(op.name);report.push({op:op.op,name:out.name});break;}
    default:throw new Error(`Unknown semantic motion edit op: ${op.op}`);
  }}
  const validation=validateSemanticMotionSpec(out);if(!validation.ok)throw new Error(validation.issues.join('; '));return {spec:out,report,validation};
}
