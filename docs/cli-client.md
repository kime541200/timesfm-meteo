# CLI Client (`timesfm-meteo-client`)

`timesfm-meteo-client` 是對應 API server 的輕量 CLI，適合讓 **AI Agent** 透過腳本呼叫遠端 API，也可供人工查詢使用。它只依賴 `httpx` 與 `pydantic`，不需要安裝 Postgres driver 或 TimesFM。

## 安裝

base install 即可使用，不需要額外 extra：

```bash
uv sync
# 確認 entry point 可用
uv run timesfm-meteo-client --help
```

## 設定

在 `.env` 或環境變數中設定：

```env
TIMESFM_API_URL=http://localhost:8000
TIMESFM_API_KEY=<與 server 端 API_KEY 相同的值>
```

## 子命令一覽

| 子命令 | 說明 |
|--------|------|
| `temperatures get` | 查詢歷史氣溫 |
| `forecasts list` | 列出已存的預測 |
| `forecast run` | 觸發預測 job（預設等待完成） |
| `fetch-history run` | 觸發歷史抓取 job（預設等待完成） |
| `evaluate get` | 取得評估報告 |
| `jobs get <id>` | 查詢 job 狀態 |

## 指令範例

```bash
# 查詢歷史氣溫
timesfm-meteo-client temperatures get \
  --latitude 25.05 --longitude 121.57 \
  --start-date 2024-06-01 --end-date 2024-06-07

# 列出已存的預測（某地點、某段 start_date）
timesfm-meteo-client forecasts list \
  --latitude 25.05 --longitude 121.57 \
  --start-date-from 2024-06-01 --start-date-to 2024-06-30

# 觸發預測並等待完成（預設行為）
timesfm-meteo-client forecast run \
  --latitude 25.05 --longitude 121.57 \
  --horizon 3

# 觸發後立即回傳 job_id，不等待
timesfm-meteo-client forecast run \
  --latitude 25.05 --longitude 121.57 \
  --horizon 3 --no-wait

# 觸發預測，等待最長 60 秒
timesfm-meteo-client forecast run \
  --latitude 25.05 --longitude 121.57 \
  --horizon 3 --timeout 60

# Backtest（指定過去日期）
timesfm-meteo-client forecast run \
  --latitude 25.05 --longitude 121.57 \
  --start-date 2024-06-01 --horizon 3

# 觸發歷史抓取
timesfm-meteo-client fetch-history run \
  --latitude 25.05 --longitude 121.57 \
  --years 2

# 查詢 job 狀態
timesfm-meteo-client jobs get <job_id>

# 取得評估報告
timesfm-meteo-client evaluate get \
  --latitude 25.05 --longitude 121.57 \
  --start-date-from 2024-06-01 --start-date-to 2024-06-30

# 只看 horizon_step=1 的評估
timesfm-meteo-client evaluate get \
  --latitude 25.05 --longitude 121.57 \
  --start-date-from 2024-06-01 --start-date-to 2024-06-30 \
  --horizon-step 1
```

## 等待行為（`forecast run` / `fetch-history run`）

預設：觸發 job 後，CLI 輪詢 `GET /jobs/{id}` 直到 `done` 或 `failed`，再印出最終結果並返回。

- 成功：exit code `0`，stdout 為 job JSON（含 `result`）
- 失敗：exit code `1`，stderr 顯示 error message
- 逾時：exit code `1`，stderr 顯示逾時訊息，server 端 job 繼續執行

`--no-wait`：觸發後立即回傳 `{ job_id, status: "pending" }`，exit code `0`。

## AI Agent 使用情境

AI Agent（例如 Claude Code）可以：

1. 用 `forecast run` 一行觸發預測並取得結果（預設同步等待）。
2. 用 `--no-wait` 觸發後繼續做其他事，再用 `jobs get` 輪詢。
3. 用 `evaluate get` 讀取評估報告，判斷預測品質。
4. 整個 client 不需要 Python 模型或 DB 設定，只要 `TIMESFM_API_URL` 和 `TIMESFM_API_KEY`。

範例（Agent 使用場景）：
```bash
# 觸發 backtest 並等結果
result=$(timesfm-meteo-client forecast run \
  --latitude 25.05 --longitude 121.57 \
  --start-date 2024-06-01 --horizon 3)
echo $result | python -m json.tool

# 評估同一段時間
timesfm-meteo-client evaluate get \
  --latitude 25.05 --longitude 121.57 \
  --start-date-from 2024-06-01 --start-date-to 2024-06-01
```

## 錯誤處理

| 情況 | 行為 |
|------|------|
| `TIMESFM_API_URL` 未設定 | 印出提示，exit 1 |
| `TIMESFM_API_KEY` 未設定 | 印出提示，exit 1 |
| HTTP 401 | 印出「API key invalid」，exit 1 |
| HTTP 404（jobs get） | 印出「not found」，exit 1 |
| 網路錯誤 | 印出 URL + 錯誤原因，exit 1 |
| Job 失敗 | 印出 server error message，exit 1 |

所有正常輸出走 **stdout**（JSON）；錯誤訊息走 **stderr**，便於腳本捕獲。
