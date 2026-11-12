# 白模 hero — 標準成人（圍巾）

| Item | Decision |
|---|---|
| 身體 | `F.Body("hero")`，高約 623px；左右對稱 |
| 這一套壓的邊界 | 基準。頸後一條鏈（圍巾）。 |
| 零件 | 37 根骨、36 個 slot、71 張圖；8 視角零件：chest、foot_L、foot_R、head、pelvis |
| 動作 | dance、idle、jump、kungfu、pick、run、turn、turntable、walk、wave（walk 403.0 px/s、run 879.41 px/s） |
| 朝向 | 鏡射骨架；`turn` 在正對鏡頭的瞬間發 `flip` |
| 用途 | 換皮測試的底模。規格 `build/001/hero.skin.json`，模板在 `skin/` |
| Target runtime | Spine 4.2 JSON；驗證 runtime：spine-webgl 4.2.119。目標引擎內未驗證 |
