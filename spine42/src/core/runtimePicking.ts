import { ClippingAttachment, MeshAttachment, RegionAttachment, SkeletonClipping, type Skeleton, type Slot } from '@esotericsoftware/spine-webgl';

export interface VertexInfluence { boneIndex:number; boneName:string; weight:number; }

export interface RuntimePickGeometry {
  id: number;
  key: string;
  slotName: string;
  boneName: string;
  attachmentName: string;
  runtimeAttachmentName: string;
  skinName: string;
  attachmentType: 'region'|'mesh';
  drawOrderIndex: number;
  alpha: number;
  texture: any;
  positions: Float32Array;
  uvs: Float32Array;
  triangles: number[];
  sourcePositions: Float32Array;
  sourceUvs: Float32Array;
  sourceTriangles: number[];
  vertexCount: number;
  hullVertexCount: number;
  weighted: boolean;
  clipped: boolean;
  renderVertexCount: number;
  renderTriangleCount: number;
  vertexInfluences: VertexInfluence[][] | null;
}

export interface AttachmentPickResult extends RuntimePickGeometry {
  pixelX: number;
  pixelY: number;
}

const QUAD_TRIANGLES=[0,1,2,2,3,0];
const clamp01=(value:number)=>Math.max(0,Math.min(1,value));

function attachmentAlpha(skeleton:Skeleton,slot:Slot,attachment:any):number {
  return clamp01(Number((skeleton as any).color?.a??1)*Number((slot as any).color?.a??1)*Number(attachment?.color?.a??1));
}
function copyPairs(values:ArrayLike<number>,length:number):Float32Array {
  const out=new Float32Array(length);for(let i=0;i<length;i++)out[i]=Number(values[i]??0);return out;
}
function geometryKey(slotName:string,attachmentName:string,drawOrderIndex:number):string { return `${drawOrderIndex}:${slotName}:${attachmentName}`; }
function resolveAttachmentEntry(skeleton:Skeleton,slot:Slot,attachment:any):{name:string;skinName:string;runtimeName:string}{const slotIndex=Number((slot as any).data?.index??-1),runtimeName=String(attachment?.name||'');const candidates:any[]=[];for(const skin of [(skeleton as any).skin,(skeleton as any).data?.defaultSkin,...((skeleton as any).data?.skins||[])])if(skin&&!candidates.includes(skin))candidates.push(skin);for(const skin of candidates){const entries:any[]=[];try{skin.getAttachmentsForSlot(slotIndex,entries);}catch{}for(const entry of entries)if(entry?.attachment===attachment)return{name:String(entry.name||runtimeName),skinName:String(skin.name||'default'),runtimeName};}return{name:runtimeName,skinName:String((skeleton as any).skin?.name||(skeleton as any).data?.defaultSkin?.name||'default'),runtimeName};}
function meshVertexInfluences(skeleton:Skeleton,attachment:MeshAttachment):VertexInfluence[][]|null {
  const bones=(attachment as any).bones as number[]|null,vertices=(attachment as any).vertices as ArrayLike<number>;if(!Array.isArray(bones)||!bones.length)return null;
  const skeletonBones=(skeleton as any).bones as any[],out:VertexInfluence[][]=[];let bi=0,vi=0;
  while(bi<bones.length){const count=Number(bones[bi++]);if(!Number.isInteger(count)||count<1||count>128)return null;const row:VertexInfluence[]=[];for(let i=0;i<count;i++){const boneIndex=Number(bones[bi++]),weight=Number(vertices[vi+2]??0);vi+=3;const boneName=String(skeletonBones?.[boneIndex]?.data?.name||'');if(boneName&&Number.isFinite(weight)&&weight>1e-8)row.push({boneIndex,boneName,weight});}row.sort((a,b)=>b.weight-a.weight);out.push(row);}
  return out;
}

