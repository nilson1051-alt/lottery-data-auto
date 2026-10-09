#!/usr/bin/env python3
"""同步台灣彩券近 36 個月官方 API 資料；驗證後才合併寫入。"""
from __future__ import annotations
import json, os, sys, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery"
OUT = Path("data")
MONTHS_BACK = max(1, min(36, int(os.getenv("MONTHS_BACK", "36"))))
GAMES = {
    "daily539": ("Daily539Result", "daily539Res", 39, 5, "539"),
    "lotto649": ("Lotto649Result", "lotto649Res", 49, 6, "大樂透"),
    "superlotto638": ("SuperLotto638Result", "superLotto638Res", 38, 6, "威力彩"),
}

def months_list(n):
    now = datetime.now()
    year, month = now.year, now.month
    result = []
    for _ in range(n):
        result.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return result

def api(endpoint, month):
    url = f"{BASE}/{endpoint}?period&month={month}&pageSize=31"
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "lottery-data-auto/1.0"})
    with urlopen(req, timeout=30) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    if obj.get("rtCode") != 0:
        raise RuntimeError(f"API 回傳錯誤：{endpoint} {month} rtCode={obj.get('rtCode')} {obj.get('rtMsg')}")
    return obj.get("content") or {}

def validate(game, d):
    period = str(d.get("period", "")).strip()
    date = str(d.get("lotteryDate", ""))[:10]
    raw = d.get("drawNumberSize")
    if not period or len(date) != 10 or not isinstance(raw, list):
        return None
    try:
        nums = [int(x) for x in raw]
    except (TypeError, ValueError):
        return None
    if game == "daily539":
        if len(nums) != 5 or len(set(nums)) != 5 or any(x < 1 or x > 39 for x in nums): return None
        return {"period": period, "date": date, "numbers": sorted(nums)}
    if game == "lotto649":
        if len(nums) != 7 or len(set(nums)) != 7 or any(x < 1 or x > 49 for x in nums): return None
        return {"period": period, "date": date, "numbers": sorted(nums[:6]), "special": nums[6]}
    if len(nums) != 7 or len(set(nums[:6])) != 6 or any(x < 1 or x > 38 for x in nums[:6]) or not (1 <= nums[6] <= 8):
        return None
    return {"period": period, "date": date, "first_zone": sorted(nums[:6]), "second_zone": nums[6]}

def main():
    OUT.mkdir(exist_ok=True)
    months = months_list(MONTHS_BACK)
    failures = []
    for game, (endpoint, key, _maxn, _count, label) in GAMES.items():
        path = OUT / f"{game}.json"
        try:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            if not isinstance(old, list): old = []
        except Exception:
            old = []
        fresh = []
        for month in months:
            try:
                content = api(endpoint, month)
                rows = content.get(key, [])
                if not isinstance(rows, list): raise RuntimeError(f"回傳欄位 {key} 格式不符")
                for row in rows:
                    item = validate(game, row)
                    if item: fresh.append(item)
                    else: print(f"警告：{label} {month} 有一筆資料未通過驗證，略過")
                time.sleep(0.15)
            except Exception as e:
                failures.append(f"{label} {month}: {e}")
                print(f"錯誤：{label} {month}: {e}")
        # 避免某次 API 失敗時把既有資料刪掉；只合併已驗證的新資料
        merged = {str(x.get("period")): x for x in old if isinstance(x, dict) and x.get("period")}
        for item in fresh: merged[item["period"]] = item
        result = sorted(merged.values(), key=lambda x: (x.get("date", ""), x.get("period", "")))
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        print(f"{label}: 新取得 {len(fresh)} 筆，保存總計 {len(result)} 筆")
    status = {
        "checked_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "months_requested": MONTHS_BACK,
        "status": "partial_failure" if failures else "success",
        "failures": failures,
    }
    (OUT / "sync-status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if failures:
        print("部分月份查詢失敗。既有資料已保留，但不能宣稱資料完整。")
        sys.exit(1)
    print("三種彩券 API 查詢完成；目前範圍為近 36 個月，不代表全歷史完整。")

if __name__ == "__main__":
    main()
