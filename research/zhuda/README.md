# 豬大系列：八個白模換皮驗證（2026-11-12）

目標：用 codex-imagegen 生出的豬大美術，把八個白模全部換皮成「zhuda」，產出 Spine 4.2 資產，驗證白模換皮方案可行。

## 產出在哪

| 內容 | 路徑 |
|---|---|
| 每個角色的交付包（runtime zip、單檔互動預覽 html、播放 mp4） | `work/zhuda/series/<model>/zhuda_<model>.{zip,html,mp4}` |
| 換皮後的 runtime（同一份骨架 JSON＋新 atlas/png） | `examples/whitemodels/<model>/build/001/skins/zhuda/` |
| 換皮來源圖（每個模板一張，2× 解析度） | `examples/whitemodels/<model>/skins/zhuda/` |
| 驗收截圖（原生 spine-webgl） | `examples/whitemodels/<model>/evidence/001/skin_zhuda/` |
| 生圖原檔、提示詞、回執 | `work/zhuda/gen/`（`*_01.png`、`p_*.txt`、`*.png.json`） |
| 參考圖（使用者給的設定拼圖） | `work/zhuda/ref/` |
| 貼皮程式 | `work/zhuda/zhuda_skin.py`（工具函式）、`work/zhuda/run.py`（每個白模的配方） |
| 渲染批次 | `work/zhuda/check.sh <model>`（貼皮→reskin→轉一圈）、`work/zhuda/render_all.sh`（stress→play mp4→export） |

重跑一個角色：

```sh
cd $KIT
work/zhuda/check.sh knight                       # 貼皮 + reskin + 轉一圈特寫
MODELS=knight bash work/zhuda/render_all.sh      # stress + 播放 mp4 + 匯出
```

環境：`work/zhuda/env.sh` 設定本機任一份 playwright-core 1.58.2 與 `~/Library/Caches/ms-playwright` 的 chrome-headless-shell。用一般 Google Chrome 會因為它要求 favicon（404）而讓 capture 判定失敗。

## 做法

**沒有逐張生成 600 張零件**。生圖只做「需要角色辨識度的東西」，其餘用程式依模板形狀上色：

- 生圖（ChatGPT 線路 gpt-image-2-codex，共 12 張，透明背景，3:1 排五個視角 F/FR/R/BR/B）：
  頭（原版、毛線帽、騎士頭盔、無耳無鼻版）、身體（裸身、吊帶裙、帽T、條紋衫＋領巾、盔甲、法袍）、盾牌、材質樣本表。
  rustgod 線路的 `/images/edits` 現在回 404，所以全部走 `--api chatgpt`。
- 視角零件：`_v0`–`_v4` 來自轉身圖的五欄，`_v5`–`_v7` 水平翻轉（豬大左右對稱）。
  頭：以「頭球」範圍對準白色形狀、放大到覆蓋 ≥98.5%，耳朵與豬鼻可以畫出白色形狀。
  胸／骨盆：取身體圖的上 64%／下 60%，貼進白色橢圓並沿輪廓裁切（覆蓋 100%）。
- 四肢、關節、手腳、配件：依模板 alpha 填材質（顏色取自生圖或材質表，紋理縮小淡化），沿用模板的明暗，衣物加棕色描邊、皮膚不描邊（描邊會讓每個關節像木偶接縫）。手腳是深棕色豬蹄。
- vtuber：臉是零件拼的。頭部圖畫空白臉＋豬鼻＋腮紅；鼻孔放在 `nose`（會跟著視線參數有視差）；豆豆眼（開／半／閉）、白色反光當虹膜、眉、五種嘴型、腮紅都用程式畫；側髮＝垂耳、髮帽／瀏海／髮束＝米色毛線帽與帽繩。

## 每個白模的造型

| 白模 | 豬大造型 | 配件對應 |
|---|---|---|
| hero | 裸身豬大＋米色毛線圍巾 | scarf 鏈＝毛線 |
| heroine | 丹寧吊帶裙（設定圖服裝 A） | 裙錐＝丹寧；馬尾鏈＝紅緞帶 |
| chibi | 粉紅毛線帽＋米白帽T（服裝 B） | 雙馬尾鏈＝毛線帽耳罩繩 |
| brute | 條紋衫＋紅點領巾（服裝 C）、丹寧褲 | 披風＝紅布；棍棒＝木頭 |
| mascot | 裸身、分件的耳朵與豬鼻、捲尾巴、側背包 | 耳朵、豬鼻、尾巴鏈、包 |
| knight | 騎士頭盔、心形胸甲、鋼製四肢 | 盾牌 8 視角（正面豬臉徽章、背面木板＋皮帶）、劍、肩甲、紅盔纓 |
| mage | 星星法袍、尖帽、木法杖 | 長袍、寬袖、帽、杖頭金球 |
| vtuber | 條紋衫＋紅裙、米色毛線帽 | 臉部零件（見上） |

