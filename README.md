# timesfm-meteo

使用 Open-Meteo 歷史氣溫資料與 TimesFM 的天氣預測實驗專案。

## 目前目標

建立最小可用 pipeline：

1. 依指定 latitude / longitude 取得至少兩年的每日最高溫與最低溫。
2. 使用歷史資料預測未來 3 日氣溫範圍。
3. 使用 p10、p50、p90 等分位數表示不確定性。
4. 保留足夠的評估輸出，讓預測結果能和後續觀測值比較。

分階段規劃請參考 `docs/roadmap.md`。

## 目前狀態

此 repository 仍在規劃與 skeleton 階段。src-layout 骨架已建立，Open-Meteo
歷史氣溫資料抓取已可用，預測 pipeline 尚未實作。

## Configuration

非敏感設定使用 YAML，預設讀取：

```text
configs/configs.yaml
```

可從範例建立本機設定：

```bash
cp configs/configs.example.yaml configs/configs.yaml
```

敏感設定使用 `.env`，由 `python-dotenv` 載入。`configs/configs.yaml` 與 `.env`
不應提交。

## Development

專案目前使用 Python 3.12，並採用 src-layout。根目錄 `main.py` 是薄入口，核心
程式碼位於 `src/timesfm_meteo/`。

```bash
uv sync
uv run python main.py
uv run python -m timesfm_meteo
uv run timesfm-meteo
uv run --extra dev pytest
```
