# 30 動畫：分層、loop、track 與控制器契約

```python
a = rig.animation("idle", duration=6.0, loop=True)
a.osc("chest", "y", 2.2, period=3)                      # 呼吸
a.sway(long_L, 0.4, period=3, lag=0.07, grow=1.1)        # 髮鏈跟隨
```

數值都相對於 setup：`rotate` 度（逆時針為正）、位移像素（父骨空間、**y 向上**）、縮放倍率（1＝不變）。

## 分層是核心

每次呼叫加一層；**同一骨同一屬性的多層會相加**（縮放是相對 1 的增量相加）。所以可以把「呼吸」「重心擺動」「點頭」分開寫，不必手算合成值。
匯出時在所有層的關鍵時間聯集處產生 key 與 bezier（三分點控制點＝精確的三次多項式），不烘焙密集影格。

| 呼叫 | 說明 |
|---|---|
| `a.rotate(bone, [(t, deg[, ease])…], ease="ease")` | 關鍵幀層 |
| `a.translate(bone, [(t, x, y[, ease])…])`／`a.scale(bone, [(t, sx, sy)…])` | 同上 |
| `a.osc(bone, prop, amp, period, phase=0, bias=0, envelope=None)` | 正弦層；`prop`: `rotate / x / y / sx / sy`；`phase` 以週期為單位（0.25＝晚四分之一拍）；`envelope=[(t, 增益)…]` 淡入淡出 |
| `a.sway(bones, amp, period, lag, grow, phase)` | 沿鏈逐節延遲（`lag`）並放大（`grow`）的擺動 |
| `a.fn(bone, prop, f, t0, t1)` | 任意平滑函式 |
| `a.pose(t, {bone: {rot, x, y, sx, sy}}, ease)` | pose-to-pose：出現過的骨頭在每個 pose 時間都下 key，沒寫的屬性回到 setup |
| `a.attachment(slot, [(t, name|None)…])`／`a.alpha(slot, [(t, 0..1)…])` | 換圖／透明度 |
| `a.event(t, name)`（先 `rig.event(name)`）／`a.draw_order(t, {slot: ±n})` | 事件／換層 |
| `a.constraint(kind, name, keys)` | 原樣寫入 ik / transform / physics timeline |

`ease`（作用於離開該 key 的那一段）：`ease` 慢入慢出（預設）、`smooth` Catmull-Rom 通過、`linear`、`in`、`out`、`hold`。

## Loop

- 給 `duration` 與 `loop=True`。`osc/sway` 的 `period` 必須**整除** duration，位置與速度才都接得上。
- `spk check` 量 loop 接縫：`positionPx` 必須 0；`velocityJumpPxPerS` 過大會警告。
- 不同部位用不同相位與少數幾個可整除的週期（例：6 秒 loop 用 6／3／1.5），避免全身同相的機械感，也避免看得出來的短循環。

## Track 與契約（控制器是資產的一部分）

`rig.contract(animations={name: {...}}, controllers=…, mix=…, title=…, background=…)` 寫出 `NAME.contract.json`，預覽頁照它運作，整合進遊戲時也照它實作：

| 欄位 | 意義 |
|---|---|
| `role: base`、`loop: true`、`track: 0` | 常駐循環 |
| `role: action`、`return: "idle"` | 一次性動作，播完接回 `return` |
| `role: overlay`、`track: n` | 疊在上層 track；`loop: true` 可開關（說話）、`hold: true` 停在最後一格直到清除（表情）、`auto: {min, max}` 隨機自動觸發（眨眼） |
| `mix.default`、`mix.pairs: [[from, to, 秒]…]` | 混合時間 |
| `controllers.<name>: {bone, unit}` | 執行期輸入 [-1,1]² × unit 加到骨頭 local x/y（look、gaze）；`manual: true` 表示不跟指標 |
| `animations.<name>.speed`（px/s）、`.feet: [骨名…]` | 原地循環的移動速度與落地骨。控制器以 `speed × 朝向` 移動 skeleton；`spk check` 用它量落地腳滑動 |
| `events.<name>: {action: "toggle_facing"}` | 動畫事件要求控制器鏡射骨架（`skeleton.scaleX *= -1`）並重設物理 |
| `patrol: {walk, turn, min, max}`、`frame_portrait` | 預覽頁的來回走示範與直式畫面取景（示範用，非必要） |

