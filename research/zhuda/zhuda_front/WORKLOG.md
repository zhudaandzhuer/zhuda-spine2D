# 豬大 Zhuda（正面）— WORKLOG

照使用者提供的設計圖（`../ref/collage.png`）從零做的 Spine 4.2 角色。**不使用白模**：骨架依豬大的身材設計（大頭直接坐在梨形身體上、沒有脖子、短手短腳、蹄）。這是 M1（只做正面）。

## State（2026-11-12）

- current build: **006**；`spk check` 0 error／0 warning；`spk fidelity` 差異 2.19%（判定 ok:false，見下）
- 交付：`dist/zhuda_front.zip`（runtime）、`dist/zhuda_front.html`（單檔互動預覽）、`dist/zhuda_front_demo.mp4`（17 秒示範）
- 動畫：`idle`、`walk_front`（原地踏步）、`wave`、`jump`、`talk`（疊加）、`blink`（疊加，自動）、8 種表情 `face_happy / laugh / angry / surprised / shy / sad / confused / cry`（hold 疊加）
- 控制器：`look`（假 3D 轉頭：五官依深度平移、頭部網格跟著變形）

## 做法

1. **主視覺**：`gen/keyart.png`。第一版身體、腿、手都太長，還多了眉毛，退件。第二版把比例寫死（頭 48%、身體 40%、腿 12%），和設計圖並排確認後才用（`gen/cmp_keyart_02.png`）。
2. **圖層**：以主視覺為參考，用改圖方式生成被遮住部分補完的圖層。
   - `head_01`：無耳、無五官，保留腮紅與下巴輪廓。
   - `body_01`：頭身一體的底層。生成結果比主視覺寬約 11%，改用縮 0.9 倍的 `body_02`。
   - `limbs_01`：四肢，上端往身體內延伸。
   - 耳朵：從主視覺切。只保留和無耳頭部不同的像素（`gen/ear_*_cut.png`）。
   - 眼睛、豬鼻：直接用多邊形從主視覺切，像素一模一樣。
   - 嘴型、閉眼／笑眼／大眼／難過眼／哭眼、眉毛、害羞紅暈、眼淚：`face_parts.py` 照主視覺的線寬和顏色畫在同一張畫布上，八種表情都準確對位。
3. **骨架**（`rig.py`）：
   - 頭、身體：加權網格。身體由 hip→belly→chest 三根骨頭帶動，可以壓扁、拉長。
   - 腿：一根骨頭加單骨 IK，開啟 stretch／compress。蹲下時腿變短，不彎膝蓋：豬大的腿太短，彎膝蓋會折網格。
   - 手：兩節，權重全部跟著手臂骨頭。
   - 耳朵：Spine 物理。
   - 舉起的手：用 draw order 換到頭前面。

## 看過的圖

- `evidence/006/fidelity.png`：setup 和主視覺幾乎重疊，差異集中在身體外框（身體圖層是生成的，輪廓和主視覺差幾 px）。
- `evidence/00x/stress/stress_full.png`：八種表情、四向轉頭、蹲、跳、手張開。
- `evidence/004/sheets/wave_full.png`、`jump_full.png`、`evidence/003/sheets/walk_front_full.png`、`evidence/006/sheets/talk_face.png`。
- `evidence/006/plays/play.png`：20 格示範，涵蓋動作轉場和表情切換。

## 一路上的修正（每次都是看圖發現）

| build | 看到的問題 | 改了什麼 | 結果 |
|---|---|---|---|
| 001 | 舉手被頭整個擋住；蹲下兩腳內八交叉；腿網格在膝蓋折疊 | — | — |
| 002 | — | 腿改成單骨伸縮 IK；舉手加 draw order | 腿不再折疊。IMPROVED |
| 003 | 手臂舉高時肩部網格翻面 | 手臂權重不再分給 chest | check 全過。IMPROVED |
| 004 | 頭太大、手太短，往上舉一定被頭擋住；手臂圖有離群碎片（切割框套到腿） | 揮手改成往側面抬 64°、畫在頭前面；切割框避開腿 | 揮手看得到了。IMPROVED |
| 005 | 手肘彎 38° 網格塌陷；跳到最高點頭頂出框 | 手肘降到 22–26°、權重混合加寬；取景加高 | 0 error／0 warning。IMPROVED |
| 006 | 說話嘴型在大頭上只剩小點 | 張嘴圖放大約 35% | 開合看得清楚。IMPROVED |

## REMAINING（誠實清單）

- **fidelity 2.19%（ok:false）**：差在身體外框和手臂內側。身體圖層的輪廓不是主視覺的像素，要更準得重生身體圖層，或從主視覺切出身體再補畫手臂後面。
- **只有正面**：3/4、側面、背面還沒做，所以沒有真正的走路位移和轉身（`walk_front` 是原地踏步）。下一步是 M2。
- **mp4 沒有用正常速度看過**：動作是用時序圖判斷的。
- **自動眨眼和表情的衝突**：`blink` 在 track 3。播完若沒有清掉 track，會蓋住表情的眼睛。spk play 的示範裡我刻意沒有同時用；整合時遊戲端要在眨眼結束後清 track 3。預覽頁的 auto 行為未驗證。
- 尾巴在正面看不到，沒有做。
- 目標引擎未驗證；只在 spine-webgl 4.2.119 驗過。
