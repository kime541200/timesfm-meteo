## 1. 領域模型重構（BREAKING）

- [x] 1.1 在 `src/timesfm_meteo/models.py` 新增 `QuantileValues(p10: float, p50: float, p90: float)`，validator 強制 `p10 <= p50 <= p90`
- [x] 1.2 在 `models.py` 新增 `DailyTemperatureForecast(date: Date, max: QuantileValues, min: QuantileValues)`，validator 強制 `max.p50 >= min.p50`
- [x] 1.3 在 `models.py` 移除舊的 `QuantileForecast` class
- [x] 1.4 在 `models.py` 新增 `QuantileForecastResult(horizon: int, point: list[float], quantiles: dict[float, list[float]])`，作為 engine 對外型別
- [x] 1.5 更新 `tests/test_models.py`：刪除 `QuantileForecast` 相關測試；新增 `QuantileValues` ordering 測試、`DailyTemperatureForecast` max>=min 測試

## 2. Settings 與設定檔

- [x] 2.1 在 `configs.py` 新增 `TimesFMSettings` class，欄位：`model_id`、`max_context`、`max_horizon`、`normalize_inputs`、`use_continuous_quantile_head`、`force_flip_invariance`、`fix_quantile_crossing`，全部用 alias 對應 kebab-case YAML key
- [x] 2.2 在 `Settings` 新增 `timesfm: TimesFMSettings = Field(default_factory=TimesFMSettings)`
- [x] 2.3 從 `Settings` 移除 `forecast_quantiles` 欄位
- [x] 2.4 更新 `tests/test_configs.py`：補 `TimesFMSettings` 預設值與 alias 解析測試；移除 `forecast_quantiles` 相關 assertion
- [x] 2.5 在 `configs/configs.example.yaml` 補 `timesfm:` 區段（含預設值）
- [x] 2.6 在 `.env.example` 補 `HF_HOME=` 與一行說明註解

## 3. 依賴：`[forecast]` extra

- [x] 3.1 在 `pyproject.toml` 新增 `[project.optional-dependencies].forecast`，列出 `timesfm`（git URL 或 PyPI，看 upstream 哪個可用）、`torch>=2.0`、`numpy>=1.26`
- [x] 3.2 確認 `uv sync`（不帶 extra）後不會拉 torch；`uv sync --extra forecast` 才裝
- [x] 3.3 在 `AGENTS.md` Setup 區補一行：「執行 forecast 需要額外 `uv sync --extra forecast`」

## 4. Inference 模組（領域無關）

- [x] 4.1 建立 `src/timesfm_meteo/inference/__init__.py`
- [x] 4.2 在 `src/timesfm_meteo/inference/timesfm_engine.py` 定義 `ForecastEngine` Protocol（`forecast(series_list: list[np.ndarray], horizon: int) -> list[QuantileForecastResult]`）
- [x] 4.3 在 `timesfm_engine.py` 實作 `TimesFMEngine` class，`__init__` 接受 `model_id`、`max_context`、`max_horizon` + 4 個 ForecastConfig flag
- [x] 4.4 `__init__` 內 lazy import `timesfm`；缺套件時 raise `RuntimeError("TimesFM dependencies not installed. Run: uv sync --extra forecast")`
- [x] 4.5 `__init__` 內呼叫 `from_pretrained(model_id)` + `model.compile(ForecastConfig(...))`
- [x] 4.6 `forecast(series_list, horizon)` 呼叫 `model.forecast(horizon, inputs=series_list)`，把 numpy 結果轉成 `list[QuantileForecastResult]`（quantile dict key 為 `0.1` ~ `0.9`，value 為 `list[float]`）
- [x] 4.7 確認 engine 模組沒有 import 任何 `timesfm_meteo` 領域類別（`Location`、`DailyTemperature` 等）

## 5. Domain adapter

- [x] 5.1 重寫 `src/timesfm_meteo/forecasting/timesfm.py`，刪除 `NotImplementedError`
- [x] 5.2 新簽名：`forecast_with_timesfm(history: list[DailyTemperature], forecast_dates: list[Date], engine: ForecastEngine) -> list[DailyTemperatureForecast]`
- [x] 5.3 從 `history` 抽 `temperature_max` / `temperature_min` 為兩條 `np.ndarray(dtype=float32)`
- [x] 5.4 呼叫 `engine.forecast([max_series, min_series], horizon=len(forecast_dates))`
- [x] 5.5 把兩個 `QuantileForecastResult` 對位 zip 成 `list[DailyTemperatureForecast]`：`max=QuantileValues(p10=q[0.1][i], p50=q[0.5][i], p90=q[0.9][i])`、`min` 同理
- [x] 5.6 `forecast_dates[i]` 對應到第 i 筆 `DailyTemperatureForecast.date`

## 6. Adapter 測試（不需 torch）

