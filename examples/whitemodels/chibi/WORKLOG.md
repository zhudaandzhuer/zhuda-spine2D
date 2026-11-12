# 白模 chibi — worklog

## State

- current build: **001**（由工具包 2.6 從零重建）
- 數值：`spk fidelity` 差異 0.0；`spk check` 0 error／0 warning；烘焙後腳的目標全部搆得到（reach 0）
- 落地腳滑動（px／步）：{'walk': [0.91, 0.04], 'run': [0.32, 0.32]}
- JSON 2.8 MB，10 個 clip；視角切換共 141 次；「去了馬上回來」的切換：{'kungfu': 6}
- 換皮：模板 73 張在 `skin/`；除錯皮用 `python3 spk.py skin . --debug` 建立

## 我實際看過的圖

最後一次重建的圖**沒有重看**；前一版看過 360° 走 8 格，更早看過 11 個關鍵姿勢。

包內的證據圖（`evidence/001/`）是這一版產生的：`sheets/turntable_full.jpg`、`stress/stress_full.jpg`。

## 沒看過、不能替你下結論的

- 正常速度的播放（只看過靜態格）。
- 逐格時序、`turn` 的過程。
- 配件在動作中的擺動是否自然。
- 用真正的美術換皮的結果——這是下一步要測的。