/** Collects the same Region/Mesh draw geometry used by the official runtime, including active Spine clipping. */
export function collectRuntimePickGeometry(skeleton:Skeleton,{alphaThreshold=.001}={}):RuntimePickGeometry[] {
  const clipper=new SkeletonClipping(),records:RuntimePickGeometry[]=[],drawOrder=(skeleton as any).drawOrder as Slot[];
  let nextId=1;
  try {
    for(let drawOrderIndex=0;drawOrderIndex<drawOrder.length;drawOrderIndex++){
      const slot=drawOrder[drawOrderIndex] as any;
      if(!slot?.bone?.active){clipper.clipEndWithSlot(slot);continue;}
      const attachment=slot.getAttachment?.()??slot.attachment;
      if(attachment instanceof ClippingAttachment){clipper.clipStart(slot,attachment);continue;}
      let positions:Float32Array|undefined,uvs:Float32Array|undefined,triangles:number[]|undefined,sourcePositions:Float32Array|undefined,sourceUvs:Float32Array|undefined,sourceTriangles:number[]|undefined,attachmentType:'region'|'mesh'|undefined,hullVertexCount=0,weighted=false,texture:any=null,vertexInfluences:VertexInfluence[][]|null=null;
      if(attachment instanceof RegionAttachment){
        const world=new Float32Array(8);attachment.computeWorldVertices(slot,world,0,2);
        sourcePositions=copyPairs(world,8);sourceUvs=copyPairs(attachment.uvs,8);sourceTriangles=[...QUAD_TRIANGLES];
        positions=sourcePositions;uvs=sourceUvs;triangles=[...sourceTriangles];attachmentType='region';hullVertexCount=4;texture=(attachment as any).region?.texture??null;
      }else if(attachment instanceof MeshAttachment){
        const length=Number(attachment.worldVerticesLength||0);if(length<6){clipper.clipEndWithSlot(slot);continue;}
        const world=new Float32Array(length);attachment.computeWorldVertices(slot,0,length,world,0,2);
        sourcePositions=copyPairs(world,length);sourceUvs=copyPairs(attachment.uvs,length);sourceTriangles=Array.from(attachment.triangles||[],Number);
        positions=sourcePositions;uvs=sourceUvs;triangles=[...sourceTriangles];attachmentType='mesh';hullVertexCount=Math.max(0,Math.min(length/2,Math.floor(Number((attachment as any).hullLength||0)/2)));weighted=Array.isArray((attachment as any).bones)&&Boolean((attachment as any).bones?.length);vertexInfluences=weighted?meshVertexInfluences(skeleton,attachment):null;texture=(attachment as any).region?.texture??null;
      }else{clipper.clipEndWithSlot(slot);continue;}
      const alpha=attachmentAlpha(skeleton,slot,attachment);
      if(alpha>alphaThreshold&&texture&&positions&&uvs&&triangles&&triangles.length>=3){
        const wasClipping=clipper.isClipping();
        if(wasClipping){
          clipper.clipTrianglesUnpacked(positions,triangles,triangles.length,uvs);
          positions=Float32Array.from(clipper.clippedVertices);uvs=Float32Array.from(clipper.clippedUVs);triangles=Array.from(clipper.clippedTriangles,Number);
        }
        if(positions.length>=6&&triangles.length>=3){
          const slotName=String(slot.data?.name||''),boneName=String(slot.bone?.data?.name||''),entry=resolveAttachmentEntry(skeleton,slot,attachment),attachmentName=entry.name;
          records.push({id:nextId++,key:geometryKey(slotName,attachmentName,drawOrderIndex),slotName,boneName,attachmentName,runtimeAttachmentName:entry.runtimeName,skinName:entry.skinName,attachmentType:attachmentType!,drawOrderIndex,alpha,texture,positions,uvs,triangles,sourcePositions:sourcePositions!,sourceUvs:sourceUvs!,sourceTriangles:sourceTriangles!,vertexCount:sourcePositions!.length/2,hullVertexCount,weighted,clipped:wasClipping,renderVertexCount:positions.length/2,renderTriangleCount:Math.floor(triangles.length/3),vertexInfluences});
        }
      }
      clipper.clipEndWithSlot(slot);
    }
  }finally{clipper.clipEnd();}
  return records;
}

