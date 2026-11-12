#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { TextureAtlas, AtlasAttachmentLoader, SkeletonJson } from '@esotericsoftware/spine-webgl';
import {
  applyAnimationPlan, cloneAnimation, createAnimation, deleteAnimation,
  listAnimations, maxTime, retimeAnimation, setBoneKey,
  validateAnimationAuthoring
} from '../src/lib/animationOps.js';
import { samplePose, summarizeHierarchy } from '../src/lib/poseOps.js';
import { inferSemanticRig, semanticLandmarks, validateSemanticRig } from '../src/lib/semanticRig.js';
import { solvePoseTargets, solvePoseTargetsStaged, poseResiduals } from '../src/lib/poseSolver.js';
import { captureReferencePose, captureRootMotion, retargetReferencePose, compareLandmarksToReference, captureAnimationVisualState, visualStateOperations } from '../src/lib/referencePose.js';
import { compareSilhouettes } from '../src/lib/imageQa.js';
import { captureReferenceMotion, retargetReferenceMotion, makePortableReferenceMotion } from '../src/lib/motionRetarget.js';
import { assessRetargetFeasibility } from '../src/lib/retargetFeasibility.js';
import { applySemanticArtPack } from '../src/lib/artPack.js';
import { captureMotionPack } from '../src/lib/motionPackCapture.js';
import { authorSemanticMotion, validateSemanticMotionSpec, semanticMotionFromSpec, semanticMotionSpecFromMotion } from '../src/lib/semanticMotionSpec.js';
import { applySemanticMotionEditPlan } from '../src/lib/semanticMotionEdit.js';
import { authorArtGapAssets } from '../src/lib/artGapAuthor.js';
import { completeArtGapPack } from '../src/lib/artGapComplete.js';
import { applyViewpointControllers } from '../src/lib/viewpointController.js';
import { assessMotionSanity } from '../src/lib/motionSanity.js';
import { renderSoftwareFrame, renderSoftwareSequence } from './softwareRenderFrame.mjs';
import { createEditorCommandBus } from '../src/core/editorCommands.ts';
import { createModeMachine, isEditorMode } from '../src/core/modeMachine.ts';

function die(message, code = 1) { console.error(message); process.exit(code); }
function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function writeJson(file, value) { fs.mkdirSync(path.dirname(path.resolve(file)), { recursive: true }); fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n'); }
function argsOf(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) out._.push(a);
    else { const k = a.slice(2); const n = argv[i + 1]; if (n !== undefined && !n.startsWith('--')) { out[k] = n; i++; } else out[k] = true; }
  }
  return out;
}
function validateRuntime(raw, atlasPath) {
  if (!atlasPath) return { ok: true, skipped: true };
  const atlas = new TextureAtlas(fs.readFileSync(atlasPath, 'utf8'));
  const parser = new SkeletonJson(new AtlasAttachmentLoader(atlas));
  const data = parser.readSkeletonData(raw);
  return { ok: true, skipped: false, bones: data.bones.length, slots: data.slots.length, animations: data.animations.map(a => ({ name: a.name, duration: a.duration })) };
}
function atlasPages(text){
  const lines=String(text||'').replace(/\r/g,'').split('\n'),out=[];
  for(let i=0;i<lines.length-1;i++){const name=lines[i].trim(),next=lines[i+1]?.trim()||'',prev=i?lines[i-1].trim():'';if(name&&(!prev||i===0)&&/^size\s*:/.test(next))out.push(name);}
  return [...new Set(out)];
}
function copyProjectSiblings(jsonPath,outDir){
  fs.mkdirSync(outDir,{recursive:true});const dir=path.dirname(path.resolve(jsonPath));
  for(const name of fs.readdirSync(dir)){const src=path.join(dir,name);if(!fs.statSync(src).isFile())continue;if(!/\.(json|atlas|png)$/i.test(name))continue;fs.copyFileSync(src,path.join(outDir,name));}
}
function saveAndValidate(raw, a) {
  const authoring = validateAnimationAuthoring(raw);
  if (!authoring.ok) die(JSON.stringify(authoring, null, 2));
  let runtime = null;
  try { runtime = validateRuntime(raw, a.atlas); } catch (e) { die(`Official Spine 4.2 runtime validation failed: ${e.message}`); }
  if (a.out) writeJson(a.out, raw);
  console.log(JSON.stringify({ ok: true, authoring, runtime, out: a.out || null }, null, 2));
}


function runSelfCli(args){
  const self=path.resolve(process.argv[1]);
  const r=spawnSync(process.execPath,[self,...args],{cwd:process.cwd(),encoding:'utf8',maxBuffer:128*1024*1024});
  if(r.status!==0)throw new Error(`subcommand failed (${args[0]}): ${r.stderr||r.stdout}`);
  let json=null;try{json=JSON.parse(r.stdout)}catch{throw new Error(`subcommand ${args[0]} returned non-JSON: ${r.stdout.slice(0,1200)}`)}
  return json;
}
function appendForwardedArgs(args,a){
  const valued=['source-json','source-atlas','source-anim','target-iou','polish-times','polish-max-worst','polish-passes','polish-roles','polish-properties','polish-max-roles','polish-step','polish-rotation-step','polish-scale-step','polish-iterations','polish-server','time-scale','frames','server','sanity-profile','sanity-frames'];
  for(const k of valued)if(a[k]!=null&&a[k]!==false)args.push(`--${k}`,String(a[k]));
  for(const k of ['visual-polish','mirror'])if(a[k])args.push(`--${k}`);
  return args;
}

