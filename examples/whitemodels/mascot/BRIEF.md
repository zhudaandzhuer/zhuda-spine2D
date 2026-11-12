# 白模 mascot — 吉祥物（耳朵、口鼻、尾巴、側背包）

| Item | Decision |
|---|---|
| 身體 | `F.Body("mascot")`，高約 381px；不對稱（單側配件） |
| 這一套壓的邊界 | 圓身短肢；頭上的耳朵與口鼻（剛性配件）、尾巴（鏈）、左肩側背包（擺錘）＝不對稱。 |
| 零件 | 40 根骨、39 個 slot、74 張圖；8 視角零件：chest、foot_L、foot_R、head、pelvis |
| 動作 | dance、idle、jump、kungfu、pick、run、turn、turntable、walk、wave（walk 221.0 px/s、run 427.14 px/s）；每個另有朝左的 `_L` 版本（turntable 除外） |
| 朝向 | clip 變體（`_L`），不鏡射 |
| 用途 | 換皮測試的底模。規格 `build/001/mascot.skin.json`，模板在 `skin/` |
| Target runtime | Spine 4.2 JSON；驗證 runtime：spine-webgl 4.2.119。目標引擎內未驗證 |
