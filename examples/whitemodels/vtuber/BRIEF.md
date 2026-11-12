# 白模 vtuber — 正面看板／虛擬主播（臉部零件、參數驅動、即時物理頭髮）

| Item | Decision |
|---|---|
| 用途 | 面向鏡頭的表演：看板、吉祥物、虛擬主播。做法見 `docs/39-front-performer.md` |
| 身體 | `F.Body("vtuber")`，高約 617px，左右對稱；頭比成人大 18% |
| 臉 | 零件貼在頭部橢球上：眼白（open／half／closed 三張）、虹膜（可移動、閉眼時隱藏）、眉、鼻、嘴（closed／smile／open1–3）、腮紅、瀏海、側瀏海、耳 |
| 頭髮 | 髮罩（剛性）；後髮一條、兩側髮束各一條，由 runtime 物理模擬（共 9 個 physics constraint）|
| Clip | front_idle、talk、idol、greet、bow、cheer、present、heart、spin |
| 即時參數 | AngleX、AngleY、AngleZ、BodyAngleX、BodyAngleZ、EyeBallX、EyeBallY、BrowY、Cheek、Smile、MouthOpen、Blink（track 10 起，additive）|
| 圖片數 | 92 張（胸、骨盆、兩腳各 8 視角；頭 1 張）|
| JSON | 1.97 MB |
| Target runtime | Spine 4.2 JSON；驗證 runtime：spine-webgl 4.2.119。目標引擎內未驗證 |
