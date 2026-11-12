# 白模 mage — 魔法師（尖帽、長袍、寬袖、法杖）

| Item | Decision |
|---|---|
| 身體 | `F.Body("mage")`，高約 616px；不對稱（單側配件） |
| 這一套壓的邊界 | 尖帽（帽簷＋會晃的帽尖）、長袍（包住整條腿，只有腳露出）、寬袖（包住前臂）、右手的法杖（比人高）。法杖直立的攜帶姿勢；類別動作：施法、引導（loop）。 |
| 零件 | 41 根骨、40 個 slot、75 張圖；8 視角零件：chest、foot_L、foot_R、head、pelvis |
| 動作 | cast、channel、idle、jump、run、turn、turntable、walk（walk 398.95 px/s、run 870.57 px/s）；每個另有朝左的 `_L` 版本（turntable 除外） |
| 朝向 | clip 變體（`_L`），不鏡射 |
| 用途 | 換皮測試的底模。規格 `build/001/mage.skin.json`，模板在 `skin/` |
| Target runtime | Spine 4.2 JSON；驗證 runtime：spine-webgl 4.2.119。目標引擎內未驗證 |
