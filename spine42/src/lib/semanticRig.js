const SIDE_RE = {
  L: /(^|[^a-z0-9])(l|left)([^a-z0-9]|$)/i,
  R: /(^|[^a-z0-9])(r|right)([^a-z0-9]|$)/i,
};

const ROLE_ORDER = [
  'root','pelvis','chest','neck','head',
  'L_shoulder','L_elbow','L_wrist','L_hand',
  'R_shoulder','R_elbow','R_wrist','R_hand',
  'L_hip','L_knee','L_ankle','L_foot',
  'R_hip','R_knee','R_ankle','R_foot',
];

function textOf(value) {
  return String(value ?? '').replace(/([a-z])([A-Z])/g,'$1 $2').replace(/[\\/_.-]+/g,' ').toLowerCase();
}

function sideOfText(value) {
  const raw = String(value ?? '');
  if (/^(L|left)[_\-.]/i.test(raw) || /[_\-.](L|left)(?:[_\-.]|$)/i.test(raw)) return 'L';
  if (/^(R|right)[_\-.]/i.test(raw) || /[_\-.](R|right)(?:[_\-.]|$)/i.test(raw)) return 'R';
  const t = textOf(raw);
  if (SIDE_RE.L.test(t)) return 'L';
  if (SIDE_RE.R.test(t)) return 'R';
  return null;
}

function boneGraph(raw, {excludeBones=new Set()}={}) {
  const bones = (raw?.bones || []).filter(b=>!excludeBones.has(b.name));
  const byName = new Map();
  bones.forEach((b,index) => byName.set(b.name,{...b,index,children:[],depth:0}));
  for (const b of byName.values()) {
    if (b.parent && byName.has(b.parent)) byName.get(b.parent).children.push(b.name);
  }
  const depthOf = name => {
    let d=0, cur=byName.get(name), seen=new Set();
    while (cur?.parent && byName.has(cur.parent) && !seen.has(cur.parent)) { seen.add(cur.parent); d++; cur=byName.get(cur.parent); }
    return d;
  };
  for (const b of byName.values()) b.depth=depthOf(b.name);
  return {bones,byName};
}

function attachmentTokens(raw) {
  const bySlot = new Map();
  const add = (slot,name,data) => {
    if (!bySlot.has(slot)) bySlot.set(slot,new Set());
    const s=bySlot.get(slot); s.add(slot); s.add(name);
    if (data?.path) s.add(data.path);
    if (data?.name) s.add(data.name);
  };
  if (Array.isArray(raw?.skins)) {
    for (const skin of raw.skins) for (const [slot,attachments] of Object.entries(skin?.attachments || {})) for (const [name,data] of Object.entries(attachments || {})) add(slot,name,data);
  } else {
    for (const skin of Object.values(raw?.skins || {})) for (const [slot,attachments] of Object.entries(skin || {})) for (const [name,data] of Object.entries(attachments || {})) add(slot,name,data);
  }
  return bySlot;
}

function slotRecords(raw, {excludeBones=new Set(),excludeSlots=new Set()}={}) {
  const tokens=attachmentTokens(raw);
  return (raw?.slots || []).map((slot,index) => ({
    ...slot,index,
    tokenText:[slot.name,slot.attachment,...(tokens.get(slot.name)||[])].map(textOf).join(' '),
    side:sideOfText(slot.name) || sideOfText(slot.attachment),
  })).filter(slot=>!excludeBones.has(slot.bone)&&!excludeSlots.has(slot.name));
}

