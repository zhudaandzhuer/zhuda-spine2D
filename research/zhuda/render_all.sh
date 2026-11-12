KIT=${KIT:-$(cd "$(dirname "$0")/../.." && pwd)}
cd $KIT
. work/zhuda/env.sh
OUT=${OUT:-work/zhuda/series}
R=${ZHUDA_MODELS:-examples/whitemodels}
COMMON="idle@0;walk@0.8~0.2;turn@2.6~0.2;walk@4.1~0.2;turn@5.9~0.2;run@7.4~0.2;wave@8.4~0.3;jump@11.2~0.2;kungfu@12.7~0.3;dance@18.8~0.3"
cues() { case $1 in
  knight) echo "idle@0;walk@0.8~0.2;turn@2.6~0.2;walk@4.1~0.2;turn@5.9~0.2;block@7.4~0.2;slash@9~0.2;bash@10.5~0.2;idle@11.7~0.3 13";;
  mage) echo "idle@0;walk@0.8~0.2;turn@2.6~0.2;walk@4.1~0.2;turn@5.9~0.2;cast@7.4~0.2;channel@9.8~0.2;idle@12.2~0.3 13.4";;
  vtuber) echo "front_idle@0;greet@1~0.2;talk@4.2~0.2;heart@7.4~0.2;spin@10.2~0.2;cheer@12.2~0.2;front_idle@14.6~0.3 15.5";;
  *) echo "$COMMON 25.5";;
esac; }
for m in ${MODELS:-hero heroine chibi brute mascot knight mage vtuber}; do
  mkdir -p $OUT/$m
  python3 spk.py --skin zhuda stress $R/$m > $OUT/$m/stress.json 2>&1 && echo "$m stress ok" || echo "$m stress FAIL"
  set -- $(cues $m); C=$1; D=$2
  python3 spk.py --skin zhuda play $R/$m --cues "$C" --duration $D --size 1280x720 --start-x -250 --frame=$(python3 work/zhuda/frame.py $m wide) --mp4 $OUT/$m/zhuda_$m.mp4 --sheet 16 > $OUT/$m/play.json 2>&1 && echo "$m play ok" || echo "$m play FAIL"
  python3 spk.py --skin zhuda export $R/$m --zip $OUT/$m/zhuda_$m.zip --html $OUT/$m/zhuda_$m.html --title "豬大 · $m" > $OUT/$m/export.json 2>&1 && echo "$m export ok" || echo "$m export FAIL"
done
