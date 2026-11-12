# 38 換皮：把白模變成有美術的角色

白模是一副已經會動的骨架＋一組白色圖片。換皮只換圖片：**骨架 JSON 與動畫不動**，產出的是另一份 atlas。這份文件給負責做換皮測試的 agent。

## 你手上有什麼

```
examples/whitemodels/<model>/
  build/NNN/<model>.json  .atlas  .png          白模 runtime
  build/NNN/<model>.skin.json                   換皮規格：每一張圖是什麼
  build/NNN/bake-report.json                    烘焙時的邊界報告
  skin/template/*.png  skin/skin.json  skin/GUIDE.md  skin/template_sheet.png     ← 模板（`spk skin <model>` 產生）
```

八個白模：`hero` `heroine` `chibi` `brute` `mascot` `knight` `mage` `vtuber`（見 `examples/whitemodels/README.md`）。`vtuber` 的臉是零件加狀態圖，見 `39-front-performer.md`。

## 流程

```sh
python3 spk.py skin   examples/whitemodels/hero            # 匯出模板到 skin/
python3 spk.py skin   examples/whitemodels/hero --debug    # 先看除錯皮：確認視角切換與左右
#   …在 examples/whitemodels/hero/skins/<皮名>/ 放入同名圖片…
python3 spk.py reskin examples/whitemodels/hero --skin <皮名> [--fill]
python3 spk.py --skin <皮名> sheet  examples/whitemodels/hero --anim turntable --n 8
python3 spk.py --skin <皮名> stress examples/whitemodels/hero
python3 spk.py --skin <皮名> play   examples/whitemodels/hero --cues "idle@0;walk@0.5;turn@2.2;walk@3.7;wave@5" --duration 8 --mp4 out.mp4
python3 spk.py --skin <皮名> export examples/whitemodels/hero --html preview.html --zip runtime.zip
```

`--skin` 要放在指令**前面**。皮的產物在 `build/NNN/skins/<皮名>/`，是完整的一組 runtime（同一份 JSON＋新的 atlas／png）。

## 每張圖的規則

1. 檔名＝attachment 名；**長寬比與模板相同**（不同就拒絕：軸心會跑掉）。解析度可以整數倍，全部一致。
2. 白色形狀的位置與大小就是零件的位置與大小。四周透明留白可以畫出去（頭髮、衣襬），主體不要移開、不要縮小。
3. **蓋滿白色形狀**。關節靠零件互相重疊遮住。`reskin` 回報 `covers_white_shape`；低於 0.6 會警告，那個關節多半會露縫。
4. 不透明實體、乾淨透明邊；不要柔邊半透明、不要陰影、不要背景色。
5. 視角零件 8 張（`_v0` F 正面、`_v1` FR、`_v2` R 右側、`_v3` BR、`_v4` B 背面、`_v5` BL、`_v6` L、`_v7` FL）。「右」＝零件朝向畫面右。左右對稱的角色可以只給 `_v0`–`_v4`，`_v5/6/7` 會由 `_v3/2/1` 水平翻轉；腳一律要給 8 張（左右腳本身不對稱）。
6. 管狀肢段、關節球、手、多數配件各 1 張，各角度共用：畫成繞自身軸大致對稱。例外是有正反面的配件：`knight` 的盾有 8 張（`shield_v0` 是盾面正對鏡頭、`_v4` 是盾背、`_v2/_v6` 是側看的薄片）。
   劍、法杖、長袍、帽尖這類長條零件，模板是「真實長度、直的」；照模板的方向畫。
7. 平光。遠側變暗是程式加的。

## 產圖建議（用影像模型時）

- 先生成一張角色的**轉身設定圖**（正、3/4、側、背，同比例同光線），通過再往下做。五官、髮型、服裝細節以這張為準。
- 逐零件、逐視角用「編輯」方式產生：以模板圖為構圖參考（同畫布、同位置、同大小），以設定圖為造型參考。提示詞固定寫明：solid flat background of a colour the character lacks、fully opaque、no shadow、same framing as the reference。
- 產出後用 `python3 spk.py key IMG --out OUT` 去背（或直接要求透明並自己檢查），再放進 `skins/<皮名>/`。
- 分批做：先頭（8 張）＋軀幹，`reskin --fill` 用白模補其餘，轉一圈看；再做四肢與腳。

## 驗收（照順序，不過就停）

| 閘門 | 做什麼 | 通過條件 |
|---|---|---|
| S0 除錯皮 | `spk skin --debug` → `--skin debug sheet --anim turntable --n 8` | 每格的戳記（F/FR/R/…）與角色朝向一致；藍色（左側零件）在角色的左邊 |
| S1 規格 | `spk reskin` | `ok: true`；沒有 missing／proportions 錯誤；看過 warnings |
| S2 靜態 | `--skin X shot`（setup）＋ `stress` | 正面站姿沒有露縫、沒有髒邊；關鍵姿勢關節處沒有破口 |
| S3 轉一圈 | `--skin X sheet --anim turntable --n 16` | 8 個視角的圖都出現過且方向正確；切換前後大小、位置連續 |
| S4 動作 | `--skin X play …` 走、跑、轉身、揮手、武打各一段，看 mp4 與時序圖 | 沒有零件方向錯、沒有長時間露縫；不對稱配件沒有換邊 |
| S5 邊界 | 對照 `bake-report.json` 的 `flicker` 時間點逐格看 | 視角來回跳不刺眼（刺眼就記下時間與零件）|

回報格式：每個閘門 PASS／FAIL＋證據圖路徑；FAIL 寫明是哪個 attachment、哪個 clip 的哪個時間。**先判斷是圖的問題還是白模的問題**：除錯皮正常而你的皮不正常＝圖的問題；除錯皮也不正常＝白模的問題，附上時間點回報。

## 已知會遇到的事

- 視角切換是「跳圖」。差異大的設計（側臉 vs 3/4 臉）會看得出跳；這是多視角 2D 的本質，不是錯誤。8 個視角不夠細時，可以回報需要加密的零件。
- 四肢單張圖：有單側圖案的袖子，轉到背面時圖案還在同一邊。
- 動作中途被打斷時（例如跳舞跳到一半切走路），頭或軀幹可能短暫變形。
- 朝左：對稱身體是整副骨架鏡射；不對稱身體（`brute`、`mascot`）用 `_L` clip，不鏡射。
- 配件（馬尾、披風、包）是白模的體積，換皮時每節一張圖；它們會穿過身體，沒有碰撞。
