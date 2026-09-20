# rev-inv

篩選台股上市公司的「營收轉強」訊號：抓取月營收，計算 YoY / MoM，並與同產業平均比較出相對強度。

這是 MVP 第一階段（月營收監測），對應規劃中的兩階段篩選邏輯：
1. **月營收初篩**（本階段已實作）：找出 YoY 成長且相對同業表現較強的公司。
2. **季報確認**（尚未實作，見下方 Roadmap）：用存貨周轉天期、應收帳款收現天期做二次確認，避免誤判「存貨降但營收也降」的收縮情境。

## 為什麼要跟產業平均比較

同樣的 YoY 數字，在產業庫存回補期和去化期意義完全相反。`revinv screen` 不是單純排序 YoY，而是計算每家公司「YoY − 當月同產業平均 YoY」（相對強度），再依相對強度排序。

## 安裝

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

## 使用方式

```bash
# 1. 抓取 TWSE OpenAPI 最新一期上市公司月營收，存進 SQLite
python -m revinv.cli fetch

# 2. 篩選：YoY >= 15%，且要求當月 MoM 也是正成長，取前 20 名
python -m revinv.cli screen --min-yoy 15 --positive-mom --top 20
```

資料庫預設存在 `data/revinv.sqlite3`（可用 `--db` 指定路徑）。

## 資料來源

- 月營收：[TWSE OpenAPI t187ap05_L](https://openapi.twse.com.tw/v1/opendata/t187ap05_L)（上市公司每月營業收入彙總表），免費、不需金鑰，官方每月 10 日前更新，且已附產業別欄位。
- 欄位名稱已對照實際串接該 API 的開源專案（[jeffrey82221/twstock_api](https://github.com/jeffrey82221/twstock_api)）驗證過，`revinv/twse.py` 的 `FIELD_MAP` 與官方回傳欄位一致。

### 金額單位

TWSE API 回傳的金額欄位（`revenue`、`revenue_prev_month`、`revenue_prev_year_month`、`cumulative_revenue`、`cumulative_revenue_prev_year`）單位是**仟元**；`normalize_record` 會統一乘以 1000 換算成**元**存進資料庫，避免之後要跟其他資料源（例如季報財務數字）比較或算比率時單位對不上。百分比欄位（`mom_pct`、`yoy_pct`、`cumulative_yoy_pct`）不受影響。

> **注意**：目前僅實作上市（TWSE）資料源。上櫃（TPEx）的開放資料 API 欄位格式不同，尚未驗證與實作，先列在 Roadmap。
>
> 在部分沙箱環境（例如本次開發所用的環境）中，出站網路對 `openapi.twse.com.tw` 是被阻擋的，因此 `fetch` 指令需要在有網路存取權限的環境下執行才能真正取得資料；程式邏輯本身已用固定的 fixture 資料做過完整測試（見 `tests/`）。

## 測試

```bash
pytest
```

測試使用 `tests/fixtures/twse_sample.json` 這份固定資料，涵蓋正常數值解析、`N/A`/空值等 placeholder 處理，以及篩選/排序邏輯，不依賴即時網路存取。

## Roadmap（尚未實作）

- **TPEx（上櫃）月營收**：串接櫃買中心對應的開放資料 API。
- **季報財務指標**：解析 MOPS 季報 XBRL（存貨周轉天期、應收帳款收現天期），作為月營收初篩後的二次確認，並可考慮採用現成套件（例如處理 MOPS 民國年轉換與速率限制的社群套件、或 FinMind）以縮短開發時間。
- **呈現層**：目前只有 CLI 文字輸出；規劃中的 Streamlit / 簡易網頁介面尚未建立。
- **排程**：目前需手動執行 `fetch`；規劃中的 cron 定期抓取尚未設置。
