const EPS=1e-6;

function skinRecords(raw){
  if(Array.isArray(raw?.skins))return raw.skins.map(s=>({name:s?.name||'default',attachments:s?.attachments||{}}));
  return Object.entries(raw?.skins||{}).map(([name,attachments])=>({name,attachments:attachments||{}}));
}
function skinByName(raw,name){const skins=skinRecords(raw),wanted=String(name||'default');return skins.find(s=>s.name===wanted)||skins.find(s=>s.name==='default')||skins[0]||{name:wanted,attachments:{}};}
function slotByName(raw,name){return (raw?.slots||[]).find(s=>s?.name===name)||null;}
function attachmentInSkin(raw,skinName,slotName,attachmentName){
  if(!attachmentName)return null;const skins=skinRecords(raw),preferred=skins.find(s=>s.name===skinName),fallback=skins.find(s=>s.name==='default');
  return preferred?.attachments?.[slotName]?.[attachmentName] ?? fallback?.attachments?.[slotName]?.[attachmentName] ?? skins.map(s=>s.attachments?.[slotName]?.[attachmentName]).find(Boolean) ?? null;
}
function resolveLinkedAttachment(raw,skinName,slotName,attachmentName,data,seen=new Set()){
  if(!data||!data.parent)return data;const key=`${skinName}/${slotName}/${attachmentName}`;if(seen.has(key))return data;seen.add(key);
  const parentSkin=data.skin||skinName||'default',parentName=data.parent,parent=attachmentInSkin(raw,parentSkin,slotName,parentName);return parent?resolveLinkedAttachment(raw,parentSkin,slotName,parentName,parent,seen):data;
}
function parseWeightedInfluences(raw,data){
  const uvs=data?.uvs,vertices=data?.vertices,bones=raw?.bones||[],vertexCount=Array.isArray(uvs)?Math.floor(uvs.length/2):0;
  if(!vertexCount||!Array.isArray(vertices)||vertices.length===vertexCount*2)return null;
  let i=0,parsed=0;const weights=new Map();
  while(i<vertices.length&&parsed<vertexCount){
    const n=Number(vertices[i++]);if(!Number.isInteger(n)||n<1||n>128)return null;
    for(let k=0;k<n;k++){
      const bi=Number(vertices[i++]),x=Number(vertices[i++]),y=Number(vertices[i++]),weight=Number(vertices[i++]);void x;void y;
      if(!Number.isInteger(bi)||bi<0||bi>=bones.length||!Number.isFinite(weight))return null;
      if(weight>EPS){const name=bones[bi]?.name;if(name)weights.set(name,(weights.get(name)||0)+weight);}
    }
    parsed++;
  }
  return parsed===vertexCount&&i===vertices.length?weights:null;
}
function buildParentMap(raw){return new Map((raw?.bones||[]).map(b=>[b.name,b.parent||null]));}
function ancestorChain(parentMap,name){const out=[];let cur=name,guard=0;while(cur&&guard++<1024&&!out.includes(cur)){out.push(cur);cur=parentMap.get(cur)||null;}return out;}
function setupAttachmentForSlot(raw,slotName){return slotByName(raw,slotName)?.attachment ?? null;}
function attachmentTimelineName(raw,animationName,slotName,time){
  const frames=raw?.animations?.[animationName]?.slots?.[slotName]?.attachment;if(!Array.isArray(frames)||!frames.length)return undefined;
  let hit;for(const frame of frames){if(Number(frame?.time||0)<=Number(time||0)+1e-7)hit=frame;else break;}
  if(hit===undefined)return undefined;return Object.prototype.hasOwnProperty.call(hit,'name')?hit.name:null;
}
function activeAttachmentName(raw,animationName,slotName,time){const timeline=attachmentTimelineName(raw,animationName,slotName,time);return timeline===undefined?setupAttachmentForSlot(raw,slotName):timeline;}
function visibleAttachmentType(data){const type=String(data?.type||'region').toLowerCase();return !['boundingbox','path','point','clipping'].includes(type);}
function evalScalarFrames(frames,time,key,setup=1){
  if(!Array.isArray(frames)||!frames.length)return setup;const t=Number(time||0);let prev=null,next=null;
  for(const frame of frames){const ft=Number(frame?.time||0);if(ft<=t+1e-7)prev=frame;else{next=frame;break;}}
  if(!prev)return setup;const a=Number(prev?.[key]??setup);if(!next||prev?.curve==='stepped')return Number.isFinite(a)?a:setup;
  const b=Number(next?.[key]??a),t0=Number(prev.time||0),t1=Number(next.time||0);if(!Number.isFinite(b)||t1<=t0)return a;const u=Math.min(1,Math.max(0,(t-t0)/(t1-t0)));return a+(b-a)*u;
}
function setupMix(constraint,key,def=1){const value=constraint?.[key];return Number.isFinite(Number(value))?Number(value):def;}
function activeIkTargetChains(raw,animationName,time,effectiveBones){
  const out=[];for(const ik of raw?.ik||[]){const mix=evalScalarFrames(raw?.animations?.[animationName]?.ik?.[ik.name],time,'mix',setupMix(ik,'mix',1));if(!(Math.abs(mix)>EPS))continue;
    const bones=(ik.bones||[]).filter(Boolean),drivesVisible=bones.some(b=>effectiveBones.has(b));if(drivesVisible&&ik.target)out.push({kind:'ik',name:ik.name,target:ik.target,targetBone:ik.target,bones,mix,order:Number(ik.order??0)});
  }return out;
}
function activeTransformTargetChains(raw,animationName,time,effectiveBones){
  const props=['mixRotate','mixX','mixY','mixScaleX','mixScaleY','mixShearY'],out=[];
  for(const constraint of raw?.transform||[]){
    const frames=raw?.animations?.[animationName]?.transform?.[constraint.name],mixes=Object.fromEntries(props.map(key=>[key,evalScalarFrames(frames,time,key,setupMix(constraint,key,1))]));
    if(!Object.values(mixes).some(value=>Math.abs(Number(value)||0)>EPS))continue;const bones=(constraint.bones||[]).filter(Boolean),drivesVisible=bones.some(b=>effectiveBones.has(b));
    if(drivesVisible&&constraint.target)out.push({kind:'transform',name:constraint.name,target:constraint.target,targetBone:constraint.target,bones,mixes,order:Number(constraint.order??0)});
  }return out;
}
function activePathTargetChains(raw,animationName,time,effectiveBones,snapshots){
  const props=['mixRotate','mixX','mixY'],out=[],activeBySlot=new Map((snapshots||[]).map(slot=>[slot.slotName,slot]));
  for(const constraint of raw?.path||[]){
    const frames=raw?.animations?.[animationName]?.paths?.[constraint.name]||raw?.animations?.[animationName]?.path?.[constraint.name],mixes=Object.fromEntries(props.map(key=>[key,evalScalarFrames(frames,time,key,setupMix(constraint,key,1))]));
    if(!Object.values(mixes).some(value=>Math.abs(Number(value)||0)>EPS))continue;const bones=(constraint.bones||[]).filter(Boolean),drivesVisible=bones.some(b=>effectiveBones.has(b)),targetSlot=slotByName(raw,constraint.target),targetState=activeBySlot.get(constraint.target);
    if(drivesVisible&&targetSlot&&targetState?.attachmentName)out.push({kind:'path',name:constraint.name,target:constraint.target,targetSlot:constraint.target,targetBone:targetSlot.bone,bones,mixes,order:Number(constraint.order??0)});
  }return out;
}

