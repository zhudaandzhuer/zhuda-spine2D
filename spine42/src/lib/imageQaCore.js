export function alphaStatsPixels(png,threshold=8){
  let minX=png.width,minY=png.height,maxX=-1,maxY=-1,area=0,sx=0,sy=0;const data=png.data;
  for(let y=0;y<png.height;y++)for(let x=0;x<png.width;x++){const a=data[(y*png.width+x)*4+3];if(a<=threshold)continue;area++;sx+=x;sy+=y;if(x<minX)minX=x;if(y<minY)minY=y;if(x>maxX)maxX=x;if(y>maxY)maxY=y;}
  if(!area)return {empty:true,bbox:null,area:0,centroid:null,width:0,height:0};
  return {empty:false,bbox:[minX,minY,maxX+1,maxY+1],area,centroid:{x:sx/area,y:sy/area},width:maxX-minX+1,height:maxY-minY+1};
}
function maskAt(png,x,y,threshold){if(x<0||y<0||x>=png.width||y>=png.height)return 0;return png.data[(y*png.width+x)*4+3]>threshold?1:0;}
function normalizedMask(png,stats,size=128,threshold=8){const out=new Uint8Array(size*size);if(stats.empty)return out;const [x0,y0,x1,y1]=stats.bbox,w=Math.max(1,x1-x0),h=Math.max(1,y1-y0);for(let j=0;j<size;j++)for(let i=0;i<size;i++){const x=Math.min(x1-1,Math.max(x0,Math.floor(x0+(i+.5)/size*w))),y=Math.min(y1-1,Math.max(y0,Math.floor(y0+(j+.5)/size*h)));out[j*size+i]=maskAt(png,x,y,threshold)}return out;}
export function compareSilhouettePixels(reference,candidate,{threshold=8,size=128,includeDiff=false}={}){
  const rs=alphaStatsPixels(reference,threshold),cs=alphaStatsPixels(candidate,threshold),rm=normalizedMask(reference,rs,size,threshold),cm=normalizedMask(candidate,cs,size,threshold);let inter=0,union=0,ra=0,ca=0,diff=0;
  for(let i=0;i<rm.length;i++){const a=rm[i],b=cm[i];if(a)ra++;if(b)ca++;if(a&&b)inter++;if(a||b)union++;if(a!==b)diff++;}
  const iou=union?inter/union:1,dice=(ra+ca)?2*inter/(ra+ca):1,rn=rs.centroid?{x:rs.centroid.x/reference.width,y:rs.centroid.y/reference.height}:null,cn=cs.centroid?{x:cs.centroid.x/candidate.width,y:cs.centroid.y/candidate.height}:null,centroidDistance=rn&&cn?Math.hypot(rn.x-cn.x,rn.y-cn.y):null,bboxAspectDelta=rs.width&&rs.height&&cs.width&&cs.height?Math.abs(rs.width/rs.height-cs.width/cs.height):null;
  let diffData=null;if(includeDiff){diffData=new Uint8ClampedArray(size*size*4);for(let i=0;i<rm.length;i++){const o=i*4,a=rm[i],b=cm[i];diffData[o]=a&&!b?255:0;diffData[o+1]=b&&!a?255:(a&&b?180:0);diffData[o+2]=0;diffData[o+3]=(a||b)?255:0;}}
  return {reference:{...rs,image:{width:reference.width,height:reference.height}},candidate:{...cs,image:{width:candidate.width,height:candidate.height}},normalized:{size,iou,dice,maskDifference:diff/rm.length,centroidDistance,bboxAspectDelta},diffData};
}
