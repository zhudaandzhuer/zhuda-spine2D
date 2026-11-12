import fs from 'node:fs';
import path from 'node:path';
import { PNG } from 'pngjs';
import { TextureAtlas, AtlasAttachmentLoader, SkeletonJson } from '@esotericsoftware/spine-webgl';
import { inferSemanticRig } from './semanticRig.js';
import { captureWeightedMeshTemplate } from './artPack.js';
import { extractAtlasRegionImage } from './motionPackCapture.js';

function defaultSkin(raw){return Array.isArray(raw?.skins)?(raw.skins.find(s=>s?.name==='default')||raw.skins[0]):{attachments:raw?.skins?.default||{}};}
function attachment(raw,slot,name){return defaultSkin(raw)?.attachments?.[slot]?.[name]||null;}
function parseWeightedVertices(raw,att){
  const bones=raw?.bones||[],v=att?.vertices||[],count=Math.floor((att?.uvs||[]).length/2),out=[];let i=0;
  for(let vi=0;vi<count;vi++){const n=Number(v[i++]),row=[];if(!Number.isInteger(n)||n<1)throw new Error('Expected weighted mesh');for(let k=0;k<n;k++){const bi=Number(v[i++]),x=Number(v[i++]),y=Number(v[i++]),weight=Number(v[i++]);row.push({bone:bones[bi]?.name,x,y,weight});}out.push(row);}if(i!==v.length)throw new Error(`Weighted vertex parse mismatch ${i}/${v.length}`);return out;
}
function meshBoneSet(raw,att){return new Set(parseWeightedVertices(raw,att).flatMap(r=>r.map(x=>x.bone)));}
function semanticChain(rig,side,kind){
  if(kind==='leg')return [rig.roles?.[`${side}_hip`]?.bone,rig.roles?.[`${side}_knee`]?.bone,rig.roles?.[`${side}_ankle`]?.bone];
  if(kind==='arm')return [rig.roles?.[`${side}_shoulder`]?.bone,rig.roles?.[`${side}_elbow`]?.bone,rig.roles?.[`${side}_wrist`]?.bone];
  return [];
}
function findMonolithicWeightedMesh(raw,rig,side,kind){
  const chain=semanticChain(rig,side,kind).filter(Boolean),skin=defaultSkin(raw),rows=[];
  for(const [slot,atts] of Object.entries(skin?.attachments||{}))for(const [name,a] of Object.entries(atts||{})){
    if(a?.type!=='mesh'||!Array.isArray(a.vertices))continue;let set;try{set=meshBoneSet(raw,a)}catch{continue}const hits=chain.filter(b=>set.has(b));if(hits.length>=2)rows.push({slot,name,att:a,hits,score:hits.length+(String(slot).toLowerCase().includes(kind==='leg'?'leg':'hand')?.25:0)});
  }
  rows.sort((a,b)=>b.score-a.score);return rows[0]||null;
}
function rasterAssignments(width,height,uvs,triangles,vertexWeights,coreBones){
  const labels=new Int16Array(width*height);labels.fill(-1);const scores=coreBones.map(()=>new Float32Array(width*height));
  const vw=vertexWeights.map(row=>coreBones.map(b=>row.filter(x=>x.bone===b).reduce((s,x)=>s+Number(x.weight||0),0)));
  const edge=(ax,ay,bx,by,px,py)=>(px-ax)*(by-ay)-(py-ay)*(bx-ax);
  for(let ti=0;ti<triangles.length;ti+=3){const ids=triangles.slice(ti,ti+3),p=ids.map(i=>({x:Number(uvs[i*2])*width,y:Number(uvs[i*2+1])*height})),area=edge(p[0].x,p[0].y,p[1].x,p[1].y,p[2].x,p[2].y);if(Math.abs(area)<1e-8)continue;
    const minX=Math.max(0,Math.floor(Math.min(...p.map(q=>q.x)))),maxX=Math.min(width-1,Math.ceil(Math.max(...p.map(q=>q.x)))),minY=Math.max(0,Math.floor(Math.min(...p.map(q=>q.y)))),maxY=Math.min(height-1,Math.ceil(Math.max(...p.map(q=>q.y))));
    for(let y=minY;y<=maxY;y++)for(let x=minX;x<=maxX;x++){const px=x+.5,py=y+.5,w0=edge(p[1].x,p[1].y,p[2].x,p[2].y,px,py)/area,w1=edge(p[2].x,p[2].y,p[0].x,p[0].y,px,py)/area,w2=1-w0-w1;if(w0<-.0001||w1<-.0001||w2<-.0001)continue;const idx=y*width+x;let best=-1,bestScore=-1;for(let s=0;s<coreBones.length;s++){const q=w0*vw[ids[0]][s]+w1*vw[ids[1]][s]+w2*vw[ids[2]][s];if(q>scores[s][idx])scores[s][idx]=q;if(q>bestScore){bestScore=q;best=s;}}if(best>=0)labels[idx]=best;}
  }
  return labels;
}

