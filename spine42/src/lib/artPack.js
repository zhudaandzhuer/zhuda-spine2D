import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { PNG } from 'pngjs';
import { inferSemanticRig, semanticLandmarks } from './semanticRig.js';
import { samplePose } from './poseOps.js';

function ensureDir(p){ fs.mkdirSync(p,{recursive:true}); }
function finitePoint(p){ return Array.isArray(p)&&p.length>=2&&Number.isFinite(Number(p[0]))&&Number.isFinite(Number(p[1])); }
function atlasPageNames(text){
  const lines=String(text||'').replace(/\r/g,'').split('\n'),out=[];
  for(let i=0;i<lines.length-1;i++){
    const name=lines[i].trim(),next=lines[i+1]?.trim()||'',prev=i?lines[i-1].trim():'';
    if(name && (!prev || i===0) && /^size\s*:/.test(next)) out.push(name);
  }
  return [...new Set(out)];
}
function getDefaultSkin(raw){
  if(Array.isArray(raw?.skins)){
    let s=raw.skins.find(x=>x?.name==='default');
    if(!s){s={name:'default',attachments:{}};raw.skins.push(s);}
    s.attachments ||= {}; return s;
  }
  raw.skins ||= {}; raw.skins.default ||= {}; return {attachments:raw.skins.default};
}
function boneMap(raw){ return new Map((raw?.bones||[]).map((b,i)=>[b.name,{...b,index:i}])); }
function normalizeAngle(v){let x=Number(v)||0;while(x>180)x-=360;while(x<=-180)x+=360;return x;}
function localAngleForWorld(parentWorld,worldRotation){
  const r=Number(worldRotation||0)*Math.PI/180,vx=Math.cos(r),vy=Math.sin(r),det=parentWorld.a*parentWorld.d-parentWorld.b*parentWorld.c;
  if(Math.abs(det)<1e-10) throw new Error('Singular parent matrix for rig template');
  const lx=(parentWorld.d*vx-parentWorld.b*vy)/det,ly=(-parentWorld.c*vx+parentWorld.a*vy)/det;
  return Math.atan2(ly,lx)*180/Math.PI;
}
export function captureSemanticRigTemplate(raw,atlasText,definitions=[]){
  const rig=inferSemanticRig(raw),setup=samplePose(raw,atlasText,{animationName:'',time:0}),landmarks=semanticLandmarks(rig,setup),rawBy=boneMap(raw),poseBy=new Map((setup.bones||[]).map(b=>[b.name,b]));
  const sourceScale=Number(landmarks.metrics?.torso||1)||1,bones=[];
  for(const def of definitions||[]){
    const rec=rawBy.get(def.name),bp=poseBy.get(def.name);if(!rec||!bp)throw new Error(`Rig template source bone missing: ${def.name}`);
    if(def.parentRole){
      const parentBone=rig.roles?.[def.parentRole]?.bone,parentPose=poseBy.get(parentBone);if(!parentBone||!parentPose)throw new Error(`Rig template parentRole missing: ${def.parentRole}`);
      bones.push({name:def.name,parentRole:def.parentRole,anchorRole:def.anchorRole||null,length:Number(rec.length||0),rotationOffset:normalizeAngle(bp.world.rotationX-parentPose.world.rotationX),scaleX:Number(rec.scaleX??1),scaleY:Number(rec.scaleY??1)});
    } else {
      const parent=def.parent||rec.parent,parentRec=rawBy.get(parent);if(!parent||!parentRec)throw new Error(`Rig template parent missing: ${def.name}`);
      const parentLen=Number(parentRec.length||1)||1;
      bones.push({name:def.name,parent,length:Number(rec.length||0),xRatio:Number(rec.x||0)/parentLen,yScale:Number(rec.y||0)/sourceScale,localRotation:Number(rec.rotation||0),scaleX:Number(rec.scaleX??1),scaleY:Number(rec.scaleY??1)});
    }
  }
  return {format:'zhuda-semantic-rig-template',version:1,sourceScale,bones};
}
function installSemanticRigTemplate(raw,template,baseRig,baseSetup,baseLandmarks){
  if(!template)return {installed:[],scaleRatio:1};
  if(template.format!=='zhuda-semantic-rig-template'||Number(template.version)!==1)throw new Error('Unsupported semantic rig template');
  const sourceScale=Number(template.sourceScale||1)||1,targetScale=Number(baseLandmarks.metrics?.torso||sourceScale)||sourceScale,ratio=targetScale/sourceScale;
  const poseBy=new Map((baseSetup.bones||[]).map(b=>[b.name,b])),existing=new Map((raw.bones||[]).map(b=>[b.name,b])),installed=[];
  raw.bones ||= [];
  for(const spec of template.bones||[]){
    if(existing.has(spec.name)){installed.push({name:spec.name,existing:true});continue;}
    let rec;
    if(spec.parentRole){
      const parent=baseRig.roles?.[spec.parentRole]?.bone,pp=poseBy.get(parent)?.world,anchor=baseLandmarks.joints?.[spec.anchorRole];
      if(!parent||!pp||!anchor)throw new Error(`Cannot install rig root ${spec.name}: parentRole/anchorRole unresolved`);
      const local=invWorld(pp,{x:anchor.x,y:anchor.y}),desiredWorldRotation=pp.rotationX+Number(spec.rotationOffset||0);
      rec={name:spec.name,parent,length:Number(spec.length||0)*ratio,x:local.x,y:local.y,rotation:localAngleForWorld(pp,desiredWorldRotation),scaleX:Number(spec.scaleX??1),scaleY:Number(spec.scaleY??1)};
    } else {
      const parent=existing.get(spec.parent);if(!parent)throw new Error(`Cannot install rig child ${spec.name}: parent ${spec.parent} missing`);
      rec={name:spec.name,parent:spec.parent,length:Number(spec.length||0)*ratio,x:Number(parent.length||0)*Number(spec.xRatio??1),y:Number(spec.yScale||0)*targetScale,rotation:Number(spec.localRotation||0),scaleX:Number(spec.scaleX??1),scaleY:Number(spec.scaleY??1)};
    }
    if(Math.abs((rec.scaleX??1)-1)<1e-9)delete rec.scaleX;if(Math.abs((rec.scaleY??1)-1)<1e-9)delete rec.scaleY;if(Math.abs(rec.y||0)<1e-9)rec.y=0;
    raw.bones.push(rec);existing.set(rec.name,rec);installed.push({name:rec.name,existing:false,parent:rec.parent,length:rec.length});
  }
  return {installed,scaleRatio:ratio,targetScale,sourceScale};
}
function invWorld(world,p){
  const dx=p.x-world.x,dy=p.y-world.y,det=world.a*world.d-world.b*world.c;
  if(Math.abs(det)<1e-10) throw new Error('Singular setup bone matrix');
  return {x:(dx*world.d-dy*world.b)/det,y:(dy*world.a-dx*world.c)/det};
}
function pmaWrite(src,dst,inputPma=false){
  const png=PNG.sync.read(fs.readFileSync(src));
  if(inputPma){fs.copyFileSync(src,dst);return {width:png.width,height:png.height};}
  for(let i=0;i<png.data.length;i+=4){const a=png.data[i+3]/255;png.data[i]=Math.round(png.data[i]*a);png.data[i+1]=Math.round(png.data[i+1]*a);png.data[i+2]=Math.round(png.data[i+2]*a);}
  fs.writeFileSync(dst,PNG.sync.write(png)); return {width:png.width,height:png.height};
}
function imageSize(src){const p=PNG.sync.read(fs.readFileSync(src));return {width:p.width,height:p.height};}
function segmentBasis(A,B){
  const dx=Number(B[0])-Number(A[0]),dy=-(Number(B[1])-Number(A[1])),len=Math.hypot(dx,dy);
  if(len<1e-8) throw new Error('Art pack source segment has zero length');
  return {ux:dx/len,uy:dy/len,vx:-dy/len,vy:dx/len,len};
}
function targetEnd(rawByBone,poseByBone,landmarks,part,startRole){
  if(part.endMode==='bone-tip'){
    const bone=landmarks.joints[startRole]?.bone,pr=poseByBone.get(bone)?.world,rb=rawByBone.get(bone);
    if(!pr||!rb) throw new Error(`Cannot resolve bone-tip for ${startRole}`);
    const len=Number(rb.length||0);return {x:pr.x+pr.a*len,y:pr.y+pr.c*len,bone};
  }
  const endRole=part.endRole;if(!endRole) throw new Error(`Part ${part.attachment} requires endRole or endMode=bone-tip`);
  const p=landmarks.joints[endRole];if(!p) throw new Error(`Semantic role missing: ${endRole}`);return {x:p.x,y:p.y,bone:p.bone};
}
function influencesFor(t,{profile='linear',prevBone=null,startBone,endBone}){
  const norm=a=>{const f=a.filter(([,w])=>w>1e-6),sum=f.reduce((s,[,w])=>s+w,0)||1;return f.map(([b,w])=>[b,w/sum]);};
  if(profile==='upper'){
    if(startBone===endBone||t<=.72)return [[startBone,1]];
    const w=Math.max(0,Math.min(1,(t-.72)/.38));return norm([[startBone,1-w],[endBone,w]]);
  }
  if(profile==='middle'){
    if(t<.18&&prevBone){const w=Math.max(0,Math.min(1,(t+.08)/.26));return norm([[prevBone,1-w],[startBone,w]]);}
    if(t>.82&&endBone&&endBone!==startBone){const w=Math.max(0,Math.min(1,(t-.82)/.26));return norm([[startBone,1-w],[endBone,w]]);}
    return [[startBone,1]];
  }
  if(profile==='terminal'){
    if(t<.20&&prevBone){const w=Math.max(0,Math.min(1,(t+.08)/.28));return norm([[prevBone,1-w],[startBone,w]]);}
    return [[startBone,1]];
  }
  if(startBone===endBone)return [[startBone,1]];
  if(t<=.15)return [[startBone,1]];if(t>=.85)return [[endBone,1]];const w=(t-.15)/.70;return [[startBone,1-w],[endBone,w]];
}
function attachmentFromRaw(raw,slotName,attachmentName){
  if(Array.isArray(raw?.skins)){
    for(const skin of raw.skins){const a=skin?.attachments?.[slotName]?.[attachmentName];if(a)return a;}
  } else {
    for(const skin of Object.values(raw?.skins||{})){const a=skin?.[slotName]?.[attachmentName];if(a)return a;}
  }
  return null;
}
export function captureWeightedMeshTemplate(raw,slotName,attachmentName,{regionUVs=null}={}){
  const att=attachmentFromRaw(raw,slotName,attachmentName);if(!att||att.type!=='mesh')throw new Error(`Weighted mesh attachment missing: ${slotName}/${attachmentName}`);
  const verts=att.vertices||[],vertexCount=Math.floor((att.uvs||[]).length/2),bones=raw?.bones||[];let i=0;const out=[];
  for(let v=0;v<vertexCount;v++){
    const n=Number(verts[i++]);if(!Number.isInteger(n)||n<1)throw new Error(`Unweighted/invalid mesh vertex in ${slotName}/${attachmentName}`);
    const inf=[];for(let k=0;k<n;k++){const bi=Number(verts[i++]),x=Number(verts[i++]),y=Number(verts[i++]),weight=Number(verts[i++]),bone=bones[bi]?.name;if(!bone)throw new Error(`Mesh bone index ${bi} invalid in ${slotName}/${attachmentName}`);inf.push({bone,x,y,weight});}out.push(inf);
  }
  if(i!==verts.length)throw new Error(`Mesh vertex packing mismatch in ${slotName}/${attachmentName}: ${i}/${verts.length}`);
  const uvs=regionUVs?Array.from(regionUVs,Number):[...(att.uvs||[])];
  if(uvs.length!==(att.uvs||[]).length)throw new Error(`regionUV length mismatch: ${slotName}/${attachmentName}`);
  return {format:'zhuda-weighted-mesh-template',version:1,uvs,triangles:[...(att.triangles||[])],vertices:out,width:Number(att.width||0),height:Number(att.height||0)};
}
function buildMeshFromTemplate(raw,part,template,scaleRatio=1){
  if(template?.format!=='zhuda-weighted-mesh-template'||Number(template.version)!==1)throw new Error(`Invalid meshTemplate: ${part.attachment}`);
  const indices=new Map((raw?.bones||[]).map((b,i)=>[b.name,i])),packed=[];
  for(const inf of template.vertices||[]){packed.push(inf.length);for(const x of inf){const bi=indices.get(x.bone);if(bi==null)throw new Error(`meshTemplate bone missing in target: ${x.bone}`);packed.push(bi,Number(x.x)*scaleRatio,Number(x.y)*scaleRatio,Number(x.weight));}}
  return {type:'mesh',path:part.attachment,uvs:[...(template.uvs||[])],triangles:[...(template.triangles||[])],vertices:packed,width:Number(template.width||0),height:Number(template.height||0)};
}
function buildMesh(raw,pose,landmarks,part,img){
  if(!finitePoint(part.sourceStart)||!finitePoint(part.sourceEnd)) throw new Error(`Invalid sourceStart/sourceEnd: ${part.attachment}`);
  const start=landmarks.joints[part.startRole];if(!start) throw new Error(`Semantic role missing: ${part.startRole}`);
  const rawByBone=boneMap(raw),poseByBone=new Map((pose.bones||[]).map(b=>[b.name,b]));
  const end=targetEnd(rawByBone,poseByBone,landmarks,part,part.startRole),startBone=start.bone,endBone=end.bone,prevBone=part.prevRole?landmarks.joints[part.prevRole]?.bone:null;
  if(part.prevRole&&!prevBone)throw new Error(`Semantic role missing: ${part.prevRole}`);
  const sb=segmentBasis(part.sourceStart,part.sourceEnd),tx=end.x-start.x,ty=end.y-start.y,tlen=Math.hypot(tx,ty);
  if(tlen<1e-8) throw new Error(`Target segment has zero length: ${part.attachment}`);
  const tux=tx/tlen,tuy=ty/tlen,tvx=-tuy,tvy=tux,baseScale=tlen/sb.len;
  const lengthScale=Number(part.lengthScale??1),thicknessScale=Number(part.thicknessScale??1),thicknessWorldScale=Number.isFinite(Number(part.thicknessWorldScale))?Number(part.thicknessWorldScale):null;
  const cols=Math.max(2,Number(part.grid?.[0]||5)),rows=Math.max(2,Number(part.grid?.[1]||5));
  const uvs=[],vertices=[],triangles=[];
  for(let ry=0;ry<rows;ry++){
    const v=ry/(rows-1);
    for(let cx=0;cx<cols;cx++){
      const u=cx/(cols-1),px=u*img.width,py=v*img.height,qx=px-Number(part.sourceStart[0]),qy=-(py-Number(part.sourceStart[1]));
      const along=qx*sb.ux+qy*sb.uy,perp=qx*sb.vx+qy*sb.vy;
      const crossScale=thicknessWorldScale??(baseScale*thicknessScale);
      const world={x:start.x+tux*along*baseScale*lengthScale+tvx*perp*crossScale,y:start.y+tuy*along*baseScale*lengthScale+tvy*perp*crossScale};
      const t=along/sb.len,inf=influencesFor(t,{profile:part.weightProfile||'linear',prevBone,startBone,endBone});uvs.push(u,v);vertices.push(inf.length);
      for(const [bone,w] of inf){const pb=poseByBone.get(bone)?.world;if(!pb)throw new Error(`Pose bone missing: ${bone}`);const local=invWorld(pb,world);vertices.push(rawByBone.get(bone).index,local.x,local.y,w);}
    }
  }
  for(let y=0;y<rows-1;y++)for(let x=0;x<cols-1;x++){const a=y*cols+x,b=a+1,c=a+cols,d=c+1;triangles.push(a,b,d,d,c,a);}
  return {type:'mesh',path:part.attachment,uvs,triangles,vertices,width:img.width,height:img.height};
}
function insertSlot(raw,slot,bone){
  if((raw.slots||[]).some(s=>s.name===slot.name)) return {existing:true};
  const rec={name:slot.name,bone},slots=raw.slots||(raw.slots=[]);
  let index=slots.length;
  if(slot.before){const i=slots.findIndex(s=>s.name===slot.before);if(i>=0)index=i;}
  else if(slot.after){const i=slots.findIndex(s=>s.name===slot.after);if(i>=0)index=i+1;}
  slots.splice(index,0,rec);return {existing:false,index};
}
function appendAtlasPage(atlasText,page,width,height,region){
  const clean=String(atlasText||'').replace(/\s+$/,'');
  return `${clean}\n\n${page}\nsize:${width},${height}\nfilter:Linear,Linear\npma:true\n${region}\nbounds:0,0,${width},${height}\n`;
}
// Immutable source-preserving preparation: copy RGB, intersect alpha with an approved mask.
// Rectangles are [x,y,width,height] in the source canvas; masks may match that canvas or the crop.
export function prepareArtSource(part,manifestDir,outputDir,index=0){
  const source=path.resolve(manifestDir,String(part.image||''));
  if(!part.maskImage&&!part.sourceRect)return {image:source,derivation:null};
  if(part.inputPma)throw new Error('Masked/cropped source must use straight alpha (inputPma=false)');
  const bytes=fs.readFileSync(source),input=PNG.sync.read(bytes),rect=part.sourceRect||[0,0,input.width,input.height];
  if(!Array.isArray(rect)||rect.length!==4||!rect.every(Number.isInteger))throw new Error('sourceRect must be [x,y,width,height] integers');
  const [x,y,width,height]=rect;
  if(x<0||y<0||width<1||height<1||x+width>input.width||y+height>input.height)throw new Error('sourceRect lies outside source image');
  const channel=part.maskChannel||'red';
  if(!['red','alpha'].includes(channel))throw new Error('maskChannel must be red or alpha');
  const maskPath=part.maskImage?path.resolve(manifestDir,part.maskImage):null,maskBytes=maskPath?fs.readFileSync(maskPath):null,mask=maskBytes?PNG.sync.read(maskBytes):null;
  const fullMask=mask&&mask.width===input.width&&mask.height===input.height;
  if(mask&&!fullMask&&(mask.width!==width||mask.height!==height))throw new Error('Mask dimensions must match source canvas or sourceRect');
  const output=new PNG({width,height});
  for(let oy=0;oy<height;oy++)for(let ox=0;ox<width;ox++){
    const si=((y+oy)*input.width+x+ox)*4,di=(oy*width+ox)*4;
    output.data[di]=input.data[si];output.data[di+1]=input.data[si+1];output.data[di+2]=input.data[si+2];
    let alpha=input.data[si+3];
    if(mask){const mi=((fullMask?y+oy:oy)*mask.width+(fullMask?x+ox:ox))*4;const coverage=mask.data[mi+(channel==='alpha'?3:0)];alpha=Math.min(alpha,part.maskInvert?255-coverage:coverage);}
    output.data[di+3]=alpha;
  }
  ensureDir(outputDir);const image=path.join(outputDir,`source-preserved-${index}.png`);
  fs.writeFileSync(image,PNG.sync.write(output));
  const sha=b=>createHash('sha256').update(b).digest('hex');
  const derivation={kind:'source-preserving-mask-crop/v1',source,sourceSha256:sha(bytes),maskImage:maskPath,maskSha256:maskBytes?sha(maskBytes):null,maskChannel:channel,maskInvert:!!part.maskInvert,sourceRect:rect,rgb:'source-exact',alpha:'intersection',image,sha256:sha(fs.readFileSync(image))};
  fs.writeFileSync(path.join(outputDir,`source-preserved-${index}.json`),JSON.stringify(derivation,null,2)+'\n');
  return {image,derivation};
}

