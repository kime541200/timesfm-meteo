## Why

MVP roadmap 第 5 步「基礎評估」是 MVP 收尾。`evaluation/metrics.py` 的三個純函式（MAE、interval coverage、interval width）已實作並有單元測試，但目前沒有資料源可餵 — `forecast` 命令的結果只印到 stdout 就消失，沒持久化，也沒辦法 JOIN 後續觀測值。本 change 補上「forecast 持久化 → 等 actual → 計算指標」的閉環，讓使用者能在 backtest 或 live 工作流下實際看到模型誤差、區間覆蓋率與不確定性寬度。

## What Changes

- 新增 `forecasts` 表（`db/forecasts.py`）：wide row、PK = `(latitude, longitude, start_date, target_date)`，欄位含 `max_p10/p50/p90`、`min_p10/p50/p90`、`model_id`、`history_days`、`run_at`。
- `cli.py:_run_forecast` 在預測完成後一律 upsert 到 `forecasts` 表。沒有 flag 切換、沒有 dry-run；`forecast` 命令本來就強制要 DB 連線，多寫一張表沒有額外負擔。
- 新增 `evaluation/orchestrator.py`：`evaluate_forecasts(...)` 函式，讀取 `forecasts` 表 → 對 target_date 範圍呼叫 `pipeline.historical.get_temperatures` 確保 actual 進 DB（cache-aware）→ LEFT JOIN → 依 `horizon_step = target_date - start_date` 分組計算 max / min × MAE / coverage / width。
- 新增 CLI 子命令 `evaluate --latitude --longitude --start-date-from --start-date-to [--horizon-step]`。輸出 stdout 為 `EvaluationReport` JSON（可直接 `model_validate_json`）、stderr 為一行 ops 摘要。
- 新增 pydantic 模型到 `models.py`：`VariableMetrics`、`GroupMetrics`、`HorizonStepReport`、`EvaluationReport`。
- `evaluate` 在範圍內無 forecast 或 actual 全 pending 時走成功路徑（exit 0），用 stderr 明確告知，避免使用者誤判。
- live 與 backtest 共用同一條 pipeline；差別只在「actual 是否已存在」，evaluate 內建補抓邏輯讓兩種工作流的步驟一致。

## Capabilities

### New Capabilities

- `forecast-evaluation`：把 forecast 結果持久化到 Postgres，並在指定範圍內把 forecast 與後續觀測值對齊，計算 max / min 各自的 MAE、interval coverage 與 interval width，依 horizon_step 分組。

### Modified Capabilities

- `temperature-forecasting`：`forecast` CLI 流程在輸出 JSON 前多一個 upsert 步驟。輸出格式不變、退出碼不變，只新增「side effect：forecasts 表會被寫入」。

## Impact

- 程式碼新增：`db/forecasts.py`、`evaluation/orchestrator.py`、`cli.py`（新增 `evaluate` 子命令、`_run_forecast` 補 upsert）、`models.py`（新增 4 個 pydantic 模型）。
- 不新增第三方依賴。
- 測試：`tests/test_db_forecasts.py`（新檔，整合測試風格，無 DSN 時 skip）、`tests/test_evaluation_orchestrator.py`（新檔，全 mock）、`tests/test_cli.py`（補 evaluate + forecast 寫入確認）。
- 文件：`AGENTS.md` Development 區補 `evaluate` CLI 範例；`docs/roadmap.md` MVP 第 5 步補 (Done) 標記（在實作完成、測試全綠後）。
- 不變動：`historical-fetch` 與其 spec、`db/repository.py`（不 rename）、`fetch-history` CLI、`forecasting/timesfm.py` adapter、`inference/timesfm_engine.py`。
