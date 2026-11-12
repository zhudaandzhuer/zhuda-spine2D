# 霜 (Shuang) — brief

| Item | Decision |
|---|---|
| Identity | 原創角色。參考：使用者提供的一張短劇截圖（長直黑髮、齊瀏海＋姬髮式、白皙膚色、灰藍眼、白襯衫、沉靜憂鬱的神情）。 |
| Reference use | **身份類型參考**（髮型、配色、氣質、半身構圖）；不是逐像素重現，也不沿用該角色的臉部細節。 |
| View / framing | 正面半身（腰上），前臂以下出鏡。取景 `FRAME = (130, 40, 740, 960)`，美術畫到 y=1200 讓身體晃動時不露底。 |
| Side convention | `_L/_R` = **畫面**左／右。 |
| Target runtime | Spine 4.2 JSON；驗證 runtime：官方 spine-webgl 4.2.119。目標引擎（LayaAir 3.x）內的實機表現：未驗證。 |
| Required animations | `idle`(loop) · `nod` `shake` `tilt` `look_around` `surprised` `hair_wind`（動作，回 idle）· `smile` `sad`（表情，hold）· `talk`（loop overlay）· `blink`（自動 overlay） |
| Runtime controllers | `look`（假 3D 轉頭，±22px）、`gaze`（視線，±4px）；物理：頭髮 49 根骨 |
| Canvas | 1000×1200 source px；原點在底邊中央 |
| Art source | 程序化：`art.py`（SVG → 36 個 part），幾何與 `rig.py` 共用 `design.py` |
| Out of scope | 手、下半身、側面／背面視角、口型對嘴（`talk` 只是示意循環） |

## Acceptance

- [x] key art 全身＋臉部特寫看過（evidence/art）
- [x] `spk fidelity` 通過；stress 全身＋臉部看過
- [x] 每個動畫的時序圖看過；轉場用 `spk play` 看過
- [x] `spk check` 無 error／warning
- [x] 匯出包與單檔預覽從新位置開啟
- [ ] 正常速度影片由人確認（agent 只看了時序圖片；`evidence/003/showcase.mp4` 供人看）
- [ ] 目標引擎（LayaAir）內實機
