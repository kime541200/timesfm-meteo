## Context

`evaluation/metrics.py` 的三個函式自開案以來已存在並有單元測試覆蓋：
- `mean_absolute_error(actual, predicted)`
- `interval_coverage(actual, lower, upper)`
- `mean_interval_width(lower, upper)`

它們是無狀態純函式、輸入輸出 list[float]，本 change 不動。

`forecast` CLI 目前流程：argparse → 取歷史（`get_temperatures`）→ 跑 TimesFM 引擎 → 拼 `ForecastResponse` JSON → stdout / stderr。整段沒有任何 DB 寫入動作，使用者 `Ctrl-C` 後 forecast 結果就消失。

`historical-fetch` 已建立兩條重要基礎建設：
1. `daily_temperatures` 表 + cache-aware `get_temperatures`：可從 Postgres 取已快取資料、缺漏自動向 Open-Meteo 補抓。
2. `psycopg.connect` + `ensure_schema` 的 CLI 連線模式：DSN 缺失或連線失敗一律 hard fail（exit 2），不靜默降級。

本 change 在這兩條基礎上加：forecast 持久化（一張新表 + upsert）、evaluate orchestration（讀 forecasts → 補 actuals → JOIN → 算指標）、新 CLI 子命令。

## Goals / Non-Goals

**Goals：**
- backtest 工作流能一條鞭跑通：`forecast --start-date 過去日期` → 立刻 `evaluate` → 拿到 MAE / coverage / width。
- live 工作流也支援：今天 `forecast` → 過幾天 actual 進 archive 後再 `evaluate`，不需要使用者手動 fetch-history 對齊。
- 指標分 max / min、分 horizon_step 輸出，避免聚合掩蓋方向性與時間衰減。
- evaluate 命令是 idempotent 純讀（除了 cache-aware 的 actual 補抓寫進 `daily_temperatures`），重跑不影響 forecasts 表。

**Non-Goals：**
- 不做 location alias（`--name Taipei` 指代座標）。已收進 roadmap Additional features，下一個 change 處理。
- 不做評估指標儀表板 / 視覺化。CLI 輸出 JSON 即可，視覺化交給下游工具或未來 Web client。
- 不做多 location 同時評估（`--all-locations`）。MVP 一次一個 location，未來再加 flag。
- 不做 forecast schema 版本化（model 換了 / 欄位變了的 migration）。MVP 階段直接 `CREATE TABLE IF NOT EXISTS`，schema 升級等實際遇到再處理。
- 不做歷史指標趨勢追蹤（`evaluate` 跑完不寫進另一張 `evaluations` 表）。MVP 只算當下、由使用者決定是否保存。

## Decisions

### 1. `forecasts` schema：wide row、PK 含 start_date 與 target_date

```sql
CREATE TABLE IF NOT EXISTS forecasts (
    latitude     NUMERIC(8, 4) NOT NULL,
    longitude    NUMERIC(8, 4) NOT NULL,
    start_date   DATE          NOT NULL,
    target_date  DATE          NOT NULL,
    max_p10      REAL          NOT NULL,
    max_p50      REAL          NOT NULL,
    max_p90      REAL          NOT NULL,
    min_p10      REAL          NOT NULL,
    min_p50      REAL          NOT NULL,
    min_p90      REAL          NOT NULL,
    model_id     TEXT          NOT NULL,
    history_days INT           NOT NULL,
    run_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (latitude, longitude, start_date, target_date)
);
```

**Wide vs tall**：max + min 各 3 分位 = 6 個 REAL，wide 與 `DailyTemperatureForecast` 1:1，查詢直接、JOIN 容易。Tall 結構（一個 row 一個 quantile）對只有 6 個 cell 的情況純粹是雜訊。

**PK 包含 `start_date`**：同一個 target_date 可以從多個「預測時點」算出（例如 5/3 預測 5/4，5/4 又預測 5/4 自己）。這兩筆 horizon_step 不同、誤差期望不同，要分開存才能算「day-1 vs day-3」差異。

**只存 p10/p50/p90**：CLI 輸出與 `QuantileValues` 模型只用三個分位；engine 雖然回 9 個但 adapter 已縮減。要更多分位時，先改 adapter 與 schema 一起升級。

**Metadata**：`model_id` 為換模型留下追溯線；`history_days` 為 debug 用（可發現「為什麼這次預測差」是不是因為餵的歷史不夠）；`run_at` 為時間戳記、debug staleness。三者都不在 PK，重跑會被覆蓋（這是預期行為）。

替代方案：把 `model_id` 加進 PK，讓不同模型的同一 forecast 並存。捨棄理由：MVP 只有一個模型；要做 model A vs B 比較時是另一個 capability，不該在 schema 預先支援。

### 2. Forecast 寫入時機：`forecast` 命令一律自動寫，無 flag

