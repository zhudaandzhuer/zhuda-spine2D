import fs from 'node:fs';
import path from 'node:path';
import { PNG } from 'pngjs';
import { TextureAtlas, AtlasAttachmentLoader, SkeletonJson } from '@esotericsoftware/spine-webgl';
import { inferSemanticRig } from './semanticRig.js';
import { captureReferenceMotion } from './motionRetarget.js';
import { captureSemanticRigTemplate, captureWeightedMeshTemplate } from './artPack.js';

const ROLE_ORDER=['R_shoulder','R_elbow','R_wrist','L_shoulder','L_elbow','L_wrist','R_hip','R_knee','R_ankle','L_hip','L_knee','L_ankle'];
const ROOT_DEFS=[
 ['R_shoulder','chest'],['L_shoulder','chest'],['R_hip','pelvis'],['L_hip','pelvis'],
];
const CHILD_PAIRS=[
 ['R_elbow','R_shoulder'],['R_wrist','R_elbow'],['L_elbow','L_shoulder'],['L_wrist','L_elbow'],
 ['R_knee','R_hip'],['R_ankle','R_knee'],['L_knee','L_hip'],['L_ankle','L_knee'],
];
function defaultSkinRaw(raw){
  if(Array.isArray(raw?.skins))return raw.skins.find(s=>s?.name==='default')||raw.skins[0];
  return {name:'default',attachments:raw?.skins?.default||{}};
}
function safeName(s){return String(s).replace(/[^\p{L}\p{N}_.-]+/gu,'_').replace(/^_+|_+$/g,'')||'asset';}
function roleByBone(rig){
  const m=new Map();for(const role of ROLE_ORDER){const b=rig?.roles?.[role]?.bone;if(b&&!m.has(b))m.set(b,role);}return m;
}
function usedAttachmentNames(motion){
  const out=new Map();for(const f of motion?.frames||[]){for(const [slot,name] of Object.entries(f?.pose?.visualState?.slots||{})){if(name==null)continue;if(!out.has(slot))out.set(slot,new Set());out.get(slot).add(name);}}return out;
}
function slotInsertion(sourceSlots,selected,name){
  const i=sourceSlots.findIndex(s=>s.name===name);for(let j=i+1;j<sourceSlots.length;j++)if(!selected.has(sourceSlots[j].name))return {before:sourceSlots[j].name};
  for(let j=i-1;j>=0;j--)if(!selected.has(sourceSlots[j].name))return {after:sourceSlots[j].name};return {};
}
function boneDefinitions(raw,rig){
  const by=new Map((raw?.bones||[]).map(b=>[b.name,b])),defs=[];
  for(const [role,parentRole] of ROOT_DEFS){const name=rig?.roles?.[role]?.bone;if(!name)throw new Error(`Semantic role missing for pack capture: ${role}`);defs.push({name,parentRole,anchorRole:role});}
  for(const [role,parentRoleName] of CHILD_PAIRS){
    const name=rig?.roles?.[role]?.bone,parent=rig?.roles?.[parentRoleName]?.bone;if(!name||!parent)throw new Error(`Semantic role missing for pack capture: ${role}`);
    if(by.get(name)?.parent!==parent)throw new Error(`motion-pack-capture v1 requires direct semantic chain: ${name} parent=${by.get(name)?.parent}, expected ${parent}`);
    defs.push({name,parent});
  }
  return defs;
}
function readPng(file){return PNG.sync.read(fs.readFileSync(file));}
function rotateCanonical(src,degrees){
  degrees=((Number(degrees)||0)%360+360)%360;if(degrees===0)return src;
  const out=(degrees===90||degrees===270)?new PNG({width:src.height,height:src.width}):new PNG({width:src.width,height:src.height});
  for(let y=0;y<src.height;y++)for(let x=0;x<src.width;x++){
    let dx,dy;if(degrees===90){dx=src.height-1-y;dy=x;} // page stores CCW; recover by CW
    else if(degrees===270){dx=y;dy=src.width-1-x;} // page stores CW; recover by CCW
    else {dx=src.width-1-x;dy=src.height-1-y;}
    const si=(y*src.width+x)*4,di=(dy*out.width+dx)*4;for(let c=0;c<4;c++)out.data[di+c]=src.data[si+c];
  }return out;
}
function cropPng(page,x,y,w,h){
  const out=new PNG({width:w,height:h});for(let yy=0;yy<h;yy++)for(let xx=0;xx<w;xx++){const si=((y+yy)*page.width+x+xx)*4,di=(yy*w+xx)*4;for(let c=0;c<4;c++)out.data[di+c]=page.data[si+c];}return out;
}
function unpremultiply(im){
  for(let i=0;i<im.data.length;i+=4){const a=im.data[i+3];if(!a){im.data[i]=im.data[i+1]=im.data[i+2]=0;continue;}if(a<255){im.data[i]=Math.min(255,Math.round(im.data[i]*255/a));im.data[i+1]=Math.min(255,Math.round(im.data[i+1]*255/a));im.data[i+2]=Math.min(255,Math.round(im.data[i+2]*255/a));}}return im;
}
export function extractAtlasRegionImage(atlas,atlasPath,regionName,outFile,{preservePma=true}={}){
  const region=atlas.findRegion(regionName);if(!region)throw new Error(`Atlas region not found: ${regionName}`);
  const pageFile=path.join(path.dirname(path.resolve(atlasPath)),region.page.name);if(!fs.existsSync(pageFile))throw new Error(`Atlas page missing: ${pageFile}`);
  const page=readPng(pageFile),rot=Number(region.degrees)||0,physW=(rot===90||rot===270)?region.height:region.width,physH=(rot===90||rot===270)?region.width:region.height;
  let crop=rotateCanonical(cropPng(page,region.x,region.y,physW,physH),rot);if(region.page.pma&&!preservePma)crop=unpremultiply(crop);
  const ow=region.originalWidth||region.width,oh=region.originalHeight||region.height,canvas=new PNG({width:ow,height:oh});
  const px=Math.round(region.offsetX||0),py=Math.round(oh-(region.offsetY||0)-region.height);
  for(let y=0;y<crop.height;y++)for(let x=0;x<crop.width;x++){const dx=px+x,dy=py+y;if(dx<0||dy<0||dx>=canvas.width||dy>=canvas.height)continue;const si=(y*crop.width+x)*4,di=(dy*canvas.width+dx)*4;for(let c=0;c<4;c++)canvas.data[di+c]=crop.data[si+c];}
  fs.mkdirSync(path.dirname(outFile),{recursive:true});fs.writeFileSync(outFile,PNG.sync.write(canvas));return {file:outFile,region:region.name,page:region.page.name,degrees:rot,width:ow,height:oh,pma:!!region.page.pma,pixelsPma:!!region.page.pma&&preservePma};
}