function encodeId(id:number):[number,number,number] { return [(id&255)/255,((id>>8)&255)/255,((id>>16)&255)/255]; }
function decodeId(pixel:Uint8Array):number { return Number(pixel[0]||0)|(Number(pixel[1]||0)<<8)|(Number(pixel[2]||0)<<16); }
function compile(gl:WebGLRenderingContext,type:number,source:string):WebGLShader {
  const shader=gl.createShader(type);if(!shader)throw new Error('Unable to allocate GPU picker shader');gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){const log=gl.getShaderInfoLog(shader)||'unknown shader error';gl.deleteShader(shader);throw new Error(`GPU picker shader compile failed: ${log}`);}return shader;
}

interface AttribState { enabled:boolean; buffer:WebGLBuffer|null; size:number; type:number; normalized:boolean; stride:number; offset:number; }
function captureAttrib(gl:WebGLRenderingContext,index:number):AttribState {
  return {enabled:Boolean(gl.getVertexAttrib(index,gl.VERTEX_ATTRIB_ARRAY_ENABLED)),buffer:gl.getVertexAttrib(index,gl.VERTEX_ATTRIB_ARRAY_BUFFER_BINDING),size:Number(gl.getVertexAttrib(index,gl.VERTEX_ATTRIB_ARRAY_SIZE)||4),type:Number(gl.getVertexAttrib(index,gl.VERTEX_ATTRIB_ARRAY_TYPE)||gl.FLOAT),normalized:Boolean(gl.getVertexAttrib(index,gl.VERTEX_ATTRIB_ARRAY_NORMALIZED)),stride:Number(gl.getVertexAttrib(index,gl.VERTEX_ATTRIB_ARRAY_STRIDE)||0),offset:Number(gl.getVertexAttribOffset(index,gl.VERTEX_ATTRIB_ARRAY_POINTER)||0)};
}
function restoreAttrib(gl:WebGLRenderingContext,index:number,state:AttribState):void {
  if(state.buffer){gl.bindBuffer(gl.ARRAY_BUFFER,state.buffer);gl.vertexAttribPointer(index,state.size,state.type,state.normalized,state.stride,state.offset);}
  if(state.enabled)gl.enableVertexAttribArray(index);else gl.disableVertexAttribArray(index);
}

