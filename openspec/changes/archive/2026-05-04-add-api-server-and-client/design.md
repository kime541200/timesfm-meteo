## Context

MVP CLI 階段已完成歷史抓取、TimesFM 預測與基礎評估三個 pipeline，目前皆為直接呼叫的 Python 函式：`get_temperatures`、`forecast_with_timesfm`、`evaluate_forecasts`。本 change 將這些 pipeline 包成 HTTP API，並提供對應的輕量 CLI client。

關鍵約束：

- 既有 CLI（`timesfm-meteo`）已穩定，受眾與 API 不同（本機 / 開發），不應因 API 而被改寫。
- TimesFM 模型載入需 30–60 秒；若每次請求都載入會無法當作互動式服務使用。
- 既有 `ForecastEngine` Protocol 已設計為注入點，未來可替換為遠端 inference client。
- AI Agent 是 CLI client 的主要消費者；它的環境通常沒有 GPU、不裝 `timesfm`、不直連 DB。

## Goals / Non-Goals

**Goals:**
- 把現有 `historical-fetch`、`temperature-forecasting`、`forecast-evaluation` pipeline 透過 HTTP endpoint 暴露。
- 模型常駐記憶體：`POST /forecast` 回應在毫秒～秒級（不含模型載入）。
- 非同步 forecast 執行：API 立即回 job_id，client 透過 `GET /jobs/{id}` 輪詢。
- Job 狀態持久化於 Postgres，重啟可恢復。
- API Key auth：單一 key，從 `.env` 讀取。
- CLI client 只依賴 `httpx` + `pydantic`，可獨立安裝給 AI Agent 使用。
- 既有 CLI 行為完全不變。
- 為未來 Web client（下一個 change）與排程器（中期 4）提供 stable API。

**Non-Goals:**
- 不抽 inference server 為獨立服務（長期規劃）。但設計需保留乾淨邊界。
- 不做 OAuth / JWT / 多用戶。本階段只支援單一 API key。
- 不做 RBAC、rate limiting、audit log。
- 不在本 change 做 Web Dashboard（下一個 change）。
- 不做地點 alias（Additional features）。本 change 端點仍以 latitude / longitude 為輸入。
- 不重寫既有 CLI 來呼叫 API。

## Decisions

### Decision 1: FastAPI + uvicorn 為 HTTP server

**Choice:** FastAPI（已在 roadmap 點名）+ `uvicorn[standard]` runner。

**Why:** Pydantic 已是專案內建依賴；FastAPI 的 type-driven 接口剛好能直接重用 `Location`、`DailyTemperature`、`ForecastResponse`、`EvaluationReport` 等模型作為 request/response schema，OpenAPI 文件自動產生。

**Alternatives considered:**
- Flask：型別整合較弱，需要額外 marshmallow 或手動驗證。
- Starlette only：失去 FastAPI 的 dependency injection 與自動文件。
- gRPC：對 AI Agent 與 Web client 都不友善（需要 proto buf 工具鏈）。

### Decision 2: 模型啟動時透過 lifespan 載入

**Choice:** 用 FastAPI `lifespan` async context manager，在 startup 時建立 `TimesFMEngine` 並掛在 `app.state.engine`；shutdown 時釋放。

**Why:** 模型載入需 30–60 秒，若每次 forecast 都重新載入，server 等同每次 cold start。常駐記憶體後，`POST /forecast` 從 client 角度可預期。

**Alternatives considered:**
- Lazy load on first request：第一次仍要等很久，且測試難寫。
- Per-request load：完全違背「server 存在的目的」。

### Decision 3: `POST /forecast` 非同步，job 狀態存 Postgres

**Choice:** `POST /forecast` 即時回 `{job_id, status: "pending"}`；FastAPI `BackgroundTasks` 在背景跑 forecast；過程中更新 `jobs` 表（`pending` → `running` → `done` / `failed`）；client 透過 `GET /jobs/{job_id}` 輪詢。

**Schema:**
```sql
CREATE TABLE jobs (
  id UUID PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('forecast', 'fetch-history')),
  status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'done', 'failed')),
  params JSONB NOT NULL,
  result JSONB,                -- forecast 結果摘要 / fetch-history 結果摘要
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX jobs_status_idx ON jobs (status);
CREATE INDEX jobs_created_at_idx ON jobs (created_at DESC);
```

