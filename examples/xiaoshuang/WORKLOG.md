# 小霜 (Xiaoshuang) — worklog

> 範例的證據圖已轉存 JPEG、逐格原圖已刪（保留收據與 `journey.mp4`）。工具實際輸出 PNG，可隨時重拍。

## State

- current build: **005**
- gates passed: G0–G5（限 spine-webgl 4.2.119）
- next smallest step: 在目標引擎實作契約的三件事——依 `speed×朝向` 位移、收到 `flip` 事件鏡射並重設物理、多 track 的 `blink`

## Log

### art（G1/G2）
- OBSERVED v1: Q 版造型成立、可愛；後髮寬得像斗篷；瀏海兩側各露出一條 2px 的膚色（太陽穴處臉皮沒被臉頰髮束蓋住）。
- 接縫檢查同時報出：`hand_n` 壓在 `arm_n` 上只重疊 2px（手一轉就露縫）；臉↔虹膜 0.0（虹膜下緣剛好碰到眼眶，後面有眼白，可接受）。
- CHANGE: 後髮收窄；臉頰髮束左緣外擴蓋住太陽穴；袖口下補一段手腕。
- VERDICT: IMPROVED。膚色細條在 build 003 的 stress 圖仍看得到 → build 004 再把髮束左緣外擴後消失。

### build 001 — 骨架＋全部動畫
- `spk fidelity` 通過（0.01%）。`spk check` **失敗**：`wave` 的袖子在肩膀處 72 個翻面取樣；walk 接縫速度跳變 260 px/s。
- HYPOTHESIS: (a) 袖子上端權重交給 shoulder，手臂轉 112° 時把袖帽摺過去——MESH_WEIGHTS；(b) 腳掌落地瞬間的滾動角速度不連續——MOTION。

### build 002 — 袖子整段跟上臂轉；腳掌滾動改 sin²
- 袖帽是以肩關節為圓心的圓，整段跟著轉外觀不變 → 肩部翻面消失。剩 13 個翻面在手肘（彎 65°、袖管只有 25px 寬）。
- walk 接縫跳變 260 → 96 px/s，仍被警告：接縫剛好在落地瞬間，加速度最大。

### build 003 — 手肘彎曲分散到較長一段；walk 的接縫移到支撐中段
- CHANGE: 袖子 `blend 0.5→1.1`、列數 9→14、揮手擺幅 20°→15°；walk 相位 +0.3。
- `spk check`：0 error／0 warning。落地腳滑動 1.27／2.55 px。
- EVIDENCE: evidence/003/stress/stress_full.jpg、evidence/003/sheets/walk_full.jpg。
- OBSERVED: IK 抬腳／蹲下膝蓋朝行進方向；揮手姿勢手在頭側、不擋臉；鏡射朝向正確。**缺陷**：走路時兩臂每圈有一次同時向外張開（身體接近正面，前後擺看起來是左右擺）。

### build 004 — 手臂擺動偏向身體；補太陽穴
- CHANGE: 擺幅 24°→15°，近側手偏向身前 +7°、遠側手偏向身後 −7°；臉頰髮束外擴。
- EVIDENCE: evidence/004/plays/journey.jpg（6.6 秒真實播放取 17 格，含位移與鏡射）、evidence/004/plays/turn_close.jpg（轉身每 2 格一張，共 16 張）。
- OBSERVED: 向右走 → 轉身（頭先轉正、小跳、正面鞋、鏡射、轉向左）→ 向左走（鞋尖朝左）→ 揮手（轉向鏡頭、舉近側手、微笑臉紅）→ 回待機。轉身逐格沒有看到跳變。事件依序觸發：`step`×3、`flip`、`step`×3、`wave`。
- VERDICT: IMPROVED；`spk check` 0 error／0 warning。

### build 005 — 原點移到兩腳之間的地面；直式取景交給編譯器算
- OBSERVED: 手機尺寸的預覽裡頭被切掉、下方一大片空白（/tmp 的無頭瀏覽器截圖）。量測後發現骨架原點在畫布底邊（y=1000）而不是地面（y=840），我手算的直式取景差了 160。類別 ALIGNMENT（我的座標假設錯）。
- CHANGE: `rig.set_origin(*D.ROOT)`；直式取景改用 `rig.world_rect()`；工具包文件補上「會移動的角色把原點設在地面」。
- EVIDENCE: `spk compare --a 004 --b 005`（walk 0.2s／0.6s）changed_px = 0；手機尺寸截圖重拍後全身入鏡；`evidence/005/plays/journey.jpg`、`evidence/005/journey.mp4`、`evidence/005/stress/stress_full.jpg`。
- 無頭瀏覽器實跑「巡邏」8 秒：x 在 −121…134 之間來回，朝向翻轉多次，無錯誤。
- VERDICT: IMPROVED（取景）；動作 UNCHANGED。

## REMAINING（誠實清單）

- **正常速度**：我看的是時序圖片（journey 17/199 格、轉身 16/31 格），沒有看影片。走路的節奏、轉身那一下順不順，請看 `evidence/005/journey.mp4`。
- **走路的方向感**：身體畫得接近正面，靠頭的轉向、鞋尖方向、腿的前後擺來表示「往側邊走」。Q 版可以接受；要更寫實的側面走路需要另畫 3/4 身體。
- **轉身**：是左右換向（經過正面），不是露出背面的 180° 轉身；要背面得加畫一組背面圖層在中點換圖。
- **鏡射瞬間**：近／遠側手腳的前後層次與陰影色會換邊（很小）；頭髮物理在那一格被重設。逐格圖上沒看出跳動，正常速度未確認。
- **手**：連指手套式的簡化手，揮手時換成張開的手掌，沒有逐指。
- **目標引擎**：未驗證。
