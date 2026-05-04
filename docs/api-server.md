# API Server

`timesfm-meteo` 提供一個 FastAPI HTTP server，將既有 CLI pipeline（歷史抓取 / 預測 / 評估）包裝成 REST endpoints，供 Web Dashboard、AI Agent 與排程器使用。

## 依賴安裝

```bash
# 只跑 server（不需要 forecast extra）
uv sync --extra api

# 同時啟動 forecast 功能（模型常駐）
uv sync --extra api --extra forecast
```

## 設定

`.env` 中需要：

```env
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/timesfm_meteo
API_KEY=<隨機字串，建議 32 bytes hex>
# 產生方式：python -c "import secrets; print(secrets.token_hex(32))"

# TimesFM checkpoint 位置（可選，留空使用 HF 預設）
HF_HOME=
```

## 啟動

```bash
uv run uvicorn timesfm_meteo.api.app:app --host 0.0.0.0 --port 8000
```

開發時加 `--reload` 可自動重載（但注意：reload 會重新載入 TimesFM 模型）。

啟動時，server 會：
1. 驗證 `DATABASE_URL` 與 `API_KEY` 已設定（缺少任一則啟動失敗）
2. 建立 psycopg connection pool
3. 執行 `ensure_schema` / `ensure_schema_forecasts` / `ensure_schema_jobs`（冪等）
4. 載入 `TimesFMEngine`（首次約 30–60 秒，之後記憶體常駐）

## 認證

所有 endpoints 需要 Bearer token：

```
Authorization: Bearer <API_KEY>
```

## Endpoints

### 讀取端點

| Method | Path | 說明 |
|--------|------|------|
| `GET` | `/temperatures` | 查詢歷史氣溫（自動補抓缺漏日期） |
| `GET` | `/forecasts` | 查詢已存的預測結果 |
| `GET` | `/evaluate` | 即時計算預測評估報告 |

#### GET /temperatures

Query params：`latitude`, `longitude`, `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD)

```bash
curl -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/temperatures?latitude=25.05&longitude=121.57&start_date=2024-06-01&end_date=2024-06-07"
```

Response: `{ cached_count, fetched_count, rows: [ { date, temperature_max, temperature_min } ] }`

#### GET /forecasts

Query params：`latitude`, `longitude`, `start_date_from`, `start_date_to`, `horizon_step` (選填)

```bash
curl -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/forecasts?latitude=25.05&longitude=121.57&start_date_from=2024-06-01&start_date_to=2024-06-30"
```

Response: 預測列表，每列含 `start_date`, `target_date`, `max_p10/p50/p90`, `min_p10/p50/p90`, `model_id`, `history_days`

#### GET /evaluate

Query params：`latitude`, `longitude`, `start_date_from`, `start_date_to`, `horizon_step` (選填)

Response: `EvaluationReport` JSON（與 CLI `evaluate` 輸出相同）

### 觸發端點（非同步 job）

| Method | Path | 說明 |
|--------|------|------|
| `POST` | `/forecast` | 觸發 TimesFM 預測 job |
| `POST` | `/fetch-history` | 觸發歷史氣溫抓取 job |
| `GET` | `/jobs/{job_id}` | 查詢 job 狀態 |

#### POST /forecast

```bash
curl -X POST -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 25.05, "longitude": 121.57, "horizon": 3}' \
  http://localhost:8000/forecast
```

Response (202): `{ job_id: <uuid>, status: "pending" }`

Body 欄位：`latitude`, `longitude`, `horizon` (選填), `history_years` (選填), `start_date` (選填，預設今天)

#### POST /fetch-history

```bash
curl -X POST -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 25.05, "longitude": 121.57, "years": 2}' \
  http://localhost:8000/fetch-history
```

Body 欄位：`latitude`, `longitude`, `years` (與 `start_date` 二擇一), `start_date`, `end_date`

#### GET /jobs/{job_id}

```bash
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8000/jobs/<job_id>
```

Response:
```json
{
  "id": "...",
  "type": "forecast",
  "status": "done",
  "params": { ... },
  "result": { "horizon": 3, "model_id": "...", "history_days": 730, "target_dates": [...] },
  "error": null,
  "created_at": "...",
  "updated_at": "..."
}
```

Status 值：`pending` → `running` → `done` | `failed`

## Jobs 表 schema

```sql
CREATE TABLE jobs (
  id          UUID        PRIMARY KEY,
  type        TEXT        NOT NULL CHECK (type IN ('forecast', 'fetch-history')),
  status      TEXT        NOT NULL CHECK (status IN ('pending', 'running', 'done', 'failed')),
  params      JSONB       NOT NULL,
  result      JSONB,
  error       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## 模型常駐與序列化

TimesFM 模型在 server 啟動時透過 FastAPI lifespan 載入，常駐記憶體。Forecast job 執行時使用一個 `asyncio.Lock` 確保同一時間只有一個 `engine.forecast()` 在執行，避免 GPU 記憶體競爭。

**已知限制**：目前 forecast 是串列執行，若同時觸發多個 `POST /forecast`，後者會在 lock 後面等待。未來可透過 TimesFM Inference Server（長期規劃）擴充並行能力。

## 自動文件

啟動後可瀏覽：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 未來部署

待「中期 2. Docker 包裝服務」實作後，server 將透過 `docker-compose.yml` 與 Postgres 一起啟動。目前手動啟動即可。