Overlay 的要點：
- 高 track 會覆蓋低 track 同屬性的 key。眨眼放最高 track，表情次之，說話再次之。
- Overlay 的第一格與最後一格要等於底層在該屬性的「休息值」（例如眼皮平常就微垂 −3.5px，眨眼從 −3.5 出發回到 −3.5），否則 mix-in 會先抖一下。
- 表情（`hold`）只 key 會變的屬性：眉、眼皮、嘴、腮紅。

## 表演順序（每個動作都一樣）

預備（反方向一小步）→ 主動作（加速）→ 到位 → 回彈／停留 → 回位。眼睛先動、頭跟上、頭髮最後（物理或 `sway` 的 lag）。
先用 3–5 個 pose 把意圖讀出來，再調時間；中間姿勢不是越多越好。局部無破洞、端點一致、「自然」是三件不同的事。

## 轉場與中途打斷

三種驗收互不代替：單一 clip → 任意兩 clip 的混合 → 產品實際的操作路徑（連點、中途反向、排隊）。
`spk play --cues` 驗第二、三種。若某組動作必須靠共同進度或 bridge 才自然，把那個控制器行為寫進契約並一起交付；只搬 JSON 不算完成。
靜態 `seek`（shot / sheet）不經過 mix 與事件，不能當轉場證據。

## 朝向與轉身

朝向是**控制器狀態**（`skeleton.scaleX = ±1`），不是某段動畫能擁有的東西：所有動畫只做「朝右」一種，朝左是同一副骨架鏡射。
轉身動畫的做法（`examples/xiaoshuang` 的 `turn`）：

1. 讓姿勢在中點變成**左右對稱**——頭與身體的假 3D 轉向歸零、兩臂兩腿對稱、側視的鞋換成正面鞋。
2. 在那個瞬間發出事件（`flip`），控制器鏡射骨架。因為姿勢對稱，鏡射在畫面上幾乎看不出來，不會有「紙片翻面」。
3. 後半段照樣播「轉向 3/4」——在鏡射後的空間裡，那就是轉向另一邊。

要點：中點的 key 用零斜率（`ease`），事件晚一格觸發也還在對稱姿勢上；鏡射後物理要 reset；`near/far` 命名的肢體鏡射後仍是 near/far。
只鏡射、不經過對稱姿勢（scaleX 穿過 0）會像卡片翻面；需要真的露出背面時，要另外畫背面圖層在中點換圖。

## 步態（全身角色）

- 先定移動契約：動畫是否含 root 位移、角色世界速度、支撐期比例。clip 內已有 root 位移時，引擎不可再疊一次。
- 接地品質看**接地點的世界速度**：`v_world = v_character + d(contact_local)/dt`，支撐期應接近 0；IK 誤差小不代表不滑步。
- 做法：腿用兩骨 IK，腳目標骨掛在 `root` 下（臀部上下起伏時腳仍踩在原地）；用 `a.fn()` 寫腳目標的 x／y／滾動。在契約寫 `speed` 與 `feet`，`spk check` 會回報每隻腳的落地比例與「每次落地滑動幾 px」（預設 >3px 算錯）。loop 接縫不要放在落地瞬間。
- 腳軌跡初稿：支撐段線性 `x = -S + 2S·p/c`、`y = 0`；回擺用 Hermite 由 +S 回 −S，兩端切線 `2S(1-c)/c`；抬腳 `lift·16u²(1-u)²`。`python3 spk.py util gait --help` 可輸出目標 CSV（規劃用，不是完整動畫）。
- 披風／長髮：根部附著、末端延遲與振幅較大；所有骨同相正弦會像硬板或海草。
