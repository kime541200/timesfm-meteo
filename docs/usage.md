# 使用說明

本文件說明如何在本機啟動 `timesfm-meteo` MVP（歷史氣溫抓取、TimesFM 預測、預測評估），並提供端到端的測試流程。

## 1. 環境需求

- macOS 或 Linux
- Python 3.12
- [`uv`](https://docs.astral.sh/uv/)（套件與虛擬環境管理）
- Docker / Docker Compose（用於本機 Postgres）
- 約 2–4 GB 磁碟空間給 TimesFM checkpoint（首次預測時下載）
- 預測階段建議有 CUDA GPU；CPU 也可跑，但載入與推論較慢。Apple Silicon（MPS）尚未驗證

## 2. 安裝

```bash
git clone <this-repo>
cd timesfm-meteo

# 基本依賴（fetch-history、evaluate、CLI client 已可用）
uv sync

# 預測指令需要額外安裝 forecast extra（含 timesfm + torch）
uv sync --extra forecast

# API server 需要 api extra
uv sync --extra api

# 開發依賴（pytest）
uv sync --extra dev
```

## 3. 啟動 Postgres

`fetch-history`、`forecast`、`evaluate` 都會把資料寫進 Postgres，因此必須先啟動資料庫。

```bash
# 建立 Postgres 設定（含預設資料庫名 timesfm_meteo）
cp .env.example.postgres .env.postgres
# 編輯 .env.postgres 填入 POSTGRES_USER / POSTGRES_PASSWORD / pgAdmin 帳密

# 啟動 Postgres + pgAdmin
docker compose -f docker-compose.postgres.yml up -d
```

服務埠：

- Postgres：`localhost:5432`
- pgAdmin：`http://localhost:5433`

關閉服務：

```bash
docker compose -f docker-compose.postgres.yml down
# 連同資料一起刪除（謹慎使用）：
# docker compose -f docker-compose.postgres.yml down -v
```

## 4. 設定應用程式

```bash
# 應用程式環境變數
cp .env.example .env
# 編輯 .env：
#   DATABASE_URL=postgresql://<user>:<password>@localhost:5432/timesfm_meteo
#   HF_HOME=（留空使用 ~/.cache/huggingface；想換位置就填絕對路徑）

# 非敏感設定
cp configs/configs.example.yaml configs/configs.yaml
```

`configs/configs.yaml` 可調整：

- `open-meteo.*`：API URL、想抓的每日變數、timeout
- `timesfm.model-id`：預設 `google/timesfm-2.5-200m-pytorch`
- `timesfm.max-context` / `max-horizon`：模型 compile 時的最大長度（影響 GPU 記憶體）

頂層 `history-years`（預設 2）、`forecast-days`（預設 3）若想改也可加進 YAML，或直接用 CLI flag 覆寫。

## 5. CLI 指令

統一入口：`uv run timesfm-meteo <subcommand>`。標準輸出（stdout）為 JSON；摘要與錯誤訊息走 stderr，因此可以安全地用管線餵給其他工具。

### 5.1 `fetch-history` — 抓歷史氣溫並快取進 Postgres

```bash
# 用「最近 N 年」抓
uv run timesfm-meteo fetch-history \
  --latitude 25.05 --longitude 121.57 \
  --years 2

# 指定起點日期（end-date 預設為今天）
uv run timesfm-meteo fetch-history \
  --latitude 25.05 --longitude 121.57 \
  --start-date 2024-01-01 --end-date 2024-12-31
```

行為：

- 先查 `daily_temperatures`，缺漏的日期才打 Open-Meteo API，回來後 upsert 進 DB。
- stdout 為 JSON，包含 `cached_count`、`fetched_count` 與 `rows`。
- 重跑相同參數時通常 `fetched_count=0`，不會重複打外部 API。

### 5.2 `forecast` — 用 TimesFM 預測（自動寫入 `forecasts` 表）

```bash
# Live forecast：以今天為起點，預測未來 3 天
uv run --extra forecast timesfm-meteo forecast \
  --latitude 25.05 --longitude 121.57 \
  --horizon 3

# Backtest：把 start-date 設為過去日期，僅使用該日之前的歷史
uv run --extra forecast timesfm-meteo forecast \
  --latitude 25.05 --longitude 121.57 \
  --horizon 3 \
  --start-date 2024-06-01 \
  --history-years 2
```

行為：

- 缺漏的歷史會自動經 `fetch-history` pipeline 補齊。
- 第一次執行會下載 TimesFM checkpoint（受 `HF_HOME` 影響），之後使用快取。
- 每天輸出 `max` / `min` 的 p10、p50、p90，並 upsert 進 `forecasts`，主鍵為 `(latitude, longitude, start_date, target_date)`。
- 重跑相同 `start_date` 會覆寫該批預測，方便迭代調整。

stdout 範例（節錄）：

```json
{
  "model": "google/timesfm-2.5-200m-pytorch",
  "history_days": 730,
  "horizon": 3,
  "forecasts": [
    {
      "date": "2026-05-04",
      "max": {"p10": 27.1, "p50": 28.4, "p90": 29.7},
      "min": {"p10": 22.3, "p50": 23.1, "p90": 24.0}
    }
  ]
}
```

### 5.3 `evaluate` — 對比預測與實際觀測

```bash
# 評估某段期間內所有 start_date 的預測
uv run timesfm-meteo evaluate \
  --latitude 25.05 --longitude 121.57 \
  --start-date-from 2024-06-01 \
  --start-date-to 2024-06-30

# 只看特定 horizon step（例如預測「往後第 1 天」的命中率）
uv run timesfm-meteo evaluate \
  --latitude 25.05 --longitude 121.57 \
  --start-date-from 2024-06-01 \
  --start-date-to 2024-06-30 \
  --horizon-step 1
```

行為：

- 從 `forecasts` 抓符合條件的列。
- 對應 `target_date` 若還沒 cache，會自動透過 `fetch-history` pipeline 補齊；未來日期（Open-Meteo 還沒提供）會被歸為 `pending`。
- 依 `horizon_step = target_date - start_date` 分組，加上 `overall` 總計。
- 每組分別計算 `max` / `min` 的 `mae_p50`、`interval_coverage`（[p10, p90] 涵蓋率）、`mean_interval_width`。

## 6. 端到端測試流程

```bash
# 0. 啟動 DB（若還沒啟動）
docker compose -f docker-compose.postgres.yml up -d

# 1. 抓 2 年歷史進 cache（首次需要打 API）
uv run timesfm-meteo fetch-history \
  --latitude 25.05 --longitude 121.57 --years 2

# 2. 用過去某個日期跑 backtest 預測（會自動寫入 forecasts 表）
uv run --extra forecast timesfm-meteo forecast \
  --latitude 25.05 --longitude 121.57 \
  --horizon 3 --start-date 2024-06-01

# 3. 立刻評估 backtest 結果（actuals 已在 cache 中）
uv run timesfm-meteo evaluate \
  --latitude 25.05 --longitude 121.57 \
  --start-date-from 2024-06-01 --start-date-to 2024-06-01
```

預期 stderr 輸出類似：

```
evaluated=3 pending=0 horizon_step=any
```

stdout 為 `EvaluationReport` JSON，可直接 pipe 給 `jq`、`python -m json.tool` 觀察。

## 7. API Server（選用）

API server 將 pipeline 包裝成 HTTP endpoints，供 Web Dashboard 或 AI Agent 遠端呼叫。

```bash
# 安裝 api extra（需要同時安裝 forecast 才能跑預測）
uv sync --extra api --extra forecast

# 在 .env 中設定 API_KEY（參見 .env.example）

# 啟動
uv run uvicorn timesfm_meteo.api.app:app --host 0.0.0.0 --port 8000
```

詳細 endpoint 說明請見 [docs/api-server.md](api-server.md)。

## 8. CLI Client（選用）

對 API server 發 HTTP request 的輕量 CLI，適合 AI Agent 使用：

```bash
# 在 .env 中設定 TIMESFM_API_URL / TIMESFM_API_KEY
uv run timesfm-meteo-client forecast run \
  --latitude 25.05 --longitude 121.57 --horizon 3
```

詳細用法請見 [docs/cli-client.md](cli-client.md)。

## 9. 跑測試

```bash
uv run --extra dev pytest
# 含 API 測試
uv run --extra dev --extra api pytest
# 含預測相關測試（需 forecast extra）
uv run --extra dev --extra forecast pytest
```

DB 整合測試會在 `DATABASE_URL` 不存在時自動 skip。

## 10. 故障排除

- **`could not connect to server`**：確認 `docker compose -f docker-compose.postgres.yml ps` 服務有起來，且 `.env` 中 `DATABASE_URL` 帳密／資料庫名與 `.env.postgres` 一致。
- **第一次 `forecast` 卡很久**：首次會下載 TimesFM checkpoint（數百 MB）；可由 `HF_HOME` 觀察下載位置。
- **`No module named 'timesfm'`**：尚未安裝 forecast extra，執行 `uv sync --extra forecast`。
- **`evaluate` 全部 pending**：對應 `target_date` 還沒有觀測值（多半是未來日期）；等 Open-Meteo 補上後重跑即可。
- **想換地點**：直接更換 `--latitude` / `--longitude`；DB 主鍵已包含座標，多地點可共存。

## 9. 進階參考

- 設計文件：`docs/roadmap.md`、`docs/quantile-forecasting.md`、`docs/timesfm-engine.md`
- 規格（OpenSpec）：`openspec/specs/historical-fetch/`、`openspec/specs/temperature-forecasting/`、`openspec/specs/forecast-evaluation/`
- 程式入口：`src/timesfm_meteo/cli.py`
