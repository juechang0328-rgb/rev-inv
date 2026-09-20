# 篩選結果

這個資料夾由 `.github/workflows/daily-screen.yml` 每天自動更新，**不要手動編輯**：

- `latest.md` — 篩選結果表格（YoY ≥ 15%、要求 MoM 為正、取前 50 名），可以直接在 GitHub 上點開瀏覽。
- `latest.csv` — 同一次篩選的完整結果（不限筆數），可用 Excel / Google Sheets 開啟做進一步排序、篩選。

篩選門檻（YoY 門檻、是否要求 MoM 為正）可以在 GitHub 的 Actions 頁面手動觸發 workflow 時調整；排程執行則固定用預設值（YoY ≥ 15%、要求 MoM 為正）。

目前只保留「最新一次」的結果，沒有保存歷史紀錄；要看某一天的結果，可以在這個檔案的 Git commit 歷史裡找對應日期的版本。
