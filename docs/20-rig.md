# 20 Rig：`rig.py` API 與配方

`spk build` 匯入專案的 `rig.py`，呼叫 `build(rig)`，輸出到新的 `build/NNN/`。
所有座標都是**畫布像素（x 向右、y 向下）**——和美術同一套數字。編譯器負責換成 Spine 的 y 向上、經過真正的父骨矩陣反解 local。

```python
from spinekit import weights as W
NAME = "hero"
def build(rig):
    rig.frame(130, 40, 740, 960)                 # 取景（畫布像素）；寫進 skeleton 與 contract
    rig.bone("root", at=(500, 1200))
    rig.bone("chest", "root", at=(500, 730), tip=(500, 560))
    …
```

## 骨頭

| 呼叫 | 說明 |
|---|---|
| `rig.bone(name, parent, at, tip=None, rot=None, length=None, inherit=None)` | 父骨必須先宣告。方向：`tip`（指向該點，同時決定長度）> `rot`（世界角度，逆時針，0＝朝右）> 0。 |
| `rig.chain(prefix, parent, points, inherit_first=None)` | 沿折線建立 `prefix1..n`，回傳名稱清單。 |
| `inherit="noRotationOrReflection"` | 父骨旋轉時保持自己的世界角度：**垂掛的頭髮、布料**根骨用它，歪頭時髮束仍然垂直。 |

命名用語意（`chest`、`arm_up_L`、`long_L3`），不要 `bone7`。物理（rotate）需要骨長 > 0，所以鏈骨一律用 `tip`/`chain`。
要當「螢幕座標控制器」父層的骨頭（例如 `head`）用 `rot=0`，子骨的 x/y 才等於畫面左右上下。

## Part → slot / attachment

`rig.part(name, bone, slot=None, mesh=None, weights=None, active=True, color=None, blend=None)`

- 沒給 `mesh`/`weights` → region attachment，剛性跟著 `bone`。
- `mesh=dict(step=px | cols=, rows=, margin=3, cull=True)` → 依 alpha 裁掉空格的規則網格，hull 在前且依序（Editor 也能正確匯入）。
- `weights=<權重場>` → 加權網格。`bone` 只是 slot 掛的骨，選一根穩定的即可。
- 同一 `slot` 多個 part ＝ 可切換的 attachment（`active=False` 的不在 setup 顯示）。
- `color="ffffff00"`：slot 初始顏色／透明度（例如腮紅預設透明，由動畫的 `alpha()` 淡入）。
- manifest 裡每個 part 都必須有 owner，否則 build 失敗；刻意不用的寫 `rig.ignore("name")`。

網格密度：沿彎曲方向至少 6–12 格；窄長髮束用 `cols=3, rows=20+`；臉 20–26px 一格；只做剛性移動的東西不需要網格。

## 權重場（`spinekit.weights`）

權重是**位置的解析函式**，不是手刷的：兩個 part 用同一個場，重疊處就會一起動（睫毛貼著臉、領口貼著胸）。

| 場 | 用途 |
|---|---|
| `W.chain(bones, blend=0.5, root=None, root_blend=0.5)` | 沿骨鏈平滑過渡：手臂、髮束、尾巴、脊椎。`root` 是鏈起點之前的擁有者（髮束上端交給 `head`）。 |
| `W.sheet([chainA, chainB, …], blend, root)` | 多條平行鏈驅動一整片：後髮、披風、裙片。鏈要依空間順序列出。 |
| `W.depth(base, front, z, back=None)` | 視差：`z(sx, sy)∈[-1,1]`，+1 完全跟 `front`（look 控制骨），−1 跟 `back`。 |
| `W.layered(inner, base, front, z, back)` | 把 `inner` 分給 `base` 的那一份再依深度拆開（後髮上端跟頭、又帶反向視差）。 |
| `W.blend(a, b, mask)` | `(1-mask)·a + mask·b`。眼皮：外緣貼臉、睫毛帶跟眼皮骨。 |
| `W.nearest(bones, power, k)` | 反距離；鈍器，能用前面幾種就不要用它。 |
| 自訂 | 任何 `f(rig, sx, sy) -> {bone: weights}`；輸入是畫布像素陣列。 |

輸出自動正規化、去掉 <1.5% 的小權重、每頂點最多 4 個 influence。

## 假 3D 轉頭：look 控制器