/** Alpha-aware color-ID attachment picker using the current Runtime projection matrix. */
export class AttachmentGpuPicker {
  private gl:WebGLRenderingContext;
  private program:WebGLProgram;
  private vertexBuffer:WebGLBuffer;
  private framebuffer:WebGLFramebuffer;
  private targetTexture:WebGLTexture;
  private width=0;
  private height=0;
  private aPosition:number;
  private aUv:number;
  private uProjection:WebGLUniformLocation;
  private uTexture:WebGLUniformLocation;
  private uId:WebGLUniformLocation;
  private uAlpha:WebGLUniformLocation;
  private uAlphaThreshold:WebGLUniformLocation;
  constructor(gl:WebGLRenderingContext){
    this.gl=gl;
    const vs=compile(gl,gl.VERTEX_SHADER,`attribute vec2 a_position;attribute vec2 a_uv;uniform mat4 u_projTrans;varying vec2 v_uv;void main(){v_uv=a_uv;gl_Position=u_projTrans*vec4(a_position,0.0,1.0);}`);
    const fs=compile(gl,gl.FRAGMENT_SHADER,`precision mediump float;varying vec2 v_uv;uniform sampler2D u_texture;uniform vec3 u_id;uniform float u_alpha;uniform float u_alphaThreshold;void main(){float a=texture2D(u_texture,v_uv).a*u_alpha;if(a<u_alphaThreshold)discard;gl_FragColor=vec4(u_id,1.0);}`);
    const program=gl.createProgram();if(!program)throw new Error('Unable to allocate GPU picker program');gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);gl.deleteShader(vs);gl.deleteShader(fs);if(!gl.getProgramParameter(program,gl.LINK_STATUS)){const log=gl.getProgramInfoLog(program)||'unknown link error';gl.deleteProgram(program);throw new Error(`GPU picker program link failed: ${log}`);}this.program=program;
    const vertexBuffer=gl.createBuffer(),framebuffer=gl.createFramebuffer(),targetTexture=gl.createTexture();if(!vertexBuffer||!framebuffer||!targetTexture)throw new Error('Unable to allocate GPU picker resources');this.vertexBuffer=vertexBuffer;this.framebuffer=framebuffer;this.targetTexture=targetTexture;
    this.aPosition=gl.getAttribLocation(program,'a_position');this.aUv=gl.getAttribLocation(program,'a_uv');const required=(name:string)=>{const loc=gl.getUniformLocation(program,name);if(!loc)throw new Error(`GPU picker uniform missing: ${name}`);return loc;};this.uProjection=required('u_projTrans');this.uTexture=required('u_texture');this.uId=required('u_id');this.uAlpha=required('u_alpha');this.uAlphaThreshold=required('u_alphaThreshold');
  }
  private ensureSize(width:number,height:number):void {
    width=Math.max(1,Math.floor(width));height=Math.max(1,Math.floor(height));if(width===this.width&&height===this.height)return;const gl=this.gl;this.width=width;this.height=height;gl.bindTexture(gl.TEXTURE_2D,this.targetTexture);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,width,height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);gl.bindFramebuffer(gl.FRAMEBUFFER,this.framebuffer);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,this.targetTexture,0);if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw new Error('GPU picker framebuffer is incomplete');
  }
  pick(records:RuntimePickGeometry[],projection:ArrayLike<number>,pixelX:number,pixelY:number,width:number,height:number,{skipKeys=new Set<string>(),alphaThreshold=.03}={}):AttachmentPickResult|null {
    const gl=this.gl;if(!records.length)return null;
    const prevFramebuffer=gl.getParameter(gl.FRAMEBUFFER_BINDING) as WebGLFramebuffer|null,prevProgram=gl.getParameter(gl.CURRENT_PROGRAM) as WebGLProgram|null,prevArray=gl.getParameter(gl.ARRAY_BUFFER_BINDING) as WebGLBuffer|null,prevElement=gl.getParameter(gl.ELEMENT_ARRAY_BUFFER_BINDING) as WebGLBuffer|null,prevViewport=gl.getParameter(gl.VIEWPORT) as Int32Array,prevClearColor=gl.getParameter(gl.COLOR_CLEAR_VALUE) as Float32Array,prevActive=Number(gl.getParameter(gl.ACTIVE_TEXTURE)),blend=gl.isEnabled(gl.BLEND),depth=gl.isEnabled(gl.DEPTH_TEST),cull=gl.isEnabled(gl.CULL_FACE),scissor=gl.isEnabled(gl.SCISSOR_TEST),dither=gl.isEnabled(gl.DITHER),colorMask=gl.getParameter(gl.COLOR_WRITEMASK) as boolean[];
    gl.activeTexture(gl.TEXTURE0);const prevTex0=gl.getParameter(gl.TEXTURE_BINDING_2D) as WebGLTexture|null;gl.activeTexture(prevActive);const prevActiveTex=gl.getParameter(gl.TEXTURE_BINDING_2D) as WebGLTexture|null;
    const posState=this.aPosition>=0?captureAttrib(gl,this.aPosition):null,uvState=this.aUv>=0&&this.aUv!==this.aPosition?captureAttrib(gl,this.aUv):null;
    try{
      gl.activeTexture(gl.TEXTURE0);this.ensureSize(width,height);gl.bindFramebuffer(gl.FRAMEBUFFER,this.framebuffer);gl.viewport(0,0,width,height);gl.disable(gl.BLEND);gl.disable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);gl.disable(gl.SCISSOR_TEST);gl.disable(gl.DITHER);gl.colorMask(true,true,true,true);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.useProgram(this.program);gl.uniformMatrix4fv(this.uProjection,false,projection as any);gl.uniform1i(this.uTexture,0);gl.uniform1f(this.uAlphaThreshold,Math.max(0,Number(alphaThreshold)||0));gl.bindBuffer(gl.ARRAY_BUFFER,this.vertexBuffer);if(this.aPosition>=0)gl.enableVertexAttribArray(this.aPosition);if(this.aUv>=0)gl.enableVertexAttribArray(this.aUv);
      for(const record of records){
        if(skipKeys.has(record.key)||!record.texture?.bind)continue;const tri=record.triangles,expanded=new Float32Array(tri.length*4);for(let i=0;i<tri.length;i++){const vi=Number(tri[i]||0)*2,o=i*4;expanded[o]=record.positions[vi]||0;expanded[o+1]=record.positions[vi+1]||0;expanded[o+2]=record.uvs[vi]||0;expanded[o+3]=record.uvs[vi+1]||0;}gl.bufferData(gl.ARRAY_BUFFER,expanded,gl.STREAM_DRAW);if(this.aPosition>=0)gl.vertexAttribPointer(this.aPosition,2,gl.FLOAT,false,16,0);if(this.aUv>=0)gl.vertexAttribPointer(this.aUv,2,gl.FLOAT,false,16,8);const [r,g,b]=encodeId(record.id);gl.uniform3f(this.uId,r,g,b);gl.uniform1f(this.uAlpha,record.alpha);record.texture.bind(0);gl.drawArrays(gl.TRIANGLES,0,tri.length);
      }
      const x=Math.max(0,Math.min(width-1,Math.floor(pixelX))),y=Math.max(0,Math.min(height-1,Math.floor(pixelY))),pixel=new Uint8Array(4);gl.readPixels(x,height-1-y,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);const id=decodeId(pixel);if(!id)return null;const record=records.find(item=>item.id===id);return record?{...record,pixelX:x,pixelY:y}:null;
    }finally{
      gl.bindFramebuffer(gl.FRAMEBUFFER,prevFramebuffer);gl.viewport(Number(prevViewport[0]??0),Number(prevViewport[1]??0),Number(prevViewport[2]??width),Number(prevViewport[3]??height));gl.clearColor(Number(prevClearColor[0]??0),Number(prevClearColor[1]??0),Number(prevClearColor[2]??0),Number(prevClearColor[3]??0));gl.useProgram(prevProgram);if(blend)gl.enable(gl.BLEND);else gl.disable(gl.BLEND);if(depth)gl.enable(gl.DEPTH_TEST);else gl.disable(gl.DEPTH_TEST);if(cull)gl.enable(gl.CULL_FACE);else gl.disable(gl.CULL_FACE);if(scissor)gl.enable(gl.SCISSOR_TEST);else gl.disable(gl.SCISSOR_TEST);if(dither)gl.enable(gl.DITHER);else gl.disable(gl.DITHER);gl.colorMask(Boolean(colorMask[0]),Boolean(colorMask[1]),Boolean(colorMask[2]),Boolean(colorMask[3]));if(posState&&this.aPosition>=0)restoreAttrib(gl,this.aPosition,posState);if(uvState&&this.aUv>=0)restoreAttrib(gl,this.aUv,uvState);gl.bindBuffer(gl.ARRAY_BUFFER,prevArray);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,prevElement);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,prevTex0);gl.activeTexture(prevActive);gl.bindTexture(gl.TEXTURE_2D,prevActiveTex);
    }
  }
  dispose():void { const gl=this.gl;gl.deleteBuffer(this.vertexBuffer);gl.deleteTexture(this.targetTexture);gl.deleteFramebuffer(this.framebuffer);gl.deleteProgram(this.program); }
}

