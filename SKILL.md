---
name: spine2d-master
description: "從零製作、接續或修復 Spine 4.2 的 2D 骨骼角色：分層美術（程序化 SVG 或既有 PNG）→ 骨架／加權網格／約束／物理 → 動畫 → 原生 WebGL 驗證 → 發布包。附一個命令列 `spk.py` 涵蓋建置、原生截圖、數值閘門與匯出。適用：要把角色圖或角色描述做成可在 Spine runtime（spine-webgl、LayaAir、Unity…）播放的資產，或修復既有 Spine JSON 的比例、白邊、滑步、抽動。不適用：純靜態插畫、3D 骨架、逐格影片。"
---

# Spine2D Master

把角色做成**在目標 runtime 裡真正成立**的資產。你唯一需要記住的入口是這份文件和 `python3 spk.py`。

## 0. 三條不可違反的規則

1. **先看圖，再下一步。** 每個可見修改都要走：看修改前的原生畫面 → 寫下觀察 → 假設 → 只改一件事 → `spk` 重新截圖 → **實際打開圖片** → 判定 `IMPROVED / UNCHANGED / WORSE`。指令成功、JSON 合法、數值閘門通過，都不是「看起來對」的證據。
2. **原生畫面才是證據。** `spk shot / sheet / stress / play / fidelity` 用官方 Spine WebGL 4.2 渲染，是驗收依據；`spk software` 只是診斷。
3. **同一假設最多兩次。** 第二次仍 `UNCHANGED / WORSE` 就停止微調，重新分類根因（見 `docs/50-failure-playbook.md`）。

把每一輪寫進專案的 `WORKLOG.md`（模板已附）；跨會話接手時先讀它。

## 1. 先分流

| 手上有什麼 | 走哪條路 |
|---|---|
| 角色描述或參考圖，沒有骨架 | **新角色流程**（下方 §2） |
| 影像模型生成的圖、手繪稿（平面圖或一層一張） | 新角色流程，S1/S2 改走 `spk layers`：去背、對位、切割、接縫檢查（`docs/15-imagegen-layers.md`） |
| 已分層且有真 alpha 的 PNG | 新角色流程，從 S2 開始：放進 `parts/` 並寫 `parts/manifest.json`（格式見 `docs/10-art.md`） |
| 既有 Spine JSON / atlas / PNG | **既有骨架流程**：`docs/70-existing-rigs.md` |
| 只要查某個症狀 | `docs/50-failure-playbook.md` |

第一次在這台機器使用：`python3 spk.py doctor`（唯讀；缺什麼會列出來）。

## 2. 新角色流程：六個階段，每段有閘門

```
S0 Brief ─▶ S1 Key art ─▶ S2 Parts ─▶ S3 Rig ─▶ S4 Animation ─▶ S5 Package
   G0          G1            G2          G3          G4              G5
```

| 階段 | 你做什麼 | 指令 | 閘門（全部成立才往下） |
|---|---|---|---|
| **S0 Brief** | `spk init DIR`，填 `BRIEF.md`：身份、視角、目標 runtime、必要動畫、控制器 | `python3 spk.py init characters/NAME` | G0：必要動畫與取景已寫下；參考圖已標成「身份／動作／排版」哪一種 |
| **S1 Key art** | 在 `art.py` 畫出**完整關鍵姿勢**（或取得生成圖）。先整體比例，再臉與手 | `python3 spk.py art DIR` → 開 `evidence/art/keyart_bg.png` | G1：全身與特寫都看過；像不像本人、比例、輪廓成立。不成立就留在這裡改美術，不要靠骨架補救 |
| **S2 Parts** | 每個要獨立運動／遮擋／變形的部位一個 part，**被遮住的地方也要畫滿** | 同上（生成圖走 `spk layers DIR`）→ 開 `evidence/art/parts_sheet.png`、`coverage.png` | G2：recompose 差異只剩邊緣細線；零件在深／淺／彩底無髒邊；`seam_candidates` 逐條判斷過；對位的 `weak` 警告都已看圖處理 |
| **S3 Rig** | `rig.py`：骨頭、part 歸屬、網格與權重、約束、物理、`rig.stress()` 極限姿勢 | `spk build` → `spk fidelity` → `spk check` → `spk stress`（全身 + `--frame` 特寫） | G3：fidelity 通過（setup＝key art）；check 無 error；stress 圖逐格看過，無破洞／穿幫／翻面 |
| **S4 Animation** | 先 `idle`，再一次一個必要動作；overlay（眨眼、說話、表情）放高 track | `spk build` → `spk check` → `spk sheet --anim A` → `spk play --cues …`（真實混合／物理） | G4：每個動畫都看過等間隔 sheet＋邊界；loop 接縫 check 通過；`play` 看過進出混合；正常速度表演另行確認（gif/mp4 或說明限制） |
| **S5 Package** | 匯出、從新目錄重開、寫驗收 | `spk export DIR --zip … --html …` | G5：zip CRC 通過；單檔預覽可開；`templates/acceptance.md` 各層分別填寫，未驗證的寫 `UNVERIFIED` |

