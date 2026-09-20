# rev-inv

篩選台股上市公司的「營收轉強」訊號：抓取月營收，計算 YoY / MoM，並與同產業 YoY 中位數比較出相對強度。

對應規劃中的兩階段篩選邏輯，兩階段都已實作：
1. **月營收初篩**：找出 YoY 成長且相對同業表現較強的公司（`revinv industries` + `revinv screen`）。
2. **季報確認**：用存貨周轉天期、應收帳款收現天期做二次確認，避免誤判「存貨降但營收也降」的收縮情境（`revinv confirm`，見下方「季報二次確認」）。

## 篩選結果在哪裡看

`.github/workflows/daily-screen.yml` 每天會自動抓最新月營收、跑篩選，把結果 commit 回 `results/`：

1. **先看產業趨勢**：[`results/industries.md`](results/industries.md)（每個產業當月 YoY 中位數排行，GitHub 上直接點開就是表格）跟 [`results/industries.csv`](results/industries.csv)（完整產業清單）。
2. **再挑個股**：[`results/latest.md`](results/latest.md)（YoY ≥ 15%、MoM 為正的公司排行）跟 [`results/latest.csv`](results/latest.csv)（完整結果，開 Excel/Google Sheets 用，可用「產業別」欄位對照第 1 步挑出的強勢產業）。
3. **季報二次確認**：[`results/confirm.md`](results/confirm.md)（針對第 2 步前 30 名，附上存貨周轉天期／應收帳款收現天期的季度趨勢）跟 [`results/confirm.csv`](results/confirm.csv)。
4. **完整全市場個股清單（沒有套用任何門檻）**：[`results/all.csv`](results/all.csv)——`latest.csv` 只有通過門檻的「贏家」，這份才是每一家當月有揭露營收的公司，`industries.md` 就是從這份算出來的。

`fetch` 抓到的資料本身沒有網路限制，因為是在 GitHub Actions 的 runner 上跑，不是這個開發用的沙箱環境。

也可以到 repo 的 **Actions** 分頁手動觸發（`workflow_dispatch`），並在觸發時調整 YoY 門檻、是否要求 MoM 為正。

> 這個排程需要 repo 有 push 到分支的權限（`permissions: contents: write`），如果分支有設保護規則擋掉 workflow 直接 push，需要另外調整（例如改成開 PR，或針對 workflow 的 bot 開白名單）。

## 為什麼要跟產業基準比較

同樣的 YoY 數字，在產業庫存回補期和去化期意義完全相反。`revinv screen` 不是單純排序 YoY，而是計算每家公司「YoY − 當月同產業 YoY 中位數」（相對強度），再依相對強度排序。

用**中位數**而不是平均數，是實際拿真實資料跑過之後才發現有必要：營建/生技這類「營收認列時間點很集中」的產業，常有個別公司因為去年同期基期接近零，單月 YoY 飆到幾百倍甚至上萬 %（例如某次真實跑出來的 建材營造業 就出現過 YoY 41420%、拉得整個產業平均 YoY 高達 32606% 的情況）。平均數會被這種極端值直接綁架，讓同產業其他公司的「相對強度」全部失真；中位數對這種單一極端值幾乎免疫。

## 產業分類：TEJ（預設）vs TWSE/TPEx

TWSE/TPEx 官方的「產業別」欄位很粗（全市場只分 36 類），把 IC 設計、晶圓代工、記憶體、封測全部混在同一個「半導體業」裡比較，同業比較的意義有限。`revinv/data/tej_industry.csv` 是從 TEJ 資料庫匯出的分類對照表（2319 家公司），`revinv screen`/`revinv industries`/Streamlit app 預設會用這份對照表把公司改分到 **TEJ產業名**（96 類，例如把「半導體業」拆成 IC 設計、晶圓代工、記憶體等）再算同業中位數，找不到對照（例如新上市公司）就自動退回原本 TWSE/TPEx 的產業別。

- TEJ 其實還有更細的「TEJ子產業名」（231 類），但那個粒度太細，很多子產業只剩 1-2 家公司可比，中位數不可靠，所以預設不用；程式裡 `enrich_with_tej_industry(records, level="sub_industry")` 保留這個選項，之後有需要可以再開。
- 用 `--industry-source twse` 可以切回原本較粗的 TWSE/TPEx 分類做對照。
- 這份對照表是**靜態快照**，不是即時抓的（TEJ 分類是付費資料庫，沒有公開 API）；新股或分類異動不會自動更新，需要時手動重新匯出、覆蓋 `revinv/data/tej_industry.csv`。
- 輸出多了一欄「同業家數」（`peer_count`），因為即使是 TEJ 產業名的 96 類，還是有些產業家數偏少，中位數的可信度會打折扣，這欄讓你自己判斷要不要相信這個「相對強度」。