function weightedBoneCounts(raw,data){
  const uvs=data?.uvs,vertices=data?.vertices,bones=raw?.bones||[],vertexCount=Array.isArray(uvs)?Math.floor(uvs.length/2):0;
  if(!vertexCount||!Array.isArray(vertices)||vertices.length===vertexCount*2)return null;
  let i=0,parsed=0;const counts=new Map();
  while(i<vertices.length&&parsed<vertexCount){const n=Number(vertices[i++]);if(!Number.isInteger(n)||n<1||n>64)return null;for(let k=0;k<n;k++){const bi=Number(vertices[i++]);i+=3;if(!Number.isInteger(bi)||bi<0||bi>=bones.length)return null;const name=bones[bi]?.name;if(name)counts.set(name,(counts.get(name)||0)+1);}parsed++;}
  return parsed===vertexCount?counts:null;
}
function weightedInfluencesBySlot(raw){
  const out=new Map(),add=(slot,data)=>{const c=weightedBoneCounts(raw,data);if(!c)return;if(!out.has(slot))out.set(slot,new Map());const dst=out.get(slot);for(const [b,n] of c)dst.set(b,(dst.get(b)||0)+n);};
  if(Array.isArray(raw?.skins))for(const skin of raw.skins)for(const [slot,atts] of Object.entries(skin?.attachments||{}))for(const data of Object.values(atts||{}))add(slot,data);
  else for(const skin of Object.values(raw?.skins||{}))for(const [slot,atts] of Object.entries(skin||{}))for(const data of Object.values(atts||{}))add(slot,data);
  return out;
}
function weightedAnchorBone(slots,influences,byName,patterns){
  const candidates=[];for(const slot of slots){if(!patterns.some(p=>p.test(slot.tokenText)))continue;for(const [bone,count] of influences.get(slot.name)||[]){const b=byName.get(bone);if(!b||Number(b.length||0)<=0)continue;candidates.push({bone,count,depth:b.depth,slot:slot.name});}}
  candidates.sort((a,b)=>b.depth-a.depth||b.count-a.count);return candidates[0]||null;
}
function weightedAnchorForExactSlots(slots,influences,byName,names){
  const wanted=new Set(names.map(x=>String(x).toLowerCase())),candidates=[];
  for(const slot of slots){if(!wanted.has(String(slot.name).toLowerCase()))continue;for(const [bone,count] of influences.get(slot.name)||[]){const b=byName.get(bone);if(!b||Number(b.length||0)<=0)continue;candidates.push({bone,count,depth:b.depth,slot:slot.name});}}
  candidates.sort((a,b)=>b.depth-a.depth||b.count-a.count);return candidates[0]||null;
}
function lowestCommonAncestor(byName,names){
  const arr=[...new Set(names)].filter(n=>byName.has(n));if(!arr.length)return null;
  const path=n=>{const out=[];let cur=byName.get(n),guard=0;while(cur&&guard++<512){out.push(cur.name);cur=cur.parent?byName.get(cur.parent):null;}return out;};
  const first=path(arr[0]);for(const n of first){if(arr.slice(1).every(x=>path(x).includes(n)))return n;}return null;
}
function weightedCommonAncestor(slots,influences,byName,patterns){
  const hits=[];for(const slot of slots){if(!patterns.some(p=>p.test(slot.tokenText)))continue;const names=[...(influences.get(slot.name)||new Map()).keys()];const lca=lowestCommonAncestor(byName,names);if(lca)hits.push({bone:lca,depth:byName.get(lca)?.depth??-1,slot:slot.name,count:names.length});}hits.sort((a,b)=>b.depth-a.depth||b.count-a.count);return hits[0]||null;
}
function weightedLimbChain(slots,influences,byName,side,pattern=/\bleg\b/){
  const chains=[];for(const slot of slots){if(slot.side!==side||!pattern.test(slot.tokenText))continue;const inf=influences.get(slot.name);if(!inf?.size)continue;const set=new Set(inf.keys());const roots=[...set].filter(n=>!set.has(byName.get(n)?.parent));
    const walk=(n,path)=>{const children=(byName.get(n)?.children||[]).filter(c=>set.has(c));if(!children.length){chains.push({slot:slot.name,path,score:path.reduce((sum,b)=>sum+(inf.get(b)||0),0)});return;}for(const c of children)walk(c,[...path,c]);};for(const r of roots)walk(r,[r]);}
  chains.sort((a,b)=>b.path.length-a.path.length||b.score-a.score);return chains.find(x=>x.path.length>=3)||null;
}

function findSlotBone(slots, patterns, {side=null}={}) {
  const scored=[];
  for (const s of slots) {
    if (side && s.side !== side) continue;
    let score=0;
    for (const p of patterns) if (p.test(s.tokenText)) score+=1;
    if (score) scored.push({slot:s,score});
  }
  scored.sort((a,b)=>b.score-a.score || b.slot.index-a.slot.index);
  return scored[0]?.slot?.bone ?? null;
}

