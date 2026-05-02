## Context

`forecasting/timesfm.py` 與 `forecasting/baseline.py` 自開案以來一直是 `NotImplementedError` 空殼。`historical-fetch` change 已讓歷史資料層走 DB 快取 + Open-Meteo 補抓的路徑跑通，現在要把預測接上。

TimesFM 2.5 API 概覽（取自 `references/timesfm/`）：
- `TimesFM_2p5_200M_torch.from_pretrained(model_id)` 從 HuggingFace 載入 checkpoint。
- `model.compile(ForecastConfig(max_context=..., max_horizon=..., ...))` 用固定 shape 編譯 batched decode 圖；compile 後 `max_context`/`max_horizon` 不可變。
- `model.forecast(horizon, inputs=[np.array, ...])` 回傳 `(point, quantiles)`：
  - `point.shape == (batch, horizon)`：mean。
  - `quantiles.shape == (batch, horizon, 10)`：mean 再來 9 個分位（10%、20%、…、90%）。

Roadmap 將「TimesFM Inference Server」列為長期目標。本 change 的設計必須讓未來抽 server 是「拉一條線」而不是大重構。

既有 `models.py` 的 `QuantileForecast(date, p10, p50, p90)` 只能描述「一天的單一變數」，不能同時表達 max 與 min。`Settings` 上的 `forecast_quantiles=(0.1, 0.5, 0.9)` 與我們最終固定輸出 p10/p50/p90 的設計重複。

## Goals / Non-Goals

**Goals：**

- 讓使用者能用 `timesfm-meteo forecast --latitude --longitude` 一行指令拿到未來 N 日 max / min 分位數預測。
- inference 層保持與領域知識完全解耦（只認 numpy 序列），讓未來抽成 server 時不需重寫。
- adapter 用 dependency injection（`ForecastEngine` Protocol）接 engine，讓單元測試完全 mock、CI 不需 torch。
- `[forecast]` extra 把重依賴（torch、timesfm）隔離；基本安裝體積不變。
- backtest 模式由 `--start-date` 設過去日期天然支援（同樣的 CLI 路徑、不另外寫程式）。
- 保留可預測性：模型版本、checkpoint 路徑、context / horizon 上限都從 `Settings` 取，方便將來換模型。

**Non-Goals：**

- 不寫 forecast 結果進 Postgres。延後到 MVP 第 5 步「基礎評估」當作前置工作。
- 不做評估指標（MAE、coverage 等）。同上。
- 不處理 MPS / Apple Silicon GPU。預設 CUDA；MPS 在 roadmap 註記延後。
- 不寫端到端 forecasting 整合測試（需要真載 200M 模型）。adapter + CLI 全 mock；engine 不寫單元測試。
- 不寫 baseline forecaster 的真實作。`forecasting/baseline.py` 維持 `NotImplementedError` 不動，本次無該需求。
- 不搭 inference server。只把架構讓出來，server 改在後續 change 做。

## Decisions

### 1. 模組分層：`inference/` 與 `forecasting/` 並列

```
src/timesfm_meteo/
├── inference/
│   ├── __init__.py
│   └── timesfm_engine.py       # TimesFMEngine + ForecastEngine Protocol
└── forecasting/
    ├── timesfm.py              # adapter: domain ↔ engine
    └── baseline.py             # 不動
```

**理由**：`inference/` 是領域無關的「給我一條序列，回我預測」純推論層 — 未來抽 server 時直接打包這個目錄 + 加 HTTP 殼。`forecasting/` 是領域層，知道什麼是 `DailyTemperature` 與 `DailyTemperatureForecast`。兩層用 `ForecastEngine` Protocol 解耦。

替代方案：把 engine 放在 `forecasting/engines/timesfm.py`。捨棄理由：太「forecast-centric」，未來 server 化時會被誤以為是 forecasting 子集；獨立 `inference/` 邊界更清楚。

### 2. Engine 對外回傳「全部 9 個分位 + mean」，不做語意縮減

```python
class QuantileForecastResult(ProjectModel):
    horizon: int
    point: list[float]                       # mean
    quantiles: dict[float, list[float]]      # {0.1, 0.2, ..., 0.9}: each list len == horizon
```

**理由**：engine 是模型輸出的忠實 wrapper；要不要只用 p10/p50/p90 是 client 的事。這樣未來 server 化也不必改 API。

替代方案：engine 直接回 `DailyTemperatureForecast`。捨棄理由：把領域語意硬塞進 inference 層，違反分層目的。

**型別選擇**：用 `list[float]`（不是 `np.ndarray`）為了 JSON 可序列化 — 將來變 server 時 wire format 不需要轉換。adapter 內部處理 numpy ↔ list 的邊界。

### 3. Engine API 採批次形態

```python
class ForecastEngine(Protocol):
    def forecast(
        self, series_list: list[np.ndarray], horizon: int
    ) -> list[QuantileForecastResult]: ...
```

**理由**：TimesFM 原生支援 batched 推論（一次 GPU pass 處理多條序列）。我們的 max + min 場景剛好是 2 條，批次最自然；單條只是 `len==1` 的批次。

### 4. `__init__` 內完成 load + compile

```python
class TimesFMEngine:
    def __init__(
        self,
        model_id: str = "google/timesfm-2.5-200m-pytorch",
        max_context: int = 1024,
        max_horizon: int = 32,
    ) -> None:
        # lazy import；compile 用 ForecastConfig，4 個 flag 開放
        ...
```

**理由**：CLI 是 one-shot、server 是 long-lived，兩者都希望初始化完就 ready。延後初始化只徒增複雜度。

