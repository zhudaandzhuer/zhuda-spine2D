import json,sys
m=sys.argv[1]; part=sys.argv[2] if len(sys.argv)>2 else 'full'
import os,glob; R=os.environ.get('ZHUDA_MODELS','examples/whitemodels'); c=json.load(open(sorted(glob.glob(f'{R}/{m}/build/*/{m}.contract.json'))[-1]))
ox,oy=c['source']['origin']; fp=c['frame_portrait']
top=fp['y']+fp['height']
if part=='wide':
    y0,y1=-30,top-30; h=y1-y0; w=h*16/9
    print(f"{ox-w/2:.0f},{oy-y1:.0f},{w:.0f},{h:.0f}"); sys.exit()
if part=='full': y0,y1=-20,top-40
else: y0,y1=top-0.42*(top+50)-40, top-40   # head & shoulders
h=y1-y0; w=h*0.8
print(f"{ox-w/2:.0f},{oy-y1:.0f},{w:.0f},{h:.0f}")
