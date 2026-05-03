## 1. Pydantic 模型

- [x] 1.1 在 `models.py` 新增 `VariableMetrics(mae_p50: float, interval_coverage: float, mean_interval_width: float)`
- [x] 1.2 在 `models.py` 新增 `GroupMetrics(evaluated_count: int, pending_count: int, max: VariableMetrics | None, min: VariableMetrics | None)`
- [x] 1.3 在 `models.py` 新增 `HorizonStepReport(horizon_step: int, metrics: GroupMetrics)`
- [x] 1.4 在 `models.py` 新增 `EvaluationReport(location: Location, start_date_from: Date, start_date_to: Date, horizon_step_filter: int | None, by_horizon_step: list[HorizonStepReport], overall: GroupMetrics)`
- [x] 1.5 在 `tests/test_models.py` 補測試：`VariableMetrics` 反序列化、`GroupMetrics` 接受 `None` 的 max/min、`EvaluationReport` JSON round-trip

## 2. DB 層：`db/forecasts.py`

- [x] 2.1 新增 `src/timesfm_meteo/db/forecasts.py`
- [x] 2.2 定義 `_CREATE_TABLE` SQL（schema 同 design.md decision 1：wide row、PK = `(latitude, longitude, start_date, target_date)`、6 個分位 REAL 欄位 + model_id / history_days / run_at）
- [x] 2.3 實作 `ensure_schema_forecasts(conn) -> None`，`CREATE TABLE IF NOT EXISTS` + commit
- [x] 2.4 實作 `upsert_forecasts(conn, location, start_date, forecasts: list[DailyTemperatureForecast], model_id: str, history_days: int) -> None`，使用 `executemany` + `ON CONFLICT DO UPDATE`
- [x] 2.5 實作 `fetch_forecasts_in_range(conn, location, start_date_from, start_date_to, horizon_step_filter: int | None) -> list[ForecastRow]`，回傳結構化 row（用 NamedTuple 或內部 dataclass，欄位與 schema 對應）
- [x] 2.6 `fetch_forecasts_in_range` 的 SQL 含可選的 `WHERE (target_date - start_date) = ?` 條件，依 `(start_date, target_date)` 升冪排序

## 3. DB 層測試

- [x] 3.1 新增 `tests/test_db_forecasts.py`，沿用 `test_db_repository.py` 的 skip-if-no-DSN pattern
- [x] 3.2 測試：`ensure_schema_forecasts` idempotent
- [x] 3.3 測試：`upsert_forecasts` 寫入後 `fetch_forecasts_in_range` 能取回，6 個分位 + metadata 欄位都正確
- [x] 3.4 測試：同 PK 重複 upsert 後最新值生效（覆蓋）
- [x] 3.5 測試：`fetch_forecasts_in_range` 的 `start_date` 範圍過濾與 `horizon_step_filter` 過濾分別正確
- [x] 3.6 測試：fixture teardown 清理測試地點的 forecast row（避免污染後續執行）

## 4. Evaluation orchestrator

- [x] 4.1 新增 `src/timesfm_meteo/evaluation/orchestrator.py`
- [x] 4.2 簽名：`evaluate_forecasts(location, start_date_from, start_date_to, horizon_step_filter: int | None, conn, open_meteo_settings) -> EvaluationReport`
- [x] 4.3 步驟 1：呼叫 `db.forecasts.fetch_forecasts_in_range` 取得篩選後的 forecasts
- [x] 4.4 步驟 2：若 forecasts 不為空，計算 target_date 集合的 min / max，呼叫 `pipeline.historical.get_temperatures(location, t_min, t_max, conn, open_meteo_settings)` 確保 actuals 進 DB
- [x] 4.5 步驟 3：把 `get_temperatures` 回傳的 `FetchResult.rows` 建成 `dict[Date, DailyTemperature]` 作為 actual lookup
- [x] 4.6 步驟 4：對每筆 forecast，依 `target_date` 從 lookup 取 actual：找到 → evaluated；找不到 → pending
- [x] 4.7 步驟 5：依 `horizon_step = (target_date - start_date).days` 分組，每組獨立計算 max / min × MAE / coverage / width（呼叫既有的 `evaluation.metrics` 三個函式）
- [x] 4.8 步驟 6：計算 `overall` 跨所有 step 聚合的 `GroupMetrics`
- [x] 4.9 步驟 7：組成 `EvaluationReport` 回傳；空組省略；無資料組 metrics 為 `None`

## 5. Orchestrator 測試（全 mock）

- [x] 5.1 新增 `tests/test_evaluation_orchestrator.py`
- [x] 5.2 測試：happy path — 3 筆 forecasts、3 筆 actuals 都對齊，驗證 `by_horizon_step` 的 step 與 metric 數值正確
- [x] 5.3 測試：部分 pending — 3 筆 forecasts、2 筆 actual，驗證 evaluated_count=2、pending_count=1，metric 只用 evaluated 那 2 筆計算
- [x] 5.4 測試：全 pending — actuals 都缺，metric 為 `None`
- [x] 5.5 測試：empty forecasts — 範圍內 0 筆，回傳 `by_horizon_step=[]`、`overall.evaluated_count=0`
- [x] 5.6 測試：horizon_step 分組 — 6 筆 forecasts 分屬 step 0/1/2，驗證每個 step 的 metric 獨立計算且不互相污染
- [x] 5.7 測試：horizon_step_filter — 給 `horizon_step_filter=1`，驗證只算 step==1 的 forecasts
- [x] 5.8 測試：MAE 用 p50、coverage 用 [p10, p90]、width 用 (p90-p10)，三個指標的計算對齊 design

