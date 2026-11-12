# 白模 brute — 壯漢（披風、手持棍棒）

| Item | Decision |
|---|---|
| 身體 | `F.Body("brute")`，高約 584px；不對稱（單側配件） |
| 這一套壓的邊界 | 肩寬是成人的 1.5 倍、手臂粗長；背後兩片布片（披風）；右手拿棍棒＝不對稱，朝左用 `_L` clip。 |
| 零件 | 35 根骨、34 個 slot、69 張圖；8 視角零件：chest、foot_L、foot_R、head、pelvis |
| 動作 | dance、idle、jump、kungfu、pick、run、turn、turntable、walk、wave（walk 364.93 px/s、run 796.34 px/s）；每個另有朝左的 `_L` 版本（turntable 除外） |
| 朝向 | clip 變體（`_L`），不鏡射 |
| 用途 | 換皮測試的底模。規格 `build/001/brute.skin.json`，模板在 `skin/` |
| Target runtime | Spine 4.2 JSON；驗證 runtime：spine-webgl 4.2.119。目標引擎內未驗證 |
