KIT=${KIT:-$(cd "$(dirname "$0")/../.." && pwd)}
cd $KIT
. work/zhuda/env.sh
P=work/miyazi_full
B=$(python3 spk.py build $P --note "${1:-probe}" 2>&1 | python3 -c "import json,sys;print(json.load(sys.stdin)['build'])")
read GY HX HY <<< $(python3 -c "
import json;m={q['name']:q for q in json.load(open('$P/parts/manifest.json'))['parts']};r=json.load(open('$P/parts-report.json'))
print(max(m[n]['y']+m[n]['h'] for n in ('leg_far','leg_near'))-4, r['held_apple'][0], r['held_apple'][1])")
cp $P/probe.mjs tools/_probe.mjs
node tools/_probe.mjs $P/build/$B/miyazi_full.json $P/build/$B/miyazi_full.atlas ${2:-1.05} $HX $HY 448 $GY
rm tools/_probe.mjs
echo "build $B"
