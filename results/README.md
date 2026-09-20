# 篩選結果

這個資料夾由 `.github/workflows/daily-screen.yml` 每天自動更新，**不要手動編輯**：

**先看整個產業趨勢，再挑個別強的公司：**

- `industries.md` — 每個產業（TEJ 96 類，可看 README 主頁「產業分類」說明）當月 YoY 中位數排行（前 30 名），可以直接在 GitHub 上點開瀏覽，先看哪些產業整體轉強。
- `industries.csv` — 同一份產業趨勢的完整結果（全部產業，不限筆數）。

**再看個股：**

- `latest.md` — 篩選結果表格（YoY ≥ 15%、要求 MoM 為正、取前 50 名），可以直接在 GitHub 上點開瀏覽。
- `latest.csv` — 同一次篩選的完整結果（不限筆數），可用 Excel / Google Sheets 開啟做進一步排序、篩選，或用「產業別」欄位對照 `industries.md` 挑出的強勢產業。

篩選門檻（YoY 門檻、是否要求 MoM 為正）可以在 GitHub 的 Actions 頁面手動觸發 workflow 時調整；排程執行則固定用預設值（YoY ≥ 15%、要求 MoM 為正）。

目前只保留「最新一次」的結果，沒有保存歷史紀錄；要看某一天的結果，可以在這個檔案的 Git commit 歷史裡找對應日期的版本。