**Why:** Server 重啟不丟 job 狀態；Dashboard 後續可顯示「上次排程結果」；若 forecast 失敗，error message 可從 DB 回查。

**Alternatives considered:**
- In-memory dict：重啟即失。
- Redis：多一個服務，本階段過重。
- Celery + broker：過度設計，目前不需要分散式 worker。

**Trade-off:** `POST /forecast` 雖然非同步，但因為模型常駐，實際背景執行通常 1–2 秒內就完成。client 第一次輪詢就常常拿到 `done`。設計上仍走 job 路線是為了：(1) 統一介面（fetch-history 也是 async）、(2) 預留未來模型變大、批次預測等情境。

### Decision 4: Auth 用 single API key

**Choice:** Server 啟動時讀 `.env` 的 `API_KEY`；所有 endpoint 用 FastAPI `Depends(verify_api_key)` 攔截 `Authorization: Bearer <key>`。

**Why:** 單人自架、單一 client 場景下，API Key 是最小可行 auth。JWT 過重；無 auth 則未來補很麻煩。

**API Key 缺失策略:**
- `.env` 沒有 `API_KEY` 時，server 啟動就 fail（不靜默放行）。
- 401 回應使用標準 FastAPI HTTPException。

### Decision 5: CLI client 只依賴 `httpx` + `pydantic`

**Choice:** `src/timesfm_meteo/client/` 不 import 任何 server / pipeline / DB 模組。重用 `models.py` 的 Pydantic 類別作為 response schema 即可。

**Why:** AI Agent 環境通常輕量，不應為了呼叫 API 而拖入 `psycopg`、`timesfm`、`torch`。`models.py` 內的 `Location`、`DailyTemperature`、`ForecastResponse`、`EvaluationReport` 不依賴重套件，可安全共用。

**安裝體驗:**
- `uv pip install timesfm-meteo`：base 依賴，`timesfm-meteo-client` 立即可用。
- `uv pip install timesfm-meteo[api]`：加上 server 依賴。
- `uv pip install timesfm-meteo[forecast,api]`：要在同一台機器同時跑 server 與 forecast。

### Decision 6: API code layout

```
src/timesfm_meteo/api/
├── __init__.py
├── app.py              # FastAPI app + lifespan
├── auth.py             # API key dependency
├── deps.py             # DB connection + engine dependency injection
├── routers/
│   ├── __init__.py
│   ├── temperatures.py # GET /temperatures
│   ├── forecasts.py    # GET /forecasts, POST /forecast
│   ├── evaluate.py     # GET /evaluate
│   ├── fetch_history.py# POST /fetch-history
│   └── jobs.py         # GET /jobs/{id}
├── jobs.py             # background job runner (calls existing pipeline funcs)
└── schemas.py          # request/response models specific to API (e.g., JobResponse)
```

**Why:** Router 切分與 endpoint 對齊，方便擴充與測試。`schemas.py` 只放 API 特有的（如 `JobResponse`），共用 model 仍 import `timesfm_meteo.models`。

### Decision 7: CLI client code layout

```
src/timesfm_meteo/client/
├── __init__.py
├── cli.py              # argparse entry point
├── http.py             # httpx client wrapper + auth header injection
└── commands/
    ├── __init__.py
    ├── temperatures.py
    ├── forecasts.py
    ├── evaluate.py
    └── jobs.py
```

CLI client 子命令：

- `timesfm-meteo-client temperatures get --latitude --longitude --start-date --end-date`
- `timesfm-meteo-client forecasts list --latitude --longitude --start-date-from --start-date-to`
- `timesfm-meteo-client forecast run --latitude --longitude --horizon`（觸發 + 輪詢直到完成，預設 timeout 120s；可加 `--no-wait` 立即回 job_id）
- `timesfm-meteo-client fetch-history run --latitude --longitude --years`（同上 async 行為）
- `timesfm-meteo-client evaluate get --latitude --longitude --start-date-from --start-date-to`
- `timesfm-meteo-client jobs get <job_id>`