`_run_forecast` 拿到 `forecasts: list[DailyTemperatureForecast]` 後立刻呼叫 `db.forecasts.upsert_forecasts(conn, location, start_date, forecasts, model_id, history_days)`。

理由：
- `forecast` 命令已強制 DSN，多一個 upsert 不增加前置條件。
- 沒寫進 DB 的 forecast 沒有用 — JSON 印完就消失，使用者要事後 evaluate 必須先寫進。
- 一律自動寫 → backtest 工作流一條鞭：`forecast --start-date X` → `evaluate --start-date-from X --start-date-to X`。
- upsert 是 idempotent，重跑不會壞資料。

代價：沒有「dry run」選項。日後真有需要再補 `--no-persist` flag。

### 3. `evaluate` 內建補抓 actuals

evaluate 拿到範圍內的 forecasts 後，計算 target_date 集合的 min/max，呼叫 `get_temperatures(location, target_min, target_max, conn, settings.open_meteo)` 確保 `daily_temperatures` 涵蓋這段範圍。

理由：
- backtest 場景使用者可能跑完 `forecast --start-date 2024-06-01 --horizon 3` 後立刻 `evaluate`，但 `forecast` 只抓了「2024-05-31 之前」的歷史，target_dates `[2024-06-01..03]` 不在 DB 裡。要使用者再手動 `fetch-history --start-date 2024-06-01 --end-date 2024-06-03` 是冗餘步驟。
- `get_temperatures` 是 cache-aware；已有 actual 不重抓，只 SQL 確認；缺的補單一連續區間。成本低。
- live 場景 target_dates 在未來，`get_temperatures` 會發 HTTP 請求但 Open-Meteo archive 對未來日期沒資料，會回空 → 對應 row 為 pending。這是預期行為。

替代方案：evaluate 純讀 DB，使用者得自己 `fetch-history`。捨棄理由：增加心智負擔，且兩個命令都已要 DSN，串起來無不一致風險。

### 4. 指標分組：依 horizon_step 分 + overall 聚合

`horizon_step = target_date - start_date`（in days，0-indexed；`start_date == target_date` 時為 0）。

evaluate 內部以 `GROUP BY (target_date - start_date)` 拆出每個 step 的 forecasts + actuals，逐組計算指標。同時計算「不分組」的 overall 聚合作為 sanity check。

`--horizon-step N` flag 為 hard filter：只算指定 step，輸出仍然走 `by_horizon_step` 結構（list 長度為 1）+ `overall`（與該 step 相同）。

理由：
- 「TimesFM 對近期準、遠期不準」是時序預測常識，沒分 step 的指標會誤導決策。
- 分組成本低，多兩行 SQL `GROUP BY` 而已。
- `--horizon-step` 為選擇性過濾；多數情況使用者一次想看全部。

### 5. 模組分層

```
src/timesfm_meteo/
├── db/
│   ├── repository.py          # 既有：daily_temperatures CRUD（不 rename，避免 historical-fetch 那條 change 的 import 路徑改動）
│   └── forecasts.py           # 新增：ensure_schema_forecasts、upsert_forecasts、fetch_forecasts_in_range
├── evaluation/
│   ├── metrics.py             # 既有純函式（不動）
│   └── orchestrator.py        # 新增：evaluate_forecasts(...) 業務邏輯
└── cli.py                     # 新增 evaluate 子命令、_run_evaluate；_run_forecast 補一個 upsert 呼叫
```

`evaluate` CLI 是 thin glue：argparse → `Location` 驗證 → DSN 檢查 → 連線 → `ensure_schema` + `ensure_schema_forecasts` → 呼叫 `evaluation.orchestrator.evaluate_forecasts(...)` → `print(report.model_dump_json(indent=2))` → stderr 摘要。

業務邏輯（讀、補抓、JOIN、分組、算 metric）全在 orchestrator。orchestrator 介面：

```python
def evaluate_forecasts(
    location: Location,
    start_date_from: Date,
    start_date_to: Date,
    horizon_step_filter: int | None,
    conn: psycopg.Connection,
    open_meteo_settings: OpenMeteoSettings,
) -> EvaluationReport: ...
```

DB 層注入 `conn`、API 層注入 `open_meteo_settings`，方便測試 mock。

### 6. EvaluationReport 三層巢狀結構

```python
class VariableMetrics(ProjectModel):
    mae_p50: float
    interval_coverage: float        # 0..1
    mean_interval_width: float

class GroupMetrics(ProjectModel):
    evaluated_count: int
    pending_count: int
    max: VariableMetrics | None     # None when evaluated_count == 0
    min: VariableMetrics | None

class HorizonStepReport(ProjectModel):
    horizon_step: int
    metrics: GroupMetrics

class EvaluationReport(ProjectModel):
    location: Location
    start_date_from: Date
    start_date_to: Date
    horizon_step_filter: int | None
    by_horizon_step: list[HorizonStepReport]   # ordered by step ascending
    overall: GroupMetrics
```

