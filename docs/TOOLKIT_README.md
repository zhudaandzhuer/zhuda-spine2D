# spine2d-master 2.7 — 給 agent 用的 Spine 4.2 角色工程包

把「角色描述或分層圖」一步步做成可在 Spine runtime 播放的資產，每一步都有可執行的指令與必須通過的閘門。
Agent 從 [`SKILL.md`](../SKILL.md) 進入；人想快速了解看這一頁。

## 30 秒上手

```sh
python3 spk.py doctor                         # 檢查環境（Python 3.9+、Pillow、numpy、Node 18+、Playwright+Chromium）
python3 spk.py init my-char --name mychar     # 產生專案（附一隻可直接跑完流程的示範小動物）
python3 spk.py art my-char                    # 分層美術 → parts/
python3 spk.py build my-char                  # → build/001/mychar.json / .atlas / .png
python3 spk.py fidelity my-char               # 原生 setup 是否重現 key art
python3 spk.py check my-char                  # 數值閘門
python3 spk.py stress my-char                 # 極限姿勢 sheet（要打開看）
python3 spk.py preview my-char                # 本機即時預覽
python3 tests/selftest.py                     # 工具包自我測試（36 項）
```

Spine runtime 已隨包附上（`node_modules/`，4.2.119，離線可用）；唯一需要另外準備的是 Playwright＋Chromium（原生截圖用）。

## 目錄

| 路徑 | 內容 |
|---|---|
| `SKILL.md` | 唯一入口：規則、流程、指令速查、文件路由 |
| `spk.py` | 唯一 CLI |
| `spinekit/` | 編譯器：`rig.py`（骨架／網格／約束／動畫 → Spine JSON）、`weights.py`、`curves.py`、`meshgen.py`、`atlas.py`、`svgart.py`、`layers.py`（生成圖 → 零件）、`sheets.py` |
| `tools/` | `capture.mjs`（原生截圖）、`sweep.mjs`（數值閘門）、`raster_svg.mjs`、`softrender.mjs`（診斷）、`py/`（沿用的稽核／精簡／重排／步態等工具） |
| `viewer/` | 原生預覽頁＋QA adapter＋契約的參考實作 |
| `docs/` | 13 份主題文件，依流程編號（`15` 生成圖 → 零件；`35` 白模；`38` 換皮；`39` 正面表演） |
| `templates/` | 專案模板、驗收表、手部契約範例、`imagegen/`（提示詞範本與 `layers.json` 起始檔） |
| `examples/shuang/` | 半身角色：臉部表演、頭髮物理（來源、三個 build、證據、WORKLOG、匯出包） |
| `examples/xiaoshuang/` | 全身 Q 版角色：走路、揮手、轉身（IK 腿、朝向鏡射、來回走示範） |
| `examples/whitemodels/` | 八個可換皮的白模（hero、heroine、chibi、brute、mascot、knight、mage、vtuber）＋各自的皮模板 |
| `fixtures/` | 三個歷史角色（豬大、紫髮女孩、Alice）供既有資產流程練習與回歸 |
| `spine42/` | Zhuda Spine Workstation 的 agent CLI 快照（既有骨架編輯／retarget） |
| `tests/` | `selftest.py` 與沿用的工具測試 |
| `node_modules/` | 釘版的 Spine runtime 與 pngjs（vendored） |

## 這一版驗證到哪裡

- `tests/selftest.py`：36/36 通過（單元、模板專案端到端、五種故障注入、沿用工具、既有 fixture）。
- `examples/shuang`：76 骨、32 slots、21 張加權網格（1,791 頂點）、12 條 transform constraint、49 個物理約束、11 段動畫；fidelity 通過、check 0 error／0 warning、極限姿勢與各動畫時序圖已讀。細節與**未完成事項**在它的 `WORKLOG.md`。
- 驗證 runtime 只有官方 spine-webgl 4.2.119（headless Chromium / SwiftShader）。LayaAir、Unity 等目標引擎內的表現未驗證。

## 維護規則

- 知識只有一份：`docs/`。新經驗先判斷是通用還是個案；通用的併入對應主題文件，個案留在該角色的 `WORKLOG.md`。數字基準要帶來源與範圍，不升格成通用門檻。
- 工具改動要過 `tests/selftest.py`；改 `viewer/` 或 `capture.mjs` 要實際跑一次原生截圖。
- `spine42/` 與 `node_modules/` 是快照：從上游重新複製，不在這裡開發。
- 從舊結構搬過來的對照與刻意未搬的內容：[`MIGRATION.md`](../MIGRATION.md)。