預設 `forecast run` / `fetch-history run` 是 sync-wait（對 AI Agent 友善，一個指令拿結果）；`--no-wait` 是 fire-and-forget。

### Decision 8: 同步 endpoint（GET）直接重用既有 pipeline 函式

**Choice:** `GET /temperatures`、`GET /forecasts`、`GET /evaluate` 內部直接 call `pipeline.historical.get_temperatures`、`db.forecasts.fetch_forecasts_in_range`、`evaluation.orchestrator.evaluate_forecasts`，傳入由 FastAPI dependency 注入的 `psycopg` connection。

**Why:** 維持既有 pipeline 為單一邏輯來源；API 只是 transport layer。`GET /evaluate` 即時計算，輸入 / 輸出與 CLI 一致。

### Decision 9: 文件策略

每個新模組附 Markdown 文件，與程式碼同步寫：

- `docs/api-server.md`：endpoint 規格、auth、啟動指令、Docker 部署準備、`jobs` 表 schema 說明。
- `docs/cli-client.md`：CLI client 安裝、設定、各子命令範例（含 AI Agent 使用情境）。
- `docs/usage.md`：補上 API server / CLI client 啟動段落。
- `AGENTS.md`：新增 API server / CLI client 啟動指令與檔案結構。
- `README.md`：簡短引用 API / client 文件。

## Risks / Trade-offs

- **[模型載入失敗時 server 起不來]** → server 啟動 log 明確顯示「TimesFM lifespan failed: ...」；docker compose 的 healthcheck 會持續 fail，迫使 operator 處理而不是讓服務看起來正常但 forecast 全爆。
- **[單一 worker uvicorn 同時跑多個 forecast 會競爭 GPU]** → 第一版只支援 `--workers 1`；CPU-bound / GPU-bound 工作放 `BackgroundTasks` 加上一個 `asyncio.Lock` 確保 `engine.forecast` 序列化執行。文件清楚標示「目前 forecast 串列執行」。
- **[BackgroundTasks 在請求處理結束才開始]** → 對純背景任務這沒問題；client 拿到 job_id 後輪詢即可。但若 server 在背景任務跑到一半被 kill，job 會永遠停在 `running`。Mitigation：`jobs` 表的 `updated_at` + `created_at` 配合，client 可判斷「running 但 5 分鐘沒更新」視為 stale；server 啟動時可選擇把舊 `running` job 標 `failed`（lifespan startup 時 sweep）。
- **[API key 寫在 `.env`，初次 setup 容易忘了改]** → `.env.example` 提供範本並註記必填；server 啟動時若 `API_KEY` 為空字串直接 raise。
- **[CLI client 預設 `wait` 行為對於長 job 不友善]** → 提供 `--timeout` flag 與 `--no-wait`。
- **[未來抽 Inference Server 可能要改 lifespan / engine 實作]** → `ForecastEngine` Protocol 已是注入點；改動只在 `deps.py` 內部，router 與 jobs 邏輯不動。

## Migration Plan

無破壞性變更。部署步驟：

1. `uv sync --extra forecast --extra api`
2. `.env` 新增 `API_KEY=<random-string>`
3. 啟動：`uv run uvicorn timesfm_meteo.api.app:app --host 0.0.0.0 --port 8000`
4. CLI client 端：`.env`（或環境）設定 `TIMESFM_API_URL=http://localhost:8000` 與 `TIMESFM_API_KEY=<same key>`
5. 既有 CLI 不受影響，可繼續使用。

回滾：移除 `[api]` extra 並停止 uvicorn 即可，無 schema 破壞性變更（`jobs` 表為新增）。

## Open Questions

- **Job sweep on startup**：lifespan startup 是否要把所有 `running` job 標為 `failed`？傾向「是」，但留作實作時細調，避免 false positive（例如多 server 部署時不該互踩）。本階段單 worker，安全。
- **CLI client 設定優先順序**：CLI flag > 環境變數 > `.env`。確認沒問題即可。
- **`POST /fetch-history` 是否需要 limit**：抓 10 年資料約幾 KB，影響不大；先不限制，未來若需要再加 throttle。
