## Why

MVP CLI（`fetch-history` / `forecast` / `evaluate`）已可運作，但只能在本機 shell 操作。為了讓 Web Dashboard、AI Agent 與排程器能透過統一介面存取資料與觸發 pipeline，需要一個 HTTP API server。

CLI 對人類友善，但對 AI Agent 與遠端 client 不友善：每次執行都要載入模型與 DB；本機環境差異大。把 pipeline 包成 FastAPI server 後，AI Agent 可透過輕量 CLI client 呼叫遠端服務，Web Dashboard（後續 change）也能基於同一份 API 開發。本 change 同時交付 API server 與 CLI client，兩者皆為 Python 專案、共用 `pyproject.toml`，所以放在同一個 change 比較自然。

## What Changes

- 新增 FastAPI server 模組 `src/timesfm_meteo/api/`
  - 讀取端點：`GET /temperatures`、`GET /forecasts`、`GET /evaluate`
  - 觸發端點：`POST /fetch-history`、`POST /forecast`（async，回 job_id）
  - Job 狀態：`GET /jobs/{id}`
  - Auth：API Key（`Authorization: Bearer <key>`，從 `.env` 讀）
  - 啟動時透過 FastAPI lifespan 載入 `TimesFMEngine`，常駐記憶體；以 `ForecastEngine` Protocol 注入，未來可換成遠端 inference client
- 新增 `jobs` 表持久化 async job 狀態（type / status / params / error / timestamps）
- 新增 CLI client 模組 `src/timesfm_meteo/client/`
  - 入口點 `timesfm-meteo-client`
  - 子命令對應到 server endpoints
  - 只依賴 `httpx` + `pydantic`（不引入 `psycopg`、`timesfm`）
  - 設定來源：`TIMESFM_API_URL`、`TIMESFM_API_KEY` 環境變數
- `pyproject.toml`：新增 `[project.optional-dependencies].api` extra（`fastapi`、`uvicorn`）；CLI client 的 entry point 加入 `[project.scripts]`
- 文件：新增 `docs/api-server.md`（endpoint 規格、auth、部署）、`docs/cli-client.md`（CLI client 操作）；更新 `AGENTS.md`、`README.md`、`docs/usage.md`
- 既有 CLI（`timesfm-meteo`）行為**不變**，繼續支援本機操作與測試

## Capabilities

### New Capabilities
- `api-server`: FastAPI HTTP server 包裝既有 pipeline，負責 endpoints、auth、async job 狀態管理、模型常駐
- `cli-client`: 輕量 CLI client，對 API server 發 HTTP request；提供與 server endpoints 對應的子命令

### Modified Capabilities
無。`historical-fetch`、`temperature-forecasting`、`forecast-evaluation` 等既有 capability 行為不變；本 change 只是把它們透過 HTTP 暴露出來。

## Impact

- **新增 Python 模組**：`src/timesfm_meteo/api/`、`src/timesfm_meteo/client/`
- **新增 DB 表**：`jobs`（透過 `ensure_schema_jobs` 建立，與既有 schema bootstrap 一致）
- **新依賴**：`fastapi`、`uvicorn[standard]`（放在 `[api]` extra）；CLI client 只用既有 `httpx` + `pydantic`
- **新環境變數**：`API_KEY`（server 端驗證）、`TIMESFM_API_URL`、`TIMESFM_API_KEY`（client 端）
- **既有元件**：CLI、pipeline、DB repository 行為不變；`ForecastEngine` Protocol 已是乾淨注入點，無需重構
- **部署**：server 啟動需要 `uv sync --extra forecast --extra api`；CLI client 只需 base 安裝
- **長期 Inference Server**：本 change 不抽出獨立 inference 服務，但透過 Protocol 已留好邊界，未來只需替換 engine 實作