## 建議的篩選流程：先看產業，再挑個股

```bash
# 第一步：看看這個月哪些產業整體轉強（依 YoY 中位數排序，預設列出前 30 名）
python -m revinv.cli industries

# 第二步：從第一步覺得有意思的產業裡，篩出表現突出的個股
python -m revinv.cli screen --min-yoy 15 --positive-mom --industry "M23G1B 記憶體製造"
# --industry 可以重複指定多個產業
python -m revinv.cli screen --industry "M23G1B 記憶體製造" --industry "M25A 建設"
```

`revinv industries` 是在完整市場快照上算的（不受 `screen` 的 YoY/MoM 門檻影響），這樣看到的才是真正的產業整體趨勢，而不是「已經篩過一輪、只剩少數強勢公司」的偏誤樣本。

## 季報二次確認：存貨周轉天期 / 應收帳款收現天期

月營收 YoY 成長，有可能是真的賣得動，也有可能只是「存貨降但營收也降」的收縮假象（詳見上面「為什麼要跟產業基準比較」）。`revinv confirm` 是第三步：對 `screen` 篩出的同一份候選名單，額外抓每家公司最近幾季的存貨、應收帳款、營收、營業成本，算出：

- **存貨周轉天期**（DIO）＝ 平均存貨 ÷ 當季營業成本 × 91 天
- **應收帳款收現天期**（DSO）＝ 平均應收帳款 ÷ 當季營收 × 91 天

並跟上一季比較，標成「存貨周轉加快/轉慢」「收現變快/變慢」這種文字說明，讓你自己判斷這波營收成長是不是健康的——這是「二次確認」，不是自動篩掉公司的硬性門檻。

```bash
# 對 screen 同一份候選名單（同樣的 --min-yoy/--positive-mom/--industry 等參數）做季報確認
python -m revinv.cli confirm --min-yoy 15 --positive-mom --top 30
```

**資料來源與限制：**

