# 霜 (Shuang) — worklog

> 為了縮小工具包，這個範例的證據圖已轉存為 JPEG，逐格原圖已刪（保留 `plan.json`／`capture.json` 收據與 `showcase.mp4`）。工具實際輸出的是 PNG；`python3 spk.py …` 可隨時重拍。

## State

- current build: **003**
- gates passed: G0 brief · G1 key art · G2 parts · G3 rig · G4 animation · G5 package（限 spine-webgl 4.2.119）
- open issues: 見最下方 REMAINING
- next smallest step: 在目標引擎內載入 `dist/shuang_runtime.zip`，依 `shuang.contract.json` 接 look／overlay，實看物理與多 track 表現

## Log

### art v1 → v3（尚無骨架；G1/G2）
- OBSERVED v1: 臉寬而圓、眼睛睜大外加厚重眼線像驚嚇的娃娃；頭頂髮片在太陽穴外凸成「耳罩」；身體像平面睡衣、肩寬不足；腮紅在 setup 就全顯。
- CHANGE v2: 臉頰與下顎收窄、肩寬 ±200、髮型重排（頭頂髮片貼頭、三片瀏海、姬髮臉頰束、每側兩束前垂髮、加寬後髮）、腮紅改為 hidden。
- OBSERVED v2: 輪廓成立；臉下半仍偏圓，眼型仍偏瞪、睫毛過厚，眉毛壓在黑髮上看不見，襯衫像一片白。
- CHANGE v3: 下顎再收、眼眶改平緩並略下垂、睫毛內細外厚、眉毛改冷灰色疊在瀏海上、襯衫加冷色環境漸層。
- EVIDENCE: 每版 key art 的半身＋臉部放大圖（evidence/art/keyart_bg.jpg 為最終版）。
- VERDICT: IMPROVED ×2。類別 ART。
- REMAINING: 風格是乾淨的向量賽璐璐，不是參考圖那種半寫實厚塗；臉頰髮束仍偏塊狀。

### build 001 — 第一版骨架（G3）
- CHANGE: 76 骨、21 張加權網格、look／gaze 控制器、49 個物理約束、28 個極限姿勢。
- EVIDENCE: evidence/001/fidelity.jpg（14 px 超過門檻，僅臉緣與領口的抗鋸齒細線）；evidence/001/stress/stress_full.jpg、stress_face.jpg。
- OBSERVED: 轉頭視差成立（鼻、五官、臉緣位移量不同）；歪頭時長髮保持垂直；虹膜被眼眶正確裁切。**缺陷**：`lids_closed` 的睫毛變成鋸齒狀粗黑塊。
- HYPOTHESIS: 睫毛厚度範圍內的頂點拿到不同的眼皮權重 → 睫毛被擠壓。class: MESH_WEIGHTS。

### build 002 — 睫毛帶整段跟眼皮骨；加入 11 段動畫（G3→G4）
- CHANGE: 眼皮權重在睫毛線上方 8px 就到 1；加入 idle/blink/talk/nod/shake/tilt/look_around/smile/sad/surprised/hair_wind 與契約。
- EVIDENCE: evidence/002/sheets/blink_face.jpg、plays/face_expr.jpg、plays/wind_phys.jpg、wind_nophys.jpg、plays/idle_phys.jpg。
- OBSERVED: 閉眼睫毛變成乾淨弧線（IMPROVED）。**新缺陷**：blink 0.07–0.12s 睫毛上方透出灰色虹膜殘影。微笑／憂鬱／驚訝／說話讀得出來。風：髮梢彎折過大，有物理時下段出現折角。idle 髮梢擺幅偏大。
- HYPOTHESIS: 眼皮補片上緣羽化帶被拉到眼眶上 → 半透明。class: ART + MESH_WEIGHTS。

### build 003 — 眼皮補片不透明且沿用臉部陰影；髮束收斂（G4）
- CHANGE: 補片加高（頂 y=276）、最上 9px 羽化帶固定不動、其下不透明並呼叫同一個 `face_shading()`；臉頰髮束改平切；idle 擺幅 0.55°→0.4°；風的幅度 −25%、逐節放大 1.22→1.13。
- EVIDENCE: evidence/003/compare/002_vs_003_blink.jpg（0.00／0.10／0.20s 同鏡頭前後對照）；evidence/003/plays/showcase.jpg（16 秒真實混合取 20 格）；evidence/003/sheets/*、stress/*、plays/face_expr.jpg、plays/wind.jpg。
- VERDICT: IMPROVED（閉眼無殘影；張眼畫面除補片邊緣外無差異）。
- `spk check`：0 error、0 warning；11 段動畫 0 翻面；idle loop 接縫位置 0px；track 0 動畫 42 組真實混合無翻面。

### 工具包 2.1 — 對既有零件補跑接縫檢查（美術未改）
- `spk art` 現在會列出 `seam_candidates`：檢查 71 組相鄰零件，18 組被列為候選（`evidence/art/coverage.jpg`）。
- 我的判讀（依 build 003 的 stress／動畫圖，**不是**逐條重新驗證）：
  - 上下眼皮 ↔ 虹膜（underpaint 0.1）：虹膜後面有眼白墊著（`backed_by: eye_white_*`），驚訝時眼皮上抬露出的是完整圓形虹膜——可接受。
  - 手臂 ↔ 身體（0.76）、前垂髮 ↔ 手臂（0.78–0.83）：`arms_out` 極限姿勢沒有露底，但幅度再大就會；動畫中手臂只動 ±0.35°。
  - 頭頂髮片 ↔ 臉頰髮束／側髮（0.5–0.6）：歪頭時髮束保持垂直，這裡正是 ±9° 會分離的地方（已記在 REMAINING）。
  - 其餘是同骨或同色相鄰（瀏海彼此、眉毛壓在瀏海上）。

## REMAINING（誠實清單）

- **美術**：類型相似（長直黑髮姬髮式、白襯衫、灰藍眼、沉靜），不是參考截圖的半寫實質感；要更接近需換成生成／手繪圖層走同一條 rig 流程。
- **正常速度**：我只看了時序圖片（showcase 20/481 格、各動畫 8–16 格），沒有實際觀看影片；`evidence/003/showcase.mp4` 請人看一次節奏。
- **歪頭**：stress 的 ±9° 會讓臉頰髮束與臉分離；動畫中限制在 ≤5.5°。
- **風**：有物理時長髮梢仍有輕微過衝；關物理版本較克制（plays/wind_nophys 於 build 002 看過）。
- **talk**：只是示意的嘴型循環，不是對嘴。
- **目標引擎**：LayaAir 內的物理、多 track、transform constraint 表現未驗證。
