# 白模 heroine — 女性成人（馬尾、裙）

| Item | Decision |
|---|---|
| 身體 | `F.Body("heroine")`，高約 600px；左右對稱 |
| 這一套壓的邊界 | 窄肩寬髖、細四肢；頭上的鏈（馬尾）；裙錐會被大腿頂開，髖與大腿永遠畫在裙子下面。 |
| 零件 | 38 根骨、37 個 slot、72 張圖；8 視角零件：chest、foot_L、foot_R、head、pelvis |
| 動作 | dance、idle、jump、kungfu、pick、run、turn、turntable、walk、wave（walk 403.0 px/s、run 879.41 px/s） |
| 朝向 | 鏡射骨架；`turn` 在正對鏡頭的瞬間發 `flip` |
| 用途 | 換皮測試的底模。規格 `build/001/heroine.skin.json`，模板在 `skin/` |
| Target runtime | Spine 4.2 JSON；驗證 runtime：spine-webgl 4.2.119。目標引擎內未驗證 |
