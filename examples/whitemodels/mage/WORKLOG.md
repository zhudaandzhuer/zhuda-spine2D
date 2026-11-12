# 白模 mage — worklog

## State

- current build: **001**（由工具包 2.6 從零重建）
- 數值：`spk fidelity` 差異 0.0；`spk check` 0 error／0 warning；烘焙後腳的目標全部搆得到（reach 0）
- 落地腳滑動（px／步）：{'walk': [0.18, 0.03], 'walk_L': [0.03, 0.18], 'run': [0.07, 0.05], 'run_L': [0.05, 0.07]}
- JSON 2.22 MB，15 個 clip；視角切換共 74 次；「去了馬上回來」的切換：無
- 換皮：模板 75 張在 `skin/`；除錯皮用 `python3 spk.py skin . --debug` 建立

## 我實際看過的圖

最後一次重建的圖**沒有重看**；前一版看過除錯皮 360° 走 8 格（長袍蓋住腿）與 9 個關鍵姿勢（含朝左施法）。

包內的證據圖（`evidence/001/`）是這一版產生的：`sheets/turntable_full.jpg`、`stress/stress_full.jpg`、`skin_debug/sheets/turntable_full.jpg`。

（2.7 補充：因為「包覆規則也套用到靜止姿勢」，這一套重建過一次；重建後 fidelity、check 仍通過，圖沒有重看。）

## 沒看過、不能替你下結論的

- 正常速度的播放（只看過靜態格）。
- 逐格時序、`turn` 的過程、大部分 `_L` 版本。
- 配件在動作中的擺動是否自然。
- 用真正的美術換皮的結果——這是下一步要測的。
