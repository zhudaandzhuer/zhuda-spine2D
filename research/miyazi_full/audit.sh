KIT=${KIT:-$(cd "$(dirname "$0")/../.." && pwd)}
cd $KIT
. work/zhuda/env.sh
P=work/miyazi_full
B=$(python3 spk.py build $P --note "${1:-audit}" 2>&1 | python3 -c "import json,sys;print(json.load(sys.stdin)['build'])")
cp $P/flipaudit.mjs tools/_fa.mjs
node tools/_fa.mjs $P/build/$B/miyazi_full.json $P/build/$B/miyazi_full.atlas | python3 -c "
import json,sys; d=json.load(sys.stdin)
tot=0
for a,v in d.items():
  for k,e in v.items(): tot+=e['flipFrames']; print('$B',a,k.split('/')[0],'frames',e['flipFrames'],'max',e['maxFlips'],'t',e['worstT'])
print('$B TOTAL flip frames',tot)"
rm tools/_fa.mjs