function pathUp(byName, start, stopExclusive=null) {
  const out=[]; let cur=byName.get(start), guard=0;
  while (cur && guard++<512) {
    if (cur.name===stopExclusive) break;
    out.push(cur.name);
    if (!cur.parent || !byName.has(cur.parent)) break;
    cur=byName.get(cur.parent);
  }
  return out;
}

function chooseDeepestSlotBone(slots, byName, predicate) {
  const c=slots.filter(predicate).map(s=>({name:s.bone,depth:byName.get(s.bone)?.depth ?? -1,slot:s}));
  c.sort((a,b)=>b.depth-a.depth || b.slot.index-a.slot.index);
  return c[0]?.name ?? null;
}

function entry(bone, confidence, evidence, source='inferred') {
  return bone ? {bone,confidence:Number(confidence.toFixed(3)),evidence:[...new Set(evidence)],source} : null;
}

function setRole(roles, role, value) { if (value?.bone) roles[role]=value; }

function hasBone(byName,name){ return byName.has(name); }

function findNamedBone(byName, patterns, {deepest=true}={}) {
  const hits=[...byName.values()].filter(b=>patterns.some(p=>p.test(textOf(b.name))));
  hits.sort((a,b)=>deepest ? b.depth-a.depth || b.index-a.index : a.depth-b.depth || a.index-b.index);
  return hits[0]?.name || null;
}
function axialName(name){ return /^(torso|chest|spine|body)\d*$/i.test(String(name||'').replace(/[_.-]+/g,'')); }
function promoteAxialChain(byName,start){
  let cur=byName.get(start),best=cur?.name||start,guard=0;
  while(cur&&guard++<32){const next=cur.children.map(n=>byName.get(n)).filter(Boolean).filter(b=>axialName(b.name));if(next.length!==1)break;cur=next[0];best=cur.name;}return best;
}
function pairLabel(name){
  const side=sideOfText(name);if(side)return {side,mode:'anatomical-label',confidence:.92,evidence:`${side} side label`};
  const t=textOf(name);if(/\bfront\b/.test(t))return {side:'L',mode:'front-rear-depth',confidence:.74,evidence:'front depth label mapped to canonical L'};
  if(/\brear\b|\bback\b/.test(t))return {side:'R',mode:'front-rear-depth',confidence:.74,evidence:'rear/back depth label mapped to canonical R'};
  const m=String(name||'').match(/(?:^|[^0-9])([12])$/);if(m)return {side:m[1]==='1'?'L':'R',mode:'numeric-pair',confidence:.80,evidence:`numeric pair ${m[1]} mapped to ${m[1]==='1'?'L':'R'}`};
  return null;
}
function childMatching(byName,parent,patterns){
  const p=byName.get(parent);if(!p)return null;const hits=p.children.map(n=>byName.get(n)).filter(Boolean).map(b=>({b,score:patterns.reduce((v,r)=>v+(r.test(textOf(b.name))?1:0),0)})).filter(x=>x.score>0);hits.sort((a,b)=>b.score-a.score || Number(b.b.length||0)-Number(a.b.length||0));return hits[0]?.b?.name||null;
}
function inferNamedLimbChains(roles,byName,warnings){
  const armRoots=[...byName.values()].filter(b=>/\bupper\s*arm\d*\b|\bupperarm\d*\b|^upper (?:left|right|l|r)$/.test(textOf(b.name)));
  const legRoots=[...byName.values()].filter(b=>/\bthigh\d*\b/.test(textOf(b.name)));
  const seenModes=new Set();
  for(const root of armRoots){const pair=pairLabel(root.name);if(!pair)continue;const prefix=pair.side+'_';if(roles[prefix+'shoulder'])continue;const elbow=childMatching(byName,root.name,[/\bfore\s*arm\d*\b/,/\bforearm\d*\b/,/^fore (?:left|right|l|r)$/,/\bbracer\b/,/\blower\s*arm\b/]);if(!elbow)continue;const wrist=childMatching(byName,elbow,[/\bhand\d*\b/,/\bfist\b/,/\bwrist\b/,/\bpalm\b/,/\bgun\b/]);if(!wrist)continue;const ev=[pair.evidence,`${root.name} -> ${elbow} -> ${wrist}`];setRole(roles,prefix+'shoulder',entry(root.name,pair.confidence,ev,'bone-name-hierarchy'));setRole(roles,prefix+'elbow',entry(elbow,pair.confidence-.02,ev,'bone-name-hierarchy'));setRole(roles,prefix+'wrist',entry(wrist,pair.confidence-.04,ev,'bone-name-hierarchy'));setRole(roles,prefix+'hand',entry(wrist,pair.confidence-.07,ev,'bone-name-hierarchy'));seenModes.add(pair.mode);}
  for(const root of legRoots){const pair=pairLabel(root.name);if(!pair)continue;const prefix=pair.side+'_';if(roles[prefix+'hip'])continue;const knee=childMatching(byName,root.name,[/\bshin\d*\b/,/\bcalf\d*\b/,/\blower\s*leg\b/]);if(!knee)continue;const ankle=childMatching(byName,knee,[/\bfoot\d*\b/,/\bankle\d*\b/]);if(!ankle)continue;const ev=[pair.evidence,`${root.name} -> ${knee} -> ${ankle}`];setRole(roles,prefix+'hip',entry(root.name,pair.confidence+.02,ev,'bone-name-hierarchy'));setRole(roles,prefix+'knee',entry(knee,pair.confidence,ev,'bone-name-hierarchy'));setRole(roles,prefix+'ankle',entry(ankle,pair.confidence-.02,ev,'bone-name-hierarchy'));setRole(roles,prefix+'foot',entry(ankle,pair.confidence-.05,ev,'bone-name-hierarchy'));seenModes.add(pair.mode);}
  if(seenModes.has('front-rear-depth'))warnings.push('front/rear depth pair mapped to canonical L/R; anatomical handedness is ambiguous');
  if(seenModes.has('numeric-pair'))warnings.push('numeric limb pair inferred as 1→L, 2→R');
  return seenModes;
}

