#!/usr/bin/env python3
"""Sample actual attachment boundary times plus nearby frames; add regular motion samples."""
import argparse, json
from pathlib import Path
from spine_common import dump


def all_times(v):
    if isinstance(v, dict):
        if isinstance(v.get('time'), (int,float)): yield v['time']
        for x in v.values(): yield from all_times(x)
    elif isinstance(v, list):
        for x in v: yield from all_times(x)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('skeleton',type=Path)
    p.add_argument('--animations',nargs='+',required=True)
    p.add_argument('--fps',type=int,default=60)
    p.add_argument('--neighbors',type=int,default=2)
    p.add_argument('--samples',type=int,default=9)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.fps<1 or a.neighbors<0 or a.samples<2 or a.out.exists(): p.error('Positive fps, neighbors>=0, samples>=2 and new output required')
    j=json.loads(a.skeleton.read_text());frames=[]
    for name in a.animations:
        if name not in j.get('animations',{}): p.error('Unknown animation: '+name)
        anim=j['animations'][name];duration=max([0,*all_times(anim)])
        times={duration*i/(a.samples-1) for i in range(a.samples)}
        for tracks in anim.get('slots',{}).values():
            for key in tracks.get('attachment',[]):
                base=key.get('time',0)
                for d in range(-a.neighbors,a.neighbors+1): times.add(max(0,min(duration,base+d/a.fps)))
        for t in sorted(times): frames.append({'animation':name,'time':t})
    dump(a.out,{'fps_reference':a.fps,'frames':frames})
    print(f'{len(frames)} requested native samples; not a runtime FPS claim')


if __name__=='__main__': main()
