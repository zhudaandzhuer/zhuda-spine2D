# 白模 chibi — Q 版大頭（雙馬尾）

| Item | Decision |
|---|---|
| 身體 | `F.Body("chibi")`，高約 407px；左右對稱 |
| 這一套壓的邊界 | 頭是全身的 2.5 分之一高，腿長只有成人的 42%——步幅、起伏、跳躍全部按腿長縮放，步頻變快。 |
| 零件 | 39 根骨、38 個 slot、73 張圖；8 視角零件：chest、foot_L、foot_R、head、pelvis |
| 動作 | dance、idle、jump、kungfu、pick、run、turn、turntable、walk、wave（walk 261.17 px/s、run 527.65 px/s） |
| 朝向 | 鏡射骨架；`turn` 在正對鏡頭的瞬間發 `flip` |
| 用途 | 換皮測試的底模。規格 `build/001/chibi.skin.json`，模板在 `skin/` |
| Target runtime | Spine 4.2 JSON；驗證 runtime：spine-webgl 4.2.119。目標引擎內未驗證 |
