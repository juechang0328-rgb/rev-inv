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
# 1. 抓取最新一期上市（TWSE）+ 上櫃（TPEx）月營收，存進 SQLite
python -m revinv.cli fetch

# 只抓其中一個市場
python -m revinv.cli fetch --market twse
python -m revinv.cli fetch --market tpex

# 2. 篩選：YoY >= 15%，且要求當月 MoM 也是正成長，取前 20 名（TWSE/TPEx 混合排序）
python -m revinv.cli screen --min-yoy 15 --positive-mom --top 20
```

資料庫預設存在 `data/revinv.sqlite3`（可用 `--db` 指定路徑）。

`fetch` 會分別呼叫兩個市場的 API；其中一個失敗只會記錄警告並繼續存另一個，兩個都失敗才會回傳非 0（exit code 1）。

## 資料來源

- 上市月營收：[TWSE OpenAPI t187ap05_L](https://openapi.twse.com.tw/v1/opendata/t187ap05_L)（上市公司每月營業收入彙總表）
- 上櫃月營收：[TPEx OpenAPI mopsfin_t187ap05_O](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O)（上櫃公司每月營業收入彙總表）
- 兩者皆免費、不需金鑰，官方每月 10 日前更新，且已附產業別欄位；因為都源自公開資訊觀測站（MOPS）格式，兩個端點回傳的 JSON 欄位名稱完全相同，`revinv/tpex.py` 直接沿用 `revinv/twse.py` 的 `FIELD_MAP` 與正規化邏輯。
- 欄位名稱已對照兩個實際在正式環境串接這兩支 API 的開源專案驗證過：[jeffrey82221/twstock_api](https://github.com/jeffrey82221/twstock_api)（確認 TWSE 欄位）、[roseamyclara/tw-stock-valuation](https://github.com/roseamyclara/tw-stock-valuation)（確認 TPEx 端點與「上市/上櫃/興櫃欄位名相同」）。

因為兩個交易所的產業別分類是同一套標準，`revinv screen` 計算「同產業平均 YoY」時會把 TWSE 跟 TPEx 的同業公司合併成同一個比較群組，peer group 更完整。

### 金額單位

兩個 API 回傳的金額欄位（`revenue`、`revenue_prev_month`、`revenue_prev_year_month`、`cumulative_revenue`、`cumulative_revenue_prev_year`）單位是**仟元**；`normalize_record` 會統一乘以 1000 換算成**元**存進資料庫，避免之後要跟其他資料源（例如季報財務數字）比較或算比率時單位對不上。百分比欄位（`mom_pct`、`yoy_pct`、`cumulative_yoy_pct`）不受影響。

> **注意**：在部分沙箱環境（例如本次開發所用的環境）中，出站網路對 `openapi.twse.com.tw` 和 `www.tpex.org.tw` 都是被阻擋的，因此 `fetch` 指令需要在有網路存取權限的環境下執行才能真正取得資料；程式邏輯本身已用固定的 fixture 資料做過完整測試（見 `tests/`）。

## 測試

```bash
pytest
```

測試使用 `tests/fixtures/twse_sample.json`、`tests/fixtures/tpex_sample.json` 這兩份固定資料，涵蓋正常數值解析、`N/A`/空值等 placeholder 處理、TWSE/TPEx 混合篩選排序、以及 `fetch` 指令在單一市場失敗時的容錯行為，不依賴即時網路存取。

## Roadmap（尚未實作）

- **季報財務指標**：解析 MOPS 季報 XBRL（存貨周轉天期、應收帳款收現天期），作為月營收初篩後的二次確認，並可考慮採用現成套件（例如處理 MOPS 民國年轉換與速率限制的社群套件、或 FinMind）以縮短開發時間。
- **呈現層**：目前只有 CLI 文字輸出；規劃中的 Streamlit / 簡易網頁介面尚未建立。
- **排程**：目前需手動執行 `fetch`；規劃中的 cron 定期抓取尚未設置。