export function clientToCanvasPixel(canvas:HTMLCanvasElement,clientX:number,clientY:number):{x:number;y:number}|null { const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return null;return{x:(clientX-rect.left)*canvas.width/rect.width,y:(clientY-rect.top)*canvas.height/rect.height}; }

export function nearestMeshVertex(record:RuntimePickGeometry,clientX:number,clientY:number,worldToClient:(x:number,y:number)=>{x:number;y:number}|null,{radius=9,skipIndices=new Set<number>()}={}):{index:number;distance:number;x:number;y:number}|null {
  if(record.attachmentType!=='mesh')return null;let best:{index:number;distance:number;x:number;y:number}|null=null;for(let i=0;i<record.vertexCount;i++){if(skipIndices.has(i))continue;const p=worldToClient(record.sourcePositions[i*2]||0,record.sourcePositions[i*2+1]||0);if(!p)continue;const distance=Math.hypot(p.x-clientX,p.y-clientY);if(distance<=radius&&(!best||distance<best.distance))best={index:i,distance,x:p.x,y:p.y};}return best;
}

/** Returns un-clipped source geometry for one currently active slot attachment. Useful for selection overlays and vertex picking. */
export function sourceGeometryForSlot(skeleton:Skeleton,slotName:string):RuntimePickGeometry|null {
  const drawOrder=(skeleton as any).drawOrder as Slot[];
  const drawOrderIndex=drawOrder.findIndex((slot:any)=>String(slot?.data?.name||'')===String(slotName));if(drawOrderIndex<0)return null;const slot:any=drawOrder[drawOrderIndex];if(!slot?.bone?.active)return null;const attachment=slot.getAttachment?.()??slot.attachment;if(!attachment)return null;
  let sourcePositions:Float32Array,sourceUvs:Float32Array,sourceTriangles:number[],attachmentType:'region'|'mesh',hullVertexCount=0,weighted=false,texture:any=null,vertexInfluences:VertexInfluence[][]|null=null;
  if(attachment instanceof RegionAttachment){const world=new Float32Array(8);attachment.computeWorldVertices(slot,world,0,2);sourcePositions=copyPairs(world,8);sourceUvs=copyPairs(attachment.uvs,8);sourceTriangles=[...QUAD_TRIANGLES];attachmentType='region';hullVertexCount=4;texture=(attachment as any).region?.texture??null;}
  else if(attachment instanceof MeshAttachment){const length=Number(attachment.worldVerticesLength||0);if(length<6)return null;const world=new Float32Array(length);attachment.computeWorldVertices(slot,0,length,world,0,2);sourcePositions=copyPairs(world,length);sourceUvs=copyPairs(attachment.uvs,length);sourceTriangles=Array.from(attachment.triangles||[],Number);attachmentType='mesh';hullVertexCount=Math.max(0,Math.min(length/2,Math.floor(Number((attachment as any).hullLength||0)/2)));weighted=Array.isArray((attachment as any).bones)&&Boolean((attachment as any).bones?.length);vertexInfluences=weighted?meshVertexInfluences(skeleton,attachment):null;texture=(attachment as any).region?.texture??null;}
  else return null;
  const entry=resolveAttachmentEntry(skeleton,slot,attachment),attachmentName=entry.name;return{id:0,key:geometryKey(slotName,attachmentName,drawOrderIndex),slotName:String(slot.data?.name||''),boneName:String(slot.bone?.data?.name||''),attachmentName,runtimeAttachmentName:entry.runtimeName,skinName:entry.skinName,attachmentType,drawOrderIndex,alpha:attachmentAlpha(skeleton,slot,attachment),texture,positions:sourcePositions,uvs:sourceUvs,triangles:[...sourceTriangles],sourcePositions,sourceUvs,sourceTriangles,vertexCount:sourcePositions.length/2,hullVertexCount,weighted,clipped:false,renderVertexCount:sourcePositions.length/2,renderTriangleCount:Math.floor(sourceTriangles.length/3),vertexInfluences};
}