export function runtimeSlotSnapshot(skeleton){
  const skeletonAlpha=Number(skeleton?.color?.a??1);return (skeleton?.slots||[]).map(slot=>({slotName:slot?.data?.name||'',attachmentName:slot?.attachment?.name??null,alpha:Number(slot?.color?.a??1)*skeletonAlpha}));
}

export function collectContextInfluence(raw,{skinName='default',animationName='',time=0,activeSlots=null,alphaThreshold=.001}={}){
  const parentMap=buildParentMap(raw),direct=new Map(),effective=new Map(),visibleSlots=[];
  const snapshots=Array.isArray(activeSlots)?activeSlots:(raw?.slots||[]).map(slot=>({slotName:slot.name,attachmentName:activeAttachmentName(raw,animationName,slot.name,time),alpha:1}));
  const add=(map,bone,record)=>{if(!map.has(bone))map.set(bone,[]);map.get(bone).push(record);};
  for(const snap of snapshots){
    const slotName=snap?.slotName;if(!slotName||!(Number(snap.alpha??1)>alphaThreshold)||!snap.attachmentName)continue;const slot=slotByName(raw,slotName);if(!slot)continue;
    const rawData=attachmentInSkin(raw,skinName,slotName,snap.attachmentName),data=resolveLinkedAttachment(raw,skinName,slotName,snap.attachmentName,rawData);if(rawData&&!visibleAttachmentType(rawData))continue;
    const weighted=parseWeightedInfluences(raw,data),drivers=[];
    if(weighted?.size){for(const [bone,weight] of weighted)drivers.push({bone,weight,kind:'weighted'});}else if(slot.bone)drivers.push({bone:slot.bone,weight:1,kind:rawData?.type||'region'});
    if(!drivers.length)continue;visibleSlots.push({slotName,attachmentName:snap.attachmentName,alpha:Number(snap.alpha??1),type:rawData?.type||'region',drivers:drivers.map(x=>({...x}))});
    for(const driver of drivers){const base={slotName,attachmentName:snap.attachmentName,weight:driver.weight,kind:driver.kind,sourceBone:driver.bone};add(direct,driver.bone,base);for(const bone of ancestorChain(parentMap,driver.bone))add(effective,bone,{...base,inherited:bone!==driver.bone});}
  }
  const effectiveBones=new Set(effective.keys()),ikChains=activeIkTargetChains(raw,animationName,time,effectiveBones),transformChains=activeTransformTargetChains(raw,animationName,time,effectiveBones),pathChains=activePathTargetChains(raw,animationName,time,effectiveBones,snapshots),constraintChains=[...ikChains,...transformChains,...pathChains];for(const chain of constraintChains)if(chain.targetBone)effectiveBones.add(chain.targetBone);
  return {skinName,animationName,time,visibleSlots,direct,effective,effectiveBones,ikChains,transformChains,pathChains,constraintChains,parentMap};
}

