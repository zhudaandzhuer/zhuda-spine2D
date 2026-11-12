# 70 既有 Spine 資產：稽核、修復、延伸

手上已有 JSON／atlas／PNG 時不要從新角色流程重來。沿用它的版本、來源與輸出方式。

## 1. 先確認你在看的是哪一份

找出實際被載入的 JSON／atlas／PNG、runtime 版本、已部署版本；記下 SHA256。確認預覽不是舊路徑或舊快取。
選基底看內容與 hash，不看 `v6/v7/final` 這種檔名。所有修改輸出到新檔，原包保留。

## 2. 唯讀盤點

```sh
python3 spk.py util audit --json X.json --atlas X.atlas [--required-clips idle walk] [--out report.json]   # 結構、頁面、必要動畫、匯出包比較
python3 spk.py util inventory X.json --atlas X.atlas                                                    # 骨／slot／附件／重複動畫；「未引用」只是候選
python3 spk.py util smooth X.json --warn-only                                                           # 階梯軌、低密度烘焙 deform、重複 key
node tools/sweep.mjs --json X.json --atlas X.atlas [--contract X.contract.json]                         # 官方 runtime：翻面、loop、物理、混合
```

要用本包的原生截圖工具看既有資產：把三個檔放進 `某資料夾/build/001/`，就能 `spk shot / sheet / play 某資料夾 …`（沒有 `rig.py` 也可以；`--frame` 需要 contract 的 source 對映，沒有時用預設取景）。`fixtures/` 內附三個歷史角色可練習。

## 3. 編輯既有動畫：`spine42` CLI（需要 Node ≥ 22）

```sh
node spine42/cli/spine42.mjs --help
node spine42/cli/spine42.mjs inspect X.json
node spine42/cli/spine42.mjs validate X.json --atlas X.atlas
node spine42/cli/spine42.mjs apply X.json --atlas X.atlas --plan change.json --out Y.json     # 可重放的修改計畫
node spine42/cli/spine42.mjs key-set X.json --anim idle --bone head --timeline rotate --time 0.5 --value 4 --out Y.json
node spine42/cli/spine42.mjs semantic-rig X.json --atlas X.atlas                                # 任意骨名 → pelvis/chest/head/肩肘腕/髖膝踝
node spine42/cli/spine42.mjs motion-feasibility TARGET.json --atlas T.atlas --reference run.motion.json   # READY / NEEDS_ART / BLOCKED
node spine42/cli/spine42.mjs motion-retarget TARGET.json --atlas T.atlas --reference run.motion.json --anim ai_run --out OUT.json
```

Plan DSL 的操作：`create_animation / clone_animation / delete_animation / retime_animation / set_bone_key / delete_bone_key / clear_bone_timeline / set_slot_attachment_key / set_ik_key / set_draw_order_key …`。
優先用 plan 與語意關節，不直接手改 raw JSON、不自己算加權頂點偏移、不猜骨名。
`motion-feasibility` 回 `NEEDS_ART` 時先補素材，**不要**用 `--force` 硬扭舊圖做出一個看似完成的動畫。
這是 Zhuda Spine Workstation 的 agent CLI 快照（來源與版本見 `spine42/PROVENANCE.md`）；其中 `render-frame`（瀏覽器版）在這裡請改用 `spk shot`。

## 4. 精簡與重排

```sh
python3 spk.py util compact X.json --out Y.json [--drop-identical test=idle]     # 無損；拒絕刪除不相同的動畫
python3 spk.py util repack --skeleton X.json --atlas X.atlas --out-dir packed --padding 4   # 只支援單頁、未旋轉、未裁切
```

之後用 `spk compare` 或 `spk util frames before/ after/` 對照，預期 `UNCHANGED`。

## 5. 缺主專案時

把現有資料分三類記下來：**存在且可讀**、**可由現有檔重建**、**真的缺**。
runtime JSON／atlas／PNG 足以恢復可播放基底，但不等於原 `.spine`、未打包原畫或完整工程。atlas 有 trim／rotate 時依 metadata 還原，不任意裁切。
最終效果可能還依賴 controller、bridge 動畫、透明 RGB 處理、材質設定——只帶走 JSON 不算完整移植。

## 6. 修復時的診斷順序

看使用者的圖與目前原生畫面 → 分類（`50-failure-playbook.md`）→ 一次修一個根因 → 同鏡頭前後對照。
畫面只出現幾根 debug 骨頭不代表實際只有那幾根；截圖成功不代表已理解。