export function validateArtPack(manifest){
  const issues=[];if(manifest?.format!=='zhuda-spine-art-pack')issues.push('format must be zhuda-spine-art-pack');if(Number(manifest?.version)!==1)issues.push('version must be 1');
  if(!Array.isArray(manifest?.slots)||!manifest.slots.length)issues.push('slots are required');if(!Array.isArray(manifest?.parts)||!manifest.parts.length)issues.push('parts are required');
  const slotNames=new Set((manifest?.slots||[]).map(s=>s.name));
  for(const s of manifest?.slots||[]){if(!s?.name)issues.push('slot name is required');if(!s?.bone&&!s?.boneRole)issues.push(`slot ${s?.name||'<unnamed>'} requires bone or boneRole`);}
  if(manifest?.rigTemplate&&(manifest.rigTemplate.format!=='zhuda-semantic-rig-template'||Number(manifest.rigTemplate.version)!==1||!Array.isArray(manifest.rigTemplate.bones)))issues.push('rigTemplate is invalid');
  for(const p of manifest?.parts||[]){const region=p?.type==='region';if(!slotNames.has(p.slot))issues.push(`part slot not declared: ${p.slot}`);if(!p.attachment)issues.push('part attachment is required');if(!p.image)issues.push(`part image missing: ${p.attachment}`);if(!region&&!p.startRole&&!p.meshTemplate)issues.push(`part startRole missing: ${p.attachment}`);if(!region&&!p.meshTemplate&&(!finitePoint(p.sourceStart)||!finitePoint(p.sourceEnd)))issues.push(`part source segment invalid: ${p.attachment}`);}
  return {ok:!issues.length,issues};
}