完整細節、每個閘門該看什麼：`docs/00-pipeline.md`。兩個走完全程的範例（各自的 `WORKLOG.md` 是實際紀錄）：
- `examples/shuang/`：半身、臉部表演為主（76 骨、21 張加權網格、49 個物理約束、11 段動畫）。
- `examples/xiaoshuang/`：全身 Q 版，**走路、揮手、轉身**（74 骨、兩骨 IK 腿、朝向鏡射、落地腳滑動檢查）。
- `examples/whitemodels/`：**八個可換皮的白模**（標準成人、女性、Q 版、壯漢、吉祥物、盾牌戰士、魔法師、正面看板／虛擬主播），動作在 3D 裡寫、烘成 2D：走、跑、跳、揮手、撿、轉身、360°、武打、舞蹈（`spinekit.figure3d`、`motions3d`）。

## 3. 指令速查

```sh
python3 spk.py doctor                                   # 環境
python3 spk.py init DIR --name NAME                     # 新專案（可放在任何位置）
python3 spk.py art DIR                                  # art.py → parts/ + key art + 檢查圖（程式畫的美術）
python3 spk.py skin DIR [--debug]  ·  spk.py reskin DIR --skin NAME [--fill]  ·  spk.py --skin NAME <指令>   # 白模換皮（docs/38）
python3 spk.py layers DIR [--init]                      # 生成圖／手繪 + layers.json → 同樣的 parts/（去背、對位、切割、接縫檢查）
python3 spk.py key IMG --out OUT   ·   spk.py grid IMG  # 單張去背 · 帶座標格線（讀多邊形座標）
python3 spk.py build DIR --note "這次改了什麼"           # rig.py → build/NNN/（永不覆蓋舊 build）
python3 spk.py fidelity DIR                             # 原生 setup vs key art
python3 spk.py check DIR                                # 數值閘門：結構、權重、翻面、loop 接縫、物理、混合
python3 spk.py stress DIR [--frame x,y,w,h]             # 極限姿勢 sheet（--frame 用美術座標做原生特寫）
python3 spk.py shot DIR --anim idle --time 1.2 [--also blink@0.1#3] [--look look=0.8,0] [--pose "head.rot=6"]
python3 spk.py sheet DIR --anim nod --n 12 [--boundaries] [--over idle] [--physics]
python3 spk.py play DIR --cues "idle@0;nod@1.0~0.2;idle@2.5~0.3;blink@0.4#3" --duration 4 [--gif out.gif] [--mp4 out.mp4]
python3 spk.py compare DIR --a 003 --b 004 --anim blink --times 0,0.1
python3 spk.py preview DIR                              # 給人看的即時預覽（本機）
python3 spk.py export DIR --zip out.zip --html out.html # runtime 包 + 單檔互動預覽
python3 spk.py util audit|inventory|compact|repack|smooth|gait|boundary …   # 既有資產工具
```

所有指令輸出 JSON、失敗時非零結束碼、不覆寫輸入。截圖工具的 `visual_verdict` 永遠是 `NOT_EVALUATED`——判定要你自己看圖後寫。

## 4. 依工作載入的文件（只讀需要的那份）

| 正在做 | 讀 |
|---|---|
| 流程、閘門、WORKLOG 寫法 | `docs/00-pipeline.md` |
| 身份與參考、拆件、隱藏區補畫、alpha；`svgart` 畫法；外部 PNG manifest | `docs/10-art.md` |
| 影像模型／手繪圖 → 零件：`layers.json`、去背、對位、接縫與覆蓋檢查、提示詞範本 | `docs/15-imagegen-layers.md` |
| `rig.py` API：骨頭、網格、權重場、look 控制器、約束、物理、stress；常用配方 | `docs/20-rig.md` |
| `Animation` API：分層、loop、overlay／track、控制器契約；步態；朝向與轉身 | `docs/30-animation.md` |
| 白模：3D 姿勢烘成可換皮的 2D 骨架（身體類型、配件、8 視角、動作庫、邊界處理） | `docs/35-figure3d.md` |
| 換皮：模板、`spk skin`／`spk reskin`／`--skin`、驗收閘門 | `docs/38-reskin.md` |
| 正面表演：看板、虛擬主播（正面 clip、臉部零件、即時參數、runtime 頭髮） | `docs/39-front-performer.md` |
| 每個檢查能證明什麼、怎麼讀圖、改了什麼要回歸什麼 | `docs/40-qa.md` |
| 看到破綻先查什麼 | `docs/50-failure-playbook.md` |
| LayaAir／其他 runtime 整合、PMA 與白邊、最佳化、交付包 | `docs/60-runtime-delivery.md` |
| 既有 Spine 資產：稽核、編輯、retarget、缺主專案恢復 | `docs/70-existing-rigs.md` |
| 手臂深度、掌背掌心、逐指 | `docs/80-hands-arms.md` |

## 5. 回報格式

角色的可見修改，最終回報必須包含：

```
HYPOTHESIS        這次要解決什麼、認為原因是什麼
CHANGE            實際改了什麼（build 編號）
VISUAL_EVIDENCE   實際打開過的圖片路徑、看的是哪些時間點
VERDICT           IMPROVED / UNCHANGED / WORSE
REMAINING_ISSUES  還沒解決或尚未驗證的部分
```

不要寫「所有裝置完美」、不要把取樣率說成實機 fps、不要把工具掃過的影格數寫成人工看過的影格數。沒有看過正常速度播放，就明說是用時序圖片判斷的。

## 6. 邊界

- 這個工具包輸出 Spine 4.2 **JSON + atlas + PNG**，不是 `.spine` Editor 專案；不要改副檔名冒充。
- 使用 Spine Runtimes 需要使用者自己的 Spine Editor 授權（`node_modules/@esotericsoftware/*/LICENSE`）。
- 對外發布只在使用者於本次對話明確授權時進行；歷史案例的授權不沿用。