function mixedJointAnchor(weights,uvs,boneA,boneB,width,height){
  let sx=0,sy=0,sw=0;for(let i=0;i<weights.length;i++){const row=weights[i],a=row.filter(x=>x.bone===boneA).reduce((q,x)=>q+Number(x.weight||0),0),b=row.filter(x=>x.bone===boneB).reduce((q,x)=>q+Number(x.weight||0),0),w=a*b;if(w<=1e-8)continue;sx+=Number(uvs[i*2])*width*w;sy+=Number(uvs[i*2+1])*height*w;sw+=w;}if(sw)return [sx/sw,sy/sw];
  let best=null;for(let i=0;i<weights.length;i++)for(let j=0;j<weights.length;j++){const ai=weights[i].some(x=>x.bone===boneA),bj=weights[j].some(x=>x.bone===boneB);if(!ai||!bj)continue;const dx=(Number(uvs[i*2])-Number(uvs[j*2]))*width,dy=(Number(uvs[i*2+1])-Number(uvs[j*2+1]))*height,d=dx*dx+dy*dy;if(!best||d<best.d)best={d,x:(Number(uvs[i*2])+Number(uvs[j*2]))*.5*width,y:(Number(uvs[i*2+1])+Number(uvs[j*2+1]))*.5*height};}return best?[best.x,best.y]:null;
}

function writeSegmentImages(sourceFile,outDir,prefix,labels,count,{bleed=2}={}){
  const src=PNG.sync.read(fs.readFileSync(sourceFile)),files=[],W=src.width,H=src.height,N=W*H;
  for(let s=0;s<count;s++){let mask=new Uint8Array(N);for(let i=0;i<N;i++)if(labels[i]===s)mask[i]=1;
    for(let pass=0;pass<Math.max(0,Number(bleed)||0);pass++){const next=mask.slice();for(let y=1;y<H-1;y++)for(let x=1;x<W-1;x++){const i=y*W+x;if(mask[i]||src.data[i*4+3]===0)continue;let hit=false;for(let yy=-1;yy<=1&&!hit;yy++)for(let xx=-1;xx<=1;xx++)if(mask[(y+yy)*W+x+xx]){hit=true;break;}if(hit)next[i]=1;}mask=next;}
    const out=new PNG({width:W,height:H});for(let i=0;i<N;i++){const si=i*4;if(!mask[i])continue;out.data[si]=src.data[si];out.data[si+1]=src.data[si+1];out.data[si+2]=src.data[si+2];out.data[si+3]=src.data[si+3];}const f=path.join(outDir,`${prefix}_${s}.png`);fs.writeFileSync(f,PNG.sync.write(out));files.push(f);
  }return files;
}
function pngStats(file){const p=PNG.sync.read(fs.readFileSync(file));let n=0,minX=p.width,minY=p.height,maxX=-1,maxY=-1;for(let y=0;y<p.height;y++)for(let x=0;x<p.width;x++){const a=p.data[(y*p.width+x)*4+3];if(!a)continue;n++;if(x<minX)minX=x;if(y<minY)minY=y;if(x>maxX)maxX=x;if(y>maxY)maxY=y;}return {pixels:n,bbox:n?[minX,minY,maxX+1,maxY+1]:null};}
function slotPlacement(raw,sourceSlot,index,count){const slots=raw?.slots||[],i=slots.findIndex(s=>s.name===sourceSlot);if(i<0)return{};return index===0?{before:sourceSlot}:{after:`__PREV_${index-1}__`};}

