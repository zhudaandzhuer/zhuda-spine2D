import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { authorSemanticMotion } from '../src/lib/semanticMotionSpec.js';
import { compareSilhouettes } from '../src/lib/imageQa.js';
import { renderFrame } from './renderFrame.mjs';

const DEFAULT_SERVER='http://127.0.0.1:4328/';
const AUTO_ROLE_CANDIDATES=['L_elbow','L_wrist','R_elbow','R_wrist','L_knee','L_ankle','R_knee','R_ankle','chest','pelvis'];
function deep(v){return structuredClone(v)}
async function alive(url){try{return(await fetch(url)).ok}catch{return false}}
async function ensurePersistentServer(root,url){if(await alive(url))return null;const u=new URL(url),proc=spawn(process.execPath,[path.join(root,'node_modules/vite/bin/vite.js'),'--host',u.hostname||'127.0.0.1','--port',u.port||'4328'],{cwd:root,stdio:'ignore'});for(let i=0;i<120&&!await alive(url);i++)await new Promise(r=>setTimeout(r,100));if(!await alive(url)){proc.kill('SIGTERM');throw new Error('Visual optimizer render server unavailable')}return proc}
function nearestFrame(spec,time){let best=-1,dist=Infinity;for(let i=0;i<(spec.frames||[]).length;i++){const d=Math.abs(Number(spec.frames[i].time)-time);if(d<dist){dist=d;best=i}}if(best<0)throw new Error('Semantic spec has no frames');return {index:best,time:Number(spec.frames[best].time),distance:dist}}
function metricScore(m){return Number(m.iou||0)-Number(m.centroidDistance||0)*.15-Number(m.bboxAspectDelta||0)*.05}
export async function optimizeSemanticPose({jsonPath,atlasPath,spec,referenceImage,time,roles=[],properties=['x','y'],step=.08,rotationStep=12,scaleStep=.06,iterations=2,autoRoleCandidates=AUTO_ROLE_CANDIDATES,autoRoleCount=2,probeStep=null,probeRotationStep=null,probeScaleStep=null,animation='__visual_optimize',outDir,server=DEFAULT_SERVER}={}){
  if(!jsonPath||!atlasPath||!spec||!referenceImage||!outDir)throw new Error('optimizeSemanticPose requires jsonPath, atlasPath, spec, referenceImage, outDir');
  const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),raw0=JSON.parse(fs.readFileSync(jsonPath,'utf8')),atlasText=fs.readFileSync(atlasPath,'utf8'),current=deep(spec),frame=nearestFrame(current,Number(time)||0);roles=Array.isArray(roles)?roles:String(roles||'').split(',').map(x=>x.trim()).filter(Boolean);const autoRequested=!roles.length||roles.includes('auto');roles=roles.filter(r=>r!=='auto');
  properties=Array.isArray(properties)?properties:String(properties||'x,y').split(',').map(x=>x.trim()).filter(Boolean);autoRoleCandidates=Array.isArray(autoRoleCandidates)?autoRoleCandidates:String(autoRoleCandidates||'').split(',').map(x=>x.trim()).filter(Boolean);fs.rmSync(outDir,{recursive:true,force:true});fs.mkdirSync(outDir,{recursive:true});const proc=await ensurePersistentServer(root,server),history=[];let evalId=0;
  async function evaluate(candidate,label){const raw=deep(raw0);authorSemanticMotion(raw,atlasText,candidate,{animation,replace:true});const jp=path.join(outDir,`candidate_${String(evalId).padStart(3,'0')}.json`),png=path.join(outDir,`candidate_${String(evalId).padStart(3,'0')}.png`);evalId++;fs.writeFileSync(jp,JSON.stringify(raw));await renderFrame({jsonPath:jp,atlasPath,animation,time:frame.time,out:png,server});const metrics=compareSilhouettes(referenceImage,png).normalized,score=metricScore(metrics),rec={label,score,metrics,json:jp,png};history.push(rec);return rec}
  try{
    let best=await evaluate(current,'baseline'),curSpec=current,curStep=Number(step),curRotationStep=Number(rotationStep),curScaleStep=Number(scaleStep),roleDiscovery=null;
    if(autoRequested){const baseline=best,candidates=[];for(const role of autoRoleCandidates){const joint=current.frames[frame.index]?.joints?.[role];if(!joint)continue;let probeBest=baseline,probeLabel=null;for(const prop of properties){if(prop==='rotation'&&!Number.isFinite(Number(joint.rotation)))continue;if((prop==='scaleX'||prop==='scaleY')&&!Number.isFinite(Number(joint[prop])))continue;const delta=prop==='rotation'?Number(probeRotationStep??rotationStep):(prop==='scaleX'||prop==='scaleY'?Number(probeScaleStep??scaleStep):Number(probeStep??step));for(const dir of [-1,1]){const trial=deep(current),j=trial.frames[frame.index].joints[role];j[prop]=Number(j[prop]??(prop.startsWith('scale')?1:0))+dir*delta;const ev=await evaluate(trial,`probe:${role}.${prop}${dir>0?'+':'-'}${delta}`);if(ev.score>probeBest.score){probeBest=ev;probeLabel=ev.label}}}candidates.push({role,bestScore:probeBest.score,gain:probeBest.score-baseline.score,bestProbe:probeLabel});}candidates.sort((a,b)=>b.gain-a.gain);const selected=candidates.slice(0,Math.max(1,Number(autoRoleCount)||2)).map(x=>x.role);roles=[...new Set([...roles,...selected])];roleDiscovery={requested:true,candidates,selected,baselineScore:baseline.score};}
    if(!roles.length)throw new Error('Visual optimizer could not resolve semantic roles');
    for(let iter=0;iter<Math.max(1,Number(iterations)||1);iter++){
      for(const role of roles){for(const prop of properties){
        const joint=curSpec.frames[frame.index]?.joints?.[role];if(!joint)continue;if(prop==='rotation'&&!Number.isFinite(Number(joint.rotation)))continue;if((prop==='scaleX'||prop==='scaleY')&&!Number.isFinite(Number(joint[prop])))continue;
        const delta=prop==='rotation'?curRotationStep:(prop==='scaleX'||prop==='scaleY'?curScaleStep:curStep);let localBest=best,localSpec=curSpec;
        for(const dir of [-1,1]){const trial=deep(curSpec),j=trial.frames[frame.index].joints[role];j[prop]=Number(j[prop]??(prop.startsWith('scale')?1:0))+dir*delta;const ev=await evaluate(trial,`iter${iter}:${role}.${prop}${dir>0?'+':'-'}${delta}`);if(ev.score>localBest.score+1e-7){localBest=ev;localSpec=trial}}
        if(localSpec!==curSpec){curSpec=localSpec;best=localBest;history.push({label:`accept:${role}.${prop}`,score:best.score});}
      }}curStep*=.55;curRotationStep*=.55;curScaleStep*=.55;
    }
    const finalRaw=deep(raw0);authorSemanticMotion(finalRaw,atlasText,curSpec,{animation,replace:true});const outSpec=path.join(outDir,'optimized.semantic-spec.json'),outJson=path.join(outDir,'optimized.json');fs.writeFileSync(outSpec,JSON.stringify(curSpec,null,2)+'\n');fs.writeFileSync(outJson,JSON.stringify(finalRaw));const report={format:'zhuda-visual-pose-optimizer-report',version:1,animation,time:frame.time,frameIndex:frame.index,roles,properties,initialStep:Number(step),initialRotationStep:Number(rotationStep),initialScaleStep:Number(scaleStep),iterations:Number(iterations),roleDiscovery,baseline:history.find(x=>x.label==='baseline'),best,improvement:best.score-history.find(x=>x.label==='baseline').score,evaluations:history.filter(x=>x.metrics).length,outSpec,outJson,history};fs.writeFileSync(path.join(outDir,'visual_optimizer_report.json'),JSON.stringify(report,null,2)+'\n');return report;
  } finally {if(proc)proc.kill('SIGTERM')}
}
