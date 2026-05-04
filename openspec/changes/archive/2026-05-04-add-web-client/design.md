## Context

MVP pipeline 與 API server 已完成：後端提供 `GET /temperatures`、`GET /forecasts`、`GET /evaluate`，以及 async job endpoints `POST /fetch-history`、`POST /forecast`、`GET /jobs/{id}`。目前資料可透過 CLI / curl 取得，但人類使用者難以一眼比較「實際氣溫」與「過往 TimesFM 預測」的長期關係。

本 change 新增 `web/` 前端專案，作為中期數據可視化的第一版。它使用既有 API，不修改 Python API 行為；production serve / Docker 整合留給後續 change。

這次 `/grill-me` 已收斂的設計決策：

- 範圍：Dashboard + 手動觸發（Fetch History / Run Forecast）。
- 主圖：Calendar view，X 軸為 `target_date`。
- 預測呈現：預設 `horizon_step=any`，顯示所有過往 forecast 點 / 淡線；可切換聚合平均線。
- 聚合平均：同一 `target_date` 的符合目前 filter forecast p50 平均，原始線低亮，平均線最高亮。
- 圖表套件：ECharts。
- 資料管理：TanStack Query。
- 設定：local-only Vite env（`VITE_TIMESFM_API_KEY`），文件明確警告不可公開部署。
- 頁面：單頁 Dashboard。
- 地點：預設 Taipei，可手動輸入 latitude / longitude。
- 手動操作：觸發 job + polling + done 後 refetch。
- 自動刷新：只在 job running 時 polling；平常不持續刷新。
- 評估：summary cards + horizon_step breakdown table。
- Responsive：desktop-first，但窄螢幕上下堆疊。
- 測試：Vitest 覆蓋資料轉換、聚合、API client、job polling；不做 Playwright。

UI/UX Pro Max 建議採用 data-dense dashboard 風格：藍色系資料視覺（primary `#1E40AF`、secondary `#3B82F6`）、amber highlights（`#F59E0B`）、淺色背景 `#F8FAFC`、技術分析感字體（Fira Sans / Fira Code），並遵守 WCAG contrast、focus states、44px touch targets、無 emoji icon、圖表提供表格替代等規則。

## Goals / Non-Goals

**Goals:**

- 建立 `web/` React + Vite + TypeScript 前端專案。
- 用 ECharts 顯示 actual vs forecast 的主圖，支援過往 forecast、p10–p90 interval、horizon_step filter、聚合平均線。
- 用 TanStack Query 管理 API calls、mutation、job polling、完成後 refetch。
- 提供單頁 Dashboard：filters、chart、evaluation cards/table、manual job controls。
- 預設 Taipei 座標，但允許手動修改 latitude / longitude。
- 使用 Vite dev proxy：前端呼叫 `/api/*`，proxy 到 FastAPI server。
- 撰寫 `web/README.md`、更新 `docs/usage.md` 與 `AGENTS.md`，清楚說明如何啟動 API + Web。
- 以 Vitest 測試資料對齊、forecast 聚合、API client、job polling。

**Non-Goals:**

- 不實作 production static file serving（留給 Docker / deployment change）。
- 不加入每日排程器或自動更新設定（中期 4）。
- 不實作 location alias 或地點管理（Additional features）。
- 不做完整 job history / retry / cancel UI。
- 不做多頁 routing；第一版為單頁 Dashboard。
- 不做公開部署安全模型；`VITE_TIMESFM_API_KEY` 只適用 localhost/private network。
- 不加入 Playwright e2e 第一版。

## Decisions

### Decision 1: React + Vite + TypeScript in `web/`

**Choice:** 在 repo 根目錄新增 `web/`，使用 React + Vite + TypeScript。

**Why:** Dashboard 不需要 SSR；Vite dev server 啟動快，與現有 Python src-layout 分離清楚。TypeScript 對 API response 與 chart transform 有高價值，能降低日期對齊、欄位命名錯誤。

**Alternatives considered:**
- Next.js：SSR / app router 對本地 Dashboard 過重。
- Streamlit / Plotly Dash：開發快，但 UI 客製化與長期產品化較弱。
- 純 HTML：無法乾淨管理 async jobs / chart state。

### Decision 2: ECharts as chart engine

**Choice:** 使用 `echarts` + `echarts-for-react`。

**Why:** 需求包含折線、散點、區間帶、低亮 / 高亮、聚合平均線、tooltip、legend、dataZoom。ECharts 的 option 模型比 Recharts 更適合複雜互動和大量資料點。

**Alternatives considered:**
- Recharts：上手快，但複雜 opacity / scatter + line + area 混合與聚合 highlighting 較不彈性。
- Chart.js：可行，但 React 狀態整合與複雜互動設定不如 ECharts 直覺。

### Decision 3: TanStack Query for API state

**Choice:** 使用 `@tanstack/react-query`。

**Why:** Dashboard 有多個 query（temperatures、forecasts、evaluate）與 mutations（fetch-history、forecast），還有 job polling 與完成後 invalidate/refetch。TanStack Query 可標準化 loading/error/cache/polling，避免 `useEffect + fetch` 狀態散落。

