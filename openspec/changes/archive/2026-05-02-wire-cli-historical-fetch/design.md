## Context

`pipeline.historical.get_temperatures` 已實作 cache-aware 流程：先 `fetch_temperatures` 從 Postgres 撈，計算缺漏日期集合，向 Open-Meteo 補單一連續區間，再 `upsert_temperatures` 回寫。但 entry point `cli.py` 是空殼 `print("timesfm-meteo")`，且專案目前只有 `main()` 一個無參數函式被 `pyproject.toml` 註冊為 `timesfm-meteo` script。

相關既有元件：
- `Settings.postgres.dsn`：已從 `DATABASE_URL` env var 讀入。
- `Location` Pydantic model：lat ∈ [-90, 90]、lon ∈ [-180, 180] 已內建驗證。
- `psycopg.Connection`：v3，支援 context manager。
- 測試慣例：`tests/conftest.py` 載入 `.env`，DB 測試在缺 DSN 時 skip。

## Goals / Non-Goals

**Goals：**
- 提供 `timesfm-meteo fetch-history` 子命令，串起 DB 快取 + API 補抓的完整路徑。
- 連線、建表、查詢、回寫的失敗情境都有明確 exit code 與 stderr 訊息。
- CLI 行為可被單元測試驗證（不需真連 DB 也能測 argument parsing 與錯誤路徑）。

**Non-Goals：**
- 不做 forecasting（TimesFM）整合，那是後續 change。
- 不輸出 JSON、CSV 或多種格式；MVP 只給單一人類可讀格式。
- 不引入額外 CLI 框架（Click / Typer）；標準 `argparse` 已足夠。
- 不做 retry / backoff；單次失敗即結束。

## Decisions

### 1. CLI 使用 argparse + 子命令

選 `argparse` 而非 `click` / `typer`，理由：
- 標準函式庫，零新依賴。
- MVP 只有一個子命令，未來新增 `forecast`、`evaluate` 時 argparse 子命令模式可直接擴展。
- `pyproject.toml` 已有 `timesfm-meteo` script 對應 `timesfm_meteo.cli:main`，沿用即可。

### 2. 日期範圍由 `--years` 或 `--start-date` 二擇一

對應 `fetch_daily_temperatures` 既有介面（`history_years` 或顯式 `start_date`）。`--end-date` 預設為昨天（與 fetcher 一致，避免今日資料未完成）。互斥檢查由 argparse `add_mutually_exclusive_group(required=True)` 處理。

### 3. DB 連線：單次 short-lived connection

CLI 是 one-shot 程序，建立一個 `psycopg.connect(dsn)` 在 `with` 區塊內完成所有操作，結束時自動關閉。不引入連線池。

### 4. 缺 `DATABASE_URL` 必須失敗，不 fallback 到純 API

若 `Settings.postgres.dsn` 為空字串 → 在連線前直接退出 exit code 2，stderr 印 `DATABASE_URL is not configured. Set it in .env.` 理由：roadmap 明確要求 DB 是 MVP 第二步的 hard requirement，靜默 fallback 會讓使用者誤以為快取已生效。

### 5. 輸出格式

stdout：每行 `YYYY-MM-DD\t<max>\t<min>`，方便 pipe 到 `awk` / `column`。
stderr：摘要行 `cached=N fetched=M total=K`，讓使用者一眼看到快取命中率。

替代方案：JSON。捨棄理由：MVP 階段 stdout 給人看就夠；要做機器可讀時再加 `--format json`。

### 6. 測試策略

- `test_cli.py` 用 `pytest.CaptureFixture` + `monkeypatch` 注入 `argv`，主要測：
  - argument parsing（`--years` / `--start-date` 互斥、lat/lon 範圍）。
  - 缺 DSN 時的錯誤路徑（不需要真 DB）。
- 整合層的「真連 DB + mock API」測試暫不在本 change 範圍；若要做需另設 fixture 抽換 `psycopg.connect` 與 `httpx.Client`。

## Risks / Trade-offs

- **Risk**：argparse 對 lat/lon 浮點驗證不如 Pydantic 強 → 直接讓 `Location()` 在解析後驗證，違反時 catch `ValidationError` 並轉成清楚的 stderr 訊息與 exit code 2。
- **Risk**：`get_temperatures` 在 missing 範圍非連續時會多抓資料（min ~ max 的整段）→ 已知取捨；upsert 冪等所以結果正確，僅是 API quota 略浪費。MVP 不處理。
- **Trade-off**：不支援 `--format json` → 若下游工具需要程式化解析，得自行 parse tab-separated 行。可接受，後續 change 再加。
