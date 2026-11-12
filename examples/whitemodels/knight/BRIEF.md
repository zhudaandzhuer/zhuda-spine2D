# 白模 knight — 盾牌戰士（盾、劍、肩甲、盔纓）

| Item | Decision |
|---|---|
| 身體 | `F.Body("knight")`，高約 613px；不對稱（單側配件） |
| 這一套壓的邊界 | 左前臂上的盾（板狀、有正反面，8 個視角）、右手的劍（薄片）、肩甲（剛性）、盔纓（鏈）。盾擋在身前的攜帶姿勢；類別動作：舉盾格擋、揮砍、盾擊。 |
| 零件 | 40 根骨、39 個 slot、81 張圖；8 視角零件：chest、foot_L、foot_R、head、pelvis、shield |
| 動作 | bash、block、idle、jump、run、slash、turn、turntable、walk（walk 394.86 px/s、run 861.64 px/s）；每個另有朝左的 `_L` 版本（turntable 除外） |
| 朝向 | clip 變體（`_L`），不鏡射 |
| 用途 | 換皮測試的底模。規格 `build/001/knight.skin.json`，模板在 `skin/` |
| Target runtime | Spine 4.2 JSON；驗證 runtime：spine-webgl 4.2.119。目標引擎內未驗證 |
