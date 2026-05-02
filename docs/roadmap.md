# Roadmap

## MVP

### 1. 歷史氣溫資料(Done)

使用 Open-Meteo 取得指定地點的每日氣溫資料。

最低目標：
- 接受 latitude 與 longitude。
- 取得至少兩年的每日資料。
- 包含每日最高溫與最低溫。
- 回傳穩定、可供預測使用的 time-series 格式。

近即時資料有價值，但不是第一版必要條件。第一優先是可靠取得歷史每日資料。

> Official GitHub repo: [open-meteo/open-meteo](https://github.com/open-meteo/open-meteo.git)

> 官方有提供 Docker 部署服務的說明：[getting-started.md](https://github.com/open-meteo/open-meteo/blob/main/docs/getting-started.md)，其本質並不是建立一個幫你發送 HTTP 請求的代理伺服器（Proxy），而是完整複製一套與官方相同的氣象資料庫與 API 後端。它會將龐大的原始氣象模型資料下載到本機，並轉化為高度優化的時間序列資料庫來提供查詢。以目前的應用來說完全是沒有必要的。

> Future client option: [open-meteo/python-requests](https://github.com/open-meteo/python-requests.git)
> 目前 MVP 先直接呼叫 Open-Meteo JSON API。若之後需要大量地點、長時間序列、
> cache / retry，或 NumPy / pandas / Polars 整合，再評估改用官方 Python client。

### 2. 整合 Postgres 資料庫(Done)

把獲取到的資料保存進資料庫中，未來需要曲重複時間段的歷史資料時不用重新透過 Open-Meteo API 獲取。
例如，每天都要用「從昨天開始往回算 2 年」的歷史資料作為預測的前提，除了第一次取資料時需要透過 API 取較大量的資料之外，其餘都只要更新一天的歷史資料即可。

目前已經可以將 Postgres 用 Docker 獨立部署，在 [docker-compose.postgres.yml](../docker-compose.postgres.yml)，Postgres 主服務運行在本機的 5432 port。

### 3. 未來 3 日氣溫預測(On-going)

使用 TimesFM 預測未來 3 日的氣溫範圍。

初始目標：
- 預測每日最高溫與最低溫，或清楚文件化等價的輸出方式。
- 明確記錄模型輸入格式。
- 若需要暫時使用 TimesFM fork 或 MPS workaround，需先文件化原因與選擇。

> 本步驟只輸出 forecast 到 stdout / stderr。Forecast 結果寫入 Postgres
> 留到「基礎評估」步驟處理，避免在 schema 不確定時搶先設計表結構。

> 預設 CUDA 環境；MPS（Apple Silicon）支援若有實際需求再評估，可能涉及切到
> fork（kime541200/timesfm）或 upstream patch，目前不在此步驟處理。

參考：
- [google-research/timesfm](https://github.com/google-research/timesfm.git)
- [kime541200/timesfm](https://github.com/kime541200/timesfm.git)，若 upstream MPS 修正仍不可用
- NotebookLM 研究：https://notebooklm.google.com/notebook/d221bce3-504a-4265-948c-7bb8c2f8257a

### 4. 預測不確定性

使用分位數預測表示不確定性，不只依賴單一點預測。

初始目標：
- 在模型支援時產出 p10、p50、p90。
- 將 p10-p90 視為未來觀測值的預測區間。
- 追蹤區間寬度，作為實務上的不確定性訊號。

參考 `docs/quantile-forecasting.md`。

### 5. 基礎評估

在加入產品層之前，先保留最小方式比較預測結果與後續觀測值。

初始目標：
- 把 forecast 結果寫入 Postgres（schema 在實作時設計），作為日後與觀測值比對的依據。
- 點預測 MAE。
- 分位數預測區間 coverage。
- 預測區間寬度。

## 中期

### 1. RESTful API Server

等 MVP pipeline 可用後，再建立 server-client 架構。

預期方向：
- Python + FastAPI server。
- Server 端 Auth flow。
- Python CLI client。
- Web client，可能使用 Node.js 工具鏈。

API 應包裝既有資料與預測 pipeline，而不是反過來由 API 先定義 pipeline。

### 2. Docker 包裝服務

把服務用 Dockerfile、docker-compose 包裝。

## 長期

### TimesFM Inference Server

把 inference 模組（`src/timesfm_meteo/inference/`）獨立成可遠端呼叫的服務。

預期方向：
- 用 FastAPI（或同等輕量框架）包成 HTTP / gRPC 服務。
- 載入後常駐，避免每次預測都重新載入 + compile 模型。
- 用 Dockerfile 與 docker-compose 部署，與主 timesfm-meteo 服務分開：
  - 主服務需要 forecast 時改打遠端 endpoint。
  - 主服務的 `[forecast]` extra 可以縮小或移除。
- 可獨立擴充 inference 資源（GPU 機器），主應用 stateless。
- 後續評估批次推論 API（一次給多個 location 的歷史，回傳對應預測）。

### Polymarket 整合

長期目標是使用氣溫預測評估或執行 Polymarket 天氣部位。

重要風險：
- Polymarket 天氣市場通常可能依 Weather Underground 資料結算。
- 本專案預期使用 Open-Meteo，因為 Weather Underground API 成本較高。
- 在考慮交易自動化前，必須量測並建模 Open-Meteo 與 Weather Underground 的差異。

參考：
- [polymarket/polymarket-cli](https://github.com/Polymarket/polymarket-cli.git)
- [polymarket/agent-skills](https://github.com/Polymarket/agent-skills.git)

### 整合 Polymarket 資料進 Postgres 資料庫

等資料與預測格式穩定後，再將 Polymarket 針對氣候的預測合約盤口導入 Postgres。

候選資料：
- 歷史天氣觀測。
- 預測輸出。
- 預測評估結果。
- Polymarket 市場 metadata 與結果。

### TimesFM Fine-Tuning

等累積足夠歷史資料、預測結果與評估紀錄後，再考慮 fine-tuning。

參考：
- [google-research/timesfm finetuning examples](https://github.com/google-research/timesfm/tree/master/timesfm-forecasting/examples/finetuning)

## Additional features

### 資料庫管理優化
- 服務啟動時如果無法從 `.env` 中設定的 `DATABASE_URL` 成功連線到 Postgres 資料庫時，自動 Fallback 到專案目錄下的 `db` 目錄，用 `sqlite` 建立資料庫。
- 目前保存的資料比較陽春，直接把所有「座標 - 日期 - 高低溫」存到同一張資料表中，未來可以優化成「by 地區名稱」細分成不同的資料表：
    ```
    地區名稱（ex: Taipei）
    |- 座標
    |- 日期
    |- 高低溫
    ```
