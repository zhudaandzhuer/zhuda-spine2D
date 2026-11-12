# 生成圖層：提示詞範本

用法：先生成一張**主視覺**並通過 G1，再用「以主視覺為參考的編輯」逐層產生。每張都輸出到 `gen/`，尺寸與主視覺完全相同。
提示詞用英文（影像模型較穩）；`{…}` 換成你的角色描述。做完跑 `python3 spk.py layers <專案>`。

## 總則（每一則提示都附上）

```
Same canvas size and framing as the reference. Character stays in exactly the same position and scale.
Solid flat {CHROMA} background (#00FF00), no gradient, no floor, no cast shadow, no vignette, no text.
Flat, even lighting identical to the reference. Fully opaque shapes with clean edges, no glow, no soft fade-out.
Do not crop. Do not add anything that is not asked for.
```

- `{CHROMA}`：角色身上沒有的飽和色。預設純綠 `#00FF00`；角色有綠色就用洋紅 `#FF00FF`。不要用白、灰、黑（柔邊去不乾淨），也不要「透明背景」（常得到烘進像素的棋盤格）。
- 同一角色的所有圖層用同一個背景色。
- 圖層要畫成**不透明的實體**，邊緣乾淨。不要要求「柔邊淡出」「半透明」「發光」：單色去背在半透明區會偏色（綠底上的粉色會變橄欖色）。淡出交給 `layers.json` 的 `fade`。

## 1. 主視覺（key art）

```
{CHARACTER DESCRIPTION: age impression, hair style and colour, eye colour, outfit, mood}.
Front view, upper body from the hips up, arms relaxed at the sides, neutral expression with eyes open and mouth closed.
Symmetric, straight posture, head not tilted. Clean anime illustration, crisp edges, soft cel shading.
```

要求中性姿勢：頭不歪、嘴閉、眼睜、手臂自然下垂不遮身體。姿勢越中性，後面補畫越少。

## 2. 逐層（每一則都是「編輯主視覺」）

| 圖層檔名 | 提示重點（接在總則後） |
|---|---|
| `hair_back.png` | `Only the hair that hangs BEHIND the head, neck and shoulders, as one complete mass from the crown down to its tips. Remove the face, body, fringe and all hair in front of the shoulders. Paint the parts that were hidden behind the head and body.` |
| `torso.png` | `Only the clothed torso from the collar down, WITHOUT head, neck, hair and arms. Complete the shoulders and the chest areas that hair or arms were covering.` |
| `neck.png` | `Only the bare neck and the skin visible in the collar opening. Extend the neck upward well under where the chin was and downward under the collar. No head, no clothes.` |
| `arm_L.png` / `arm_R.png` | `Only the {screen-left / screen-right} arm with its sleeve, complete from the shoulder cap down, including the part the hair or torso was covering.` |
| `hair_long_L.png` … | `Only the single lock of hair that falls in front of the {screen-left} shoulder, complete from its root at the scalp to its tip.`（每束一張） |
| `face.png` | `Only the head's skin: face, forehead up to the top of the skull, ears and jaw, completely bald, with NO eyes, eyebrows, nose or mouth drawn (smooth skin where they were) and the same shading. No hair, no neck.` |
| `eye_white_L/R.png`、`iris_L/R.png` | 很小又要乾淨，建議直接從主視覺用多邊形切（`"source": "keyart"`），或用任何繪圖工具畫成全畫布 PNG；眼白要比眼眶大一圈。 |
| `hair_top.png` | `Only the hair on top of the head down to the hairline, as a cap, without the fringe strands and without any hair below ear level.` |
| `bang_*.png` | `Only the fringe (bangs) from where it leaves the scalp to its cut edge.`（要分片就各一張） |
| `mouth_*.png`（替換嘴型） | 以**主視覺的臉部裁切**為參考：`Same face, same position, only the mouth changes: {slightly open / open / small round "o" / gentle closed smile}.` 之後用和 `mouth_neutral` 同一個多邊形切出，標 `"hidden": true`。 |

五官（眉、鼻、嘴、睫毛）在主視覺上本來就完整可見：直接用多邊形從主視覺切，不必另外生成。
眼皮補片不要生成：在 `layers.json` 用 `"source": "@face"` 加多邊形從 `face` 複製，像素才會和臉完全一致。

## 3. 每張生成後自己先看

- 位置、大小是否和主視覺一致（明顯跑掉就重生，不要指望對位救回來）。
- 被要求補出的隱藏區是否真的畫了、和可見區同風格同光影。
- 背景是否真的是純色（`python3 spk.py key gen/x.png --out /tmp/x.png` 會回報偵測結果，並輸出深／淺／綠三底檢查圖）。
- 有沒有多畫東西（多一隻手、飾品、陰影）。

保存每張圖的提示詞與原始輸出在專案的 `gen/`；它們是可編輯來源，不進 runtime 包。
