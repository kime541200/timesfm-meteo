# AGENTS.md

## 專案範圍

本專案目前仍在規劃與 MVP 階段。優先完成天氣資料與預測 pipeline，再處理
API、資料庫、UI 或交易自動化。

目前 MVP 目標：
- 依指定經緯度取得每日歷史氣溫資料。
- 使用至少兩年的每日最高溫與最低溫作為模型輸入。
- 產出未來 3 日氣溫預測。
- 使用 p10、p50、p90 等分位數表示預測不確定性。
- 保留足夠的評估輸出，讓預測結果能和後續觀測值比較。

## Setup

專案目前使用 Python 3.12 與 `pyproject.toml`。

```bash
uv sync
```

runtime 依賴目前包含 `httpx`、`psycopg`、`pydantic`、`python-dotenv`、`PyYAML`；
dev extra 包含 `pytest` 與 `respx`；`forecast` extra 包含 `timesfm[torch]` 與 `numpy`；
`api` extra 包含 `fastapi`、`uvicorn[standard]`、`psycopg-pool`。
若任務需要新增依賴，請加到 `pyproject.toml`，並讓改動維持在該任務所需範圍內。

```bash
uv sync --extra forecast   # 執行 forecast 子命令
uv sync --extra api        # 啟動 API server
uv sync --extra dev        # pytest
```

## Development

目前入口：

```bash
uv run python main.py
uv run python -m timesfm_meteo
uv run timesfm-meteo
```

抓取歷史氣溫（會自動使用 Postgres 快取，缺漏日期才呼叫 Open-Meteo 並回寫）：

```bash
uv run timesfm-meteo fetch-history --latitude 25.05 --longitude 121.57 --years 2
```

預測未來氣溫（需要先 `uv sync --extra forecast`；輸出為 `ForecastResponse` JSON；預測結果會自動寫進 `forecasts` 表）：

```bash
uv run timesfm-meteo forecast --latitude 25.05 --longitude 121.57 --horizon 3
```

評估儲存的預測與觀測值（輸出為 `EvaluationReport` JSON；`--horizon-step` 選填）：

```bash
uv run timesfm-meteo evaluate --latitude 25.05 --longitude 121.57 \
    --start-date-from 2024-06-01 --start-date-to 2024-06-30
```

啟動 API server（需要先 `uv sync --extra api --extra forecast`；同時設定 `.env` 中 `API_KEY`）：

```bash
uv run uvicorn timesfm_meteo.api.app:app --host 0.0.0.0 --port 8000
```

AI Agent / 遠端呼叫用輕量 CLI client（只需 base install；設定 `.env` 中 `TIMESFM_API_URL` / `TIMESFM_API_KEY`）：

```bash
uv run timesfm-meteo-client forecast run --latitude 25.05 --longitude 121.57 --horizon 3
```

Web Dashboard（`web/`，React + Vite；需先啟動 API server，並設定 `web/.env.local` 中 `VITE_TIMESFM_API_KEY`）：

```bash
cd web
npm install
npm run dev
npm test
npm run build
```

早期實作順序：
1. Open-Meteo 歷史每日資料 fetcher。
2. TimesFM 輸入所需的 time-series 正規化。
3. 未來 3 日預測 command 或 function。
4. 分位數預測輸出與簡單 backtesting 指標。

除非使用者明確要求，否則不要在上述 MVP pipeline 完成前先做 FastAPI server、
Web client、Postgres 整合或 Polymarket 自動化。

## Project Structure

