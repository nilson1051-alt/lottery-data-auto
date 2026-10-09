# 台灣彩券歷史資料自動同步

這個儲存庫用來批次匯入並保存大樂透、今彩539、威力彩的歷史開獎資料，並以 GitHub Actions 定期同步新增期數。

## 資料來源
- 台灣彩券官方最新開獎結果：https://www.taiwanlottery.com/lotto/lotto_lastest_result/
- 官方歷史查詢：https://www.taiwanlottery.com/lotto/history/history_result/
- 官方年度資料下載：https://www.taiwanlottery.com/lotto/history/result_download/
- 官方 API（端點格式若有變化，必須在 workflow 日誌中明確失敗，不得寫入虛構資料）：https://api.taiwanlottery.com/TLCAPIWeB/Lottery/

## 設計原則
- 開獎資料以遊戲、期別為唯一識別鍵，先驗證後合併，防止重複。
- 官方資料抓取失敗時，不覆蓋已驗證的資料。
- 大樂透主號為 6 個 1–49 號碼及 1 個不重複特別號；539 為 5 個 1–39 號碼；威力彩為第一區 6 個 1–38 號碼及第二區 1 個 1–8 號碼。
- 初次批次匯入與日常增量更新分開執行。
- 這是公開資料儲存庫，不存放任何 API token 或其他秘密。
- 樂透抽獎是隨機事件，歷史統計不保證提高中獎率。

## 目前狀態
儲存庫已初始化；在自動排程首次成功執行前，不能視為歷史資料已補齊或已開始自動更新。
