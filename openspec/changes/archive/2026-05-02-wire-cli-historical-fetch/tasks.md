## 1. CLI argument parsing

- [x] 1.1 在 `src/timesfm_meteo/cli.py` 建立 `argparse.ArgumentParser` 與 `fetch-history` 子命令，含 `--latitude`、`--longitude`、`--end-date` 與互斥的 `--years` / `--start-date`
- [x] 1.2 解析後用 `Location(latitude=..., longitude=...)` 觸發 Pydantic 驗證；捕捉 `ValidationError` 轉成 stderr 訊息與 exit code 2
- [x] 1.3 解析 `--years` / `--start-date` / `--end-date` 為 `datetime.date`；缺漏或衝突時走 argparse 內建錯誤路徑

## 2. DB 連線與 orchestration

- [x] 2.1 從 `load_settings()` 取得 `Settings`；若 `settings.postgres.dsn` 為空字串，stderr 印「DATABASE_URL is not configured. Set it in .env.」並 exit code 2
- [x] 2.2 用 `psycopg.connect(dsn)` 在 `with` 區塊建立連線；連線失敗時捕捉 `psycopg.OperationalError`，stderr 印錯誤摘要並 exit code 2
- [x] 2.3 連線成功後呼叫 `db.repository.ensure_schema(conn)`
- [x] 2.4 解出 `start_date` / `end_date`（與 `fetch_daily_temperatures` 同樣規則：`end_date` 預設為昨天，`start_date` 由 `--years` 或 `--start-date` 推導）
- [x] 2.5 呼叫 `pipeline.historical.get_temperatures(location, start_date, end_date, conn, settings.open_meteo)` 取回完整序列

## 3. 結果輸出

- [x] 3.1 對 `get_temperatures` 回傳的 list，依 date 升冪逐筆 print 至 stdout：`YYYY-MM-DD\t<max>\t<min>`
- [x] 3.2 在 stderr 印一行摘要 `cached=N fetched=M total=K`；計算方式：先記錄 `get_temperatures` 呼叫前 DB 已有筆數，與最終 total 相減推 fetched
- [x] 3.3 為避免重複查 DB 推算 cached/fetched，將 `get_temperatures` 重構為回傳 `(rows, cached_count, fetched_count)` 或在 `cli.py` 端先呼叫 `fetch_temperatures` 取得 cached_count，再呼叫 `get_temperatures` 取最終結果

## 4. 測試

- [x] 4.1 新增 `tests/test_cli.py`，使用 `monkeypatch` 設定 `argv` 與環境變數
- [x] 4.2 測試：`--years` 與 `--start-date` 同時給出時 argparse 報錯（exit code 2）
- [x] 4.3 測試：`--latitude 95.0` 觸發 `ValidationError`，stderr 含「latitude」字樣，exit code 2
- [x] 4.4 測試：`DATABASE_URL` 未設定時，stderr 含「DATABASE_URL is not configured」，exit code 2，且不發出任何 HTTP / DB 呼叫（用 `monkeypatch` 替換 `psycopg.connect` 與 `httpx.Client` 偵測未被呼叫）
- [ ] 4.5 （選用）端到端 happy path 測試：mock `httpx.Client` 與 `psycopg.connect`，驗證 stdout 與 stderr 摘要格式 — 跳過：design.md 已說明整合層測試不在本 change 範圍

## 5. 文件

- [x] 5.1 在 `AGENTS.md` 的 Development 區段補上 `uv run timesfm-meteo fetch-history --latitude ... --longitude ... --years 2` 範例
- [x] 5.2 跑 `uv run --extra dev pytest`，確認 28+ 個既有測試 + 新增 CLI 測試全綠（32/32 passed）
