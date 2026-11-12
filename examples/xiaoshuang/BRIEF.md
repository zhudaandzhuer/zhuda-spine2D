# 小霜 (Xiaoshuang) — brief

| Item | Decision |
|---|---|
| Identity | 「霜」的 Q 版全身（約 2.7 頭身）：長直黑髮姬髮式、灰藍大眼、白襯衫＋深藍領結、深藍百褶裙、白短襪、棕色樂福鞋。原創，用程式畫。 |
| View / framing | 身體接近正面、頭用假 3D 轉成 3/4；預設朝**畫面右**。取景 `FRAME = (-170, 120, 1140, 770)`（留出左右走動空間）。 |
| Side convention | 頭部零件 `_L/_R` = 畫面左右；四肢 `_n/_f` = 靠近／遠離鏡頭。朝右時 near 是畫面左側的手腳，畫在前面。 |
| Target runtime | Spine 4.2 JSON；驗證 runtime：官方 spine-webgl 4.2.119。目標引擎內未驗證。 |
| Required animations | `idle`(loop) · `walk`(loop，原地，141.67 px/s) · `wave`（轉向鏡頭揮手，回 idle）· `turn`（轉身換朝向，回 idle）· `blink`（自動 overlay） |
| Runtime controller | 朝向 = `skeleton.scaleX`；`turn` 的 `flip` 事件要求鏡射；`walk` 由控制器以 speed×朝向 位移。`look`／`turn`／`gaze` 三個控制骨。 |
| Art source | `art.py`（35 個 part），幾何與 `rig.py` 共用 `design.py` |
| Out of scope | 背面視角（轉身是左右換向，不露背）、跑、跳、手指、口型 |

## Acceptance

- [x] key art 全身＋頭部特寫看過
- [x] `spk fidelity` 通過；stress（含 IK 抬腳、蹲、揮手、鏡射朝向）看過
- [x] `spk check`：0 error／0 warning；落地腳滑動 ≤2.55 px／步
- [x] 真實播放看過：待機 → 向右走 → 轉身 → 向左走 → 揮手 → 待機；轉身逐格
- [x] 單檔預覽的「巡邏」來回走以無頭瀏覽器實跑
- [ ] 正常速度影片由人確認（`evidence/005/journey.mp4`）
- [ ] 目標引擎內實機
