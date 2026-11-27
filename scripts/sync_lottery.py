#!/usr/bin/env python3
"""v2.6 incremental sync: preserve all history; fail closed on incomplete or conflicting API data."""
from __future__ import annotations
import hashlib, json, os, re, sys, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from import_official_history import validate as validate_history

BASE = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery"
OUT = Path("data")
TZ = ZoneInfo("Asia/Taipei")
GAMES = {
    "daily539": ("Daily539Result", "daily539Res", 39, 5, 2007, {0,1,2,3,4,5}),
    "lotto649": ("Lotto649Result", "lotto649Res", 49, 6, 2007, {1,4}),
    "superlotto638": ("SuperLotto638Result", "superLotto638Res", 38, 6, 2008, {0,3}),
}
def month_index(d):
    return d.year*12+d.month-1
def month_name(i):
    return f"{i//12:04d}-{i%12+1:02d}"
def query_months(last, today, minimum=2):
    end=month_index(today)
    start=min(month_index(last),end-minimum+1)
    if start>end or end-start+1>36: raise ValueError("catch-up exceeds 36 months; run historical recovery")
    return [month_name(i) for i in range(start,end+1)]
def expected_date(game, now):
    # Routine schedule only; 23:00 cutoff allows official publishing time.
    d=now.date() if now.hour>=23 else now.date()-timedelta(days=1)
    while d.weekday() not in GAMES[game][5]:
        d-=timedelta(days=1)
    return d
def api(endpoint, month):
    url=f"{BASE}/{endpoint}?period&month={month}&pageSize=31"
    for attempt in range(3):
        try:
            req=Request(url,headers={"Accept":"application/json","User-Agent":"lottery-data-auto/2.6"})
            with urlopen(req,timeout=30) as resp: obj=json.load(resp)
            if obj.get("rtCode")!=0 or not isinstance(obj.get("content"),dict):
                raise ValueError(f"API invalid {endpoint} {month}: {obj.get('rtCode')}")
            return obj["content"]
        except Exception:
            if attempt==2: raise
            time.sleep(2**attempt)
def normalize(game,row,month,today):
    p=str(row["period"]).strip().zfill(9)
    d=date.fromisoformat(str(row["lotteryDate"])[:10])
    if d.isoformat()[:7]!=month or d>today: raise ValueError(f"out of range API date {game} {p} {d}")
    raw=row["drawNumberSize"]
    if not isinstance(raw,list) or any(not re.fullmatch(r"\d+",str(x)) for x in raw):
        raise ValueError(f"invalid API draw numbers {game} {p}")
    nums=[int(x) for x in raw]
    n=GAMES[game][3]
    if len(nums)!=n+(game!="daily539"): raise ValueError(f"wrong number count {game} {p}")
    item={"period":p,"date":d.isoformat()}
    if game=="superlotto638": item.update(first_zone=sorted(nums[:n]),second_zone=nums[n])
    else:
        item["numbers"]=sorted(nums[:n])
        if game=="lotto649": item["special"]=nums[n]
    return validate_history(game,item)
def index_rows(game,rows):
    if not isinstance(rows,list) or not rows: raise ValueError(f"missing or empty {game} history")
    result={}
    for row in rows:
        validate_history(game,row)
        p=row["period"]
        if p in result: raise ValueError(f"duplicate {game} {p}")
        result[p]=row
    return result
def validate_sequence(game,rows,today):
    years={}
    for row in rows:
        d=date.fromisoformat(row["date"])
        if d>today: raise ValueError(f"future history {game} {d}")
        p=row["period"]
        years.setdefault(d.year,[]).append(int(p[3:]))
    expected=set(range(GAMES[game][4],today.year+1))
    # At the beginning of a new year there may not yet be any draws.
    if today.month==1 and today.day<=7: expected.discard(today.year)
    if not expected.issubset(years) or set(years)-set(range(GAMES[game][4],today.year+1)):
        raise ValueError(f"historical years missing {game}")
    for y,seq in years.items():
        if sorted(seq)!=list(range(1,max(seq)+1)): raise ValueError(f"missing periods {game} {y}")
    chronological=sorted(rows,key=lambda x:x["period"])
    if [x["date"] for x in chronological]!=sorted(x["date"] for x in chronological):
        raise ValueError(f"nonchronological periods {game}")
