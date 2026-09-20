# rev-inv

篩選台股上市公司的「營收轉強」訊號：抓取月營收，計算 YoY / MoM，並與同產業 YoY 中位數比較出相對強度。

這是 MVP 第一階段（月營收監測），對應規劃中的兩階段篩選邏輯：
1. **月營收初篩**（本階段已實作）：找出 YoY 成長且相對同業表現較強的公司。
2. **季報確認**（尚未實作，見下方 Roadmap）：用存貨周轉天期、應收帳款收現天期做二次確認，避免誤判「存貨降但營收也降」的收縮情境。

## 篩選結果在哪裡看

`.github/workflows/daily-screen.yml` 每天會自動抓最新月營收、跑篩選，把結果 commit 回 [`results/latest.md`](results/latest.md)（GitHub 上直接點開就是表格）跟 [`results/latest.csv`](results/latest.csv)（完整結果，開 Excel/Google Sheets 用）。也可以到 repo 的 **Actions** 分頁手動觸發（`workflow_dispatch`），並在觸發時調整 YoY 門檻、是否要求 MoM 為正。

> 這個排程需要 repo 有 push 到分支的權限（`permissions: contents: write`），如果分支有設保護規則擋掉 workflow 直接 push，需要另外調整（例如改成開 PR，或針對 workflow 的 bot 開白名單）。

## 為什麼要跟產業基準比較

同樣的 YoY 數字，在產業庫存回補期和去化期意義完全相反。`revinv screen` 不是單純排序 YoY，而是計算每家公司「YoY − 當月同產業 YoY 中位數」（相對強度），再依相對強度排序。

用**中位數**而不是平均數，是實際拿真實資料跑過之後才發現有必要：營建/生技這類「營收認列時間點很集中」的產業，常有個別公司因為去年同期基期接近零，單月 YoY 飆到幾百倍甚至上萬 %（例如某次真實跑出來的 建材營造業 就出現過 YoY 41420%、拉得整個產業平均 YoY 高達 32606% 的情況）。平均數會被這種極端值直接綁架，讓同產業其他公司的「相對強度」全部失真；中位數對這種單一極端值幾乎免疫。

## 產業分類：TEJ（預設）vs TWSE/TPEx

TWSE/TPEx 官方的「產業別」欄位很粗（全市場只分 36 類），把 IC 設計、晶圓代工、記憶體、封測全部混在同一個「半導體業」裡比較，同業比較的意義有限。`revinv/data/tej_industry.csv` 是從 TEJ 資料庫匯出的分類對照表（2319 家公司），細到 231 個子產業（例如把「半導體業」拆成「M23G3C 晶圓材料」等），`revinv screen`/Streamlit app 預設會用這份對照表把公司改分到 TEJ 子產業再算同業中位數，找不到對照（例如新上市公司）就自動退回原本 TWSE/TPEx 的產業別。

- 用 `--industry-source twse` 可以切回原本較粗的 TWSE/TPEx 分類做對照。
- 這份對照表是**靜態快照**，不是即時抓的（TEJ 分類是付費資料庫，沒有公開 API）；新股或分類異動不會自動更新，需要時手動重新匯出、覆蓋 `revinv/data/tej_industry.csv`。
- 輸出多了一欄「同業家數」（`peer_count`），因為分類變細之後，有些子產業可能只剩 1-2 家公司，中位數的可信度會打折扣，這欄讓你自己判斷要不要相信這個「相對強度」。

## 安裝

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

要用 Streamlit 瀏覽器的話，改裝 `requirements-app.txt`（多裝 `streamlit`）：

```bash
pip install -r requirements-app.txt
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

# 也可以輸出成 CSV 或 Markdown 表格，寫到檔案（--top 0 = 不限筆數）
python -m revinv.cli screen --min-yoy 15 --positive-mom --top 0 \
    --format csv --output results/latest.csv
python -m revinv.cli screen --min-yoy 15 --positive-mom --top 50 \
    --format markdown --output results/latest.md

# 想拿 TWSE 官方較粗的產業別做對照，而不是預設的 TEJ 細產業分類
python -m revinv.cli screen --min-yoy 15 --industry-source twse

# 3. 想快速瀏覽/排序/搜尋，用互動式 Streamlit 網頁（見下方「互動瀏覽」）
streamlit run revinv/streamlit_app.py
```

資料庫預設存在 `data/revinv.sqlite3`（可用 `--db` 指定路徑）。

