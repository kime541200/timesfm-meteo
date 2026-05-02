## Why

MVP roadmap 第 3 步要求用 TimesFM 預測未來 N 日氣溫。目前 `forecasting/timesfm.py` 與 `forecasting/baseline.py` 都只是 `raise NotImplementedError` 的空殼，沒有任何推論能力。歷史資料層（`historical-fetch`）已可運作，下一步要把模型接上去，並讓 inference 模組從一開始就保持「可被獨立成 server」的乾淨邊界，避免未來重構成本。

## What Changes

- 新增 `src/timesfm_meteo/inference/` 子套件作為**模型無關**的推論層；`TimesFMEngine` 包裝 upstream `timesfm` 套件，對外只暴露 `forecast(series_list, horizon)` 並回傳完整 mean + 9 quantiles。
- 新增 `forecasting/timesfm.py` 真實作（取代 `NotImplementedError`），作為**領域 adapter**：把 `list[DailyTemperature]` 轉成 numpy 序列、呼叫注入的 engine、再把結果映射回領域模型。Engine 以 `ForecastEngine` Protocol 注入，方便測試與未來換成遠端 client。
- **BREAKING**：重構 `models.py` — 拆 `QuantileForecast(date, p10, p50, p90)` 為 `QuantileValues(p10, p50, p90)`；新增複合模型 `DailyTemperatureForecast(date, max: QuantileValues, min: QuantileValues)` 表達「一天的最高溫與最低溫各自的分位數預測」。同時新增 `QuantileForecastResult` 表達 engine 原始輸出。`Settings` 移除 `forecast_quantiles` 欄位（語意已被新模型固定為 p10/p50/p90）。
- 新增 `TimesFMSettings` 進 `Settings`，預設 `model_id=google/timesfm-2.5-200m-pytorch`、`max_context=1024`、`max_horizon=32`，並把 4 個 `ForecastConfig` flag 開放成設定。
- 新增 CLI 子命令 `forecast --latitude --longitude [--horizon] [--history-years] [--start-date]`：複用 `pipeline.historical.get_temperatures` 取歷史，呼叫 adapter，輸出 stdout 為 `ForecastResponse` JSON、stderr 為一行 ops 摘要。`--start-date` 預設今天，設過去日期即為 backtest 模式。
- `pyproject.toml` 新增 `[forecast]` extra（`timesfm`、`torch>=2.0`、`numpy>=1.26`）。基本安裝不再背 torch；engine 模組用 lazy import，缺 extra 時 `import` 不會炸，呼叫 `forecast()` 才報錯。
- `.env.example` 新增 `HF_HOME=`（空值用 HF 預設），讓使用者可改 checkpoint 快取位置。
- 新增 `docs/timesfm-engine.md`，文件化引擎使用、預設值取捨、模型架構上限（context 16k / horizon 1k）。
- `docs/roadmap.md` 兩處更新：
  - MVP 第 3 步段落補一行「本步驟只輸出到 stdout / stderr，forecast 持久化延後到第 5 步」與「預設 CUDA 環境；MPS 支援若有實際需求再評估」。
  - MVP 第 5 步「基礎評估」最上方加 sub-bullet「把 forecast 結果寫入 Postgres」。
  - 長期段落新增「TimesFM Inference Server（Docker 封裝）」章節，敘述把 `inference/` 抽出成獨立服務的方向。

## Capabilities

### New Capabilities

- `temperature-forecasting`：用 TimesFM 對指定地點與起始日期，依歷史每日溫度產出未來 N 天的 max / min 分位數預測。包含 CLI 入口、引擎抽象、領域 adapter、結果 JSON 輸出格式。

### Modified Capabilities

（無 — `historical-fetch` 不變動）

## Impact

- 程式碼新增：`inference/timesfm_engine.py`、`forecasting/timesfm.py`（重寫）、`models.py`（重構）、`configs.py`（新增 `TimesFMSettings`、移除 `forecast_quantiles`）、`cli.py`（新增 `forecast` 子命令）。
- 依賴：`pyproject.toml` 新增 `[forecast]` extra；不影響核心依賴。
- 測試：`tests/test_forecasting_timesfm.py`（新檔，全 mock）、`tests/test_cli.py`（補充 `forecast` 路徑）、`tests/test_models.py`（更新已重構的模型測試）。
- 文件：`docs/timesfm-engine.md`（新檔）、`docs/roadmap.md`（更新三處）、`AGENTS.md`（補 `forecast` CLI 範例與 `[forecast]` extra 安裝指令）、`configs/configs.example.yaml`（補 `timesfm:` 區段）、`.env.example`（補 `HF_HOME=`）。
- 不變動：`historical-fetch` capability 與其 spec、`db/` 模組、既有 `fetch-history` CLI。