- 資料來自 [FinMind](https://github.com/FinMind/FinMind) 的 `TaiwanStockBalanceSheet`（資產負債表）跟 `TaiwanStockFinancialStatements`（綜合損益表）——這是原始規劃裡提到、用來省掉自己解析 MOPS XBRL 的社群套件；TWSE/TPEx 官方沒有像月營收那樣「全市場一次拿到」的季報 API。
- FinMind 一次 API 呼叫只能拿一家公司的資料，全市場（近 2000 家）逐一問一輪要打幾千次 API，免費額度撐不住也太慢，所以 `confirm` **刻意只對 `screen` 篩出的候選名單**（預設前 30 名）做確認，不是對全市場，這也呼應原始規劃「月營收初篩→季報二次確認」的兩階段設計。
- 如果你有 FinMind 帳號的免費 token（可以拉高速率限制），用 `--finmind-token` 或設定 `FINMIND_TOKEN` 環境變數（GitHub Actions 則是設定 repo secret `FINMIND_TOKEN`）；不設也能跑，只是匿名額度較低。
- 台灣季報的損益表數字是**年初累計**（Q2 揭露的是 1-6 月累計、Q3 是 1-9 月累計，只有 Q1 本身是單季），`revinv/quarterly.py` 的 `dequarterize()` 會用相鄰季別相減還原成單季數字，遇到當年度缺前面季別的資料就直接跳過該季（不用猜的）；資產負債表項目（存貨、應收帳款）本身就是某個時間點的餘額，不需要這個轉換。
- 金融/保險股沒有存貨、營業成本的概念，`存貨周轉天期` 會顯示 `-`（無法計算，不是 0 或錯誤）；近期才上市、季報歷史不足 3 季的公司也一樣顯示 `-`。

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

# 想拿 TWSE 官方較粗的產業別做對照，而不是預設的 TEJ 產業分類
python -m revinv.cli screen --min-yoy 15 --industry-source twse

# 3. 先看產業趨勢，再挑個股（見上方「建議的篩選流程」）
python -m revinv.cli industries
python -m revinv.cli screen --industry "M25A 建設"

# 4. 對篩出的候選名單做季報二次確認（見上方「季報二次確認」）
python -m revinv.cli confirm --min-yoy 15 --positive-mom --top 30

# 5. 想快速瀏覽/排序/搜尋，用互動式 Streamlit 網頁（見下方「互動瀏覽」）
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

頁面分兩步：**第一步**是產業趨勢表（YoY 中位數排行，未套用任何個股篩選門檻），**第二步**才是個股表，側邊欄可以即時調整資料年月、YoY 門檻、是否要求 MoM 為正、TEJ/TWSE 產業分類切換、市場、產業別多選（可以直接從第一步看到的強勢產業去挑）、代號/名稱搜尋，表格支援點欄位排序，也有「下載 CSV」按鈕。如果本機還沒跑過 `fetch`（資料庫是空的），會自動改讀 repo 裡 `results/latest.csv`／`results/industries.csv`（GitHub Actions 每天自動更新的結果）做唯讀瀏覽，這樣不用先跑 `fetch` 也能先看看排程幫你篩出來的東西長什麼樣子——只是這個模式下個股篩選門檻已經固定在 YoY ≥ 15%、MoM 為正、前 50 名，沒辦法即時調整。

## 資料來源

- 上市月營收：[TWSE OpenAPI t187ap05_L](https://openapi.twse.com.tw/v1/opendata/t187ap05_L)（上市公司每月營業收入彙總表）
- 上櫃月營收：[TPEx OpenAPI mopsfin_t187ap05_O](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O)（上櫃公司每月營業收入彙總表）
- 兩者皆免費、不需金鑰，官方每月 10 日前更新，且已附產業別欄位；因為都源自公開資訊觀測站（MOPS）格式，兩個端點回傳的 JSON 欄位名稱完全相同，`revinv/tpex.py` 直接沿用 `revinv/twse.py` 的 `FIELD_MAP` 與正規化邏輯。
- 欄位名稱已對照兩個實際在正式環境串接這兩支 API 的開源專案驗證過：[jeffrey82221/twstock_api](https://github.com/jeffrey82221/twstock_api)（確認 TWSE 欄位）、[roseamyclara/tw-stock-valuation](https://github.com/roseamyclara/tw-stock-valuation)（確認 TPEx 端點與「上市/上櫃/興櫃欄位名相同」）。

因為兩個交易所的產業別分類是同一套標準，`revinv screen` 計算「同產業 YoY 中位數」時會把 TWSE 跟 TPEx 的同業公司合併成同一個比較群組，peer group 更完整。

- 季報財務數字（存貨、應收帳款、營收、營業成本）：[FinMind](https://finmindtrade.com/) 的 `TaiwanStockBalanceSheet`／`TaiwanStockFinancialStatements`，只用在 `revinv confirm` 對候選名單做二次確認（詳見上方「季報二次確認」），不是全市場抓取。欄位比對來源：[FinMind-Doc](https://github.com/FinMind/FinMind-Doc) 的 `docs/tutor/TaiwanMarket/Fundamental.md`。

### 金額單位

兩個 API 回傳的金額欄位（`revenue`、`revenue_prev_month`、`revenue_prev_year_month`、`cumulative_revenue`、`cumulative_revenue_prev_year`）單位是**仟元**；`normalize_record` 會統一乘以 1000 換算成**元**存進資料庫，避免之後要跟其他資料源（例如季報財務數字）比較或算比率時單位對不上。百分比欄位（`mom_pct`、`yoy_pct`、`cumulative_yoy_pct`）不受影響。

> **注意**：在部分沙箱環境（例如本次開發所用的環境）中，出站網路對 `openapi.twse.com.tw`、`www.tpex.org.tw`、`api.finmindtrade.com` 都是被阻擋的，因此 `fetch`/`confirm` 指令需要在有網路存取權限的環境下執行才能真正取得資料；程式邏輯本身已用固定的 fixture 資料做過完整測試（見 `tests/`）。

## 測試

```bash
pytest
```

測試使用 `tests/fixtures/twse_sample.json`、`tests/fixtures/tpex_sample.json` 這兩份固定資料，涵蓋正常數值解析、`N/A`/空值等 placeholder 處理、TWSE/TPEx 混合篩選排序、`fetch` 指令在單一市場失敗時的容錯行為、`screen`/`industries`/`confirm` 指令的 CSV/Markdown 輸出與 `--output` 寫檔行為、產業趨勢彙總（`summarize_industries`）、TEJ 產業對照表的查詢與退回機制、以及季報累計數字還原成單季（`dequarterize`）與存貨/應收帳款周轉天期計算，不依賴即時網路存取（Streamlit UI 本身沒有自動化測試，用真實資料手動跑過驗證）。

## Roadmap（尚未實作）

- **互動瀏覽整合季報確認**：Streamlit app 目前只有月營收篩選兩步驟，`revinv confirm` 的存貨/應收帳款趨勢還沒接進互動介面（只有 CLI 跟每日自動產出的 `results/confirm.md`）。
- **歷史紀錄**：`results/latest.*` 每次執行都會被覆蓋，沒有另外保存每個月的歷史結果；要回頭看某天的結果只能翻 Git commit 歷史。
- **TEJ 分類自動更新**：`revinv/data/tej_industry.csv` 是手動匯出的靜態快照，沒有排程自動重新匯出/更新的機制。