## 6. CLI `forecast` 補 upsert

- [x] 6.1 在 `cli.py:_run_forecast` 中：連線後新增 `ensure_schema_forecasts(conn)`
- [x] 6.2 在 `forecast_with_timesfm` 拿到結果後、組 `ForecastResponse` 之前，新增 `upsert_forecasts(conn, location, start_date, forecasts, settings.timesfm.model_id, len(history_result.rows))`
- [x] 6.3 寫入失敗讓 exception 自然往上冒（例外路徑 exit 1，與一般 runtime error 一致；不另外 catch）
- [x] 6.4 在 `tests/test_cli.py:test_forecast_happy_path_emits_valid_json` 補 mock：把 `ensure_schema_forecasts` 與 `upsert_forecasts` patch 為 spy，確認 `upsert_forecasts` 被呼叫一次、參數含正確的 location / start_date / forecasts list / model_id / history_days
- [x] 6.5 新增 `test_forecast_happy_path_persists_forecasts`：dedicated 測試專門驗證 upsert 行為（與 happy path 分開，確保未來改動 happy path 不會掩蓋 upsert 漏呼叫的 regression）

## 7. CLI `evaluate` 子命令

- [x] 7.1 在 `cli.py:_build_parser` 新增 `evaluate` subparser：`--latitude`、`--longitude`、`--start-date-from`、`--start-date-to`（兩個都 required）、`--horizon-step`（選填，預設 None）
- [x] 7.2 新增 `_run_evaluate(args, settings) -> int`：
  - validate `Location`，越界 → exit 2
  - parse 日期範圍：`start_date_from <= start_date_to`，否則 → exit 2
  - DSN 缺失 → exit 2、stderr 訊息（沿用既有錯誤模式）
  - `with psycopg.connect(...) as conn`：`ensure_schema(conn)` + `ensure_schema_forecasts(conn)` → 呼叫 `evaluation.orchestrator.evaluate_forecasts(...)` → 拿到 `EvaluationReport`
  - 若 `report.overall.evaluated_count == 0 and report.overall.pending_count == 0`：stderr 印 `evaluated=0 pending=0 (no forecasts in range)`
  - 一律 `print(report.model_dump_json(indent=2))` 到 stdout，stderr 摘要 `evaluated=N pending=M horizon_step=<val|any>`
  - return 0
- [x] 7.3 把 `evaluate` 接進 `main()` dispatcher

## 8. CLI `evaluate` 測試

- [x] 8.1 在 `test_cli.py` 新增 `test_evaluate_invalid_latitude_returns_exit_code_2`
- [x] 8.2 新增 `test_evaluate_missing_database_url_does_not_load_anything`：mock `psycopg.connect` 與 `evaluate_forecasts` 都不可被呼叫
- [x] 8.3 新增 `test_evaluate_happy_path_emits_valid_json`：mock 整條 pipeline，驗證 stdout 可被 `EvaluationReport.model_validate_json` 反序列化、stderr 摘要格式正確
- [x] 8.4 新增 `test_evaluate_no_forecasts_in_range_exits_zero`：mock orchestrator 回 empty report，驗證 exit 0、stderr 含「no forecasts in range」
- [x] 8.5 新增 `test_evaluate_rejects_inverted_date_range`：`--start-date-from 2024-06-30 --start-date-to 2024-06-01`，exit 2

## 9. 文件

- [x] 9.1 在 `AGENTS.md` Development 區補 `evaluate` CLI 範例，例如：
  ```bash
  uv run timesfm-meteo evaluate --latitude 25.05 --longitude 121.57 \
      --start-date-from 2024-06-01 --start-date-to 2024-06-30
  ```
- [x] 9.2 在 `docs/roadmap.md` 把 MVP 第 5 步「基礎評估」標記為 (Done)（在所有任務完成、測試全綠後再改）

## 10. 端到端驗證

- [x] 10.1 跑 `uv run --extra dev pytest`，確認既有 + 新增測試全綠
- [x] 10.2 手動煙霧測試 — backtest 流程：
  - `uv run --extra forecast timesfm-meteo forecast --latitude 25.05 --longitude 121.57 --horizon 3 --start-date 2024-06-01`
  - 直接接著 `uv run timesfm-meteo evaluate --latitude 25.05 --longitude 121.57 --start-date-from 2024-06-01 --start-date-to 2024-06-01`
  - 驗證輸出含 3 個 horizon_step 的 metrics、`evaluated_count=3`、`pending_count=0`
- [x] 10.3 手動 SQL 確認：`SELECT * FROM forecasts WHERE start_date = '2024-06-01' AND latitude::float = 25.05 AND longitude::float = 121.57;` 應有 3 筆
- [x] 10.4 手動 empty range 煙霧測試：`uv run timesfm-meteo evaluate --latitude 25.05 --longitude 121.57 --start-date-from 2099-01-01 --start-date-to 2099-01-31`，驗證 exit 0、stderr 有 no-data 訊息
