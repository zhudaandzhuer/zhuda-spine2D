#!/usr/bin/env python3
"""Compare native captures and create same-scale contact sheets; does not claim Visual PASS."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from spine_common import dump


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--crop',help='Optional x,y,width,height applied identically to both images')
    p.add_argument('--tile-width',type=int,default=480)
    args=p.parse_args()
    if args.out.exists() or args.tile_width<1:p.error('Output must be new; tile-width positive')
    before=json.loads((args.before/'capture.json').read_text());after=json.loads((args.after/'capture.json').read_text())
    if before['viewport']!=after['viewport'] or before['dpr']!=after['dpr']:p.error('Capture viewport/DPR differ')
    plan = lambda frames: [{k: f[k] for k in ('animation','time','file')} for f in frames]
    if plan(before['frames'])!=plan(after['frames']):p.error('Capture action/time/file plans differ')
    box=None
    if args.crop:
        x,y,w,h=map(int,args.crop.split(','))
        if min(x,y)<0 or min(w,h)<=0:p.error('Invalid crop')
        box=x,y,x+w,y+h
    args.out.mkdir(parents=True);stats=[];pairs=[]
    for index,f in enumerate(before['frames']):
        a=Image.open(args.before/f['file']).convert('RGB');b=Image.open(args.after/f['file']).convert('RGB')
        if a.size!=b.size:raise ValueError('Mismatched image dimensions')
        if box:
            if box[2]>a.width or box[3]>a.height:raise ValueError('Crop exceeds image bounds')
            a=a.crop(box);b=b.crop(box)
        d=np.abs(np.asarray(a).astype(np.int16)-np.asarray(b).astype(np.int16))
        stats.append({**f,'max_channel_delta':int(d.max()),'mean_abs_delta':float(d.mean()),'pixels_over_8':int(np.any(d>8,axis=2).sum())})
        size=(args.tile_width,max(1,round(a.height*args.tile_width/a.width)))
        pair=Image.new('RGB',(size[0]*2,size[1]+24),'#eee8f0');draw=ImageDraw.Draw(pair)
        for col,(im,label) in enumerate([(a,'BEFORE'),(b,'AFTER')]):
            pair.paste(im.resize(size),(col*size[0],24));draw.text((col*size[0]+4,4),f'{label} {index} {f["animation"]} {f["time"]:.4f}s',fill='black')
        pairs.append(pair)
        if len(pairs)==4 or index==len(before['frames'])-1:
            sheet=Image.new('RGB',(pairs[0].width,sum(q.height for q in pairs)),'white');y=0
            for q in pairs:sheet.paste(q,(0,y));y+=q.height
            sheet.save(args.out/f'contact-{index//4:04}.jpg',quality=94);pairs=[]
    dump(args.out/'comparison.json',{'frames':stats,'visual_verdict':'NOT_EVALUATED','required':'Open native/contact images and inspect worst local differences before assigning a verdict'})
    print(f'{len(stats)} comparisons saved. Visual observation still required.')


if __name__=='__main__':main()