```python
zface = rig.ellipsoid(cx=500, cy=322, rx=146, ry=188)      # 頭部表面的深度場：中心 1、輪廓 0
look = rig.look("look", parent="head", at=(500, 330), unit=22, back="look_back")
look.follow("eye_L", rig.depth_at(zface, 447, 320))         # 五官骨依所在位置的深度跟隨
look.follow("nose", 1.12)                                   # 鼻尖比臉面更前
rig.part("face", "head", mesh=dict(step=22), weights=W.depth("head", "look", zface))
```

- 移動 `look` 骨 (u, v) → 每個 follower 位移 (u, v)×mix；臉皮網格依深度場連續變形（近側拉伸、遠側壓縮）。`back` 骨反向移動，給後髮用。
- 編譯成 Spine 的 transform constraint（local + relative），同 mix 的骨頭合併成一條；任何 4.2 runtime 都能跑，不需要自訂程式。
- follower 必須與控制骨同一個父骨（同一座標空間）。
- 第二個控制器（視線）：`gaze` 骨＋一條 `rig.transform(..., mix_x=1, mix_y=1, x=-g.lx, y=-g.ly)` 帶動兩顆虹膜。
- contract 會列出控制器（骨名、單位）；預覽頁用指標驅動它，遊戲裡照 contract 設骨頭 local x/y 即可。

## 其他約束與物理

| 呼叫 | 說明 |
|---|---|
| `rig.transform(name, bones, target, mix_x, mix_y, mix_rotate, …, local=True, relative=True, x, y, rotation)` | 原樣對應 Spine transform constraint。 |
| `rig.counter_rotate(name, bones, target, mix=-1)` | 讓骨頭抵銷目標的動畫旋轉。 |
| `rig.ik(name, bones, target, bend_positive, mix, softness, stretch)` | 一或兩根骨的 IK。 |
| `rig.physics(bone, rotate=1, inertia, strength, damping, mass, wind, gravity, mix)` | Spine 4.2 物理，一根骨一個。 |
| `rig.physics_chain(bones, inertia=(根,梢), strength=(根,梢), damping=(根,梢), mix=(根,梢))` | 沿鏈內插；越往梢越軟。 |

**約束的套用順序 = 在 `rig.py` 宣告的順序**（look 控制器以 `rig.look()` 的位置計）。順序有意義：腿的 IK 要先於「讓腳掌跟隨目標骨旋轉」的 transform，物理放最後。
兩骨 IK 的 `bend_positive` 決定膝蓋朝哪邊，用一個抬腳的 stress pose 看一次就知道。

物理起手值：瀏海 `strength 150–190, damping .8`；及肩髮束 `110–150, .82–.86`；長髮 `70–120, .84–.9`；`inertia` 根 .35–.4、梢 .7–.8。
關掉物理（`rig.set(physics=False)`）角色也必須成立：idle 的髮絲擺動用關鍵幀做，物理只負責反應。目標引擎是否支援 4.2 物理要實測。

## 極限姿勢

`rig.stress(name, pose={bone:{rot,x,y,sx,sy}}, slots={slot: attachment}, look={"look":[x,y]})`
在 setup 上疊加（旋轉／位移相加、縮放相乘），存到 `.stress.json`，**不進 runtime 包**。每個自由度至少一個：控制器四向與對角、歪頭、閉眼／半閉、每個嘴型、聳肩、呼吸、手臂、頭髮左右甩。

## 選項

`rig.set(padding=4, bleed=6, pma=False, max_influences=4, physics=True)`；`rig.set_origin(x, y)`（預設畫布底邊中央；**會移動的角色請設在兩腳之間的地面點**，遊戲移動的就是這個點）；`rig.frame(x, y, w, h)`；`rig.world_rect(x, y, w, h)` 把畫布矩形換成骨架座標（寫額外的 contract 取景用，不要手算）。

## 資料不變量（改既有 JSON 時也適用）

- JSON、atlas、PNG 是一組，永遠一起更新。
- 加權頂點格式是 `[influence 數, 骨索引, localX, localY, weight, …]`，頂點數由 UV 數決定，不是 `vertices.length/2`。
- 改拓撲要同步 UV、triangles、hull/edges、weights、deform timeline、linked mesh。
- 骨頭順序父先於子；重排骨頭要遷移所有加權網格裡的骨索引。
- world→local 一律用父骨矩陣反解；有旋轉、縮放、shear 時不能直接相減。
- 檢查工具以「slot＋attachment 身份」追蹤，不用陣列位置（動畫會換圖、換 draw order）。