**lazy import 策略**：`from timesfm import ...` 寫在 `__init__` 函式內部，不在 module top-level；缺 extra 時 `from timesfm_meteo.inference import timesfm_engine` 不會炸，但 `TimesFMEngine()` 會給出清楚錯誤訊息：
```
TimesFM dependencies not installed. Run: uv sync --extra forecast
```

### 5. 模型上限 vs 我們的預設

| 參數 | TimesFM 2.5 上限 | 本專案預設 | 理由 |
|---|---|---|---|
| `max_context` | 16384 (16k) | 1024 | 2 年每日資料 ≈ 730 個點，1024 已綽綽有餘；編譯較輕 |
| `max_horizon` | 1000 (1k) | 32 | MVP 只要 3 天，留至 ~1 個月彈性，避免改參數要重 compile |

詳細說明寫進 `docs/timesfm-engine.md`，方便將來調整時有上下文。

### 6. 領域模型重構

```python
class QuantileValues(ProjectModel):
    p10: float
    p50: float
    p90: float
    # validator: p10 <= p50 <= p90

class DailyTemperatureForecast(ProjectModel):
    date: Date
    max: QuantileValues
    min: QuantileValues
    # validator: max.p50 >= min.p50
```

**理由**：「一天的最高溫與最低溫各自的分位數」是不可分割的合成單位；用複合模型表達最自然。

**BREAKING**：移除原有 `QuantileForecast(date, p10, p50, p90)` 與 `Settings.forecast_quantiles`。前者目前沒有真實使用者（只在 stub 簽名出現），後者語意已被新模型固定。

### 7. 預測日期推導放 CLI

CLI 用 `--start-date`（預設今天）與 `horizon` 算出待預測日期清單，傳進 adapter。

**理由**：start-date 是 CLI 的語意（特別是 backtest 模式可能往回拉），adapter 別猜。

```python
def forecast_with_timesfm(
    history: list[DailyTemperature],
    forecast_dates: list[Date],
    engine: ForecastEngine,
) -> list[DailyTemperatureForecast]: ...
```

### 8. CLI flow

```
1. argparse → location、start_date、horizon、history_years
2. start_date 預設 = today
3. history range = [start_date - history_years * 365 天, start_date - 1]
4. 載 Settings；DSN 缺失或連線失敗都 hard fail（複用 fetch-history 模式）
5. with psycopg.connect(...) as conn:
       ensure_schema(conn)
       history = pipeline.historical.get_temperatures(location, hist_start, hist_end, conn, settings.open_meteo)
6. forecast_dates = [start_date + i for i in range(horizon)]
7. engine = TimesFMEngine(...settings.timesfm...)
8. forecasts = forecast_with_timesfm(history, forecast_dates, engine)
9. response = ForecastResponse(model=..., history_days=..., horizon=..., forecasts=forecasts)
10. print(response.model_dump_json(indent=2))  # stdout
11. print summary line to stderr
```

### 9. 測試策略

- **adapter 測試**：mock engine（自寫 fake class 滿足 `ForecastEngine` Protocol，回傳 canned `QuantileForecastResult`），驗證：
  - max / min 序列正確分離成兩條輸入。
  - quantiles[0.1] / [0.5] / [0.9] 正確被映射到 `QuantileValues.p10/p50/p90`。
  - 輸出長度 == `len(forecast_dates)`。
  - 輸出日期一一對應 `forecast_dates`。
- **CLI 測試**：
  - argparse 預設值取自 settings、`--start-date` 預設今天、`--horizon` override 生效。
  - DSN 缺失 → exit 2、stderr 訊息（沿用 fetch-history 既有模式）。
  - 完整 happy path：mock 整條 pipeline（`get_temperatures`、`TimesFMEngine`），驗證 stdout 是合法 JSON、能反序列化進 `ForecastResponse`、stderr 摘要格式正確。
- **engine 不寫單元測試**：純 upstream wrapper、測試 wrapper 不能驗證模型行為，沒意義。
- **既有測試需更新**：`test_models.py` 的 `QuantileForecast` 相關測試改測 `QuantileValues` 與 `DailyTemperatureForecast`；`test_configs.py` 移除 `forecast_quantiles` 相關 assertion（若有）。

### 10. HF 快取目錄

不在 `Settings` 處理；`.env.example` 補 `HF_HOME=`，空值用 HF 預設（`~/.cache/huggingface/`）。HF Hub library 自己會讀 env var，engine 不需要額外 glue code。

## Risks / Trade-offs

- **Risk**：TimesFM 2.5 PyTorch checkpoint 之前曾有 safetensors 載入問題（reference 範例特地用 1.0）→ 試了若失敗，先把 `model_id` 切到 `google/timesfm-1.0-200m-pytorch` 並把該事實寫進 `docs/timesfm-engine.md`。Engine API 不需動（1.0 也回 quantile 矩陣）。
- **Risk**：Engine 在 `__init__` 載入耗時 30 秒以上 → 對 CLI 是「使用者按 Enter 後等 30 秒才看到結果」，不算理想。可接受，後續 server 化後就解決。
- **Risk**：torch 在不同硬體（CPU / CUDA / MPS）行為不同；MPS 可能炸 → roadmap 已註記延後處理；本 change 不寫 fallback。若使用者環境出問題會是 runtime error，design.md 對此誠實。
- **Trade-off**：`max_horizon=32` 預設值在使用者想做 1 個月以上預測時要重 compile → 可接受；換需求時改 `configs.yaml` 即可，無程式碼改動。
- **Trade-off**：JSON 輸出比 TSV 多花字元 → JSON 可被 pydantic 直接吃，符合「未來變 server」的方向，值得。
- **Trade-off**：BREAKING change 重構 `QuantileForecast` → 該模型目前沒有真實使用者，重構成本接近零。下個 change 才開始用新模型，趁早重構最便宜。