- [x] 6.1 新增 `tests/test_forecasting_timesfm.py`，定義 `_FakeEngine` 滿足 `ForecastEngine` Protocol，回傳 canned `QuantileForecastResult`
- [x] 6.2 測試：max / min 序列正確分離且順序為 `[max, min]`
- [x] 6.3 測試：quantile dict key `0.1 / 0.5 / 0.9` 正確映射到 `QuantileValues.p10 / p50 / p90`
- [x] 6.4 測試：輸出長度 == `len(forecast_dates)`，且 i-th 輸出的 `date` == `forecast_dates[i]`
- [x] 6.5 測試：輸入空 `history` 或空 `forecast_dates` 的邊界行為（建議：raise `ValueError`）

## 7. CLI `forecast` 子命令

- [x] 7.1 在 `cli.py` 新增 `_build_parser()` 內的 `forecast` 子命令：`--latitude`、`--longitude`、`--horizon`（預設由 `Settings.forecast_days`）、`--history-years`（預設由 `Settings.history_years`）、`--start-date`（預設今天，型別 `_parse_iso_date`）
- [x] 7.2 新增 `ForecastResponse(ProjectModel)`：`model: str`、`history_days: int`、`horizon: int`、`forecasts: list[DailyTemperatureForecast]`（放在 `models.py`）
- [x] 7.3 新增 `_run_forecast(args, settings)` 流程：
  - validate `Location`
  - 算 `history range = [start_date - history_years*365 d, start_date - 1 d]`
  - 算 `forecast_dates = [start_date + i for i in range(horizon)]`
  - DSN 缺失 / 連線失敗：複用 `fetch-history` 既有錯誤處理（exit 2 + stderr 訊息）
  - `with psycopg.connect(...) as conn`：`ensure_schema(conn)` → `get_temperatures(...)` 取歷史
  - `engine = TimesFMEngine(...settings.timesfm 對應欄位)` → `forecast_with_timesfm(history, forecast_dates, engine)`
  - 組 `ForecastResponse`，stdout `print(response.model_dump_json(indent=2))`
  - stderr 一行 `history=N horizon=M model=<id>`
- [x] 7.4 把 `forecast` 分支接進 `main()` dispatcher

## 8. CLI 測試

- [x] 8.1 在 `tests/test_cli.py` 新增 `test_forecast_parses_defaults_from_settings`：mock `load_settings`，驗證沒給 `--horizon` / `--history-years` 時用 settings 預設
- [x] 8.2 新增 `test_forecast_rejects_invalid_latitude`（沿用 fetch-history 模式）
- [x] 8.3 新增 `test_forecast_missing_database_url_does_not_load_model`：mock `psycopg.connect` 與 `TimesFMEngine` 都不可被呼叫
- [x] 8.4 新增 `test_forecast_happy_path_emits_valid_json`：
  - mock `psycopg.connect` 回 fake conn
  - mock `pipeline.historical.get_temperatures` 回 canned history
  - mock `cli` 內的 `TimesFMEngine` 為 `_FakeEngine`
  - 驗證 stdout 可被 `ForecastResponse.model_validate_json` 反序列化
  - 驗證 stderr 摘要格式

## 9. 文件更新

- [x] 9.1 新增 `docs/timesfm-engine.md`：說明 engine 介面、`__init__` 行為、`max_context=1024` / `max_horizon=32` 預設值取捨、模型架構上限（context 16k、horizon 1k）、HF cache（`HF_HOME`）
- [x] 9.2 在 `docs/roadmap.md` MVP 第 3 步段落補：「本步驟只輸出到 stdout / stderr，forecast 持久化延後到第 5 步」+「預設 CUDA 環境；MPS 支援若有實際需求再評估」
- [x] 9.3 在 `docs/roadmap.md` MVP 第 5 步「基礎評估」最上方加 sub-bullet「把 forecast 結果寫入 Postgres（schema 在實作時設計）」
- [x] 9.4 在 `docs/roadmap.md` 長期段落新增「TimesFM Inference Server」章節（FastAPI 包裝 + Docker 部署 + 常駐 inference 避免重複載入）
- [x] 9.5 在 `AGENTS.md` Development 區補 `uv run timesfm-meteo forecast --latitude ... --longitude ...` 範例

## 10. 端到端驗證

- [x] 10.1 跑 `uv sync --extra forecast` 確認依賴可裝起來
- [x] 10.2 跑 `uv run --extra dev pytest` 確認所有單元測試通過（不需 forecast extra）
- [x] 10.3 手動煙霧測試：`uv run --extra forecast --extra dev timesfm-meteo forecast --latitude 25.05 --longitude 121.57 --horizon 3`，驗證輸出是合法 JSON 且能 `ForecastResponse.model_validate_json` 解析；觀察 stderr 摘要
- [x] 10.4 手動 backtest 煙霧測試：給 `--start-date 2024-01-15`，驗證歷史範圍只到 `2024-01-14`、輸出日期從 `2024-01-15` 起算