`fetch` 會分別呼叫兩個市場的 API；其中一個失敗只會記錄警告並繼續存另一個，兩個都失敗才會回傳非 0（exit code 1）。

## 互動瀏覽（Streamlit）

```bash
pip install -r requirements-app.txt
python -m revinv.cli fetch          # 先確保本機資料庫有資料
streamlit run revinv/streamlit_app.py
```

側邊欄可以即時調整資料年月、YoY 門檻、是否要求 MoM 為正、TEJ/TWSE 產業分類切換、市場、產業別多選、代號/名稱搜尋，表格支援點欄位排序，也有「下載 CSV」按鈕。如果本機還沒跑過 `fetch`（資料庫是空的），會自動改讀 repo 裡 `results/latest.csv`（GitHub Actions 每天自動更新的結果）做唯讀瀏覽，這樣不用先跑 `fetch` 也能先看看排程幫你篩出來的東西長什麼樣子——只是這個模式下門檻已經固定在 YoY ≥ 15%、MoM 為正、前 50 名，沒辦法即時調整。

## 資料來源

- 上市月營收：[TWSE OpenAPI t187ap05_L](https://openapi.twse.com.tw/v1/opendata/t187ap05_L)（上市公司每月營業收入彙總表）
- 上櫃月營收：[TPEx OpenAPI mopsfin_t187ap05_O](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O)（上櫃公司每月營業收入彙總表）
- 兩者皆免費、不需金鑰，官方每月 10 日前更新，且已附產業別欄位；因為都源自公開資訊觀測站（MOPS）格式，兩個端點回傳的 JSON 欄位名稱完全相同，`revinv/tpex.py` 直接沿用 `revinv/twse.py` 的 `FIELD_MAP` 與正規化邏輯。
- 欄位名稱已對照兩個實際在正式環境串接這兩支 API 的開源專案驗證過：[jeffrey82221/twstock_api](https://github.com/jeffrey82221/twstock_api)（確認 TWSE 欄位）、[roseamyclara/tw-stock-valuation](https://github.com/roseamyclara/tw-stock-valuation)（確認 TPEx 端點與「上市/上櫃/興櫃欄位名相同」）。

因為兩個交易所的產業別分類是同一套標準，`revinv screen` 計算「同產業 YoY 中位數」時會把 TWSE 跟 TPEx 的同業公司合併成同一個比較群組，peer group 更完整。

### 金額單位

兩個 API 回傳的金額欄位（`revenue`、`revenue_prev_month`、`revenue_prev_year_month`、`cumulative_revenue`、`cumulative_revenue_prev_year`）單位是**仟元**；`normalize_record` 會統一乘以 1000 換算成**元**存進資料庫，避免之後要跟其他資料源（例如季報財務數字）比較或算比率時單位對不上。百分比欄位（`mom_pct`、`yoy_pct`、`cumulative_yoy_pct`）不受影響。

> **注意**：在部分沙箱環境（例如本次開發所用的環境）中，出站網路對 `openapi.twse.com.tw` 和 `www.tpex.org.tw` 都是被阻擋的，因此 `fetch` 指令需要在有網路存取權限的環境下執行才能真正取得資料；程式邏輯本身已用固定的 fixture 資料做過完整測試（見 `tests/`）。

## 測試

```bash
pytest
```

測試使用 `tests/fixtures/twse_sample.json`、`tests/fixtures/tpex_sample.json` 這兩份固定資料，涵蓋正常數值解析、`N/A`/空值等 placeholder 處理、TWSE/TPEx 混合篩選排序、`fetch` 指令在單一市場失敗時的容錯行為、`screen` 指令的 CSV/Markdown 輸出與 `--output` 寫檔行為、以及 TEJ 產業對照表的查詢與退回機制，不依賴即時網路存取（Streamlit UI 本身沒有自動化測試，用真實資料手動跑過驗證）。

## Roadmap（尚未實作）

- **季報財務指標**：解析 MOPS 季報 XBRL（存貨周轉天期、應收帳款收現天期），作為月營收初篩後的二次確認，並可考慮採用現成套件（例如處理 MOPS 民國年轉換與速率限制的社群套件、或 FinMind）以縮短開發時間。
- **歷史紀錄**：`results/latest.*` 每次執行都會被覆蓋，沒有另外保存每個月的歷史結果；要回頭看某天的結果只能翻 Git commit 歷史。
- **TEJ 分類自動更新**：`revinv/data/tej_industry.csv` 是手動匯出的靜態快照，沒有排程自動重新匯出/更新的機制。