- `main.py`：repo 根目錄的薄入口，只呼叫 `timesfm_meteo.cli.main`，不要放核心邏輯。
- `src/timesfm_meteo/`：可匯入的核心 Python package。
- `src/timesfm_meteo/cli.py`：CLI 入口（`timesfm-meteo`）。
- `src/timesfm_meteo/api/`：FastAPI HTTP server（`[api]` extra）。
- `src/timesfm_meteo/client/`：輕量 CLI client（`timesfm-meteo-client`，base install）。
- `web/`：React + Vite Web Dashboard，透過 `/api/*` Vite proxy 呼叫 FastAPI。
- `src/timesfm_meteo/configs.py`：讀取 `.env` 與 `configs/configs.yaml`，並以 Pydantic 驗證設定。
- `src/timesfm_meteo/models.py`：核心資料結構。
- `src/timesfm_meteo/db/`：Postgres repository（`repository.py`、`forecasts.py`、`jobs.py`）。
- `src/timesfm_meteo/data_sources/`：外部資料來源，例如 Open-Meteo。
- `src/timesfm_meteo/inference/`：TimesFM engine（`ForecastEngine` Protocol、`TimesFMEngine`）。
- `src/timesfm_meteo/forecasting/`：TimesFM adapter 與 baseline forecast。
- `src/timesfm_meteo/pipeline/`：資料抓取、預測與評估的 orchestration。
- `src/timesfm_meteo/evaluation/`：回測與評估指標。
- `tests/`：測試程式；不要加入 `__init__.py`。
- `configs/configs.example.yaml`：非敏感設定範例。
- `configs/configs.yaml`：本機 runtime 設定，預設由 `load_settings()` 讀取，不應提交。
- `pyproject.toml`：Python 專案 metadata 與依賴設定。
- `docs/roadmap.md`：專案目標與分階段規劃。
- `docs/api-server.md`：API server endpoint 規格與部署說明。
- `docs/cli-client.md`：CLI client 操作說明（含 AI Agent 使用情境）。
- `docs/quantile-forecasting.md`：分位數預測與不確定性說明。

## Code Style

- 使用 src-layout；所有可匯入的 production Python 模組都放在 `src/timesfm_meteo/`。
- 不要在 repo 根目錄新增可匯入模組。根目錄只保留 `main.py` 作為薄入口。
- 固定且非敏感設定放在 YAML；敏感設定放在 `.env`，由 `python-dotenv` 載入。
- 新功能優先補對應測試，測試放在 `tests/`。

## Domain Notes

- 歷史每日最高溫與最低溫資料優先使用 Open-Meteo。
- 地點應盡量用 latitude / longitude 表示。
- Polymarket 天氣市場可能使用 Weather Underground 作為結算資料，但本專案預期
  使用 Open-Meteo。這個資料源差異應視為建模與回測風險，不是單純實作細節。
- 若 TimesFM upstream 仍有 MPS 推論問題，加入模型相關程式前需先文件化選定的
  workaround。

## Security Notes

- Agent 不可以讀取、列印、複製、修改或要求使用者貼上私鑰、助記詞、錢包 seed、
  API secret、`.env` 內的敏感值，或任何可直接控制資產的憑證。
- Agent 不可以在未經使用者明確同意的情況下執行任何交易、下單、撤單、簽名、
  轉帳、授權、approve、deposit、withdraw，或其他會影響資產、部位、資金或
  wallet 狀態的操作。
- 若任務需要 Polymarket、wallet 或交易相關命令，必須先說明將執行的命令、可能
  影響與是否會觸及真實資產，並等待使用者明確同意。
- 預設只能進行唯讀研究、文件整理、資料抓取、回測、模擬交易與 dry-run。任何從
  模擬切換到真實交易的步驟都必須再次取得明確同意。
- 不要把私鑰、token、交易簽名、wallet address 對應身份、或其他敏感資訊寫入
  repo、log、測試 fixture、文件、commit message 或錯誤輸出。
- `configs/configs.yaml` 與 `.env` 都視為本機設定檔，不應提交；只提交 example 檔。

## Validation

文件變更只需檢查受影響的 Markdown。

Python 變更先跑最小相關命令：

```bash
uv run python main.py
uv run python -m timesfm_meteo
uv run --extra dev pytest
```

之後加入測試時，請在本節更新明確的 test、lint 與 typecheck 指令。
