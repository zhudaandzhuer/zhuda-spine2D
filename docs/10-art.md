# 10 美術：身份、拆件與分層

## 身份先於一切

角色先像本人，才談骨架。常見誤判：動畫都能播、數值都通過，但使用者說「這不是他」——那是 `ART` 問題。
等高度、同鏡頭比較頭身比、頭輪廓、五官相對位置、手掌大小、服裝主輪廓；不要各自縮放到滿版再比。

## Part 契約

- **一個 part ＝ 一個會獨立運動、遮擋或變形的東西。** 不是越碎越好；輪廓連續與歸屬正確優先於可編輯性。
- **畫滿被遮住的部分。** 裁切不會創造像素：肩根、頸部上下端、瀏海下的額頭、眼眶後的眼白、袖口內的手腕。極限姿勢露出硬切邊或別的部位殘色，只能回來補畫，不能用遮罩或縮小動作掩蓋。
- **同一視覺元素只屬於一個 part**（owner）。同一 slot 的替換圖（嘴型、手勢、開閉眼）用 `hidden=True` 標成非 setup。
- 命名帶語意與側別：`arm_L`、`hair_long_R`、`mouth_open_s`。
- 前後順序就是 `art.part()` 的呼叫順序（後畫的在上面），也是 Spine 的 slot 順序。

## 用程式畫（`art.py` + `spinekit.svgart`）

```python
from spinekit.svgart import Art, smooth, poly, ribbon, mirror, shift, path, circle, ellipse, group
art = Art(1000, 1200)                           # 畫布像素；x 向右、y 向下；rig.py 用同一組座標
skin = smooth([(500,150), (600,240), (560,430), (500,454), (440,430), (400,240)])   # Catmull-Rom 平滑閉合路徑
clip = art.clip(skin)
art.part("face",
         path(skin, fill="#f9ebe5"),
         group(ellipse(500, 460, 66, 22, fill="#edd0ce", opacity=.6, filter=art.blur(8)), clip_path=clip))  # 陰影裁在輪廓內
```

| 工具 | 用途 |
|---|---|
| `smooth(pts, closed, tension)` | 通過所有點的平滑路徑；`tension=0` 變折線 |
| `ribbon(center, widths)` | 沿中心線的漸細形狀：髮束、尾巴、眉毛 |
| `mirror(pts, cx)` / `shift(pts, dx, dy)` | 左右對稱與平移（用數值鏡射，不用 SVG transform，高光才不會跟著翻） |
| `art.linear / radial` | 漸層（畫布座標）；`art.blur(std)` 柔邊；`art.clip(d, rule)` 裁切；`art.mask_fade(...)` 邊緣羽化 |
| `art.part(name, *svg, hidden=False)` | 新增 part |

實戰要點（都來自 `examples/shuang/art.py`）：
- **共用幾何放 `design.py`**，`art.py` 與 `rig.py` 都 import——樞紐點、眼眶曲線只定義一次。
- **眼睛**：眼白＋虹膜畫在臉的**後面**，臉皮上開眼眶洞（`fill_rule="evenodd"`）；虹膜移動時自然被眼眶裁切，不需要 clipping attachment。
- **眼皮**：一塊膚色補片＋睫毛。補片上緣羽化、其餘不透明，並**重用臉部同一組陰影元素**（寫成函式兩邊呼叫），張眼時與臉完全融合，閉眼時拉下來就是眼瞼。
- **瀏海與頭頂**：瀏海上緣用 `mask_fade` 融進頭頂髮片，同色不見接縫。
- 深色頭髮加冷色邊光與少量髮絲線，否則在深色背景上讀不出輪廓。

`spk art` 之後一定要看 `evidence/art/keyart_bg.png` 與 `parts_sheet.png`。

## 用生成圖或手繪稿

平面圖、帶純色背景的圖、位置略有漂移的逐層圖：走 `spk layers`（去背、對位、多邊形切割、接縫檢查、提示詞範本），見 `15-imagegen-layers.md`。

## 用已經分好層的 PNG

已有真 alpha、位置正確的圖層：刪掉 `art.py`，自己提供：

```
parts/NAME.png            RGBA、有真正 alpha、未縮放
parts/manifest.json       {"canvas":[W,H], "parts":[{"name":"face","file":"face.png","x":388,"y":150,"w":224,"h":306}, …]}
parts/keyart.png          （選用）完整姿勢參考；有它才能跑 spk fidelity
```

`x,y` 是該圖左上角在畫布上的位置；`parts` 陣列順序＝由後到前。之後直接 `spk build`。

- 生成圖常把棋盤格烘進 RGB：檢查實際 alpha channel，不看副檔名。
- 去背不要用單一亮度閾值：會吃掉眼睛高光、淺色袖口、髮絲半透明邊。深／淺／飽和三種底都看。
- 配準用解剖基準（掌寬、腕口中心、指根線），不用整張 bbox——伸指與握拳的 bbox 不同，會把手掌縮小。
- 只有**不存在的視覺資訊**（側掌、手背、衣服背面）才需要補畫或生成；位置錯、掛錯、層序錯都不是生圖能解的。
- 保存 prompt、原始結果、裁切框與處理腳本在專案內，不放進 runtime 包。

## Alpha 與邊緣

圖集打包時會自動把全透明像素的 RGB 往外擴（`bleed`），避免線性取樣把透明區的黑／白混進邊緣——這只解決取樣汙染，不補輪廓。
原圖乾淨、縮小後才出現黑點或白邊 → 先看 `60-runtime-delivery.md` 的取樣診斷，不要急著重畫。

## 手

手是最容易讓整個角色失敗的部位。掌背與掌心是不同的美術表面，鏡射或負 scale 不能互換；伸指與彎指不能用腕到指尖總長對齊。需要手部動作時先讀 `80-hands-arms.md`。
