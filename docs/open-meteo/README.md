# Open-Meteo Notes

本目錄記錄專案使用 Open-Meteo 時需要查閱的官方資源與目前決策。

## 官方文件

- API 文件總覽：[Open-Meteo Docs](https://open-meteo.com/en/docs)
- Historical Weather API：[Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- 官方 GitHub repo：[open-meteo/open-meteo](https://github.com/open-meteo/open-meteo.git)
- Historical Weather OpenAPI spec：[openapi_historical_weather_api.yml](https://github.com/open-meteo/open-meteo/blob/main/openapi_historical_weather_api.yml)
- Docker / self-hosting 說明：[getting-started.md](https://github.com/open-meteo/open-meteo/blob/main/docs/getting-started.md)
- Future client option：[open-meteo/python-requests](https://github.com/open-meteo/python-requests.git)

## 目前專案使用方式

MVP 階段先直接呼叫 Open-Meteo JSON API，不自架 Open-Meteo server，也不先使用
`openmeteo-requests` client。

目前實作位置：

- `src/timesfm_meteo/data_sources/open_meteo.py`

目前使用 Historical Weather API：

```text
https://archive-api.open-meteo.com/v1/archive
```

目前查詢參數：

- `latitude`
- `longitude`
- `start_date`
- `end_date`
- `daily=temperature_2m_max,temperature_2m_min`
- `temperature_unit=celsius`
- `timezone=auto`

## 決策紀錄

### 不自架 Open-Meteo server

Open-Meteo 的 Docker / self-hosting 說明不是單純建立 HTTP proxy，而是建立一套
完整氣象資料庫與 API 後端，需要下載並轉換大量原始氣象模型資料。

以目前 MVP 目標來說，直接使用官方 hosted API 即可。

### 暫不使用 [openmeteo-requests](https://github.com/open-meteo/python-requests.git)

`openmeteo-requests` 適合大量地點、長時間序列、cache / retry，或需要
NumPy、pandas、Polars 整合時再評估。

目前 MVP 只需要每日最高溫與最低溫的 JSON response；直接用 `httpx` 比較簡單、
透明，也比較容易用 `httpx.MockTransport` 測試。

## 後續可能調整

- 若開始批量抓取多個地點或更長時間序列，重新評估 `openmeteo-requests`。
- 若官方 API rate limit 或資料可用性成為瓶頸，再評估 cache、retry 或資料庫暫存。
- 若需要離線或大量歷史資料，才重新評估 self-hosting 成本。