export function inferSemanticRig(raw, {excludeBones=[],excludeSlots=[],disableMiddlewareCanonical=false}={}) {
  const excludedBones=new Set(excludeBones),excludedSlots=new Set(excludeSlots);
  const {byName}=boneGraph(raw,{excludeBones:excludedBones});
  const slots=slotRecords(raw,{excludeBones:excludedBones,excludeSlots:excludedSlots});
  const weightedInfluences=weightedInfluencesBySlot(raw);
  const roles={};
  const warnings=[];

  const roots=[...byName.values()].filter(b=>!b.parent || !byName.has(b.parent));
  if (roots.length) setRole(roles,'root',entry(roots[0].name, roots[0].name==='root'?1:.9, ['hierarchy root'], 'hierarchy'));

  const exactSlot = name => slots.find(s=>String(s.name).toLowerCase()===name)?.bone || null;
  const pelvisBone=exactSlot('biult') || exactSlot('belt') || findSlotBone(slots,[/\bbiult\b/,/\bbelt\b/,/\bwaist\b/,/\bpelvis\b/,/\bhip\b/]) || findNamedBone(byName,[/^hip$/,/^hips$/,/^pelvis$/,/^waist$/],{deepest:false});
  let chestBone=exactSlot('body') || exactSlot('torso') || exactSlot('chest') || findSlotBone(slots,[/\btorso\b/,/\bchest\b/,/\bbody\b/]) || findNamedBone(byName,[/^torso\d*$/,/^chest\d*$/,/^spine\d*$/,/^body$/]);
  if(chestBone&&axialName(chestBone))chestBone=promoteAxialChain(byName,chestBone);
  const weightedChest=weightedAnchorForExactSlots(slots,weightedInfluences,byName,['body','torso','chest']);if(weightedChest&&(!chestBone||chestBone===pelvisBone))chestBone=weightedChest.bone;
  let headBone=exactSlot('head') || findSlotBone(slots,[/\bhead\b/]) || findNamedBone(byName,[/^head$/]);
  if(!headBone){const weightedHead=weightedCommonAncestor(slots,weightedInfluences,byName,[/\bhead\b/,/\bface\b/]);if(weightedHead)headBone=weightedHead.bone;}
  setRole(roles,'pelvis',entry(pelvisBone,.97,['belt/waist slot token'],'slot-token'));
  setRole(roles,'chest',entry(chestBone,.98,['body/torso slot token'],'slot-token'));
  setRole(roles,'head',entry(headBone,.99,['head slot token'],'slot-token'));
  if (headBone) {
    const namedNeck=findNamedBone(byName,[/^neck$/],{deepest:false}),p=namedNeck||byName.get(headBone)?.parent;
    if (p) setRole(roles,'neck',entry(p,namedNeck?.length? .9:.72,[namedNeck?'neck bone name':'parent of head bone'],namedNeck?'bone-name':'hierarchy'));
  }

  // Explicit authoring-rig convention. These names are produced by the middleware itself.
  const exact={
    L_shoulder:'run_L_upper', L_elbow:'run_L_fore', L_wrist:'run_L_hand', L_hand:'run_L_hand',
    R_shoulder:'run_R_upper', R_elbow:'run_R_fore', R_wrist:'run_R_hand', R_hand:'run_R_hand',
    L_hip:'run_L_thigh', L_knee:'run_L_shin', L_ankle:'run_L_foot', L_foot:'run_L_foot',
    R_hip:'run_R_thigh', R_knee:'run_R_shin', R_ankle:'run_R_foot', R_foot:'run_R_foot',
  };
  let exactCount=0;
  if(!disableMiddlewareCanonical)for (const [role,bone] of Object.entries(exact)) if (hasBone(byName,bone)) { setRole(roles,role,entry(bone,1,[`middleware canonical bone ${bone}`],'explicit')); exactCount++; }

  const chest=roles.chest?.bone || chestBone;
  const pelvis=roles.pelvis?.bone || pelvisBone;

  const namedPairModes=inferNamedLimbChains(roles,byName,warnings) || new Set();

  for (const side of ['L','R']) {
    const prefix=side+'_';
    if (!roles[prefix+'shoulder']) {
      const terminal=chooseDeepestSlotBone(slots,byName,s=>s.side===side && /\bhand\d*\b/.test(s.tokenText));
      if (terminal && chest) {
        const chain=pathUp(byName,terminal,chest).reverse();
        if (chain.length>=3) {
          setRole(roles,prefix+'shoulder',entry(chain[0],.92,[`${side} hand slots`,`path to chest ${chest}`],'slot-hierarchy'));
          setRole(roles,prefix+'elbow',entry(chain[1],.90,[`${side} hand slots`,`second limb joint from chest`],'slot-hierarchy'));
          setRole(roles,prefix+'wrist',entry(chain[2],.88,[`${side} hand slots`,`third limb joint from chest`],'slot-hierarchy'));
          setRole(roles,prefix+'hand',entry(chain[3] || chain[2],.82,[`${side} hand terminal chain`],'slot-hierarchy'));
        } else warnings.push(`${side} arm chain too short from ${terminal} to ${chest}`);
      }
    }
    if (!roles[prefix+'hip']) {
      const terminal=chooseDeepestSlotBone(slots,byName,s=>s.side===side && /\bleg\b/.test(s.tokenText));
      const chain=(terminal&&pelvis)?pathUp(byName,terminal,pelvis).reverse():[];
      if(chain.length>=3){
        setRole(roles,prefix+'hip',entry(chain[0],.95,[`${side} leg slot`,`path to pelvis ${pelvis}`],'slot-hierarchy'));
        setRole(roles,prefix+'knee',entry(chain[1],.94,[`${side} leg slot`,`second leg joint`],'slot-hierarchy'));
        setRole(roles,prefix+'ankle',entry(chain[2],.93,[`${side} leg slot`,`third leg joint`],'slot-hierarchy'));
        setRole(roles,prefix+'foot',entry(chain[2],.86,[`${side} leg terminal bone`],'slot-hierarchy'));
      } else {
        const weightedChain=weightedLimbChain(slots,weightedInfluences,byName,side,/\bleg\b/);
        if(weightedChain){const [hip,knee,ankle]=weightedChain.path;const ev=[`${side} weighted leg mesh ${weightedChain.slot}`,`influence chain ${hip} -> ${knee} -> ${ankle}`];setRole(roles,prefix+'hip',entry(hip,.98,ev,'mesh-weight-hierarchy'));setRole(roles,prefix+'knee',entry(knee,.97,ev,'mesh-weight-hierarchy'));setRole(roles,prefix+'ankle',entry(ankle,.96,ev,'mesh-weight-hierarchy'));setRole(roles,prefix+'foot',entry(ankle,.9,ev,'mesh-weight-hierarchy'));}
        else if(terminal&&pelvis)warnings.push(`${side} leg chain too short from ${terminal} to ${pelvis}`);
      }
    }
  }

  const missing=ROLE_ORDER.filter(r=>!roles[r]);
  if (missing.length) warnings.push(`Missing semantic roles: ${missing.join(', ')}`);

  const boneToRoles={};
  for (const [role,v] of Object.entries(roles)) (boneToRoles[v.bone] ||= []).push(role);
  return {
    version:1,
    sideConvention: exactCount>=12 ? 'anatomical-lr' : namedPairModes.has('front-rear-depth') ? 'front-rear-depth' : namedPairModes.has('numeric-pair') ? 'numeric-pair' : slots.some(s=>s.side) ? 'anatomical-lr' : 'unknown',
    exactMiddlewareRoles:exactCount,
    roles,
    boneToRoles,
    missing,
    warnings,
  };
}

