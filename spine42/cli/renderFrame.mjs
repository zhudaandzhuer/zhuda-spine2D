import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import { TextureAtlas, AtlasAttachmentLoader, SkeletonJson } from '@esotericsoftware/spine-webgl';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEFAULT_RENDER_SERVER = 'http://127.0.0.1:4328/';
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

function parseAtlasPages(text) {
  const lines = text.replace(/\r/g,'').split('\n');
  const pages=[];
  for(let i=0;i<lines.length;i++){
    const line=lines[i].trim(); if(!line || line.includes(':')) continue;
    let j=i+1; while(j<lines.length && !lines[j].trim()) j++;
    if(/^size\s*:/i.test(lines[j]?.trim()||'')) pages.push(line);
  }
  return [...new Set(pages)];
}
async function alive(url){ try { const r=await fetch(url); return r.ok; } catch { return false; } }
async function ensureServer(url){
  if(await alive(url)) return null;
  const u=new URL(url),host=u.hostname||'127.0.0.1',port=u.port||'80';
  const child=spawn(process.execPath,[path.join(ROOT,'node_modules/vite/bin/vite.js'),'--host',host,'--port',port],{cwd:ROOT,stdio:'ignore'});
  const start=Date.now();
  while(Date.now()-start<12000){ if(await alive(url)) return child; await new Promise(r=>setTimeout(r,120)); }
  child.kill('SIGTERM'); throw new Error('Unable to start workstation server');
}
function runtimeDuration(jsonPath,atlasPath,anim){
  const raw=JSON.parse(fs.readFileSync(jsonPath,'utf8'));
  const atlas=new TextureAtlas(fs.readFileSync(atlasPath,'utf8'));
  try { const data=new SkeletonJson(new AtlasAttachmentLoader(atlas)).readSkeletonData(raw); const a=data.findAnimation(anim); if(!a) throw new Error(`Animation not found: ${anim}`); return a.duration; }
  finally { atlas.dispose?.(); }
}
function writeDataUrl(file,dataUrl){
  fs.mkdirSync(path.dirname(path.resolve(file)),{recursive:true});
  fs.writeFileSync(file,Buffer.from(dataUrl.replace(/^data:image\/png;base64,/,''),'base64'));
}
async function openRenderSession({jsonPath,atlasPath,animation,server}){
  if(!fs.existsSync(CHROME)) throw new Error('Google Chrome executable not found');
  const atlasText=fs.readFileSync(atlasPath,'utf8');
  const dir=path.dirname(atlasPath);
  const pageNames=parseAtlasPages(atlasText);
  const pages=pageNames.map(name=>path.join(dir,name));
  for(const p of [jsonPath,atlasPath,...pages]) if(!fs.existsSync(p)) throw new Error(`Missing render input: ${p}`);
  const duration=runtimeDuration(jsonPath,atlasPath,animation);
  const staging=fs.mkdtempSync(path.join(os.tmpdir(),'zhuda-spine-render-'));
  const stagedJson=path.join(staging,'render.json');
  const stagedAtlas=path.join(staging,'render.atlas');
  fs.copyFileSync(jsonPath,stagedJson); fs.copyFileSync(atlasPath,stagedAtlas);
  const stagedPages=[];
  for(let i=0;i<pages.length;i++){ const dst=path.join(staging,pageNames[i]); fs.mkdirSync(path.dirname(dst),{recursive:true}); fs.copyFileSync(pages[i],dst); stagedPages.push(dst); }
  const serverProc=await ensureServer(server);
  const browser=await chromium.launch({headless:true,executablePath:CHROME,args:['--use-gl=angle','--use-angle=metal','--disable-gpu-sandbox']});
  try{
    const page=await browser.newPage({viewport:{width:1400,height:1000},deviceScaleFactor:1});
    await page.goto(server,{waitUntil:'domcontentloaded'});
    await page.locator('#filesInput').setInputFiles([stagedJson,stagedAtlas,...stagedPages]);
    await page.waitForFunction(() => window.zhudaSpine?.getState?.().project && !document.querySelector('#animationSelect')?.disabled,{timeout:12000});
    await page.evaluate(animation=>window.zhudaSpine.setAnimation(animation),animation);
    return {page,browser,serverProc,staging,duration,pageCount:pages.length};
  } catch(error){
    await browser.close(); if(serverProc) serverProc.kill('SIGTERM'); fs.rmSync(staging,{recursive:true,force:true}); throw error;
  }
}
async function closeSession(s){
  await s.browser.close(); if(s.serverProc) s.serverProc.kill('SIGTERM'); fs.rmSync(s.staging,{recursive:true,force:true});
}
async function seekAndCapture(page,time){
  await page.evaluate(time=>window.zhudaSpine.seek(time),time);
  await page.waitForTimeout(50);
  return await page.evaluate(()=>window.zhudaSpine.cleanCanvasPngDataUrl?.() ?? window.zhudaSpine.canvasPngDataUrl());
}