export function decomposeMonolithicLimb({raw,atlasText,atlasPath,side,kind='leg',outputDir,semanticRig=inferSemanticRig(raw)}={}){
  if(!raw||!atlasText||!atlasPath||!side||!outputDir)throw new Error('decomposeMonolithicLimb missing arguments');fs.mkdirSync(outputDir,{recursive:true});
  const cand=findMonolithicWeightedMesh(raw,semanticRig,side,kind);if(!cand)throw new Error(`No monolithic weighted ${side} ${kind} mesh found`);const chain=semanticChain(semanticRig,side,kind);if(chain.some(x=>!x))throw new Error(`Incomplete semantic ${side} ${kind} chain`);
  const atlas=new TextureAtlas(atlasText),data=new SkeletonJson(new AtlasAttachmentLoader(atlas)).readSkeletonData(raw),slotIndex=data.findSlot(cand.slot)?.index,runtimeAtt=data.defaultSkin?.getAttachment(slotIndex,cand.name);if(!runtimeAtt?.regionUVs)throw new Error(`Runtime region UV missing: ${cand.slot}/${cand.name}`);
  const source=path.join(outputDir,`${side}_${kind}_source.png`),regionName=cand.att.path||cand.name;extractAtlasRegionImage(atlas,atlasPath,regionName,source,{preservePma:false});atlas.dispose?.();const png=PNG.sync.read(fs.readFileSync(source)),weights=parseWeightedVertices(raw,cand.att),uvs=Array.from(runtimeAtt.regionUVs,Number),labels=rasterAssignments(png.width,png.height,uvs,cand.att.triangles||[],weights,chain),names=kind==='leg'?['thigh','shin','foot']:['upper','fore','hand'],files=writeSegmentImages(source,outputDir,`${side}_${kind}`,labels,names.length),baseTemplate=captureWeightedMeshTemplate(raw,cand.slot,cand.name,{regionUVs:runtimeAtt.regionUVs});
  const parts=names.map((name,i)=>{const stats=pngStats(files[i]);return {name,side,kind,file:files[i],pixels:stats.pixels,bbox:stats.bbox,boneRole:kind==='leg'?[`${side}_hip`,`${side}_knee`,`${side}_ankle`][i]:[`${side}_shoulder`,`${side}_elbow`,`${side}_wrist`][i],meshTemplate:structuredClone(baseTemplate)}});
  const jointAnchors=kind==='leg'?{knee:mixedJointAnchor(weights,uvs,chain[0],chain[1],png.width,png.height),ankle:mixedJointAnchor(weights,uvs,chain[1],chain[2],png.width,png.height)}:{elbow:mixedJointAnchor(weights,uvs,chain[0],chain[1],png.width,png.height),wrist:mixedJointAnchor(weights,uvs,chain[1],chain[2],png.width,png.height)};
  return {side,kind,sourceSlot:cand.slot,sourceAttachment:cand.name,regionName,chain,source,pixels:{width:png.width,height:png.height},jointAnchors,parts};
}

export function buildDecomposedBaseArtPack({raw,atlasText,atlasPath,families=['L_leg','R_leg'],outputDir,name='auto-decomposed-base'}={}){
  fs.mkdirSync(outputDir,{recursive:true});const rig=inferSemanticRig(raw),decomposed=[],slots=[],parts=[];
  for(const family of families){const m=String(family).match(/^([LR])_(arm|leg)$/);if(!m)continue;const d=decomposeMonolithicLimb({raw,atlasText,atlasPath,side:m[1],kind:m[2],outputDir:path.join(outputDir,'assets'),semanticRig:rig});decomposed.push(d);let previous=null;for(const p of d.parts){const slot=`auto_${p.side}_${p.name}_base_slot`,attachment=`auto_${p.side}_${p.name}_base`;const rec={name:slot,boneRole:p.boneRole};if(previous)rec.after=previous;else rec.before=d.sourceSlot;slots.push(rec);previous=slot;parts.push({slot,attachment,image:path.relative(outputDir,p.file).split(path.sep).join('/'),inputPma:false,meshTemplate:p.meshTemplate,metadata:{viewCoverage:'base-only',sourceSlot:d.sourceSlot,segment:p.name}});}}
  const manifest={format:'zhuda-spine-art-pack',version:1,name,slots,parts,metadata:{kind:'decomposed-base',resolvesViewpointArt:false,decomposedFamilies:decomposed.map(d=>({family:`${d.side}_${d.kind}`,sourceSlot:d.sourceSlot,slots:d.parts.map(p=>`auto_${d.side}_${p.name}_base_slot`),attachments:d.parts.map(p=>`auto_${d.side}_${p.name}_base`)}))}};const manifestPath=path.join(outputDir,'manifest.json');fs.writeFileSync(manifestPath,JSON.stringify(manifest,null,2)+'\n');return{manifest,manifestPath,decomposed};
}