def merge(game,old,fresh,months):
    result=dict(old)
    seen={}
    for item in fresh:
        p=item["period"]
        if p in seen: raise ValueError(f"duplicate API period {game} {p}")
        seen[p]=item
        if p in old and old[p]!=item: raise ValueError(f"official data conflict {game} {p}: stored={old[p]} API={item}")
        result[p]=item
    required={p for p,x in old.items() if x["date"][:7] in months}
    missing=required-set(seen)
    if missing: raise ValueError(f"API omitted existing periods {game}: {sorted(missing)[:10]}")
    return sorted(result.values(),key=lambda x:(x["date"],x["period"])),len(set(seen)-set(old)),len(required)
def encode(obj):
    return (json.dumps(obj,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
def atomic_write(path,data):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
def digest(data):
    return hashlib.sha256(data).hexdigest()
def main():
    now=datetime.now(TZ)
    status_path=OUT/"sync-status.json"
    previous={}
    reports={}
    pending={}
    stage="load previous status"
    try:
        previous=json.loads(status_path.read_text(encoding="utf-8"))
        if not isinstance(previous,dict): raise ValueError("invalid previous status")
        stage="load history baseline"
        baseline=json.loads((OUT/"history-import-status.json").read_text(encoding="utf-8"))
        if baseline.get("status")!="success": raise ValueError("history baseline not verified")
        minimum=int(os.getenv("MONTHS_BACK","2"))
        if not 2<=minimum<=36: raise ValueError("MONTHS_BACK must be 2..36")
        prior=previous if previous.get("status")=="success" else previous.get("last_success",{})
        for game,(endpoint,key,*_) in GAMES.items():
            stage=f"{game}: verify stored history"
            path=OUT/f"{game}.json"
            raw=path.read_bytes()
            old=index_rows(game,json.loads(raw))
            base=baseline["games"][game]
            if len(old)<base["count"] or min(old.values(),key=lambda x:x["period"])!=base["first"]:
                raise ValueError(f"history below verified baseline {game}")
            recorded=prior.get("games",{}).get(game,{}).get("sha256")
            if recorded and digest(raw)!=recorded: raise ValueError(f"stored hash mismatch {game}")
            validate_sequence(game,list(old.values()),now.date())
            last=max(date.fromisoformat(x["date"]) for x in old.values())
            months=query_months(last,now.date(),minimum)
            stage=f"{game}: fetch official API"
            fresh=[]
            for month in months:
                content=api(endpoint,month)
                rows=content.get(key)
                if not isinstance(rows,list): raise ValueError(f"missing API list {game} {month}")
                fresh.extend(normalize(game,r,month,now.date()) for r in rows)
                time.sleep(.15)
            stage=f"{game}: merge and verify"
            result,added,overlap=merge(game,old,fresh,months)
            validate_sequence(game,result,now.date())
            latest=date.fromisoformat(result[-1]["date"])
            due=expected_date(game,now)
            if latest<due: raise ValueError(f"possible missing latest draw {game}: {latest}, expected at least {due}")
            data=encode(result)
            pending[path]=data
            reports[game]={"count":len(result),"added":added,"overlap_verified":overlap,"months":months,"first":result[0],"last":result[-1],"sha256":digest(data),"expected_latest_minimum":due.isoformat()}
            print(f"{game}: added={added} total={len(result)} overlap={overlap} months={months}",flush=True)
        stage="publish validated files"
        for path,data in pending.items():
            if path.read_bytes()!=data: atomic_write(path,data)
        report={"schema_version":"2.6","checked_at_utc":datetime.now(timezone.utc).isoformat(),"status":"success","months_requested":minimum,"failures":[],"games":reports}
        atomic_write(status_path,encode(report))
    except Exception as exc:
        # Workflow commits only this failure report, never game JSON, on failure.
        last_success=previous if previous.get("status")=="success" else previous.get("last_success",{})
        report={"schema_version":"2.6","checked_at_utc":datetime.now(timezone.utc).isoformat(),"status":"failure","failures":[f"{stage}: {exc}"],"last_success":last_success}
        atomic_write(status_path,encode(report))
        print(report["failures"][0],file=sys.stderr,flush=True)
        return 1
    return 0
if __name__=="__main__":
    sys.exit(main())