export async function renderFrame({jsonPath,atlasPath,animation,time=0,out,server=DEFAULT_RENDER_SERVER}){
  const s=await openRenderSession({jsonPath,atlasPath,animation,server});
  try{
    const clamped=Math.min(Math.max(0,Number(time)||0),s.duration);
    const dataUrl=await seekAndCapture(s.page,clamped); writeDataUrl(out,dataUrl);
    const details=await s.page.evaluate(()=>({state:window.zhudaSpine.getState(),pose:window.zhudaSpine.pose(5),timelineRows:document.querySelectorAll('.timeline-row').length,poseRows:document.querySelectorAll('.pose-row').length}));
    return {ok:true,out:path.resolve(out),...details,pages:s.pageCount};
  } finally { await closeSession(s); }
}

export async function renderSequence({jsonPath,atlasPath,animation,frames=7,outDir,server=DEFAULT_RENDER_SERVER}){
  frames=Math.max(2,Math.min(25,Math.round(Number(frames)||7)));
  const s=await openRenderSession({jsonPath,atlasPath,animation,server});
  try{
    fs.mkdirSync(outDir,{recursive:true});
    const times=Array.from({length:frames},(_,i)=>s.duration*i/(frames-1));
    const urls=[]; const files=[];
    for(let i=0;i<times.length;i++){
      const url=await seekAndCapture(s.page,times[i]); urls.push(url);
      const file=path.join(outDir,`frame_${String(i).padStart(2,'0')}_${times[i].toFixed(3)}s.png`); writeDataUrl(file,url); files.push(path.resolve(file));
    }
    const contactUrl=await s.page.evaluate(async ({urls,times})=>{
      const imgs=await Promise.all(urls.map(src=>new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;img.src=src;})));
      const cols=Math.min(4,imgs.length), rows=Math.ceil(imgs.length/cols), cellW=300, labelH=25;
      const ratio=imgs[0].height/Math.max(1,imgs[0].width), cellH=Math.round(cellW*ratio);
      const c=document.createElement('canvas'); c.width=cols*cellW; c.height=rows*(cellH+labelH); const ctx=c.getContext('2d');
      ctx.fillStyle='#12161c'; ctx.fillRect(0,0,c.width,c.height);
      for(let i=0;i<imgs.length;i++){
        const col=i%cols,row=Math.floor(i/cols),x=col*cellW,y=row*(cellH+labelH);
        const tile=16; ctx.fillStyle='#171c22'; ctx.fillRect(x,y,cellW,cellH); ctx.fillStyle='#1d232b';
        for(let yy=0;yy<cellH;yy+=tile) for(let xx=0;xx<cellW;xx+=tile) if(((xx/tile+yy/tile)&1)===0) ctx.fillRect(x+xx,y+yy,tile,tile);
        const scale=Math.min(cellW/imgs[i].width,cellH/imgs[i].height); const w=imgs[i].width*scale,h=imgs[i].height*scale;
        ctx.drawImage(imgs[i],x+(cellW-w)/2,y+(cellH-h)/2,w,h);
        ctx.fillStyle='#0c0f13';ctx.fillRect(x,y+cellH,cellW,labelH);ctx.fillStyle='#d8e0ea';ctx.font='13px sans-serif';ctx.fillText(`${i+1}/${imgs.length}  ${times[i].toFixed(3)}s`,x+8,y+cellH+17);
      }
      return c.toDataURL('image/png');
    },{urls,times});
    const contact=path.join(outDir,'contact_sheet.png'); writeDataUrl(contact,contactUrl);
    return {ok:true,animation,duration:s.duration,frames:files,contact:path.resolve(contact),times,pages:s.pageCount};
  } finally { await closeSession(s); }
}