export function captureMotionPack({raw,atlasText,jsonPath,atlasPath,animationName,outDir,frames=13,label=null}={}){
  if(!raw||!atlasText||!jsonPath||!atlasPath||!animationName||!outDir)throw new Error('captureMotionPack requires raw, atlasText, jsonPath, atlasPath, animationName, outDir');
  fs.mkdirSync(outDir,{recursive:true});const assetDir=path.join(outDir,'assets');fs.mkdirSync(assetDir,{recursive:true});
  const rig=inferSemanticRig(raw),motion=captureReferenceMotion(raw,atlasText,{animationName,frames,label:label||animationName,semanticRig:rig}),used=usedAttachmentNames(motion),roleBones=roleByBone(rig),sourceSlots=raw.slots||[],skin=defaultSkinRaw(raw),atlas=new TextureAtlas(atlasText),data=new SkeletonJson(new AtlasAttachmentLoader(atlas)).readSkeletonData(raw);
  const candidates=[];
  for(const slot of sourceSlots){const role=roleBones.get(slot.bone),names=used.get(slot.name);if(!role||!names?.size)continue;const slotIndex=data.findSlot(slot.name)?.index;if(slotIndex==null)continue;for(const attachment of names){const rawAtt=skin?.attachments?.[slot.name]?.[attachment];const runtimeAtt=data.defaultSkin?.getAttachment?.(slotIndex,attachment);if(!rawAtt||rawAtt.type!=='mesh'||!runtimeAtt?.regionUVs)continue;candidates.push({slot:slot.name,boneRole:role,attachment,rawAtt,runtimeAtt});}}
  if(!candidates.length){atlas.dispose?.();throw new Error('No visible semantic weighted-mesh limb attachments found. motion-pack-capture v1 expects segmented weighted limb meshes.');}
  const selected=new Set(candidates.map(x=>x.slot)),slotSeen=new Set(),slots=[],parts=[];
  for(const x of candidates){if(!slotSeen.has(x.slot)){slots.push({name:x.slot,boneRole:x.boneRole,...slotInsertion(sourceSlots,selected,x.slot)});slotSeen.add(x.slot);}
    const regionName=x.rawAtt.path||x.attachment,imgName=`${safeName(x.slot)}__${safeName(x.attachment)}.png`,imgPath=path.join(assetDir,imgName),extracted=extractAtlasRegionImage(atlas,atlasPath,regionName,imgPath,{preservePma:true});
    parts.push({slot:x.slot,attachment:x.attachment,image:path.posix.join('assets',imgName),inputPma:extracted.pixelsPma,meshTemplate:captureWeightedMeshTemplate(raw,x.slot,x.attachment,{regionUVs:x.runtimeAtt.regionUVs})});
  }
  const rigTemplate=captureSemanticRigTemplate(raw,atlasText,boneDefinitions(raw,rig)),manifest={format:'zhuda-spine-art-pack',version:1,name:`${label||animationName}-auto-art-pack`,rigTemplate,slots,parts};
  const manifestPath=path.join(outDir,'manifest.json'),motionPath=path.join(outDir,`${safeName(animationName)}.motion.json`);fs.writeFileSync(manifestPath,JSON.stringify(manifest,null,2)+'\n');fs.writeFileSync(motionPath,JSON.stringify(motion,null,2)+'\n');atlas.dispose?.();
  return {format:'zhuda-motion-pack-capture-report',version:1,animation:animationName,frames:motion.frames.length,semanticRoles:Object.fromEntries(ROLE_ORDER.map(r=>[r,rig.roles?.[r]?.bone||null])),slots:slots.length,parts:parts.length,rigBones:rigTemplate.bones.length,manifest:manifestPath,motion:motionPath,assetDir};
}