export function semanticLandmarks(semanticRig, poseResult) {
  const byBone=new Map((poseResult?.bones || []).map(b=>[b.name,b]));
  const joints={};
  for (const role of ROLE_ORDER) {
    const mapped=semanticRig?.roles?.[role];
    if (!mapped) continue;
    const bone=byBone.get(mapped.bone);
    if (!bone) continue;
    joints[role]={
      bone:mapped.bone,
      confidence:mapped.confidence,
      x:bone.world.x,
      y:bone.world.y,
      rotation:bone.world.rotationX,
      scaleX:bone.world.scaleX,
      scaleY:bone.world.scaleY,
    };
  }
  const dist=(a,b)=>joints[a]&&joints[b]?Math.hypot(joints[a].x-joints[b].x,joints[a].y-joints[b].y):null;
  const metrics={
    shoulderWidth:dist('L_shoulder','R_shoulder'),
    hipWidth:dist('L_hip','R_hip'),
    leftUpperArm:dist('L_shoulder','L_elbow'),
    leftForearm:dist('L_elbow','L_wrist'),
    rightUpperArm:dist('R_shoulder','R_elbow'),
    rightForearm:dist('R_elbow','R_wrist'),
    leftThigh:dist('L_hip','L_knee'),
    leftShin:dist('L_knee','L_ankle'),
    rightThigh:dist('R_hip','R_knee'),
    rightShin:dist('R_knee','R_ankle'),
    torso:Math.max(dist('pelvis','chest')||0, (()=>{const b=byBone.get(semanticRig?.roles?.chest?.bone);return b?Math.abs(Number(b.length||0)*Number(b.world?.scaleX||1)):0;})()),
  };
  return {animation:poseResult?.animation ?? null,time:poseResult?.time ?? 0,duration:poseResult?.duration ?? 0,joints,metrics};
}

