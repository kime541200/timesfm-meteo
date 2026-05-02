# TimesFM Engine

`src/timesfm_meteo/inference/timesfm_engine.py` 是專案的推論層，刻意與
`timesfm_meteo` 領域模型解耦，方便未來抽成獨立的 Inference Server（見
`docs/roadmap.md` 長期目標）。本檔說明引擎介面、預設值取捨與相關設定。

## 介面

```python
class ForecastEngine(Protocol):
    def forecast(
        self, series_list: list[np.ndarray], horizon: int
    ) -> list[QuantileForecastResult]: ...
```

引擎只接受純數值序列（`numpy.ndarray`），輸出由 pydantic 的
`QuantileForecastResult` 表達，內部欄位（`point`、`quantiles`）皆為
`list[float]`。這個型別選擇刻意避開 `numpy.ndarray`，讓未來變成
HTTP 服務時可以直接 `model_dump_json()` 過 wire format，不需要自寫
encoder / decoder。

## 載入與 compile 時機

`TimesFMEngine.__init__` 一次完成：

1. lazy import `timesfm`、`numpy`（缺 `[forecast]` extra 時 raise
   `RuntimeError`，提示 `uv sync --extra forecast`）。
2. `TimesFM_2p5_200M_torch.from_pretrained(model_id)` 從 HuggingFace 載入
   checkpoint（首次呼叫會下載，之後使用 HF 快取）。
3. `model.compile(ForecastConfig(...))` 編譯 batched decode 圖。

`compile` 之後 `max_context` / `max_horizon` 不可變，要更動需要重新
建立引擎。CLI 是 one-shot、未來 server 是 long-lived，兩者都希望
初始化結束就 ready，因此沒有把 load / compile 拆成單獨的
`prepare()` 方法。

## 參數預設值

| 參數 | TimesFM 2.5 模型上限 | 本專案預設 | 理由 |
|---|---|---|---|
| `max_context` | 16384 (16k) | 1024 | 2 年每日資料 ≈ 730 個點，1024 已綽綽有餘；編譯較輕。 |
| `max_horizon` | 1000 (1k) | 32 | MVP 只要 3 天，預留至 ~1 個月彈性，避免改參數要重 compile。 |
| `normalize_inputs` | — | `True` | 對輸入 z-score 正規化；溫度量級雖不誇張但開啟成本極低。 |
| `use_continuous_quantile_head` | — | `True` | 啟用連續分位頭，避免分位 collapse；輸出 9 個分位（10%、20%、…、90%）。 |
| `force_flip_invariance` | — | `True` | 強制 `f(-x) = -f(x)`，提升小資料下的穩定性。 |
| `fix_quantile_crossing` | — | `True` | 修正分位數交叉，保證 `p10 <= p50 <= p90`。 |

要調整以上任何值，改 `configs/configs.yaml` 的 `timesfm:` 區段即可，
不需要動程式碼。

## HF checkpoint 快取目錄

`HF_HOME` 環境變數（在 `.env` 設定）控制 HuggingFace Hub 的根目錄；
checkpoint 預設下載到 `${HF_HOME}/hub/`。空值或未設定時走 HF 預設
（`~/.cache/huggingface/`）。

引擎本身不讀 `HF_HOME` — `huggingface_hub` 套件會自動讀環境變數，
我們只需要保證該變數有設好。`load_settings()` 會經由 `python-dotenv`
把 `.env` 內的 `HF_HOME` 注入 `os.environ`，再轉給 HF 套件使用。

## 引擎與專案的邊界

引擎不 import 任何 `timesfm_meteo` 領域型別（`Location`、`DailyTemperature`
等）。`QuantileForecastResult` 雖然定義在 `models.py`，但屬於「引擎輸出契約」、
不是領域模型；未來抽 server 時這個 schema 會跟著被搬到共用 schema 套件。

領域語意（max + min 兩條序列、回傳 `DailyTemperatureForecast`）由
`forecasting/timesfm.py` 的 adapter 負責，呼叫引擎時透過 `ForecastEngine`
Protocol 注入，方便測試以 fake 取代真實引擎、CI 不需要安裝 torch。

## MPS / Apple Silicon

目前預設假設執行環境有 CUDA。Apple Silicon（MPS）若實際遇到問題再評估
切換到 fork（`kime541200/timesfm`）或上游 patch；本檔在發生時會記錄選定的
workaround。
