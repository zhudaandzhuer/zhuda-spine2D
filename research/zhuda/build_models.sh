KIT=${KIT:-$(cd "$(dirname "$0")/../.." && pwd)}
cd $KIT
. work/zhuda/env.sh
for m in ${MODELS:-hero heroine chibi brute mascot knight mage vtuber}; do
  d=work/zhuda/models/$m
  python3 spk.py art $d > $d/_art.json 2>&1 || { echo "$m art FAIL"; continue; }
  python3 spk.py build $d --note "zhuda shape" > $d/_build.json 2>&1 || { echo "$m build FAIL"; continue; }
  python3 spk.py check $d > $d/_check.json 2>&1; python3 -c "import json;d=json.load(open('$d/_check.json'));print('$m check errors',len(d.get('errors',[])),'warnings',len(d.get('warnings',[])))"
  python3 spk.py skin $d > $d/_skin.json 2>&1 && echo "$m skin template ok" || echo "$m skin FAIL"
done
echo BUILDDONE