export function validateSemanticRig(semanticRig, {required=['pelvis','chest','head','L_shoulder','L_elbow','L_wrist','R_shoulder','R_elbow','R_wrist','L_hip','L_knee','L_ankle','R_hip','R_knee','R_ankle']}={}) {
  const issues=[];
  for (const role of required) if (!semanticRig?.roles?.[role]?.bone) issues.push(`Missing role: ${role}`);
  const armL=['L_shoulder','L_elbow','L_wrist'].map(r=>semanticRig?.roles?.[r]?.bone).filter(Boolean);
  const armR=['R_shoulder','R_elbow','R_wrist'].map(r=>semanticRig?.roles?.[r]?.bone).filter(Boolean);
  const legL=['L_hip','L_knee','L_ankle'].map(r=>semanticRig?.roles?.[r]?.bone).filter(Boolean);
  const legR=['R_hip','R_knee','R_ankle'].map(r=>semanticRig?.roles?.[r]?.bone).filter(Boolean);
  for (const [name,arr] of [['L arm',armL],['R arm',armR],['L leg',legL],['R leg',legR]]) if (new Set(arr).size!==arr.length) issues.push(`${name} has duplicate joint bones: ${arr.join(', ')}`);
  return {ok:issues.length===0,issues,warnings:semanticRig?.warnings || []};
}

export const SEMANTIC_ROLE_ORDER=[...ROLE_ORDER];
