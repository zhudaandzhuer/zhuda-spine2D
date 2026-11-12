KIT=${KIT:-$(cd "$(dirname "$0")/../.." && pwd)}
# usage: check.sh model [anim n]
set -e
cd $KIT
. work/zhuda/env.sh
m=$1; anim=${2:-turntable}; n=${3:-8}
python3 work/zhuda/run.py $m | tail -1
python3 spk.py reskin examples/whitemodels/$m --skin zhuda > work/zhuda/out_reskin_$m.json 2>&1 || { cat work/zhuda/out_reskin_$m.json; exit 1; }
python3 -c "import json;d=json.load(open('work/zhuda/out_reskin_$m.json'));print('$m reskin ok',d['ok'],'warn',d['warnings'][:4],'low',d['lowest_cover'][:2])"
F=$(python3 work/zhuda/frame.py $m)
python3 spk.py --skin zhuda sheet examples/whitemodels/$m --anim $anim --n $n --frame $F --tag close --cols 4 2>&1 | grep '"sheet"'
