# 八個白模（換皮測試用）

每個白模都是：一種身體比例＋配件，加上從 3D 烘出來的動作。做法見 `docs/35-figure3d.md`，換皮流程與驗收見 `docs/38-reskin.md`。

| 白模 | 類型 | 高(px) | 圖片數 | clip | JSON(MB) | 朝左的做法 | check |
|---|---|---|---|---|---|---|---|
| `hero` | 標準成人（圍巾） | 623 | 71 | 10 | 2.87 | 鏡射 | 通過 |
| `heroine` | 女性成人（馬尾、裙） | 600 | 72 | 10 | 2.96 | 鏡射 | 通過 |
| `chibi` | Q 版大頭（雙馬尾） | 407 | 73 | 10 | 2.8 | 鏡射 | 通過 |
| `brute` | 壯漢（披風、手持棍棒） | 584 | 69 | 19 | 5.08 | clip 變體 | 通過 |
| `mascot` | 吉祥物（耳朵、口鼻、尾巴、側背包） | 381 | 74 | 19 | 5.59 | clip 變體 | 通過 |
| `knight` | 盾牌戰士（盾、劍、肩甲、盔纓） | 613 | 81 | 17 | 2.5 | clip 變體 | 通過 |
| `mage` | 魔法師（尖帽、長袍、寬袖、法杖） | 616 | 75 | 15 | 2.21 | clip 變體 | 通過 |
| `vtuber` | 正面看板／虛擬主播（臉部零件、參數驅動、即時物理頭髮） | 617 | 92 | 9＋12 參數 | 1.97 | 鏡射 | 通過 |

前五個共用同一組十段動作（idle、walk、run、jump、wave、pick、turn、turntable、kungfu、dance）。`vtuber` 是面向鏡頭的表演角色（9 個正面 clip＋12 個即時參數，見 `docs/39-front-performer.md`）。`knight` 與 `mage` 是職業角色：idle、walk、run、jump、turn、turntable 加上各自的類別動作（`knight`：block、slash、bash；`mage`：cast、channel）。

它們各自壓到的邊界：

- `hero`：基準。頸後一條鏈（圍巾）。
- `heroine`：窄肩寬髖、細四肢；頭上的鏈（馬尾）；裙錐會被大腿頂開，髖與大腿永遠畫在裙子下面。
- `chibi`：頭是全身的 2.5 分之一高，腿長只有成人的 42%——步幅、起伏、跳躍全部按腿長縮放，步頻變快。
- `brute`：肩寬是成人的 1.5 倍、手臂粗長；背後兩片布片（披風）；右手拿棍棒＝不對稱，朝左用 `_L` clip。
- `mascot`：圓身短肢；頭上的耳朵與口鼻（剛性配件）、尾巴（鏈）、左肩側背包（擺錘）＝不對稱。
- `knight`：左前臂上的盾（板狀、有正反面，8 個視角）、右手的劍（薄片）、肩甲（剛性）、盔纓（鏈）。盾擋在身前的攜帶姿勢；類別動作：舉盾格擋、揮砍、盾擊。
- `vtuber`：臉是 3D 表面上的零件（眼、眉、嘴有狀態圖）；頭、身體、視線、眨眼、嘴型由即時參數疊加；頭髮由 runtime 物理模擬。
- `mage`：尖帽（帽簷＋會晃的帽尖）、長袍（包住整條腿，只有腳露出）、寬袖（包住前臂）、右手的法杖（比人高）。法杖直立的攜帶姿勢；類別動作：施法、引導（loop）。

## 在電腦上做換皮測試

```sh
python3 spk.py doctor
python3 spk.py skin examples/whitemodels/knight --debug
python3 spk.py --skin debug sheet examples/whitemodels/knight --anim turntable --n 8      # 閘門 S0
# 之後照 docs/38-reskin.md：放圖 → spk reskin → --skin X sheet / stress / play
```

重建任何一個白模：`python3 spk.py art <dir> && python3 spk.py build <dir> && python3 spk.py check <dir>`（產出與包內逐位元組相同）。

## 目前確定與不確定的

確定（有數值）：八個都能建、fidelity 0、數值檢查無錯誤無警告、腳不滑、腳的目標全部搆得到。除錯皮在 hero／brute／mascot／knight／mage 上看過，視角戳記與左右都對（各自看的是哪一版，寫在各自的 WORKLOG）。

不確定（要靠換皮測試回答）：真正的美術貼上去好不好看；8 個視角夠不夠；視角切換的跳動能不能接受；配件穿過身體有多礙眼；目標引擎是否支援 shear／drawOrder／rgba／attachment 四種 timeline 的組合。
