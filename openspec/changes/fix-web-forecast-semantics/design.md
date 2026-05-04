## Context

TimesFM 是基於過去資料預測未來的模型。後端 `POST /forecast` 的語意是：`start_date` 代表第一個 forecast target date，模型 input 會使用 `start_date` 之前的歷史資料。這個語意在 CLI / API 內部是合理的。

Web Dashboard 第一版將同一組 `startDate/endDate` 同時用於：

1. 歷史 actual chart range。
2. forecasts 查詢 range。
3. evaluation range。
4. `POST /forecast.start_date`。

這造成使用者誤解：UI 上的 Start date / End date 看起來像歷史資料起訖，但 Run Forecast 卻把 Start date 當作預測起點。正確 UI 應該把「歷史區間」與「未來預測 horizon」分開。

## Goals / Non-Goals

**Goals:**

- 修正 Web Dashboard 的語意，使它符合「History range → Forecast future」模型。
- 將 UI 控制命名改為 `History start`、`History end`、`Forecast horizon`。
- Run Forecast 使用 `forecast_start_date = historyEnd + 1 day`。
- 主圖顯示 actual history 到 `historyEnd`，forecast 接在 `historyEnd + 1` 後面。
- 保留過往 forecast 分析能力，但把 `horizon_step` 定位為 evaluation / analysis filter。
- 更新 docs 與 tests，避免未來再次混淆。

**Non-Goals:**

- 不修改 FastAPI API contract。
- 不修改 CLI forecast / evaluate 語意。
- 不新增 location alias。
- 不新增每日排程器。
- 不重新設計整個 Dashboard UI。

## Decisions

### Decision 1: `historyEnd + 1 day` as forecast start

**Choice:** Web `Run Forecast` 會將 API body 的 `start_date` 設為 `historyEnd + 1 day`。

**Why:** 使用者把 `historyEnd` 理解為已知資料終點，因此預測應接在它後面。這也讓圖表視覺形成清楚的分界：actual historical line 先結束，forecast uncertainty 接續開始。

**Alternative considered:** `forecast_start_date = historyEnd`。這符合目前 CLI live 預設，但在 Web UI 中會讓「歷史終點」同一天同時有 actual 與 forecast，較不直覺。

### Decision 2: Rename state fields to reflect semantics

**Choice:** 前端 `DashboardFilters` 改成：

```ts
type DashboardFilters = {
  latitude: number;
  longitude: number;
  historyStart: string;
  historyEnd: string;
  forecastHorizon: number;
  evaluationHorizonStep: 'any' | number;
  showAggregate: boolean;
};
```

**Why:** 讓程式碼與 UI 都避免泛用 `startDate/endDate`，降低下一次把歷史區間與 forecast 起點混在一起的風險。

### Decision 3: Forecast query must include future target dates

**Choice:** Web 查 forecasts 時要查足夠範圍來涵蓋剛產生的 future forecasts。因為 API `GET /forecasts` 是按 `start_date` 篩選，不是按 `target_date` 篩選，所以 after forecast done 時至少要查 `start_date_from = forecastStartDate` 且 `start_date_to = forecastStartDate`，或合併查詢範圍涵蓋 analysis range + live forecast start。

Implementation approach:

- 對主圖需要兩份 forecast 資料：
  1. `analysisForecasts`：用 history range 查過往 forecast，用於長期相關性分析與 aggregate。
  2. `futureForecasts`：用 `forecastStartDate` 查剛產生的未來 forecast，確保尾端顯示未來預測。
- chart transform 合併這兩份資料並以 `target_date` 排序。

**Why:** API contract 不變的前提下，這是最小修正。若未來 API 提供 `target_date_from/to` 查詢，再簡化前端。

### Decision 4: Evaluation horizon step remains analysis-only

**Choice:** `evaluationHorizonStep` 只影響 evaluation 與過往 forecast analysis；不影響 Run Forecast horizon。Forecast horizon 是獨立數字輸入。

**Why:** `horizon_step` 的正確含義是 forecast row 的 lead time（`target_date - start_date`），不是「要預測幾天」。UI 必須把兩者拆開。

### Decision 5: Documentation must use the same vocabulary

Docs should consistently define:

- **History start**：歷史 actual 查詢 / 補抓起點。
- **History end**：歷史 actual 查詢 / 補抓終點，也是 forecast cutoff。
- **Forecast start**：`historyEnd + 1 day`，第一個 future target date。
- **Forecast horizon**：從 Forecast start 起往後預測 N 天。
- **Evaluation horizon step**：過往 forecast 的 lead time filter。

## Risks / Trade-offs

- **[兩份 forecast query 增加前端複雜度]** → 封裝成 hook / utility，測試確保 query ranges 與 merge 行為正確。
- **[舊的 horizon_step UI 使用者可能困惑]** → 改名為 Evaluation horizon step，並放到 analysis/evaluation 區塊或加 help text。
- **[future forecast 沒 actual，evaluation pending 增加]** → UI 應允許 pending，並在表格顯示 `—`，不把 pending 當錯誤。
- **[API 仍按 start_date 查 forecasts]** → 文件寫明目前 limitation；未來可新增 target_date range endpoint。

## Migration Plan

1. 修改前端 filter state / component labels。
2. 修改 Run Forecast request body。
3. 修改 query hooks，分開 actual history range、analysis forecast range、future forecast range。
4. 修改 chart transform tests，確認 future forecast 接在 historyEnd 後面。
5. 更新 docs。
6. Run `npm test`、`npm run build`。

Rollback：恢復 web filter/query 邏輯；API 不涉及 migration。
