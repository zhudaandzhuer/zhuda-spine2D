import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {captureReferenceMotion} from '../src/lib/motionRetarget.js';
import {authorSemanticMotion} from '../src/lib/semanticMotionSpec.js';
import {compareSilhouettes} from '../src/lib/imageQa.js';
import {TextureAtlas,AtlasAttachmentLoader,SkeletonJson} from '@esotericsoftware/spine-webgl';
import {inferSemanticRig} from '../src/lib/semanticRig.js';
import {renderFrame} from './renderFrame.mjs';
import {optimizeSemanticPose} from './visualOptimizePose.mjs';

const DEFAULT_SERVER='http://127.0.0.1:4329/';
const DEFAULT_ROLES=['L_elbow','L_wrist','R_elbow','R_wrist','L_knee','L_ankle','R_knee','R_ankle'];
function deep(v){return structuredClone(v)}
async function alive(url){try{return(await fetch(url)).ok}catch{return false}}
async function ensureServer(root,url){if(await alive(url))return null;const u=new URL(url),proc=spawn(process.execPath,[path.join(root,'node_modules/vite/bin/vite.js'),'--host',u.hostname||'127.0.0.1','--port',u.port||'4329'],{cwd:root,stdio:'ignore'});for(let i=0;i<140&&!await alive(url);i++)await new Promise(r=>setTimeout(r,100));if(!await alive(url)){proc.kill('SIGTERM');throw new Error('Visual motion optimizer render server unavailable')}return proc}
function nearestFrame(frames,time){let best=-1,dist=Infinity;for(let i=0;i<(frames||[]).length;i++){const d=Math.abs(Number(frames[i].time)-Number(time));if(d<dist){dist=d;best=i}}if(best<0)throw new Error('No semantic frame available');return {index:best,frame:frames[best],distance:dist}}
function roleDelta(cur,ref,role){const a=cur?.joints?.[role],b=ref?.pose?.joints?.[role];if(!a||!b)return -1;return Math.hypot(Number(a.x)-Number(b.x),Number(a.y)-Number(b.y))}
function chooseRoles(specFrame,refFrame,{roles=null,maxRoles=2}={}){const pool=(Array.isArray(roles)&&roles.length?roles:DEFAULT_ROLES).filter(r=>specFrame?.joints?.[r]&&refFrame?.pose?.joints?.[r]);const ranked=pool.map(role=>({role,delta:roleDelta(specFrame,refFrame,role)})).sort((a,b)=>b.delta-a.delta);const meaningful=ranked.filter(x=>x.delta>1e-5);return (meaningful.length?meaningful:ranked).slice(0,Math.max(1,Number(maxRoles)||2)).map(x=>x.role)}
function mean(xs){return xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:0}
export async function optimizeSemanticMotion({jsonPath,atlasPath,spec,referenceJsonPath,referenceAtlasPath,referenceAnimation,times=null,roles=null,properties=['x','y'],maxRoles=2,step=.08,rotationStep=12,scaleStep=.06,iterations=1,animation='__visual_motion_optimize',outDir,server=DEFAULT_SERVER}={}){
  if(!jsonPath||!atlasPath||!spec||!referenceJsonPath||!referenceAtlasPath||!referenceAnimation||!outDir)throw new Error('optimizeSemanticMotion requires target json/atlas/spec, reference json/atlas/animation, and outDir');
  const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');fs.rmSync(outDir,{recursive:true,force:true});fs.mkdirSync(outDir,{recursive:true});
  const targetSpec=deep(spec),refRaw=JSON.parse(fs.readFileSync(referenceJsonPath,'utf8')),refAtlas=fs.readFileSync(referenceAtlasPath,'utf8');
  const sampleTimes=(Array.isArray(times)&&times.length?times:targetSpec.frames.map(f=>Number(f.time))).map(Number);const refMotion=captureReferenceMotion(refRaw,refAtlas,{animationName:referenceAnimation,times:sampleTimes,semanticRig:inferSemanticRig(refRaw),label:`visual-opt:${referenceAnimation}`});
  const proc=await ensureServer(root,server);let current=targetSpec;const frames=[];
  try{
    for(let i=0;i<sampleTimes.length;i++){
      const time=sampleTimes[i],refFrame=refMotion.frames[i],specFrame=nearestFrame(current.frames,time).frame,selected=chooseRoles(specFrame,refFrame,{roles,maxRoles});
      const refPng=path.join(outDir,`reference_${String(i).padStart(2,'0')}_${time.toFixed(3)}s.png`);await renderFrame({jsonPath:referenceJsonPath,atlasPath:referenceAtlasPath,animation:referenceAnimation,time,out:refPng,server});
      const sub=path.join(outDir,`frame_${String(i).padStart(2,'0')}_${time.toFixed(3)}s`);const report=await optimizeSemanticPose({jsonPath,atlasPath,spec:current,referenceImage:refPng,time,roles:selected,properties,step,rotationStep,scaleStep,iterations,animation,outDir:sub,server});
      current=JSON.parse(fs.readFileSync(report.outSpec,'utf8'));frames.push({time,roles:selected,baselineIoU:report.baseline.metrics.iou,finalIoU:report.best.metrics.iou,improvement:report.improvement,evaluations:report.evaluations,report:path.join(sub,'visual_optimizer_report.json')});
    }
    const outSpec=path.join(outDir,'optimized.semantic-spec.json');fs.writeFileSync(outSpec,JSON.stringify(current,null,2)+'\n');
    const finalRaw=deep(JSON.parse(fs.readFileSync(jsonPath,'utf8')));authorSemanticMotion(finalRaw,fs.readFileSync(atlasPath,'utf8'),current,{animation,replace:true});const outJson=path.join(outDir,'optimized.json');fs.writeFileSync(outJson,JSON.stringify(finalRaw));
    const atlas=new TextureAtlas(fs.readFileSync(atlasPath,'utf8'));const data=new SkeletonJson(new AtlasAttachmentLoader(atlas)).readSkeletonData(finalRaw);atlas.dispose?.();if(!data.findAnimation(animation))throw new Error(`Optimized animation missing in runtime: ${animation}`);
    const finalQa=[];for(let i=0;i<sampleTimes.length;i++){const time=sampleTimes[i],png=path.join(outDir,`final_${String(i).padStart(2,'0')}_${time.toFixed(3)}s.png`);await renderFrame({jsonPath:outJson,atlasPath,animation,time,out:png,server});const metrics=compareSilhouettes(path.join(outDir,`reference_${String(i).padStart(2,'0')}_${time.toFixed(3)}s.png`),png).normalized;finalQa.push({time,iou:metrics.iou,dice:metrics.dice,png});}
    const baselineMeanIoU=mean(frames.map(f=>f.baselineIoU)),stepFinalMeanIoU=mean(frames.map(f=>f.finalIoU)),finalMeanIoU=mean(finalQa.map(f=>f.iou));
    const summary={format:'zhuda-visual-motion-optimizer-report',version:1,animation,reference:{json:referenceJsonPath,atlas:referenceAtlasPath,animation:referenceAnimation},times:sampleTimes,properties:Array.isArray(properties)?properties:String(properties).split(',').map(x=>x.trim()).filter(Boolean),step:Number(step),rotationStep:Number(rotationStep),scaleStep:Number(scaleStep),iterations:Number(iterations),maxRoles:Number(maxRoles),frames,baselineMeanIoU,stepFinalMeanIoU,finalMeanIoU,finalMinIoU:Math.min(...finalQa.map(f=>f.iou)),improvement:finalMeanIoU-baselineMeanIoU,finalQa,outSpec,outJson,runtime:{bones:data.bones.length,slots:data.slots.length,duration:data.findAnimation(animation).duration}};
    fs.writeFileSync(path.join(outDir,'visual_motion_optimizer_report.json'),JSON.stringify(summary,null,2)+'\n');return summary;
  } finally {if(proc)proc.kill('SIGTERM')}
}