## 驗收（docs/38 的閘門）

所有截圖都是原生 spine-webgl 4.2.119（headless Chromium）。判定是我打開圖看過後寫的；**mp4 我沒有用正常速度看過**，動作是用等間隔時序圖（每支 16 格）判斷的。

| 閘門 | 結果 | 證據（`examples/whitemodels/<m>/evidence/001/skin_zhuda/`） |
|---|---|---|
| S0 除錯皮 | 沿用包內既有結果（hero/brute/mascot/knight/mage 看過）；這次沒重跑 | `../skin_debug/` |
| S1 規格 | 8/8 `reskin ok:true`，0 error。頭部覆蓋 ≥0.99，身體／四肢 1.0。vtuber 的臉部零件（眼、嘴、眉）覆蓋 0.003–0.54 會有警告：那些是畫在臉上的小圖，不是關節，預期如此 | `work/zhuda/out_reskin_<m>.json` |
| S2 靜態 | 8/8 PASS：stress 關鍵姿勢沒看到破口 | `stress/stress_full.png` |
| S3 轉一圈 | 7/7 PASS（vtuber 沒有 turntable）：8 個視角都出現、方向正確，正面是臉、背面是後腦／尾巴 | `sheets/turntable_close.png` |
| S4 動作 | 8/8 PASS（見下方問題）：走、轉身、走回、跑、揮手、跳、武打、跳舞；knight 格擋／揮砍／盾擊；mage 施法／引導；vtuber 打招呼／說話／比心／轉圈／歡呼。不對稱身體（brute、knight、mage、mascot）朝左時棍棒、劍盾、包沒有換邊 | `plays/play.png`、`work/zhuda/series/<m>/zhuda_<m>.mp4` |
| S5 邊界 | 只抽查 hero kungfu 1.0–1.4 s：骨盆在 1.10→1.15 s 從正面（米色肚皮）跳到側面，看得出但幅度小；腳的跳圖因為整塊深棕蹄看不出來 | `sheets/kungfu_flicker.png` |
| G5 交付 | 8/8：zip CRC 通過；解壓到新資料夾後 spine-core 讀得起來；zip 裡的 png 與 zhuda 圖集逐位元組相同；`spk check` 8/8 0 error／0 warning | `work/zhuda/series/` |

## 結論：白模換皮方案可行

- **同一副骨架、同一份動畫，只換圖集**，就從八種體型做出八個豬大造型，全部能播、能轉身、能匯出。換皮來源只要 12 次生圖＋程式貼圖，八個角色合計 599 張零件圖。
- 最有效的組合是「視角零件靠轉身圖、其他零件靠模板形狀上色」。視角零件指頭、胸、骨盆、盾牌這類有 8 個方向的圖。轉身圖一次生成五個視角，左右對稱就翻轉補齊。
- 豬大這種圓頭大頭角色最適合 chibi 和 mascot 的比例。hero／heroine／brute／knight／mage 的成人比例讓豬頭顯得很小，這是體型選擇，不是錯誤。

## 這次發現的白模本身問題（除錯皮應該也會有）

1. **mascot 的耳朵在頭的輪廓裡面**：從每個角度看都貼在頭球表面，畫什麼都像貼紙。要讓動物耳朵立在頭頂外，得把白模的耳朵往外移，或是放大圖片四周的留白。
2. **mage 走路時後腳伸出長袍**（play 1.67、2.50、5.83 s）：長袍的錐形不夠寬，蓋不住往後擺的腿。
3. **brute 的披風是兩片大橢圓**：換成布料後從背面看像兩顆氣球。白模需要比較像布片的輪廓（上窄下寬、下緣不規則）。
4. **管狀肢段＋關節球的結構會露出木偶感**：皮膚色上了描邊，每個關節都像接縫，所以皮膚零件我改成不描邊。這要寫進換皮指南。

## 換皮流程上的發現（給工具包）

- `spk play` 的 `--frame` 若是負數開頭，要寫成 `--frame=-362,...`，否則 argparse 會當成選項。
- 用一般 Google Chrome 截圖時，favicon 的 404 會被記為 pageErrors，整批判失敗；要用 chrome-headless-shell。
- 播放的取景預設是直式，走路會走出畫面；要加 `--size 1280x720` 和寬鏡頭。
- 透明背景生圖的邊緣會帶紅黃色雜點：要先取 alpha>160 的連通區、只留大塊，再侵蝕 1px，才會乾淨。

## 還沒做／沒驗證

- mp4 沒有用正常速度看過。
- S5 只抽查一段，其餘 `bake-report.json` 的 flicker 時間點沒有逐一看。
- 沒有在 LayaAir、Unity 等目標引擎驗證。
- 各角色的 `WORKLOG.md` 沒有更新；這份 README 就是這次的紀錄。

---

# 第二輪（2026-11-12）：修白模，讓豬大維持矮胖

