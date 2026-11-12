# 00 流程與閘門

一個角色專案的目錄（`spk init` 產生）：

```
NAME/
├── BRIEF.md            S0：需求與驗收條件
├── WORKLOG.md          每一輪「觀察→假設→修改→證據→判定」；接手時先讀
├── art.py              S1/S2：分層美術（或刪掉，改放 parts/*.png + manifest.json）
├── rig.py              S3/S4：骨架、權重、約束、動畫、契約
├── parts/              art 產物：每個 part 一張 RGBA PNG、manifest.json、keyart.png
├── build/NNN/          每次 build 一個新資料夾：NAME.json/.atlas/.png、.contract.json、.stress.json、receipt、check 報告
└── evidence/           art/、NNN/（fidelity、stress、sheets、plays、compare…）
```

舊 build 永遠保留——它就是你的「修改前」基線，`spk compare --a 003 --b 004` 直接對照。

## 閘門細節

### G0 Brief
- 參考圖逐張標用途：**身份**（決定長相比例）、**動作**（只取姿勢節奏）、**排版**（只取呈現方式）。動作板上的武器、別的角色、不同朝向不帶進來。
- 寫下目標 runtime 與版本、必要動畫（是否 loop、在哪個 track、結束回到誰）、runtime 控制器（視線跟隨、口型…）、畫布與取景。
- 側別一律寫明：`_L/_R` 是畫面左右還是角色自己的左右。

### G1 Key art（還沒有任何骨頭）
開 `evidence/art/keyart_bg.png`（深／淺／彩三底）。順序：整體比例與輪廓 → 臉 → 手 → 服裝。
- 第一眼認得出是這個角色嗎？頭身比、臉型、眼距、髮型輪廓對不對？
- 不成立 → 類別是 `ART`，留在 `art.py` 修。**不要**期待骨架、網格或動畫補救造型。
- 需要特寫時自己裁切放大來看；看過才算。

### G2 Parts
開 `evidence/art/parts_sheet.png`。
- `spk art`／`spk layers` 回報的 recompose 差異應接近 0：零件疊回去等於 key art（證明沒有遺失或位移；**不能**證明歸屬正確）。
- `seam_candidates`：畫面上相鄰、但下層沒有延伸到上層底下的零件對。逐條判斷——兩者會各自運動的，回去補底層像素；`backed_by` 告訴你那條縫現在會露出誰。開 `coverage.png` 看整體。
- 走 `spk layers` 時：對位標 `weak` 的零件要看 `recompose.png` 確認，必要時填 `place`。
- 每個會被掀開的地方都有底層像素：肩根在袖子下、脖子在下巴與領口下、頭皮在瀏海下、眼白比眼眶大一圈。
- 同一像素不屬於兩個各自會動的 part（例如袖口不能同時畫在手臂和身體上）。

### G3 Rig
1. `spk build` → `spk fidelity`：原生 setup pose 以美術解析度渲染後與 key art 相減。通過代表骨頭座標、UV、權重編碼、圖集、draw order 全對；差異圖上只該有抗鋸齒細線，出現色塊就是錯位／掛錯／層序錯。
2. `spk check`：無 error。
3. `spk stress`（全身）＋ `spk stress --frame x,y,w,h`（臉、手等特寫）。逐格看：破洞、露底、翻面尖刺、關節折痕、頭髮與身體穿插、眼皮閉合是否蓋滿。
4. 極限姿勢要比動畫會用到的幅度**更大**；這裡過了，動畫才不會踩雷。

### G4 Animation（一次一個）
1. 先 `idle`。`spk check` 的 loop seam：`positionPx` 必須是 0，`velocityJump` 太大會被警告（看得到的頓挫）。
2. `spk sheet --anim A --n 12`（必要時 `--frame` 特寫、`--boundaries` 加拍換圖前後、`--over idle` 檢查 overlay 疊在 idle 上的樣子）。
3. `spk play --cues "idle@0;A@0.8~0.2;idle@…"`：真的 AnimationState、真的 mix、真的物理、固定 dt。看進入、離開、物理甩動。`seek` 取樣（shot/sheet）不經過 mix，不能當轉場證據。
4. 正常速度觀感：加 `--gif`／`--mp4` 給人看。你自己只能看時序圖片時，回報裡要寫明。
5. 每加一個動畫就重跑 `spk check`（會做 track 0 動畫兩兩真實混合的翻面檢查）。

### G5 Package
- `spk export --zip`：只含 runtime 需要的 JSON/atlas/PNG/contract＋SHA256；zip 會自驗 CRC。
- `spk export --html`：單檔互動預覽，從新位置打開確認。
- 目標引擎（例如 LayaAir）內的實機畫面是另一層驗證，見 `60-runtime-delivery.md`；沒做就寫 `UNVERIFIED`。
- 用 `templates/acceptance.md` 分層記錄。

## WORKLOG 一則的樣子

```
### build 003 — 眼皮補片改為不透明並沿用臉部陰影
- OBSERVED (before): blink 0.07–0.12s 閉眼時，睫毛上方透出灰色虹膜殘影（sheets/blink_face.png）
- HYPOTHESIS: 眼皮補片上緣的羽化帶被拉到眼眶上方 → 半透明。class: ART + MESH_WEIGHTS
- CHANGE: 補片加高、羽化帶固定不動、其下不透明並套同一組臉部陰影
- EVIDENCE: evidence/003/compare/002_vs_003_blink.png（0.00 / 0.10 / 0.20s）
- VERDICT: IMPROVED（第 1 次）
- REMAINING: 傾頭 ±9° 時臉頰髮束與臉分離，動畫中限制在 ≤6°
```

## Anti-loop

同一假設做過兩次有意義的不同修正仍 `UNCHANGED/WORSE`：停。把問題重新歸類到下列其中之一，再選最小修法。

```
缺像素／造型不對        → ART
位置對不上              → ALIGNMENT
掛在錯的骨頭／slot      → OWNERSHIP
前後遮擋錯              → DRAW_ORDER
彎折、拉扯、翻面        → MESH_WEIGHTS
路徑、節奏、接縫        → MOTION
白邊、黑點、半透明異常   → MATERIAL（alpha / PMA / 取樣）
```

純最佳化（壓縮、重排圖集）預期結果是 `UNCHANGED`，那是成功。
