# 白模 knight — worklog

## State

- current build: **001**（由工具包 2.6 從零重建）
- 數值：`spk fidelity` 差異 0.0；`spk check` 0 error／0 warning；烘焙後腳的目標全部搆得到（reach 0）
- 落地腳滑動（px／步）：{'walk': [0.16, 0.42], 'walk_L': [0.42, 0.16], 'run': [0.09, 0.09], 'run_L': [0.09, 0.09]}
- JSON 2.5 MB，17 個 clip；視角切換共 124 次；「去了馬上回來」的切換：{'run_L': 1}
- 換皮：模板 81 張在 `skin/`；除錯皮用 `python3 spk.py skin . --debug` 建立

## 我實際看過的圖

這一版看過：除錯皮的盾擊、格擋、360° 走中兩個接近側看的時刻（盾的視角戳記與盾面方向一致，沒有被拉扯的破圖）。前幾版看過白模與除錯皮的 360° 走、10 個關鍵姿勢。這一版的 360° 走整圈與關鍵姿勢圖**沒有重看**。

包內的證據圖（`evidence/001/`）是這一版產生的：`sheets/turntable_full.jpg`、`stress/stress_full.jpg`、`skin_debug/sheets/turntable_full.jpg`。

## 沒看過、不能替你下結論的

- 正常速度的播放（只看過靜態格）。
- 逐格時序、`turn` 的過程、大部分 `_L` 版本。
- 配件在動作中的擺動是否自然。
- 用真正的美術換皮的結果——這是下一步要測的。