第一輪的問題是：五個成人體型的白模把豬大拉成細長人體＋小豬頭，看起來很沙雕。這一輪改的是白模本身，不是貼圖。

## 產出（取代第一輪）

| 內容 | 路徑 |
|---|---|
| 八個豬大體型白模專案（art.py／rig.py／build／skins／evidence） | `work/zhuda/models/<model>/` |
| 交付包（zip／html／mp4） | `work/zhuda/series_v2/<model>/zhuda_<model>.{zip,html,mp4}` |
| 引擎改動前的備份 | `work/zhuda/figure3d.before.py` |

重建一個：`MODELS=knight bash work/zhuda/build_models.sh` → `work/zhuda/check2.sh knight` → `ZHUDA_MODELS=$PWD/work/zhuda/models OUT=work/zhuda/series_v2 MODELS=knight bash work/zhuda/render_all.sh`。

## 引擎改動（`spinekit/figure3d.py`）

1. **體型 `shape`**：`F.Body("knight", shape="zhuda")` 用 `SHAPES["zhuda"]` 取代原本的比例，但保留該職業的配件、攜帶姿勢和動作組。
   - 豬大體型：總高 418px，頭高 159px（占 38%）。
   - 蛋形胖身體，胸窄腰寬（chest 0.98／waist 1.22／pelvis 1.12）。
   - 短粗四肢：腿 0.36、手 0.46，粗細 1.32／1.18。
2. **配件跟著身體縮放**：`_extras` 裡寫死的像素尺寸改乘以三個倍率，比例都是和職業原本身體相比。
   - `acc`：掛在身上的東西，跟身高比。
   - `acc_h`：戴在頭上的東西，跟頭的大小比。
   - `acc_w`：橫跨背部的東西。
   - 原本的八個預設 `acc=1`，數值不變。
3. **大頭上的配件另外收短**：只在指定 `shape` 時生效，否則會變成角或棍子。包括馬尾、雙馬尾、帽繩、法師帽尖；盔纓改跟身高走，不跟頭。
4. **mascot 耳朵**：移到頭頂邊緣、往外傾，大部分立在頭的輪廓外。原本從每個角度看都貼在頭裡面。
5. **mage 長袍**：原本預設的下擺 1.55→1.85，跟腿程度 0.55→0.8，蓋住往後擺的腿。豬大體型骨盆本來就寬，用 1.3。
6. **brute 披風**：豬大體型的布片改成「長大於寬」（寬 cx×0.62／0.7，長 0.72）。
   - 原因：薄片的貼圖會跟著長軸走。長寬太接近時長軸會跳，畫在裡面的形狀就被轉成菱形。
   - 貼圖改畫上下對稱的圓角布片。
7. **短循環的鏈條模擬**：
   - 至少模擬 3 秒才取最後一圈。
   - 一圈剩下的位置誤差平均分攤回整圈，最後一格接回第一格。

`tests/selftest.py`：80/80 通過。

## 驗收（第二輪）

| 項目 | 結果 |
|---|---|
| 建置 | 8/8；`spk check` 0 error。brute（run）和 mage（channel）各有 2 個「loop 接縫速度跳動」警告，見下 |
| 換皮 | 8/8 `reskin ok`。heroine 馬尾覆蓋 0.58–0.59：刻意畫成細緞帶。vtuber 臉部零件覆蓋低：預期如此 |
| 轉一圈 | 7/7 看過：八個方向正確，全部是大頭胖身的豬大（`models/<m>/evidence/*/skin_zhuda/sheets/turntable_close.png`） |
| 播放 | 8/8 看過時序圖：全程在畫面內。轉身往回走、武打、跳舞、knight 三招、mage 施法、vtuber 表演都正常（`plays/play.png`、`series_v2/<m>/*.mp4`） |
| 交付 | 8/8：zip CRC 通過；從新資料夾能用 spine-core 載入；png 與 zhuda 圖集相同 |

**接縫警告**：
- brute run 的 cape_2 跳 738 px/s，mage channel 的 robe_1 跳 51 px/s。
- 兩次修正（加長模擬、分攤誤差）都沒有改變數值。照規則停止微調。
- 我看了 brute run 接縫前後五格（`models/brute/evidence/003/skin_zhuda/sheets/run_seam.png`），披風角度連續，看不出跳動。
- 數值上的跳動可能來自曲線刪點，**未查證**。

## 還沒做

- mp4 沒有用正常速度看。
- 原本 `examples/whitemodels/` 的八個白模**沒有重建**。引擎修正（mascot 耳朵、mage 長袍、鏈條接縫）要等它們下次 `spk build` 才會生效；包內的 build 001 和第一輪的 zhuda 皮都還是舊的。
- 腳本覆寫的貼皮有兩處還算普通：
  - mage 的長袍從正面看是一個大梯形。
  - vtuber 的毛線帽圈在頭後面像兜帽。