### Decision 4: Local-only Vite env auth

**Choice:** `web/.env.local` 設定：

```env
VITE_TIMESFM_API_KEY=<same as API_KEY>
```

前端 API client 對 `/api/*` request 加上 `Authorization: Bearer <key>`。

**Why:** 第一版是 localhost/private network Dashboard。若引入 server-side session、cookie、CSRF，會把 scope 擴到 auth product。文件必須明確標示：Vite env 會暴露在 browser runtime，不可公開部署。

### Decision 5: Vite dev proxy with `/api/*`

**Choice:** 前端呼叫 `/api/temperatures`、`/api/forecasts` 等，Vite proxy rewrite 到 `http://localhost:8000/temperatures`、`/forecasts`。

**Why:** 避免 CORS；也為未來 production reverse proxy 保留一致路徑。API server 不需要在本 change 增加 CORS middleware。

### Decision 6: Single-page dashboard layout

**Choice:** 一頁內包含：

1. Header：產品名、API connection status。
2. Filters：location、date range、horizon_step、show aggregate toggle。
3. Main chart card：actual vs forecast。
4. Evaluation cards：overall metrics。
5. Breakdown table：by horizon_step metrics。
6. Action panel：Fetch History / Run Forecast + current job status。

**Why:** 第一版不需要 routing；資料關係都圍繞同一組 filter。單頁能最快驗證可用性。

### Decision 7: Chart data model derived in pure utilities

**Choice:** 將 API response 轉 chart series 的邏輯放在 pure functions，例如：

- `mergeTemperatureAndForecasts(temperatures, forecasts, filters)`
- `filterForecastsByHorizonStep(forecasts, horizonStep)`
- `aggregateForecastsByTargetDate(forecasts)`
- `buildChartOption(chartData, uiState)`

**Why:** 最容易出錯的是資料對齊與聚合，而非 UI component。Pure utilities 可以用 Vitest 精準測試。

### Decision 8: `horizon_step=any` defaults to raw forecast distribution

**Choice:** 預設顯示所有符合 date range 的 forecast 點 / 淡線；使用者可切換聚合平均。

**Why:** 使用者想看長期預測與實際值相關性，原始分布比單一平均更能看出不同預測起點的變異。聚合平均作為輔助視角，不取代原始資料。

### Decision 9: UI visual system

**Choice:** Data-dense dashboard：

- Background：`#F8FAFC`
- Text：深藍 / slate，確保 4.5:1 對比
- Actual max/min：高對比實線
- Forecast p50：藍色系
- Aggregate forecast：amber highlight `#F59E0B`
- Raw forecast when aggregate enabled：降低 opacity
- Fonts：Fira Sans（body）+ Fira Code（metrics / labels）

**Why:** 資料分析 dashboard 需要清晰、密度高、低裝飾。Amber 用於聚合平均與重要 CTA，符合 UI/UX Pro Max 對 data dashboard 的建議。

### Decision 10: Testing scope

**Choice:** Vitest + React Testing Library（只在必要 component 上）+ build smoke。

**What to test:**

- Forecast filtering by horizon_step。
- Same target_date aggregation average。
- Temperature + forecast merge。
- API client adds Authorization header and `/api/*` path。
- Job polling stops on `done` / `failed` / timeout。

**Non-goal:** Playwright browser e2e 留到前端互動更複雜後再補。

## Risks / Trade-offs

- **[VITE_TIMESFM_API_KEY 暴露於瀏覽器]** → 文件明確標示 local-only / private network，不可公開部署；正式部署安全模型留到 Docker/deployment change。
- **[ECharts option 複雜]** → 將 option builder 拆成 pure function 並以 Vitest 測資料系列與 highlighting 邏輯。
- **[any + aggregate 容易讓使用者誤解 horizon_step]** → UI 明確標示「Any = all forecast origins」；aggregate toggle 說明為「same target_date mean across visible forecasts」。
- **[圖表資訊太多]** → 預設透過 opacity、legend、tooltip 控制視覺層級；提供 horizon_step filter 讓使用者切乾淨視圖。
- **[API server 未啟動時體驗差]** → Header 顯示 connection/error state；README 清楚列出先啟動 FastAPI 再啟動 Vite。
- **[小螢幕圖表難讀]** → 基本 responsive：filters/cards/table 上下堆疊；主要使用場景仍以 desktop dashboard 為主。

## Migration Plan

新增前端專案，不影響既有 Python CLI / API。

開發啟動：

1. 啟動 Postgres。
2. 啟動 API server：`uv run --extra api --extra forecast uvicorn timesfm_meteo.api.app:app --port 8000`。
3. 建立 `web/.env.local`，設定 `VITE_TIMESFM_API_KEY=<API_KEY>`。
4. 進入 `web/`，`npm install`，`npm run dev`。
5. 瀏覽 Vite URL（預設 `http://localhost:5173`）。

Rollback：刪除 `web/` 與相關文件更新即可；不涉及 DB migration。

## Open Questions

無。Production static serve、正式 auth model、Docker compose、每日排程與 location alias 均已明確列為後續 change。
