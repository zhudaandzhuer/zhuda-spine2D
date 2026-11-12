# 39 正面表演：看板角色與虛擬主播

側面走跑跳是遊戲角色的需求；看板、吉祥物、直播主的需求是**面向鏡頭**：打招呼、鞠躬、歡呼、介紹、跳舞，以及即時跟著輸入轉頭、眨眼、說話。白模 `vtuber` 是這一類的底模，做法都在 `figure3d`／`motions3d` 裡，任何身體都能用。

## 三件事

1. **正面 clip**（track 0）：`front_idle`、`talk`、`idol`（loop）；`greet`、`bow`、`cheer`、`present`、`heart`、`spin`。寫法和其他 clip 一樣是 3D 姿勢，只是 `heading = 0`。
2. **臉是零件，不是貼圖**：眼白、虹膜、眉、鼻、嘴、腮紅、瀏海是貼在頭部橢球表面上的小片，和頭一起在 3D 裡轉——轉頭時自然前縮，轉到背面自動被頭擋住。眼睛、嘴是**狀態圖**（`eye_L_open／half／closed`、`mouth_closed／smile／open1／open2／open3`），同一個位置換圖。
3. **即時參數**：每個參數是一段 1 秒的 clip，時間的意義是「數值」。控制器把它停在對應的時間、放在自己的 track、用 additive 混合，就會疊在 track 0 的任何 clip 上。

| 參數 | 範圍 | 做什麼 |
|---|---|---|
| `AngleX`／`AngleY`／`AngleZ` | ±30／±20／±20 | 頭左右、上下、傾斜 |
| `BodyAngleX`／`BodyAngleZ` | ±15／±10 | 身體左右轉、側傾 |
| `EyeBallX`／`EyeBallY` | ±1 | 視線 |
| `BrowY` | −1…1 | 眉毛（負值＝皺眉）|
| `Blink` | 0…1 | 閉眼（換狀態圖，虹膜跟著隱藏）|
| `MouthOpen` | 0…1 | 張嘴（對嘴用）|
| `Smile`／`Cheek` | 0…1 | 微笑嘴型／腮紅 |

契約 `parameters: [{id, clip, min, max, default, track}]`。Runtime 每格要做的事（參考 `viewer/viewer.js` 的 `applyParams`）：

```js
e = state.setAnimation(track, clip, false);  e.timeScale = 0;  e.mixBlend = MixBlend.add;  e.alpha = 1;   // 一次
e.trackTime = animation.duration * (value - min) / (max - min);                                              // 每格
```

預覽頁內建四種驅動：跟隨手指、自動擺動＋自動眨眼、說話（模擬音量的嘴型）、表情。接上臉部追蹤或麥克風音量時，換掉驅動來源即可，骨架不用動。

## 頭髮要即時反應

烘焙好的模擬（馬尾、披風）不會回應即時輸入。`rchain` 配件改由 runtime 模擬：掛點是烘出來的骨頭（跟著頭在 3D 裡移動），掛點下面是真正的 Spine 骨鏈＋physics constraint。`vtuber` 的後髮與兩側髮束就是這樣做的。

## 一定要遵守的規則

**被參數疊加的 clip，必須 key 每一個參數會動到的屬性。** additive 是「加到骨頭目前的值上」；底下的 clip 沒有每格把它設回去，就會逐格累加——胸口幾秒內縮成一條線（這是實際發生過的錯）。`F.bake(..., key_all=True)` 會寫出所有通道；`spk check` 會檢查，缺了就是 error。

其他：
- 參數 clip 是「相對休息姿勢的差值」，不寫 draw order、不寫深度色調（`F.bake(..., param=True)`）。
- 預設值在時間 0 的參數（Blink、MouthOpen、Smile、Cheek）在預設值時不寫任何 key，所以 track 0 的 clip 自己做的表情（打招呼時的笑）不會被蓋掉。
- 兩個參數同時推到極端時是線性相加，不是真正的 3D 合成：頭同時左轉 30°又低頭 20° 會有些微變形。

## 換皮

和其他白模相同（`38-reskin.md`），多了兩種圖：
- **狀態圖**（`kind: state`）：同一個 slot 的幾張圖（眼睛三張、嘴五張），位置與軸心相同。
- **臉部零件**都是「正面畫的一小片」：轉頭時由程式壓扁，不需要畫各角度。頭本身只有一張圖。

## 驗證到哪裡

`vtuber`：fidelity、數值檢查全過（含參數規則）；22 個姿勢（9 個 clip 的關鍵格＋12 組參數）看過全身與半身；手機尺寸的即時預覽實跑過自動擺動、跟隨、說話、表情，量過胸口縮放不再累積；16 秒連續表演看過時序圖。
沒驗證：正常速度的觀感、真正的臉部追蹤輸入、真的美術貼上去的臉、其他身體（`mascot`、`chibi`…）套用正面 clip。