理由：
- `VariableMetrics` 隔離「max 還是 min」的對稱結構，避免 6 個欄位攤平難讀。
- `GroupMetrics.max/min` 用 `Optional` 表達「此分組沒有資料可算」，比放 0 / NaN 語義更清楚；JSON 序列化為 `null`。
- `HorizonStepReport` 包 `horizon_step` + 該 step 的 metrics，方便依序輸出。
- `overall` 直接重用 `GroupMetrics`，省一個型別。

### 7. 邊界情境一律 exit 0

| 情境 | 處理 |
|---|---|
| 範圍內 0 筆 forecasts | `by_horizon_step: []`、`overall.evaluated_count=0/pending_count=0`、`overall.max/min=None`。stderr 印 `evaluated=0 pending=0 (no forecasts in range)` |
| 全部 pending（actual 都還沒到） | 同上邏輯但 `pending_count` 反映實際筆數 |
| 某 horizon_step 完全沒資料 | 從 `by_horizon_step` 省略該 step（不放 count=0 的空 entry） |

理由：使用者問了空範圍不是「程式錯誤」，是「事實是這個範圍沒資料」。回 exit 0 + 訊息比 exit 2 更精準。argparse / 座標 / DSN 等真正錯誤仍 exit 2、執行例外 exit 1。

### 8. Schema bootstrap 在兩個 CLI 路徑都呼叫

`_run_forecast` 與 `_run_evaluate` 都在連線後呼叫：
```python
ensure_schema(conn)              # daily_temperatures
ensure_schema_forecasts(conn)    # forecasts
```

兩者都是 `CREATE TABLE IF NOT EXISTS`，重複呼叫無副作用。從未跑過 forecast 直接跑 evaluate 也不會炸。

### 9. 測試策略

| 層 | 檔案 | 策略 |
|---|---|---|
| 純函式 metrics | `test_metrics.py` | 既有，不動 |
| DB 層 `db/forecasts` | `test_db_forecasts.py`（新）| 整合測試：真連 DB、無 `DATABASE_URL` 時 skip。沿用 `test_db_repository.py` pattern |
| Orchestrator | `test_evaluation_orchestrator.py`（新）| 全 mock：`fetch_forecasts_in_range`、`get_temperatures` 注入 fake，驗證 JOIN、分組、metric 計算、邊界情境（empty / all pending / 部分 pending）|
| CLI evaluate | `test_cli.py` 補充 | 全 mock 整條 pipeline，驗證 `EvaluationReport` JSON 可被反序列化、邊界情境、DSN 缺失與座標錯誤路徑 |
| Forecast 寫入 | `test_cli.py` 補充 | 既有 happy path 測試擴充：mock `upsert_forecasts`、確認被呼叫一次且參數正確 |

`evaluation/orchestrator.py` 設計上接受 dependency injection（conn 傳入、`get_temperatures` 與 `fetch_forecasts_in_range` 都是模組函式可被 monkeypatch），讓 mock 容易寫、不需要動 production 簽名。

## Risks / Trade-offs

- **Risk**：使用者在不同 model_id 之間切換 → 同一 PK 的 forecast 被覆蓋、看不到舊模型的指標。MVP 接受此 trade-off。日後若需要 model A/B 比較，加 `model_id` 進 PK 即可，舊資料可保留為「最近一個 model」的 snapshot。
- **Risk**：evaluate 補抓會發 HTTP（在 actual 缺失時）。對 live 工作流意義不大（archive 對近期日期都會空），但每次 evaluate 至少會打一次 Open-Meteo API。可接受；若未來流量變大再加 cache TTL 或顯式 `--no-fetch` flag。
- **Trade-off**：`forecasts` 表沒有 `forecast_run_id`，重跑同 `(loc, start_date, target_date)` 即覆蓋。代表「我想看上次跑的結果」必須在重跑前手動 query 或 dump。MVP 不處理；若日後需要追溯歷次 run，引入 `run_id` 欄位（或 audit table）即可。
- **Trade-off**：「evaluate 自動補抓 actual」隱含 evaluate 命令會修改 `daily_temperatures`（透過 `upsert_temperatures`）。文件需明確說明。設計上沒問題（`get_temperatures` 是 cache-aware idempotent），但「evaluate 是純讀」的直覺會被打破。可接受；補抓比強迫使用者額外跑 `fetch-history` 友善太多。
- **Trade-off**：location 強制要給 `--latitude --longitude` → 使用者要記座標。已知 UX 痛點；roadmap Additional features 已有「地點 alias」項目，下一個 change 一次幫 fetch-history / forecast / evaluate 三者補上 `--name` 支援。
