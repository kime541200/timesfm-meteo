## Why

Web Dashboard 的日期控制語意目前混淆了「歷史資料區間」、「預測起點」與「評估用 horizon_step」。使用者合理預期 Start date / End date 是歷史資料顯示與抓取範圍，Forecast horizon 是向未來預測天數，預測線應接在歷史線尾端；但目前 UI 把 Start date 拿去當 forecast start_date，導致預測結果可能出現在圖表歷史區間內或完全看不到。

此 change 修正 Web Dashboard 的產品語意：History end 是已知歷史資料的最後一天，Run Forecast 應從 History end 的隔天開始預測，Forecast horizon 才是未來天數。

## What Changes

- Web filter 語意調整：
  - `Start date` → `History start`
  - `End date` → `History end`
  - 新增 `Forecast horizon`，預設 `3`
  - `Horizon step` 改為 evaluation / historical forecast analysis 的進階 filter，不再代表 forecast horizon
- Run Forecast 行為調整：
  - `forecast_start_date = historyEnd + 1 day`
  - `horizon = forecastHorizon`
  - 成功後查詢並顯示 `forecast_start_date ... forecast_start_date + horizon - 1` 的預測結果
- 查詢範圍調整：
  - `GET /temperatures` 使用 `historyStart ... historyEnd`
  - `GET /forecasts` 需要同時涵蓋：
    1. 過往 forecast 分析用的 start_date range
    2. live forecast 剛寫入的 future target dates
  - 前端 chart data merge 必須允許 actual 歷史資料與未來 forecast target dates 共存在同一 X 軸
- 圖表調整：
  - 歷史 actual 線顯示到 `historyEnd`
  - forecast p50 / p10–p90 顯示在 `historyEnd + 1` 之後
  - 視覺上預測值接在歷史資料尾端
- 文件更新：`web/README.md`、`docs/usage.md`、`docs/roadmap.md` 說清楚 History range、Forecast start、Forecast horizon、Evaluation horizon step 的差異
- 測試更新：補上 historyEnd + 1、forecast query range、chart future target date merge 的 Vitest 覆蓋

## Capabilities

### New Capabilities
無。

### Modified Capabilities
- `web-dashboard`: 修正 Web Dashboard 的日期與 forecast horizon 語意，使 UI 符合「用歷史資料預測未來」的模型直覺。

## Impact

- **前端行為變更**：Web Dashboard filter 與 Run Forecast 行為調整。
- **前端測試更新**：資料轉換與 query 參數測試需反映新語意。
- **文件更新**：清楚區分 History range、Forecast start、Forecast horizon、Evaluation horizon step。
- **API 不變**：FastAPI endpoints 與 CLI 行為維持不變；此 change 只修正 Web client 對既有 API 的使用方式。
