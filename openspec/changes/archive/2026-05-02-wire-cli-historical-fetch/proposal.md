## Why

`db/repository.py` 與 `pipeline/historical.py` 已經實作 Postgres 快取與 cache-aware fetch，但 `cli.py` 目前只是 `print("timesfm-meteo")`，沒有任何呼叫者。使用者無法透過任何入口實際觸發「先查 DB、再補 API」的流程，整個快取層形同未連通。本次變更把 CLI 串到既有的 `get_temperatures`，讓 MVP roadmap 第 1、2 步真正可被使用。

## What Changes

- 新增 CLI `fetch-history` 子命令，接受 `--latitude`、`--longitude`、`--years`（或 `--start-date`）、`--end-date` 參數。
- CLI 從 `Settings.postgres.dsn` 建立 `psycopg.Connection`，呼叫 `ensure_schema` 確保表存在，再呼叫 `pipeline.historical.get_temperatures`。
- CLI 將回傳結果以可讀格式（每行一筆 `date  max  min`）輸出到 stdout，並在 stderr 顯示「自 DB 命中 N 筆 / 自 API 取得 M 筆」摘要。
- 若 `DATABASE_URL` 未設定或連線失敗，CLI 必須以非零 exit code 結束並輸出明確錯誤訊息，不可靜默降級為純 API 呼叫。

## Capabilities

### New Capabilities

- `historical-fetch`: 從指定經緯度與時間範圍取得每日歷史氣溫的端到端流程，包含 CLI 入口、Postgres 快取查詢、缺漏日期回填到 Open-Meteo、結果回寫 DB，並回傳完整時間序列。

### Modified Capabilities

（無，這是首個 spec）

## Impact

- `src/timesfm_meteo/cli.py`：實作 argparse 子命令與 orchestration。
- `tests/test_cli.py`（新檔）：CLI 行為測試，含 DB 連線失敗的錯誤路徑。
- 不新增第三方依賴；argparse 為標準函式庫即可。
- `AGENTS.md` 的 Development 區段範例命令可順帶補充新的 CLI 用法（如有需要）。
