import fs from 'node:fs';
import { PNG } from 'pngjs';
import { alphaStatsPixels, compareSilhouettePixels } from './imageQaCore.js';
function load(file){return PNG.sync.read(fs.readFileSync(file));}
export function compareSilhouettes(referenceFile,candidateFile,{threshold=8,size=128,diffOut=null}={}){const r=load(referenceFile),c=load(candidateFile),result=compareSilhouettePixels(r,c,{threshold,size,includeDiff:!!diffOut});if(diffOut&&result.diffData){const png=new PNG({width:size,height:size});png.data=Buffer.from(result.diffData);fs.writeFileSync(diffOut,PNG.sync.write(png));}return {reference:{file:referenceFile,...result.reference},candidate:{file:candidateFile,...result.candidate},normalized:result.normalized,diffOut};}
export const alphaStats=alphaStatsPixels;
