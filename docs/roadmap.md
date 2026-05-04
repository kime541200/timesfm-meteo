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

### 3. 未來 3 日氣溫預測(Done)

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

### 4. 預測不確定性(Done)

使用分位數預測表示不確定性，不只依賴單一點預測。

初始目標：
- 在模型支援時產出 p10、p50、p90。
- 將 p10-p90 視為未來觀測值的預測區間。
- 追蹤區間寬度，作為實務上的不確定性訊號。

> p10/p50/p90 分位數已透過 `QuantileValues` 模型與 TimesFM 2.5 連續分位頭（`use_continuous_quantile_head=True`）完整產出，並包含在 `forecast` CLI 的 JSON 輸出中。區間寬度作為評估指標的計算延後到第 5 步處理。

參考 `docs/quantile-forecasting.md`。

### 5. 基礎評估(Done)

在加入產品層之前，先保留最小方式比較預測結果與後續觀測值。

初始目標：
- 把 forecast 結果寫入 Postgres（schema 在實作時設計），作為日後與觀測值比對的依據。
- 點預測 MAE。
- 分位數預測區間 coverage。
- 預測區間寬度。

## 中期

### 1. RESTful API Server (Done)

把 MVP pipeline 包裝成 HTTP API，供 Web Dashboard、AI Agent、未來排程器使用。

實際交付：
- FastAPI server（`src/timesfm_meteo/api/`），啟動時透過 lifespan 載入 TimesFM 模型並常駐記憶體。
- Endpoints：
  - 讀：`GET /temperatures`、`GET /forecasts`、`GET /evaluate`
  - 觸發（async job + Postgres `jobs` 表）：`POST /forecast`、`POST /fetch-history`
  - Job 狀態：`GET /jobs/{id}`
- API Key auth（`Authorization: Bearer <key>`，從 `.env` 讀 `API_KEY`）。
- 輕量 CLI client `timesfm-meteo-client`（`src/timesfm_meteo/client/`），AI Agent 友善，只依賴 `httpx` + `pydantic`，不需 DB / 模型即可呼叫遠端 API。
- 文件：`docs/api-server.md`、`docs/cli-client.md`，並補進 `docs/usage.md` 與 `AGENTS.md`。

> Web client（前端 SPA）獨立成「中期 3. 數據可視化」這個 change，避免 Python / Node 兩套工具鏈擠在同一個 change。

### 2. Docker 包裝服務 (Not Started)

把服務用 Dockerfile、docker-compose 包裝。

目前狀態：
- 已有 `docker-compose.postgres.yml` 可單獨啟動 Postgres / pgAdmin。
- API server、Web UI 的 Dockerfile 與完整 `docker-compose.yml` 尚未落地。
- production 靜態檔 serve 與整體部署流程仍待後續 change。

### 3. 數據可視化 (In Progress)

提供一個 React + Vite Web Dashboard，讓使用者能夠以視覺化方式檢視歷史氣溫、過往預測結果、預測區間與評估指標，而不需要靠 stdout JSON 自己拼。

目前已完成（change: `add-web-client` + `fix-web-forecast-semantics`）：
- 前端 Dashboard：歷史氣溫折線圖、過往 forecast p50 預測點 / 淡線、p10–p90 區間、聚合平均線。
- 主圖以 `target_date` 為 X 軸；actual history 顯示到 `History end`，未來 forecast 由 `History end + 1 day` 開始接續。
- `Forecast horizon` 與 `Evaluation horizon step` 明確拆開：前者控制 `Run Forecast` 未來天數，後者只影響過往 forecast analysis / evaluation。
- 評估報表：overall summary cards + 依 horizon_step 分組的 MAE / coverage / interval width table。
- 手動操作：Fetch History / Run Forecast 按鈕會呼叫 API server 建立 async job，並在 job 完成後自動 refetch 圖表與評估資料。
- 技術選型：React + Vite + TypeScript、ECharts、TanStack Query、Vitest。
- 第一版仍以 latitude / longitude 輸入，預設 Taipei；地點 alias 另列 Additional feature。

尚未完成：
- production 靜態檔 serve。
- 與 Docker 包裝整合的部署流程。

依賴：使用「中期 1. RESTful API Server」提供的 `/api/*` endpoints；production 靜態檔 serve 與 Docker 包裝留到後續 change。

### 4. 每日自動更新與 Web Dashboard 整合

讓使用者只要 `docker compose up`，就能持續取得最新歷史資料、最新預測，並透過 Web 介面定時自動刷新觀察。

預期方向：
- 排程器（cron / APScheduler / Celery beat 擇一），每日固定時間：
  1. 對已註冊地點呼叫 `fetch-history` pipeline 增量更新觀測值。
  2. 觸發 `forecast` 寫入新一批 `forecasts`（live mode，`start_date = today`）。
  3. 觸發 `evaluate` 對先前的預測補算指標。
- Web Dashboard（依「中期 3」）支援自動刷新（HTTP 輪詢、SSE 或 WebSocket 擇一），使用者開著瀏覽器即可看到最新結果。
- 完整服務以單一 `docker-compose.yml` 帶起：Postgres、API server、scheduler worker、Web UI；TimesFM inference 可內嵌或委外給「長期：TimesFM Inference Server」。
- 需要設定的最小資訊：要追蹤的地點清單、預測 horizon、刷新頻率。
- 失敗處理：單次排程失敗不影響後續，DB 紀錄錯誤狀態以便 Dashboard 標示。

依賴：建議落地順序為「中期 1 → 中期 2 → 中期 3 → 中期 4」，這樣排程器能透過 API 觸發 pipeline，且 Web 端有資料可顯示。

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

### 地點 alias 與識別

把經緯度與人類好認的地點名稱（例如 `Taipei`）對應起來，讓使用者不必每次都輸入精確座標。

預期方向：
- 新增 `locations` 表（或 alias 表），欄位至少包含 `name`、`latitude`、`longitude`，可能含可選的 `display_name` / `country` 等 metadata。
- CLI 加上 `--name <alias>` flag，可與現有的 `--latitude` / `--longitude` 二擇一；解析時優先 lookup alias，找不到才報錯。
- 一次回頭把 `fetch-history` / `forecast` / `evaluate` 三個命令同時加上 alias 支援，避免一半命令認名字、一半不認的不一致。
- 新增管理用的 subcommand（例如 `location add Taipei --latitude 25.06 --longitude 121.55`）或預先 seed YAML 檔。
- 後續可以評估是否串接 Open-Meteo 的 geocoding API，使用者輸入 `Taipei` 自動補上座標。

獨立成 change 的理由：影響面不只 evaluate，需要設計座標精度容差與 alias 管理流程。MVP 第 5 步先以 `--latitude --longitude` 收尾，alias 在 MVP 完成後接著做。

### 資料庫管理優化
- 服務啟動時如果無法從 `.env` 中設定的 `DATABASE_URL` 成功連線到 Postgres 資料庫時，自動 Fallback 到專案目錄下的 `db` 目錄，用 `sqlite` 建立資料庫。
- 目前保存的資料比較陽春，直接把所有「座標 - 日期 - 高低溫」存到同一張資料表中，未來可以優化成「by 地區名稱」細分成不同的資料表（依賴上面的「地點 alias 與識別」先落地）：
    ```
    地區名稱（ex: Taipei）
    |- 座標
    |- 日期
    |- 高低溫
    ```