export interface MeshEdgeHit { a:number; b:number; distance:number; }
export interface MeshFaceHit { triangleIndex:number; indices:[number,number,number]; barycentric:[number,number,number]; }
function pointSegmentDistance(px:number,py:number,ax:number,ay:number,bx:number,by:number):number {const dx=bx-ax,dy=by-ay,len=dx*dx+dy*dy;if(len<=1e-12)return Math.hypot(px-ax,py-ay);const t=Math.max(0,Math.min(1,((px-ax)*dx+(py-ay)*dy)/len)),x=ax+dx*t,y=ay+dy*t;return Math.hypot(px-x,py-y);}
export function uniqueMeshEdges(geometry:RuntimePickGeometry):Array<[number,number]> {const seen=new Set<string>(),out:Array<[number,number]>=[];for(let i=0;i+2<geometry.sourceTriangles.length;i+=3){const tri=[geometry.sourceTriangles[i]!,geometry.sourceTriangles[i+1]!,geometry.sourceTriangles[i+2]!];for(let e=0;e<3;e++){const a=tri[e]!,b=tri[(e+1)%3]!,lo=Math.min(a,b),hi=Math.max(a,b),key=`${lo}:${hi}`;if(!seen.has(key)){seen.add(key);out.push([lo,hi]);}}}return out;}
export function nearestMeshEdge(geometry:RuntimePickGeometry,clientX:number,clientY:number,worldToClient:(x:number,y:number)=>{x:number;y:number}|null,{radius=10}: {radius?:number}={}):MeshEdgeHit|null {let best:MeshEdgeHit|null=null;for(const [a,b] of uniqueMeshEdges(geometry)){const pa=worldToClient(Number(geometry.sourcePositions[a*2]||0),Number(geometry.sourcePositions[a*2+1]||0)),pb=worldToClient(Number(geometry.sourcePositions[b*2]||0),Number(geometry.sourcePositions[b*2+1]||0));if(!pa||!pb)continue;const distance=pointSegmentDistance(clientX,clientY,pa.x,pa.y,pb.x,pb.y);if(distance<=radius&&(!best||distance<best.distance))best={a,b,distance};}return best;}
function barycentricPoint(px:number,py:number,ax:number,ay:number,bx:number,by:number,cx:number,cy:number):[number,number,number]|null {const v0x=bx-ax,v0y=by-ay,v1x=cx-ax,v1y=cy-ay,v2x=px-ax,v2y=py-ay,den=v0x*v1y-v1x*v0y;if(Math.abs(den)<1e-12)return null;const b=(v2x*v1y-v1x*v2y)/den,c=(v0x*v2y-v2x*v0y)/den,a=1-b-c;return[a,b,c];}
export function meshFaceAtWorld(geometry:RuntimePickGeometry,x:number,y:number):MeshFaceHit|null {for(let i=geometry.sourceTriangles.length-3;i>=0;i-=3){const a=geometry.sourceTriangles[i]!,b=geometry.sourceTriangles[i+1]!,c=geometry.sourceTriangles[i+2]!,p=(idx:number)=>[Number(geometry.sourcePositions[idx*2]||0),Number(geometry.sourcePositions[idx*2+1]||0)] as const,[ax,ay]=p(a),[bx,by]=p(b),[cx,cy]=p(c),weights=barycentricPoint(x,y,ax,ay,bx,by,cx,cy);if(weights&&weights.every(value=>value>=-1e-7&&value<=1+1e-7))return{triangleIndex:i/3,indices:[a,b,c],barycentric:weights};}return null;}