const a = argsOf(process.argv.slice(2));
const command = a._[0];
const file = a._[1];
if (!command || command === 'help' || command === '--help') {
  console.log(`spine42 CLI\n\nCommands:\n  inspect <json>\n  validate <json> [--atlas file]\n  anim-create <json> --name NAME --out file [--atlas file]\n  anim-clone <json> --source NAME --name NAME --out file [--atlas file]\n  anim-delete <json> --name NAME --out file [--atlas file]\n  anim-retime <json> --name NAME --factor N --out file [--atlas file]\n  key-set <json> --anim NAME --bone NAME --timeline rotate|translate|scale|shear --time N [--value N] [--x N] [--y N] [--curve linear|stepped|'[...]'] --out file [--atlas file]\n  apply <json> --plan plan.json --out file [--atlas file]\n  render-frame <json> --atlas file --anim NAME --time N --out frame.png\n  render-sequence <json> --atlas file --anim NAME --frames 7 --out-dir folder\n  pose-inspect <json> --atlas file --anim NAME --time N [--top N]\n  skeleton-map <json> [--atlas file]\n  semantic-rig <json> [--atlas file]\n  landmarks <json> --atlas file [--anim NAME] [--time N]\n  pose-solve <json> --atlas file --spec targets.json --out solved.json [--plan-out plan.json]\n  reference-capture <json> --atlas file [--anim NAME] [--time N] --out reference.json\n  reference-retarget <json> --atlas file --reference reference.json --anim NAME [--time N] --out spec.json [--mirror]\n  retarget-solve <json> --atlas file --reference reference.json --anim NAME [--time N] --out solved.json [--plan-out plan.json] [--mirror]\n  image-qa <candidate.png> --reference reference.png [--out diff.png]\n  motion-capture <json> --atlas file --anim NAME [--frames 13] --out motion.json\n  motion-portable <motion.json> --out portable.json [--keep-visual-state] [--keep-channels] [--keep-source-animation]\n  motion-feasibility <json> --atlas file --reference motion.json\n  motion-sanity <json> --atlas file --anim NAME [--profile front-run] [--frames 13]\n  motion-retarget <json> --atlas file --reference motion-or-spec.json --anim NAME --out solved.json [--mirror] [--time-scale N] [--force]\n  art-gap-author <json> --atlas file --reference motion-or-spec.json --out-dir folder\n  art-gap-complete <base-manifest.json> --tasks generation_tasks.json --images-dir folder --out-dir folder [--allow-identical]\n  art-pack-apply <json> --atlas file --manifest pack.json --out-dir folder\n  motion-adapt <json> --atlas file --reference motion-or-spec.json --anim NAME --out-dir folder [--art-pack pack.json] [--source-json file --source-atlas file] [--visual-polish] [--target-iou .97] [--polish-times .2,.4] [--sanity-profile front-run] [--mirror] [--time-scale N]\n  motion-adapt-auto <json> --atlas file --reference motion-or-spec.json --anim NAME --out-dir folder [--generated-dir folder] [--source-json file --source-atlas file] [--visual-polish] [--sanity-profile front-run] [--mirror] [--time-scale N]\n  motion-pack-capture <json> --atlas file --anim NAME --out-dir folder [--frames 13]\n  motion-author <json> --atlas file --spec semantic-motion.json --anim NAME --out solved.json [--mirror] [--time-scale N]\n  motion-spec-edit <semantic-motion.json> --plan edits.json --out edited.json\n  motion-visual-optimize <json> --atlas file --spec semantic-motion.json --reference frame.png --time N --roles L_knee,R_wrist --out-dir folder [--properties x,y,rotation] [--role-candidates L_knee,R_wrist] [--auto-role-count 2] [--probe-step .06] [--step .08] [--rotation-step 12] [--scale-step .06] [--iterations 2]\n  motion-visual-optimize-sequence <json> --atlas file --spec semantic-motion.json --reference-json file --reference-atlas file --reference-anim NAME --out-dir folder [--times .0,.15,.3,.45,.6] [--roles L_knee,R_wrist] [--properties x,y,rotation] [--max-roles 2] [--step .08] [--rotation-step 12] [--scale-step .06] [--iterations 1]`);
  process.exit(0);
}
if (!file) die(command==='image-qa' ? 'Candidate PNG is required' : 'JSON file is required');
if (command === 'image-qa') {
  if (!a.reference) die('image-qa requires --reference');
  try { console.log(JSON.stringify(compareSilhouettes(path.resolve(a.reference),path.resolve(file),{diffOut:a.out?path.resolve(a.out):null}),null,2)); }
  catch(e) { die(e.stack||e.message); }
  process.exit(0);
}
const raw = readJson(file);
try {
  if (command === 'software-render-sequence') {
    if(!a.atlas||!a['out-dir']||!a.anim)die('software-render-sequence requires --atlas, --out-dir, and --anim');console.log(JSON.stringify(renderSoftwareSequence({jsonPath:path.resolve(file),atlasPath:path.resolve(a.atlas),animation:a.anim,outDir:path.resolve(a['out-dir']),frames:Number(a.frames||0),bones:!!a.bones,selectedBone:String(a['selected-bone']||''),rigOut:a['rig-json']?path.resolve(a['rig-json']):'',maxWidth:Number(a.width||720),maxHeight:Number(a.height||720)}),null,2));
  } else if (command === 'software-render-frame') {
    if(!a.atlas||!a.out)die('software-render-frame requires --atlas and --out');console.log(JSON.stringify(renderSoftwareFrame({jsonPath:path.resolve(file),atlasPath:path.resolve(a.atlas),animation:a.anim||'',time:Number(a.time||0),out:path.resolve(a.out),bones:!!a.bones,selectedBone:String(a['selected-bone']||''),rigOut:a['rig-json']?path.resolve(a['rig-json']):'',maxWidth:Number(a.width||1200),maxHeight:Number(a.height||1200)}),null,2));
  } else if (command === 'editor-apply') {
    if(!a.plan||!a.out)die('editor-apply requires --plan and --out');const plan=readJson(a.plan),commands=Array.isArray(plan.commands)?plan.commands:[];if(!commands.length)die('editor-apply plan.commands must not be empty');let document=structuredClone(raw);const bus=createEditorCommandBus(),receipts=[],inferredMode=type=>String(type).startsWith('setup.')?'setup':String(type).startsWith('mesh.')?'mesh':String(type).startsWith('weights.')?'weights':String(type).startsWith('constraint.')?'constraints':String(type).startsWith('deform.')?'deform':'animate';
    for(let index=0;index<commands.length;index++){const row=commands[index]||{},type=String(row.type||''),modeName=String(row.mode||inferredMode(type));if(!type)throw new Error(`editor-apply command ${index} missing type`);if(!isEditorMode(modeName))throw new Error(`editor-apply command ${index} invalid mode: ${modeName}`);const result=bus.dispatch(document,{type,payload:row.payload||{}},{mode:createModeMachine(modeName)});document=result.document;receipts.push({index,type,mode:modeName,label:result.patch.label,metadata:result.metadata||null});}
    const authoring=validateAnimationAuthoring(document);if(!authoring.ok)throw new Error(JSON.stringify(authoring));let runtime=null;try{runtime=validateRuntime(document,a.atlas)}catch(e){throw new Error(`Official Spine 4.2 runtime validation failed: ${e.message}`);}writeJson(a.out,document);console.log(JSON.stringify({ok:true,out:path.resolve(a.out),commands:receipts,authoring,runtime},null,2));
  } else if (command === 'motion-portable') {
    if(!a.out) die('motion-portable requires --out');const portable=makePortableReferenceMotion(raw,{keepVisualState:!!a['keep-visual-state'],keepChannels:!!a['keep-channels'],keepSourceAnimation:!!a['keep-source-animation']});writeJson(a.out,portable);console.log(JSON.stringify({ok:true,out:a.out,frames:portable.frames?.length||0,portable:portable.portable},null,2));
  } else if (command === 'motion-visual-polish') {
    if(!a.atlas||!a.spec||!a['reference-json']||!a['reference-atlas']||!a['reference-anim']||!a['out-dir']) die('motion-visual-polish requires --atlas, --spec, --reference-json, --reference-atlas, --reference-anim, and --out-dir');
    const {polishSemanticMotion}=await import('./visualPolishMotion.mjs');const times=a.times?String(a.times).split(',').map(Number).filter(Number.isFinite):null,roles=a.roles?String(a.roles).split(',').map(x=>x.trim()).filter(Boolean):null,properties=String(a.properties||'x,y,rotation').split(',').map(x=>x.trim()).filter(Boolean);const report=await polishSemanticMotion({jsonPath:path.resolve(file),atlasPath:path.resolve(a.atlas),spec:readJson(a.spec),referenceJsonPath:path.resolve(a['reference-json']),referenceAtlasPath:path.resolve(a['reference-atlas']),referenceAnimation:a['reference-anim'],times,targetIoU:Number(a['target-iou']||.97),maxWorst:Number(a['max-worst']||2),passes:Number(a.passes||1),roles,properties,maxRoles:Number(a['max-roles']||2),step:Number(a.step||.08),rotationStep:Number(a['rotation-step']||12),scaleStep:Number(a['scale-step']||.06),iterations:Number(a.iterations||1),animation:a.anim||'__visual_polish',outDir:path.resolve(a['out-dir']),server:a.server||'http://127.0.0.1:4330/'});console.log(JSON.stringify({ok:true,...report},null,2));
  } else if (command === 'motion-visual-optimize-sequence') {
    if(!a.atlas||!a.spec||!a['reference-json']||!a['reference-atlas']||!a['reference-anim']||!a['out-dir']) die('motion-visual-optimize-sequence requires --atlas, --spec, --reference-json, --reference-atlas, --reference-anim, and --out-dir');
    const {optimizeSemanticMotion}=await import('./visualOptimizeMotion.mjs');const times=a.times?String(a.times).split(',').map(Number).filter(Number.isFinite):null,roles=a.roles?String(a.roles).split(',').map(x=>x.trim()).filter(Boolean):null,properties=String(a.properties||'x,y').split(',').map(x=>x.trim()).filter(Boolean);const report=await optimizeSemanticMotion({jsonPath:path.resolve(file),atlasPath:path.resolve(a.atlas),spec:readJson(a.spec),referenceJsonPath:path.resolve(a['reference-json']),referenceAtlasPath:path.resolve(a['reference-atlas']),referenceAnimation:a['reference-anim'],times,roles,properties,maxRoles:Number(a['max-roles']||2),step:Number(a.step||.08),rotationStep:Number(a['rotation-step']||12),scaleStep:Number(a['scale-step']||.06),iterations:Number(a.iterations||1),animation:a.anim||'__visual_motion_optimize',outDir:path.resolve(a['out-dir']),server:a.server||'http://127.0.0.1:4329/'});console.log(JSON.stringify({ok:true,...report},null,2));
  } else if (command === 'motion-visual-optimize') {
    if(!a.atlas||!a.spec||!a.reference||!a['out-dir']) die('motion-visual-optimize requires --atlas, --spec, --reference, and --out-dir');
    const {optimizeSemanticPose}=await import('./visualOptimizePose.mjs');const report=await optimizeSemanticPose({jsonPath:path.resolve(file),atlasPath:path.resolve(a.atlas),spec:readJson(a.spec),referenceImage:path.resolve(a.reference),time:Number(a.time||0),roles:String(a.roles||'auto').split(',').map(x=>x.trim()).filter(Boolean),properties:String(a.properties||'x,y').split(',').map(x=>x.trim()).filter(Boolean),autoRoleCandidates:a['role-candidates']?String(a['role-candidates']).split(',').map(x=>x.trim()).filter(Boolean):undefined,autoRoleCount:Number(a['auto-role-count']||2),probeStep:a['probe-step']!=null?Number(a['probe-step']):null,probeRotationStep:a['probe-rotation-step']!=null?Number(a['probe-rotation-step']):null,probeScaleStep:a['probe-scale-step']!=null?Number(a['probe-scale-step']):null,step:Number(a.step||.08),rotationStep:Number(a['rotation-step']||12),scaleStep:Number(a['scale-step']||.06),iterations:Number(a.iterations||2),animation:a.anim||'__visual_optimize',outDir:path.resolve(a['out-dir']),server:a.server||'http://127.0.0.1:4328/'});console.log(JSON.stringify({ok:true,...report},null,2));
  } else if (command === 'motion-spec-edit') {
    if(!a.plan||!a.out) die('motion-spec-edit requires --plan and --out');
    const result=applySemanticMotionEditPlan(raw,readJson(a.plan));writeJson(a.out,result.spec);console.log(JSON.stringify({ok:true,out:path.resolve(a.out),report:result.report,validation:result.validation},null,2));
  } else if (command === 'render-sequence') {
    if (!a.atlas || !a.anim || !a['out-dir']) die('render-sequence requires --atlas, --anim, and --out-dir');
    const { renderSequence } = await import('./renderFrame.mjs');
    const result = await renderSequence({ jsonPath:path.resolve(file), atlasPath:path.resolve(a.atlas), animation:a.anim, frames:Number(a.frames||7), outDir:path.resolve(a['out-dir']), server:a.server||'http://127.0.0.1:4318/' });
    console.log(JSON.stringify(result,null,2));
  } else if (command === 'render-frame') {
    if (!a.atlas || !a.anim || !a.out) die('render-frame requires --atlas, --anim, and --out');
    const { renderFrame } = await import('./renderFrame.mjs');
    const result = await renderFrame({ jsonPath:path.resolve(file), atlasPath:path.resolve(a.atlas), animation:a.anim, time:Number(a.time||0), out:path.resolve(a.out), server:a.server||'http://127.0.0.1:4318/' });
    console.log(JSON.stringify(result,null,2));
  } else if (command === 'pose-inspect') {
    if (!a.atlas) die('--atlas is required for pose-inspect');
    const result = samplePose(raw, fs.readFileSync(a.atlas, 'utf8'), { animationName: a.anim || '', time: Number(a.time || 0) });
    const top = Math.max(1, Math.min(500, Number(a.top || 20)));
    console.log(JSON.stringify({ animation: result.animation, time: result.time, duration: result.duration, topBones: result.ranked.slice(0, top) }, null, 2));
  } else if (command === 'motion-author') {
    if(!a.atlas||!a.spec||!a.anim||!a.out) die('motion-author requires --atlas, --spec, --anim, and --out');
    const spec=readJson(a.spec),check=validateSemanticMotionSpec(spec);if(!check.ok)die(JSON.stringify(check,null,2));
    const result=authorSemanticMotion(raw,fs.readFileSync(a.atlas,'utf8'),spec,{animation:a.anim,replace:true,mirror:!!a.mirror,timeScale:Number(a['time-scale']||1)});
    saveAndValidate(raw,a);
  } else if (command === 'motion-pack-capture') {
    if(!a.atlas||!a.anim||!a['out-dir']) die('motion-pack-capture requires --atlas, --anim, and --out-dir');
    const report=captureMotionPack({raw,atlasText:fs.readFileSync(a.atlas,'utf8'),jsonPath:path.resolve(file),atlasPath:path.resolve(a.atlas),animationName:a.anim,outDir:path.resolve(a['out-dir']),frames:Number(a.frames||13),label:a.label||a.anim});
    console.log(JSON.stringify({ok:true,...report},null,2));
  } else if (command === 'art-gap-complete') {
    if(!a.tasks||!a['images-dir']||!a['out-dir']) die('art-gap-complete requires --tasks, --images-dir, and --out-dir');
    const report=completeArtGapPack({baseManifestPath:path.resolve(file),tasksPath:path.resolve(a.tasks),imagesDir:path.resolve(a['images-dir']),outputDir:path.resolve(a['out-dir']),allowIdentical:!!a['allow-identical'],minMeanAbs:Number(a['min-mean-abs']||.25)});console.log(JSON.stringify({ok:true,...report},null,2));
  } else if (command === 'art-gap-author') {
    if(!a.atlas||!a.reference||!a['out-dir']) die('art-gap-author requires --atlas, --reference, and --out-dir');
    const input=readJson(a.reference),motion=input?.format==='zhuda-semantic-motion-spec'?semanticMotionFromSpec(input):input;if(motion?.format!=='zhuda-semantic-motion')die('art-gap-author reference must be zhuda-semantic-motion or zhuda-semantic-motion-spec');
    const report=authorArtGapAssets({raw,atlasText:fs.readFileSync(a.atlas,'utf8'),atlasPath:path.resolve(a.atlas),motion,outputDir:path.resolve(a['out-dir']),name:a.name||path.basename(file,'.json')});
    console.log(JSON.stringify({ok:true,...report},null,2));
  } else if (command === 'art-pack-apply') {
    if(!a.atlas||!a.manifest||!a['out-dir']) die('art-pack-apply requires --atlas, --manifest, and --out-dir');
    const atlasText=fs.readFileSync(a.atlas,'utf8'),manifest=readJson(a.manifest),outDir=path.resolve(a['out-dir']);
    copyProjectSiblings(file,outDir);
    const report=applySemanticArtPack({raw,atlasText,jsonPath:path.resolve(file),atlasPath:path.resolve(a.atlas),manifest,manifestDir:path.dirname(path.resolve(a.manifest)),outputDir:outDir});
    const upgraded=readJson(report.outJson),runtime=validateRuntime(upgraded,report.outAtlas);
    console.log(JSON.stringify({ok:true,report,runtime},null,2));
  } else if (command === 'motion-sanity') {
    if(!a.atlas||!a.anim) die('motion-sanity requires --atlas and --anim');
    const report=assessMotionSanity(raw,fs.readFileSync(a.atlas,'utf8'),{animationName:a.anim,profile:a.profile||'front-run',frames:Number(a.frames||13),minUpperOutRatio:a['min-upper-out-ratio']!=null?Number(a['min-upper-out-ratio']):undefined,minForeOutRatio:a['min-fore-out-ratio']!=null?Number(a['min-fore-out-ratio']):undefined});
    console.log(JSON.stringify(report,null,2));if(report.status!=='PASS')process.exitCode=2;
  } else if (command === 'motion-adapt-auto') {
    if(!a.atlas||!a.reference||!a.anim||!a['out-dir']) die('motion-adapt-auto requires --atlas, --reference, --anim, and --out-dir');
    const outDir=path.resolve(a['out-dir']),gapDir=path.join(outDir,'_art_gap'),completeDir=path.join(outDir,'_completed_pack'),projectDir=path.join(outDir,'project');fs.mkdirSync(outDir,{recursive:true});for(const d of [gapDir,completeDir,projectDir])fs.rmSync(d,{recursive:true,force:true});
    const input=readJson(a.reference),motion=input?.format==='zhuda-semantic-motion-spec'?semanticMotionFromSpec(input):input;if(motion?.format!=='zhuda-semantic-motion')die('motion-adapt-auto reference must be zhuda-semantic-motion or zhuda-semantic-motion-spec');const atlasText=fs.readFileSync(a.atlas,'utf8'),rig=inferSemanticRig(raw),setup=samplePose(raw,atlasText,{animationName:'',time:0}),preflight=assessRetargetFeasibility(raw,motion,setup,{semanticRig:rig,atlasText});
    const rootReport={format:'zhuda-motion-adapt-auto-report',version:1,target:path.resolve(file),reference:path.resolve(a.reference),animation:a.anim,outDir,preflight:{status:preflight.status,kinematicStatus:preflight.kinematicStatus,visualStatus:preflight.visualStatus,score:preflight.score,kinematic:preflight.kinematic,artPlan:preflight.artPlan}};
    const finish=(extra)=>{const report={...rootReport,...extra};writeJson(path.join(outDir,'motion_adapt_auto_report.json'),report);console.log(JSON.stringify({ok:true,...report},null,2));};
    if(preflight.status==='BLOCKED'){finish({status:'BLOCKED',flags:preflight.flags});process.exitCode=2;}
    else if(preflight.status==='READY'){
      const args=['motion-adapt',path.resolve(file),'--atlas',path.resolve(a.atlas),'--reference',path.resolve(a.reference),'--anim',a.anim,'--out-dir',projectDir];appendForwardedArgs(args,a);const adapted=runSelfCli(args),sanityStatus=adapted.motionSanity?.status,finalStatus=sanityStatus==='BLOCKED'?'BLOCKED':sanityStatus&&sanityStatus!=='PASS'?'NEEDS_REVIEW':'COMPLETE';finish({status:finalStatus,artGap:null,completedPack:null,adapted,project:adapted.project||null});if(finalStatus==='BLOCKED')process.exitCode=2;
    } else {
      const gap=authorArtGapAssets({raw:structuredClone(raw),atlasText,atlasPath:path.resolve(a.atlas),motion,outputDir:gapDir,name:a.name||path.basename(file,'.json')});
      if(!gap.tasks?.length){finish({status:'NEEDS_EXTERNAL_ART_PACK',artGap:gap,reason:'No automatically decomposable viewpoint tasks were found.'});}
      else if(!a['generated-dir']){finish({status:'WAITING_FOR_ART',artGap:gap,generatedDirSuggestion:path.join(outDir,'generated')});}
      else {
        const baseManifest=path.resolve(gapDir,gap.baseManifest),tasksPath=path.resolve(gapDir,gap.generationTasks),completed=completeArtGapPack({baseManifestPath:baseManifest,tasksPath,imagesDir:path.resolve(a['generated-dir']),outputDir:completeDir,allowIdentical:!!a['allow-identical'],minMeanAbs:Number(a['min-mean-abs']||.25)});
        const args=['motion-adapt',path.resolve(file),'--atlas',path.resolve(a.atlas),'--reference',path.resolve(a.reference),'--anim',a.anim,'--out-dir',projectDir,'--art-pack',path.resolve(completed.manifest)];appendForwardedArgs(args,a);const adapted=runSelfCli(args),sanityStatus=adapted.motionSanity?.status,finalStatus=sanityStatus==='BLOCKED'?'BLOCKED':sanityStatus&&sanityStatus!=='PASS'?'NEEDS_REVIEW':'COMPLETE';finish({status:finalStatus,artGap:gap,completedPack:{manifest:completed.manifest,controllers:completed.controllers,validation:completed.validation},adapted,project:adapted.project||null});if(finalStatus==='BLOCKED')process.exitCode=2;
      }
    }
  } else if (command === 'motion-adapt') {
    if(!a.atlas||!a.reference||!a.anim||!a['out-dir']) die('motion-adapt requires --atlas, --reference, --anim, and --out-dir');
    const outDir=path.resolve(a['out-dir']);fs.rmSync(outDir,{recursive:true,force:true});fs.mkdirSync(outDir,{recursive:true});copyProjectSiblings(file,outDir);
    const referenceInput=readJson(a.reference);const motion=referenceInput?.format==='zhuda-semantic-motion-spec'?semanticMotionFromSpec(referenceInput):referenceInput;if(motion?.format!=='zhuda-semantic-motion')die(`motion-adapt reference must be zhuda-semantic-motion or zhuda-semantic-motion-spec`);let workRaw=raw,workAtlasText=fs.readFileSync(a.atlas,'utf8'),workJson=path.join(outDir,path.basename(file)),workAtlas=path.join(outDir,path.basename(a.atlas));
    let rig=inferSemanticRig(workRaw),setup=samplePose(workRaw,workAtlasText,{animationName:'',time:0}),preflight=assessRetargetFeasibility(workRaw,motion,setup,{semanticRig:rig,atlasText:workAtlasText}),artPack=null,artPackManifest=null;
    if(preflight.status==='NEEDS_ART'){
      if(!a['art-pack']) die(`motion-adapt requires --art-pack because preflight is NEEDS_ART.\n${JSON.stringify({status:preflight.status,score:preflight.score,artPlan:preflight.artPlan,flags:preflight.flags},null,2)}`);
      const manifest=readJson(a['art-pack']);artPackManifest=manifest;if(manifest?.metadata?.kind==='decomposed-base'&&manifest?.metadata?.resolvesViewpointArt===false)die('motion-adapt received a base decomposition pack without viewpoint variants. Run art-gap-complete first.');artPack=applySemanticArtPack({raw:workRaw,atlasText:workAtlasText,jsonPath:path.resolve(file),atlasPath:path.resolve(a.atlas),manifest,manifestDir:path.dirname(path.resolve(a['art-pack'])),outputDir:outDir});
      workJson=artPack.outJson;workAtlas=artPack.outAtlas;workRaw=readJson(workJson);workAtlasText=fs.readFileSync(workAtlas,'utf8');rig=inferSemanticRig(workRaw);setup=samplePose(workRaw,workAtlasText,{animationName:'',time:0});
    }
    const postflight=assessRetargetFeasibility(workRaw,motion,setup,{semanticRig:rig,atlasText:workAtlasText});if(postflight.status!=='READY')die(`motion-adapt postflight ${postflight.status}.\n${JSON.stringify(postflight,null,2)}`);
    const retarget=retargetReferenceMotion(workRaw,workAtlasText,motion,{animation:a.anim,replace:true,mirror:!!a.mirror,timeScale:Number(a['time-scale']||1),semanticRig:rig});
    const viewpoint=artPackManifest?.metadata?.viewpointControllers?.length?applyViewpointControllers({raw:workRaw,atlasText:workAtlasText,motion,animation:a.anim,manifest:artPackManifest,timeScale:Number(a['time-scale']||1),semanticRig:rig}):null;
    const authoring=validateAnimationAuthoring(workRaw);if(!authoring.ok)die(JSON.stringify(authoring,null,2));fs.writeFileSync(workJson,JSON.stringify(workRaw));let runtime=validateRuntime(workRaw,workAtlas);
    const {renderSequence}=await import('./renderFrame.mjs');let preview=await renderSequence({jsonPath:workJson,atlasPath:workAtlas,animation:a.anim,frames:Number(a.frames||motion.frames?.length||13),outDir:path.join(outDir,'_preview'),server:a.server||'http://127.0.0.1:4318/'});
    let imageQa=null,sourcePreview=null,visualPolish=null;
    if(a['source-json']&&a['source-atlas']){
      const sourceRawForQa=readJson(a['source-json']),sourceAnimation=[a['source-anim'],motion.source?.animation,referenceInput?.sourceAnimation,referenceInput?.name].find(n=>n&&sourceRawForQa.animations?.[n]);if(!sourceAnimation)die(`Unable to resolve source animation for QA. Pass --source-anim. Candidates: ${JSON.stringify([a['source-anim'],motion.source?.animation,referenceInput?.sourceAnimation,referenceInput?.name])}`);sourcePreview=await renderSequence({jsonPath:path.resolve(a['source-json']),atlasPath:path.resolve(a['source-atlas']),animation:sourceAnimation,frames:preview.frames.length,outDir:path.join(outDir,'_reference_preview'),server:a.server||'http://127.0.0.1:4318/'});
      const rows=preview.frames.map((f,i)=>compareSilhouettes(sourcePreview.frames[i],f));const ious=rows.map(x=>x.normalized.iou);imageQa={meanIoU:ious.reduce((x,y)=>x+y,0)/ious.length,minIoU:Math.min(...ious),frames:ious,times:preview.times};
      if(a['visual-polish']){
        if(!sourceAnimation)die('motion-adapt --visual-polish requires a source animation name in the motion or --source-anim');
        const {polishSemanticMotion}=await import('./visualPolishMotion.mjs'),polishSpec=referenceInput?.format==='zhuda-semantic-motion-spec'?referenceInput:semanticMotionSpecFromMotion(motion,{name:a.anim});
        const polishTimes=a['polish-times']?String(a['polish-times']).split(',').map(Number).filter(Number.isFinite):imageQa.frames.map((iou,i)=>({iou,time:preview.times?.[i]})).filter(x=>Number.isFinite(x.time)).sort((x,y)=>x.iou-y.iou).slice(0,Number(a['polish-max-worst']||2)).map(x=>x.time);
        visualPolish=await polishSemanticMotion({jsonPath:workJson,atlasPath:workAtlas,spec:polishSpec,referenceJsonPath:path.resolve(a['source-json']),referenceAtlasPath:path.resolve(a['source-atlas']),referenceAnimation:sourceAnimation,times:polishTimes,targetIoU:Number(a['target-iou']||.97),maxWorst:Number(a['polish-max-worst']||2),passes:Number(a['polish-passes']||1),roles:a['polish-roles']?String(a['polish-roles']).split(',').map(x=>x.trim()).filter(Boolean):null,properties:String(a['polish-properties']||'x,y,rotation').split(',').map(x=>x.trim()).filter(Boolean),maxRoles:Number(a['polish-max-roles']||2),step:Number(a['polish-step']||.08),rotationStep:Number(a['polish-rotation-step']||12),scaleStep:Number(a['polish-scale-step']||.06),iterations:Number(a['polish-iterations']||1),animation:a.anim,outDir:path.join(outDir,'_visual_polish'),server:a['polish-server']||'http://127.0.0.1:4330/'});
        fs.copyFileSync(visualPolish.outJson,workJson);workRaw=readJson(workJson);runtime=validateRuntime(workRaw,workAtlas);preview=await renderSequence({jsonPath:workJson,atlasPath:workAtlas,animation:a.anim,frames:Number(a.frames||motion.frames?.length||13),outDir:path.join(outDir,'_preview_polished'),server:a.server||'http://127.0.0.1:4318/'});sourcePreview=await renderSequence({jsonPath:path.resolve(a['source-json']),atlasPath:path.resolve(a['source-atlas']),animation:sourceAnimation,frames:preview.frames.length,outDir:path.join(outDir,'_reference_preview_polished'),server:a.server||'http://127.0.0.1:4318/'});const postRows=preview.frames.map((f,i)=>compareSilhouettes(sourcePreview.frames[i],f)),postIous=postRows.map(x=>x.normalized.iou);imageQa={...imageQa,postPolish:{meanIoU:postIous.reduce((x,y)=>x+y,0)/postIous.length,minIoU:Math.min(...postIous),frames:postIous,times:preview.times}};
      }
    }
    const motionSanity=a['sanity-profile']?assessMotionSanity(workRaw,workAtlasText,{animationName:a.anim,profile:String(a['sanity-profile']),frames:Number(a['sanity-frames']||a.frames||13)}):null;
    const report={format:'zhuda-motion-adapt-report',version:1,inputFormat:referenceInput?.format||null,preflight:{status:preflight.status,kinematicStatus:preflight.kinematicStatus,visualStatus:preflight.visualStatus,score:preflight.score,kinematic:preflight.kinematic,artPlan:preflight.artPlan},artPack:artPack?{slots:artPack.slots.length,parts:artPack.parts.length,rigTemplate:artPack.rigTemplate}:null,viewpoint:viewpoint?{applied:viewpoint.applied,controllers:viewpoint.controllers,keys:viewpoint.keys}:null,postflight:{status:postflight.status,kinematicStatus:postflight.kinematicStatus,visualStatus:postflight.visualStatus,score:postflight.score,kinematic:postflight.kinematic,flags:postflight.flags},retarget:{animation:retarget.animation,frames:retarget.frames.length,duration:retarget.duration,maxResidual:Math.max(...retarget.frames.map(f=>f.residual.maxDistance)),channelTransfer:retarget.channelTransfer,frameReports:retarget.frames.map(f=>({sourceTime:f.sourceTime,targetTime:f.targetTime,residual:f.residual,resolvedTargets:f.resolvedTargets||{}}))},runtime,preview:{contact:preview.contact,frames:preview.frames.length},imageQa,visualPolish:visualPolish?{status:visualPolish.status,targetIoU:visualPolish.targetIoU,initial:visualPolish.initial,final:{meanIoU:visualPolish.final.meanIoU,minIoU:visualPolish.final.minIoU,improvement:visualPolish.final.improvement},passes:visualPolish.passes}:null,motionSanity,outDir,project:{json:workJson,atlas:workAtlas}};
    writeJson(path.join(outDir,'motion_adapt_report.json'),report);console.log(JSON.stringify({ok:true,...report},null,2));
  } else if (command === 'motion-capture') {
    if(!a.atlas||!a.anim||!a.out) die('motion-capture requires --atlas, --anim, and --out');
    const motion=captureReferenceMotion(raw,fs.readFileSync(a.atlas,'utf8'),{animationName:a.anim,frames:Number(a.frames||13),label:a.label||a.anim}); writeJson(a.out,motion);
    console.log(JSON.stringify({ok:true,out:a.out,frames:motion.frames.length,duration:motion.source.duration},null,2));
  } else if (command === 'motion-feasibility') {
    if(!a.atlas||!a.reference) die('motion-feasibility requires --atlas and --reference');
    const motion=readJson(a.reference),atlasText=fs.readFileSync(a.atlas,'utf8'),rig=inferSemanticRig(raw),setup=samplePose(raw,atlasText,{animationName:'',time:0});
    const feasibility=assessRetargetFeasibility(raw,motion,setup,{semanticRig:rig,atlasText});
    console.log(JSON.stringify(feasibility,null,2));
  } else if (command === 'motion-retarget') {
    if(!a.atlas||!a.reference||!a.anim||!a.out) die('motion-retarget requires --atlas, --reference, --anim, and --out');
    const motion=readJson(a.reference),atlasText=fs.readFileSync(a.atlas,'utf8'),rig=inferSemanticRig(raw),setup=samplePose(raw,atlasText,{animationName:'',time:0});
    const feasibility=assessRetargetFeasibility(raw,motion,setup,{semanticRig:rig,atlasText});
    if(feasibility.status!=='READY' && !a.force) die(`Retarget preflight ${feasibility.status}. Run motion-feasibility for details or pass --force.\n${JSON.stringify({status:feasibility.status,kinematicStatus:feasibility.kinematicStatus,visualStatus:feasibility.visualStatus,kinematic:feasibility.kinematic,score:feasibility.score,flags:feasibility.flags,artPlan:feasibility.artPlan},null,2)}`);
    const report=retargetReferenceMotion(raw,atlasText,motion,{animation:a.anim,replace:true,mirror:!!a.mirror,timeScale:Number(a['time-scale']||1),semanticRig:rig});
    const authoring=validateAnimationAuthoring(raw);if(!authoring.ok)die(JSON.stringify(authoring,null,2));let runtime;try{runtime=validateRuntime(raw,a.atlas)}catch(e){die(`Official Spine 4.2 runtime validation failed: ${e.message}`)}writeJson(a.out,raw);
    console.log(JSON.stringify({ok:true,out:a.out,feasibility,frames:report.frames.length,duration:report.duration,maxResidual:Math.max(...report.frames.map(f=>f.residual.maxDistance)),authoring,runtime},null,2));
  } else if (command === 'reference-capture') {
    if (!a.atlas || !a.out) die('reference-capture requires --atlas and --out');
    const rig=inferSemanticRig(raw);
    const pose=samplePose(raw,fs.readFileSync(a.atlas,'utf8'),{animationName:a.anim||'',time:Number(a.time||0)});
    const reference=captureReferencePose(rig,pose,{label:a.label||null}); const setupPose=samplePose(raw,fs.readFileSync(a.atlas,'utf8'),{animationName:'',time:0}); reference.rootMotion=captureRootMotion(rig,setupPose,pose); reference.visualState=captureAnimationVisualState(raw,a.anim||'',Number(a.time||0)); writeJson(a.out,reference);
    console.log(JSON.stringify({ok:true,out:a.out,reference},null,2));
  } else if (command === 'reference-retarget') {
    if (!a.atlas || !a.reference || !a.anim || !a.out) die('reference-retarget requires --atlas, --reference, --anim, and --out');
    const reference=readJson(a.reference),rig=inferSemanticRig(raw);
    const setup=samplePose(raw,fs.readFileSync(a.atlas,'utf8'),{animationName:'',time:0});
    const template=a.template || (raw.animations?.run_skeletal_setup ? 'run_skeletal_setup' : null);
    const spec=retargetReferencePose(reference,rig,setup,{animation:a.anim,time:Number(a.time||0),mirror:!!a.mirror,templateAnimation:template}); writeJson(a.out,spec);
    console.log(JSON.stringify({ok:true,out:a.out,spec},null,2));
  } else if (command === 'retarget-solve') {
    if (!a.atlas || !a.reference || !a.anim || !a.out) die('retarget-solve requires --atlas, --reference, --anim, and --out');
    const reference=readJson(a.reference),rig=inferSemanticRig(raw),atlasText=fs.readFileSync(a.atlas,'utf8');
    const setup=samplePose(raw,atlasText,{animationName:'',time:0});
    const template=a.template || (raw.animations?.run_skeletal_setup ? 'run_skeletal_setup' : null);
    const spec=retargetReferencePose(reference,rig,setup,{animation:a.anim,time:Number(a.time||0),mirror:!!a.mirror,templateAnimation:template});
    if (!raw.animations?.[spec.animation]) { if (spec.templateAnimation && raw.animations?.[spec.templateAnimation]) cloneAnimation(raw,spec.templateAnimation,spec.animation,{replace:false}); else createAnimation(raw,spec.animation,{replace:false}); }
    const visualOps=visualStateOperations(raw,spec.animation,spec.time,spec.visualState); if(visualOps.length) applyAnimationPlan(raw,{operations:visualOps});
    const solution=solvePoseTargetsStaged(raw,atlasText,spec,{semanticRig:rig});
    if (a['plan-out']) writeJson(a['plan-out'],{operations:[...visualOps,...solution.operations],diagnostics:solution.solutions,reference:reference.source,retarget:spec.meta,visualStateApplied:visualOps.length});
    const authoring=validateAnimationAuthoring(raw); if (!authoring.ok) die(JSON.stringify(authoring,null,2));
    let runtime; try { runtime=validateRuntime(raw,a.atlas); } catch(e) { die(`Official Spine 4.2 runtime validation failed: ${e.message}`); }
    writeJson(a.out,raw);
    const solvedPose=samplePose(raw,atlasText,{animationName:spec.animation,time:Number(spec.time||0)});
    const residual=poseResiduals(rig,solvedPose,spec.targets||{});
    console.log(JSON.stringify({ok:true,spec,solution:{operations:solution.operations,unsupported:solution.unsupported},residual,authoring,runtime,out:a.out},null,2));
  } else if (command === 'pose-solve') {
    if (!a.atlas || !a.spec || !a.out) die('pose-solve requires --atlas, --spec, and --out');
    const spec=readJson(a.spec);
    const rig=inferSemanticRig(raw);
    if (!raw.animations?.[spec.animation]) { if (spec.templateAnimation && raw.animations?.[spec.templateAnimation]) cloneAnimation(raw,spec.templateAnimation,spec.animation,{replace:false}); else createAnimation(raw,spec.animation,{replace:false}); }
    const basePose=samplePose(raw,fs.readFileSync(a.atlas,'utf8'),{animationName:spec.baseAnimation||'',time:Number(spec.baseTime||0)});
    const visualOps=visualStateOperations(raw,spec.animation,spec.time,spec.visualState); if(visualOps.length) applyAnimationPlan(raw,{operations:visualOps});
    const solution=solvePoseTargetsStaged(raw,fs.readFileSync(a.atlas,'utf8'),spec,{semanticRig:rig});
    if (a['plan-out']) writeJson(a['plan-out'],{operations:solution.operations,diagnostics:solution.solutions});
    const authoring=validateAnimationAuthoring(raw);
    if (!authoring.ok) die(JSON.stringify(authoring,null,2));
    let runtime; try { runtime=validateRuntime(raw,a.atlas); } catch(e) { die(`Official Spine 4.2 runtime validation failed: ${e.message}`); }
    writeJson(a.out,raw);
    const solvedPose=samplePose(raw,fs.readFileSync(a.atlas,'utf8'),{animationName:spec.animation,time:Number(spec.time||0)});
    const residual=poseResiduals(rig,solvedPose,spec.targets||{});
    console.log(JSON.stringify({ok:true,solution:{animation:solution.animation,time:solution.time,operations:solution.operations,unsupported:solution.unsupported},residual,authoring,runtime,out:a.out},null,2));
  } else if (command === 'semantic-rig') {
    const rig=inferSemanticRig(raw);
    let setup=null;
    if (a.atlas) {
      const pose=samplePose(raw,fs.readFileSync(a.atlas,'utf8'),{animationName:'',time:0});
      setup=semanticLandmarks(rig,pose);
    }
    console.log(JSON.stringify({ rig, validation:validateSemanticRig(rig), setup },null,2));
  } else if (command === 'landmarks') {
    if (!a.atlas) die('--atlas is required for landmarks');
    const rig=inferSemanticRig(raw);
    const pose=samplePose(raw,fs.readFileSync(a.atlas,'utf8'),{animationName:a.anim||'',time:Number(a.time||0)});
    console.log(JSON.stringify({ rig: { roles:rig.roles, warnings:rig.warnings }, landmarks:semanticLandmarks(rig,pose), validation:validateSemanticRig(rig) },null,2));
  } else if (command === 'skeleton-map') {
    let bones = summarizeHierarchy(raw);
    if (a.atlas) {
      const pose = samplePose(raw, fs.readFileSync(a.atlas,'utf8'), { animationName:'', time:0 });
      const world = new Map(pose.bones.map(b => [b.name,b.world]));
      bones = bones.map(b => ({ ...b, setupWorld:world.get(b.name) || null }));
    }
    console.log(JSON.stringify({ version: raw.skeleton?.spine, bones }, null, 2));
  } else if (command === 'inspect') {
    const animations = Object.entries(raw.animations || {}).map(([name, anim]) => ({ name, duration: maxTime(anim), boneTimelines: Object.keys(anim.bones || {}).length, slotTimelines: Object.keys(anim.slots || {}).length, hasAttachments: !!anim.attachments }));
    console.log(JSON.stringify({ version: raw.skeleton?.spine, bones: (raw.bones || []).length, slots: (raw.slots || []).length, animations }, null, 2));
  } else if (command === 'validate') {
    saveAndValidate(raw, a);
  } else if (command === 'anim-create') {
    createAnimation(raw, a.name, { replace: !!a.replace }); saveAndValidate(raw, a);
  } else if (command === 'anim-clone') {
    cloneAnimation(raw, a.source, a.name, { replace: !!a.replace }); saveAndValidate(raw, a);
  } else if (command === 'anim-delete') {
    deleteAnimation(raw, a.name); saveAndValidate(raw, a);
  } else if (command === 'anim-retime') {
    retimeAnimation(raw, a.name, Number(a.factor)); saveAndValidate(raw, a);
  } else if (command === 'key-set') {
    const values = {};
    for (const k of ['value','x','y']) if (a[k] !== undefined) values[k] = Number(a[k]);
    setBoneKey(raw, a.anim, a.bone, a.timeline, Number(a.time), values, { curve: a.curve });
    saveAndValidate(raw, a);
  } else if (command === 'apply') {
    const plan = readJson(a.plan); applyAnimationPlan(raw, plan); saveAndValidate(raw, a);
  } else die(`Unknown command: ${command}`);
} catch (e) { die(e.stack || e.message); }