export function applySemanticArtPack({raw,atlasText,jsonPath,atlasPath,manifest,manifestDir='.',outputDir}){
  const check=validateArtPack(manifest);if(!check.ok) throw new Error(check.issues.join('; '));if(!outputDir)throw new Error('outputDir is required');ensureDir(outputDir);
  const baseRig=inferSemanticRig(raw),baseSetup=samplePose(raw,atlasText,{animationName:'',time:0}),baseLandmarks=semanticLandmarks(baseRig,baseSetup);
  const rigTemplateReport=installSemanticRigTemplate(raw,manifest.rigTemplate,baseRig,baseSetup,baseLandmarks);
  const rig=inferSemanticRig(raw),setup=samplePose(raw,atlasText,{animationName:'',time:0}),landmarks=semanticLandmarks(rig,setup),skin=getDefaultSkin(raw);
  const copiedPages=[];for(const page of atlasPageNames(atlasText)){const src=path.resolve(path.dirname(atlasPath),page),dst=path.join(outputDir,page);if(!fs.existsSync(src))throw new Error(`Atlas page missing: ${src}`);ensureDir(path.dirname(dst));fs.copyFileSync(src,dst);copiedPages.push(page);}
  const slotReport=[];for(const s of manifest.slots){const directBone=String(s.bone||'').trim(),role=directBone?null:rig.roles?.[s.boneRole],bone=directBone||String(role?.bone||'');if(!bone)throw new Error(`Slot ${s.name}: semantic boneRole missing ${s.boneRole}`);if(!(raw.bones||[]).some(b=>b.name===bone))throw new Error(`Slot ${s.name}: bone missing ${bone}`);slotReport.push({name:s.name,bone,...insertSlot(raw,s,bone)});}
  let outAtlas=atlasText;const parts=[];
  for(const part of manifest.parts){const prepared=prepareArtSource(part,manifestDir,outputDir,parts.length),src=prepared.image;if(!fs.existsSync(src))throw new Error(`Art image not found: ${src}`);const img=imageSize(src),attachment=part.type==='region'?{type:'region',path:part.attachment,x:Number(part.x||0),y:Number(part.y||0),rotation:Number(part.rotation||0),scaleX:Number(part.scaleX??1),scaleY:Number(part.scaleY??1),width:Number(part.width||img.width),height:Number(part.height||img.height)}:(part.meshTemplate?buildMeshFromTemplate(raw,part,part.meshTemplate,rigTemplateReport.scaleRatio||1):buildMesh(raw,setup,landmarks,part,img));skin.attachments[part.slot] ||= {};skin.attachments[part.slot][part.attachment]=attachment;const setupSlot=(raw.slots||[]).find(s=>s.name===part.slot);if(setupSlot&&!setupSlot.attachment)setupSlot.attachment=part.attachment;
    const page=`${part.attachment}.png`,dst=path.join(outputDir,page);pmaWrite(src,dst,!!part.inputPma);outAtlas=appendAtlasPage(outAtlas,page,img.width,img.height,part.attachment);parts.push({slot:part.slot,attachment:part.attachment,type:part.type==='region'?'region':'mesh',image:src,derivation:prepared.derivation,page,width:img.width,height:img.height,startRole:part.startRole,prevRole:part.prevRole||null,endRole:part.endRole||null,endMode:part.endMode||null,weightProfile:part.weightProfile||'linear',thicknessWorldScale:part.thicknessWorldScale??null});}
  const outJson=path.join(outputDir,path.basename(jsonPath)),outAtlasPath=path.join(outputDir,path.basename(atlasPath));fs.writeFileSync(outJson,JSON.stringify(raw));fs.writeFileSync(outAtlasPath,outAtlas);
  return {format:'zhuda-art-pack-report',version:1,semanticRig:rig,rigTemplate:rigTemplateReport,slots:slotReport,parts,copiedPages,outJson,outAtlas:outAtlasPath};
}
