# 台灣彩券資料自動同步

此儲存庫保存大樂透、今彩539、威力彩的 JSON 開獎資料，並由 GitHub Actions 每日呼叫台灣彩券官方 API 查核、驗證與合併近 36 個月的資料。

## 檔案
- `scripts/sync_lottery.py`：呼叫官方 API、檢查資料格式與號碼範圍、按期別去重並合併。
- `.github/workflows/sync-lottery.yml`：每日排程（台灣時間約 06:30）及手動觸發入口。
- `data/daily539.json`：今彩539資料（首次執行後產生）。
- `data/lotto649.json`：大樂透資料（首次執行後產生）。
- `data/superlotto638.json`：威力彩資料（首次執行後產生）。
- `data/sync-status.json`：最近同步狀態與錯誤摘要。

## 資料來源
- 台灣彩券官方最新開獎結果：https://www.taiwanlottery.com/lotto/lotto_lastest_result/
- 官方歷史查詢：https://www.taiwanlottery.com/lotto/history/history_result/
- 官方年度資料下載：https://www.taiwanlottery.com/lotto/history/result_download/
- 官方 API：https://api.taiwanlottery.com/TLCAPIWeB/Lottery/

## 驗證規則
- 今彩539：5 個不同號碼，範圍 1–39。
- 大樂透：6 個不同主號及 1 個不重複特別號，範圍 1–49。
- 威力彩：第一區 6 個不同號碼，範圍 1–38；第二區 1–8。
- 以期別去重；API 查詢失敗時保留原資料，並在同步狀態記錄錯誤。
- 若某個月份的 API 請求失敗，該次 workflow 會以失敗狀態結束，不能宣稱該次資料完整。

## 重要限制
目前 workflow 只抓取近 36 個月的官方 API 資料，**尚未完成民國 96 年起的官方年度檔案全歷史批次匯入**。因此，第一次執行後的資料不可標示為完整歷史。下一階段需要加入官方年度檔下載／解析流程，並驗證每個年度檔的實際格式後，才能宣稱歷史已補齊。

這個儲存庫是公開的，僅保存公開開獎資料，不要放入 API token、密碼或其他秘密。歷史統計不保證提高中獎機率。
