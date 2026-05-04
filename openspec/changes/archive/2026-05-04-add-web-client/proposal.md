## Why

MVP pipeline 與 REST API server 已可用，但目前使用者仍需要透過 CLI / curl / JSON 觀察資料。為了讓人類使用者能直觀看到歷史氣溫、過往預測、預測區間與評估指標，需要一個 Web Dashboard 作為主要操作介面。

這個 Web client 是中期「數據可視化」的第一版：它不處理 production 部署與每日排程，專注在把現有 API 轉成可操作、可比較、可視覺分析的單頁 Dashboard。

## What Changes

- 新增 `web/` React + Vite + TypeScript 專案。
- 使用 ECharts 建立主圖：
  - X 軸為 `target_date`。
  - 顯示實際最高 / 最低溫折線。
  - 顯示過往 forecast p50 預測資料。
  - 顯示 p10–p90 預測區間。
  - `horizon_step=any` 預設顯示所有過往預測點 / 淡線。
  - 提供「聚合平均」切換：同一 target_date 的符合篩選 forecast p50 取平均，原始線低亮、平均線最高亮。
- 使用 TanStack Query 管理 API 讀取、mutation、job polling、refetch。
- 提供單頁 Dashboard：
  - filter：latitude / longitude（預設 Taipei）、date range、horizon_step、聚合平均開關。
  - chart：actual vs forecast 主圖。
  - evaluation summary cards + horizon_step breakdown table。
  - controls：Fetch History / Run Forecast 按鈕，觸發 job 後自動 polling，done 後自動 refetch chart / evaluation。
- Vite dev proxy：前端呼叫 `/api/*`，proxy 到 FastAPI server，避免 CORS。
- API key 由 Vite env 提供（local-only）：`VITE_TIMESFM_API_KEY`。
- 文件：
  - `web/README.md`：安裝、啟動、`.env.local`、Vite proxy、測試、常見問題。
  - `docs/usage.md`：補 Web Dashboard 使用段落。
  - `AGENTS.md`：補 Web 開發與測試指令。
- 測試：
  - Vitest 覆蓋資料轉換、forecast 聚合平均、API client URL/header、job polling 行為。
  - `npm run build` 作為 build smoke test。

## Capabilities

### New Capabilities
- `web-dashboard`: React + Vite Web Dashboard，用視覺化方式呈現歷史氣溫、過往預測、聚合平均與評估指標，並支援手動觸發 API jobs。

### Modified Capabilities
無。`api-server`、`cli-client` 與既有 pipeline 行為不變；本 change 僅新增 Web client，透過既有 API 操作。

## Impact

- **新增前端專案**：`web/`，包含 React、Vite、TypeScript、ECharts、TanStack Query、Vitest。
- **新增 Node 工具鏈**：`web/package.json`、`web/package-lock.json`、`web/vite.config.ts` 等。
- **文件更新**：`web/README.md`、`docs/usage.md`、`AGENTS.md`。
- **不改 Python API 行為**：Web client 使用既有 endpoints；若需要 CORS 或 production static serve，留到後續 Docker / deployment change。
- **安全提醒**：`VITE_TIMESFM_API_KEY` 會進入前端 runtime，只適用 localhost / private network，不可公開部署。
