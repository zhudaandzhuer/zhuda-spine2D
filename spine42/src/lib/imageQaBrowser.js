import { compareSilhouettePixels } from './imageQaCore.js';
async function drawableToPixels(drawable,width,height){const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.clearRect(0,0,width,height);ctx.drawImage(drawable,0,0,width,height);return {width,height,data:ctx.getImageData(0,0,width,height).data};}
export async function imageFilePixels(file){const bitmap=await createImageBitmap(file);try{return await drawableToPixels(bitmap,bitmap.width,bitmap.height)}finally{bitmap.close?.()}}
export async function canvasPixels(canvas){const bitmap=await createImageBitmap(canvas);try{return await drawableToPixels(bitmap,bitmap.width,bitmap.height)}finally{bitmap.close?.()}}
export async function compareReferenceFileToCanvas(file,canvas,options={}){const [ref,candidate]=await Promise.all([imageFilePixels(file),canvasPixels(canvas)]);return compareSilhouettePixels(ref,candidate,options);}