function assessBoneWithGraph(raw,boneName,graph){
  const direct=graph.direct.get(boneName)||[],effective=graph.effective.get(boneName)||[],constraintChains=graph.constraintChains.filter(chain=>chain.targetBone===boneName||chain.bones.includes(boneName));
  const directWeight=direct.reduce((s,r)=>s+Number(r.weight||0),0),effectiveWeight=effective.reduce((s,r)=>s+Number(r.weight||0),0),timelineParticipation=!!raw?.animations?.[graph.animationName]?.bones?.[boneName];
  const pass=effective.length>0||constraintChains.length>0;let code=pass?'visible_influence':'no_visible_attachment_influence';
  if(!pass&&/^run_/i.test(String(boneName||''))&&!/^run(?:_|$)/i.test(String(graph.animationName||'')))code='cross_animation_helper_zero_influence';
  return {status:pass?'PASS':'BLOCKED',code,boneName,animationName:graph.animationName,time:graph.time,skinName:graph.skinName,directWeight,effectiveWeight,directSlots:[...new Set(direct.map(r=>r.slotName))],effectiveSlots:[...new Set(effective.map(r=>r.slotName))],constraintChains,timelineParticipation,visibleSlotCount:graph.visibleSlots.length};
}

export function assessBoneContextInfluence(raw,{boneName,skinName='default',animationName='',time=0,activeSlots=null,alphaThreshold=.001}={}){
  return assessBoneWithGraph(raw,boneName,collectContextInfluence(raw,{skinName,animationName,time,activeSlots,alphaThreshold}));
}

export function assessSemanticContext(raw,semanticRig,{skinName='default',animationName='',time=0,activeSlots=null,alphaThreshold=.001}={}){
  const graph=collectContextInfluence(raw,{skinName,animationName,time,activeSlots,alphaThreshold}),roles={};for(const [role,mapping] of Object.entries(semanticRig?.roles||{}))roles[role]=assessBoneWithGraph(raw,mapping?.bone,graph);
  const blocked=Object.entries(roles).filter(([,r])=>r.status!=='PASS').map(([role,result])=>({role,...result}));return {roles,blocked,pass:blocked.length===0,visibleSlots:graph.visibleSlots};
}
