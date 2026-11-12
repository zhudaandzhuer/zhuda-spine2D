# 從舊 `spine2D/` 到 spine2d-master 2.0

舊包：441 MB、約 3,000 個檔案（不含 `.git` 與 `node_modules`），同一份知識有四個版本。
新包：一個入口、一個 CLI、九份文件；`readme/` 下的說明文字約 270 KB，新的 `SKILL.md`＋`docs/` 約 50 KB。

## 對照表

| 舊位置 | 新位置 | 說明 |
|---|---|---|
| `readme/README.md`、`readme/MASTER_SKILL.md`、`readme/skill-package/SKILL.md`、`readme/sources/{codex,zhuda-mac-agent}/SKILL.md` | `SKILL.md` | 四份入口合成一份 |
| `readme/foundations/CHARACTER_IDENTITY_AND_ASSETS.md`、`skill-package/references/{art,art-and-parts}.md` | `docs/10-art.md` | |
| `readme/foundations/SPINE42_RUNTIME_INVARIANTS.md`、`authoring/RIG_MESH_WEIGHTS.md`、`references/{rig-and-mesh,rig-motion}.md` | `docs/20-rig.md` | 資料不變量＋新編譯器 API |
| `authoring/{MOTION_RETARGETING,INTERACTION_TRANSITIONS}.md`、`references/{motion-and-cape,interaction-and-transitions,live-state,performance}.md` | `docs/30-animation.md` | 步態、轉場、控制器契約、表演順序 |
| `qa/VALIDATION_LAYERS.md`、`references/visual-qa.md`、`sources/*/visual-qa.md` | `docs/40-qa.md`、`docs/00-pipeline.md` | Micro Gate、Anti-loop 進流程文件 |
| `qa/FAILURE_PLAYBOOK.md`、`references/failure-playbook.md` | `docs/50-failure-playbook.md` | 合併去重，補上本次遇到的症狀 |
| `foundations/RENDERING_ALPHA_VFX.md`、`references/{rendering-and-vfx,runtime,optimization,deployment}.md` | `docs/60-runtime-delivery.md` | Laya 經驗標明「案例值，升級需重驗」 |
| `workstation/*.md`、`references/workstation-and-portability.md`、`references/tools.md` | `docs/70-existing-rigs.md` | 只留 agent 用得到的部分 |
| `authoring/HANDS_ARMS_SURFACE_DEPTH.md`、`references/arms-and-hands.md` | `docs/80-hands-arms.md` | |
| `skill-package/assets/{acceptance-template.md,change-record.md}` | `templates/acceptance.md`、專案 `WORKLOG.md` | |
| `skill-package/assets/{hand-motion-contract.example.json,walk-board-prompt.txt}` | `templates/` | 原樣 |
| `skill-package/scripts/{audit_package,spine_audit,spine_common,compact_spine_json,repack_spine_atlas,motion_smoothness,gait_curve,boundary_plan,compare_frames}.py` | `tools/py/`（`spk util …`） | 原樣；原測試在 `tests/` |
| `scripts/doctor.py` | `spk doctor` | 多檢查 vendored runtime 與原生截圖能力 |
| `scripts/new_project.py` ＋ `assets/region-starter/` | `spk init` ＋ `spinekit/` ＋ `templates/project/` | starter 只支援平移 region；新編譯器支援旋轉骨、加權網格、約束、物理、分層動畫 |
| `scripts/native_capture.mjs` | `tools/capture.mjs`（`spk shot/sheet/stress/play/compare/fidelity`） | 保留「核對 renderer 實際時間」契約；新增物理預跑、真實播放、美術座標取景 |
| `scripts/runtime_sweep.mjs` | `tools/sweep.mjs`（`spk check`） | 保留以身份追蹤 attachment；新增 loop 速度接縫、時間步進物理、權重靜態檢查 |
| `scripts/starter_live_check.mjs` | `spk play --cues` | 真實 AnimationState 佇列／mix／事件 |
| `scripts/selftest.py`、`tests/*` | `tests/selftest.py`、`tests/test_*.py` | |
| `projects/Spine研發基地/workstation/{cli,src/lib,src/core}` | `spine42/` | 位元組相同的快照，見 `spine42/PROVENANCE.md` |
| `projects/Spine研發基地/workstation/node_modules/{@esotericsoftware,pngjs}` | `node_modules/` | 只留 JS 與授權；去掉 source map 與型別檔（5 MB → 1.6 MB） |
| `projects/regression-fixtures/Spine2D自由大師_三角色測試/{01_豬大_r34,02_紫髮女孩_r14,03_Alice_r31}` | `fixtures/{zhuda_r34,purple_girl_r14,alice_r31}/build/001/` | 改成 ASCII 路徑並放進 `build/001/`，`spk` 可直接讀 |

