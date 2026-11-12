# 60 Runtime 整合、材質與交付

## 交付物

| 類別 | 內容 |
|---|---|
| runtime 包（`spk export --zip`） | `NAME.json`、`NAME.atlas`、`NAME.png`、`NAME.contract.json`、SHA256 |
| 可編輯來源 | `art.py`／`parts/`、`rig.py`、`design.py`、`BRIEF.md`、`WORKLOG.md` |
| 證據 | `evidence/`（fidelity、stress、sheets、plays、compare）、`build/NNN/check-report.json` |
| 預覽 | `spk export --html`（單檔，內含 runtime 與資產；`--cdn` 改由 jsDelivr 載入 runtime） |

線上只放 runtime 包。來源、證據、日誌不進線上 payload。zip 大小、JSON 位元組、圖集 RGBA8 記憶體（寬×高×4）分開報；PNG 小不代表 GPU 佔用小。

## 契約（`*.contract.json`）是資產的一部分

整合時依它實作：哪些動畫 loop、在哪個 track、動作播完回到誰、混合時間、overlay 行為（`hold`/`auto`）、控制器（骨名與單位）。`viewer/viewer.js` 是參考實作（約 300 行）。只搬 JSON 而不實作契約，眨眼、表情疊加、視線跟隨都不會出現。

## Alpha／PMA

預設輸出 **straight alpha**（`pma:false`）並把透明像素 RGB 外擴 6px。渲染端必須用非預乘混合；四者要一致：像素資料、atlas 的 `pma`、貼圖上傳時是否預乘、材質 blend。
需要預乘：`rig.set(pma=True)`（不再做 bleed，RGB 已乘 alpha）。

診斷順序：單件在深淺底乾淨嗎 → 原尺寸乾淨、縮小才髒嗎（取樣：filter、mipmap、padding、鄰區）→ 邊緣隨縮放變暗嗎（PMA 與材質不一致，被乘了兩次）。

## LayaAir 3.x（未在本工具包環境實測；整合時逐項確認）

- `layaair create / build / run` 先看當版 `--help`，不猜旗標。使用者要求 CLI 建專案就真的用 CLI，不複製舊專案冒充。
- 初始化前把 `spineVersion` 設成與骨架相符的 4.2；模組需要 core、webgl_2D、對應版 spine-core、laya.spine。
- 場景掛 `Laya.Spine2DRenderNode`，用本包的 JSON/atlas/PNG。
- 已知經驗（Laya 3.4.x 案例，升級後要重驗）：
  - `templet.checkPremultipliedAlpha()` 與材質設定不一致時，半透明邊會被再乘一次 alpha 而變暗；templet 就緒後 `node.setPremultipliedAlpha(node.templet.checkPremultipliedAlpha())` 對齊。
  - `useFastRender=false` 是驗證過的配置；改快路徑視為另一個需要回歸的變更。
  - templet 原點偏移可能需要 `node.offset` 修正；先量再套。
  - `currentTime` setter 不一定移動 AnimationState 游標；暫停旗標不一定停止 update。凡是「以為凍結了」的截圖都要記錄 renderer 實際時間。
  - 倍速不要在 UI、controller、renderer 各乘一次。
- **4.2 物理約束、多 track overlay、transform constraint 是否與 spine-webgl 表現一致，必須在目標引擎內實看**；本包的驗證只到官方 spine-webgl 4.2.119。
- 取景依完整動作包絡（含頭髮最大延伸）留安全區；resize 時更新同一個場景，不重建控制器。

## 最佳化（在視覺通過之後）

1. 先列依賴：所有 skin/slot/attachment 的圖片路徑、程式動態換的 attachment、事件、混合名單。`spk util inventory` 的「未引用」只是候選。
2. 無損優先：`spk util compact`（移除確認相同的動畫、稀疏零分量、等值數字表示）。不要隨手刪零 deform timeline——它可能負責跨動畫復位。
3. 圖集：`spk util repack` 只處理單頁、未旋轉、未裁切；其他格式會拒絕而不是猜。
4. 每一步之後 `spk compare` 新舊 build，預期 `UNCHANGED`。

## 對外發布

只在使用者於本次對話明確授權、且目的地明確時進行。先存前一版可回滾包與 hash；發布後從**外部 URL** 實際載入，確認無 404／CORS／runtime error，同 viewport 與基線比較構圖，保留舊快取再載一次。歷史案例的子站、金鑰、授權一律不沿用。
