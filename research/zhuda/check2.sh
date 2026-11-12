KIT=${KIT:-$(cd "$(dirname "$0")/../.." && pwd)}
# Zhuda-shape models: paint + reskin + close turntable.  usage: check2.sh model [anim n]
set -e
cd $KIT
. work/zhuda/env.sh
export ZHUDA_MODELS=$KIT/work/zhuda/models
m=$1; anim=${2:-turntable}; n=${3:-8}; d=$ZHUDA_MODELS/$m
python3 work/zhuda/run.py $m | tail -1
python3 spk.py reskin $d --skin zhuda > $d/_reskin.json 2>&1 || { cat $d/_reskin.json; exit 1; }
python3 -c "import json;d=json.load(open('$d/_reskin.json'));print('$m reskin ok',d['ok'],'warn',d['warnings'][:3],'low',d['lowest_cover'][:2])"
F=$(python3 work/zhuda/frame.py $m)
python3 spk.py --skin zhuda sheet $d --anim $anim --n $n --frame=$F --tag close --cols 4 2>&1 | grep '"sheet"'