## 刻意沒有搬的（都還在你原本的資料夾裡）

| 內容 | 大小 | 原因 |
|---|---|---|
| `projects/Spine研發基地/.git` | 131 MB | 版本庫留在原處；快照記錄了 commit `1ce9e6f` 與未提交變更 |
| `…/experiments/run_unarmed_skeletal_v1`、`releases/`、`reports/` | 144 MB | 單一任務的中間產物與截圖 |
| `…/corpus/`（戰神賽特、CGSlot、官方範例）、`vendor/spine-unity_*` | 64 MB | 第三方商業素材與 Unity runtime；agent 製作角色用不到 |
| Workstation GUI（`index.html`、`src/main.js`、`style.css`、`dist/`）與約 150 支 UI／corpus 測試 | — | 給人用的編輯器，測試依賴上面的 corpus；它是獨立產品，不適合在這裡留第二份 |
| `…/docs/*`（0.4→1.0 各版里程碑）、`CONTEXT.md` | 0.4 MB | 版本流水帳；可重用的結論已在 `docs/` |
| `skill-package/assets/case-study-tools/`（86 支）、`references/{case-study,case-tools}.md`、`case-tool-manifest.json` | 0.4 MB | 桌面陪伴女孩專案的專用腳本，依賴不在包內的素材與路徑；通用教訓已併入 `docs/50-failure-playbook.md`、`docs/60-runtime-delivery.md` |
| `references/{validation,validation-vnext}.md`、`assets/validation/*` | 0.5 MB | 過去某次工具驗證的紀錄；新工具的驗證是 `tests/selftest.py` 的即時結果 |
| `projects/archive/build-spine-character-legacy-source` | 12 MB | 你們的 `SOURCE_MAP.md` 已標記為「已吸收的 legacy」 |
| `readme/_meta/*`、`SOURCE_COMPARISON.md`、`MAINTENANCE.md` | — | 描述舊來源之間的同步關係；新包只有一份來源，維護規則濃縮在 `README.md` |
| 所有 `$HOME/...` 絕對路徑、已退役子站與部署工具的描述 | — | 不可攜；新包沒有任何絕對路徑 |

## 行為上的改變（接手的 agent 需要知道）

1. 入口只有 `SKILL.md`；不要再找 `MASTER_SKILL.md` 或 `references/from-zero.md`。
2. 專案格式從 `project.json`（region-only）換成 `rig.py`＋`parts/manifest.json`。舊 `project.json` 的 `bones[].pivot`、`parts[].top_left` 可直接對應 `rig.bone(at=…)` 與 manifest 的 `x,y`。
3. build 不再用 `--out build-v2` 手動命名：每次 `spk build` 自動建立 `build/NNN/`。
4. 截圖 adapter 從 `window.spineMasterReview` 換成 `window.spk`（`seek / begin / advance / snapshot / png / view / info`），契約見 `viewer/viewer.js` 開頭。
5. `spk check` 比舊 sweep 嚴格：歷史 fixture `alice_r31` 會被報出 overlap helper 網格翻面（`bow` 766 個取樣、`walk` 223 個）——這是它本來就有的狀態，現在看得見了。
