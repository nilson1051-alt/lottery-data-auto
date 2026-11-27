#!/usr/bin/env python3
"""Descriptive historical statistics, version 2.6; no predictive claims."""
import json, math, hashlib, os
from collections import Counter
from itertools import combinations
from datetime import datetime, timezone
from pathlib import Path
from sync_lottery import index_rows, validate_sequence, encode, digest, TZ
CONFIG={"daily539":("numbers",39,400),"lotto649":("numbers",49,240),"superlotto638":("first_zone",38,None)}
def percentile(values,p):
    v=sorted(values)
    if not v:return None
    i=(len(v)-1)*p
    a=math.floor(i); b=math.ceil(i)
    return v[a]+(v[b]-v[a])*(i-a)
def structure(nums,maximum):
    n=sorted(nums)
    return {"odd":sum(x%2 for x in n),"small":sum(x<=maximum//2 for x in n),"sum":sum(n),"span":n[-1]-n[0],"ac":len({b-a for a,b in combinations(n,2)})-(len(n)-1),"adjacent_pairs":sum(b-a==1 for a,b in zip(n,n[1:])),"max_same_tail":max(Counter(x%10 for x in n).values())}
def statistics(draws,maximum,half_life=None,coverage=.65,recent=30,pairs=True):
    total=len(draws)
    if not total:raise ValueError("empty sample")
    history=Counter(); recent_counts=Counter(); pair_counts=Counter(); weighted=Counter(); skips={}
    for age,nums in enumerate(reversed(draws)):
        history.update(nums)
        if age<recent:recent_counts.update(nums)
        if pairs:pair_counts.update(combinations(sorted(nums),2))
        for n in nums:
            skips.setdefault(n,age)
            if half_life is not None:weighted[n]+=2**(-age/half_life)
    q={f"P{p}":percentile(list(skips.values()),p/100) for p in (30,70,85,90)}
    numbers={}
    for n in range(1,maximum+1):
        s=skips.get(n)
        numbers[str(n)]={"count":history[n],"frequency":history[n]/total,"recent_count":recent_counts[n],"recent_frequency":recent_counts[n]/min(total,recent),"skip":s,"ewma":weighted[n] if half_life is not None else None}
    hot=None; actual=None; top15=None
    if half_life is not None:
        rank=sorted(range(1,maximum+1),key=lambda n:(-weighted[n],n))
        top15=rank[:15]; hot=[]; acc=0; denom=sum(weighted.values())
        for n in rank:
            hot.append(n);acc+=weighted[n]
            if acc/denom>=coverage:break
        actual=acc/denom
    active=sorted(n for n,s in skips.items() if s<=q["P30"])
    semi=sorted(n for n,s in skips.items() if q["P30"]<s<q["P70"])
    cold=sorted(n for n,s in skips.items() if q["P70"]<=s<=q["P85"])
    extreme=sorted(n for n,s in skips.items() if s>=q["P90"])
    core=sorted(set(hot)&set(active)-set(extreme)) if hot is not None else None
    satellite=sorted((set(semi)|set(cold))-set(extreme)-set(core or []))
    lifts=None
    if pairs:
        lifts={f"{a}-{b}":{"count":pair_counts[a,b],"lift":total*pair_counts[a,b]/(history[a]*history[b]) if history[a]*history[b] else None} for a,b in combinations(range(1,maximum+1),2)}
    return {"sample_count":total,"recent_sample_count":min(total,recent),"half_life":half_life,"coverage_target":coverage if half_life is not None else None,"coverage_actual":actual,"numbers":numbers,"skip_percentiles":q,"skip_sample_count":len(skips),"hot":hot,"weighted_top15":top15,"active":active,"semi_active":semi,"moderate_cold":cold,"extreme_cold":extreme,"core":core,"satellite":satellite,"pair_lift":lifts,"lift_high_threshold":None}
def build(game,rows,source_hash):
    field,maximum,half=CONFIG[game]
    draws=[r[field] for r in rows]
    stats=statistics(draws,maximum,half)
    distributions={}
    for nums in draws:
        for k,v in structure(nums,maximum).items():distributions.setdefault(k,Counter())[v]+=1
    result={"schema_version":"2.6","game":game,"source_sha256":source_hash,"first":rows[0],"last":rows[-1],"main":stats,"structure_histograms":{k:dict(sorted(v.items())) for k,v in distributions.items()},"latest_structure":structure(draws[-1],maximum),"method":{"percentile":"linear interpolation across current known number skips","coverage_target":.65,"recent":30,"tie_break":"number ascending","lift_threshold":"not specified in original rules","interpretation":"descriptive only"}}
    if game=="superlotto638":result["second_zone"]=statistics([[r["second_zone"]] for r in rows],8,None,pairs=False)
    if game=="lotto649":result["special"]=statistics([[r["special"]] for r in rows],49,None,pairs=False)
    return result
def main():
    root=Path("data"); out=Path("stats"); out.mkdir(exist_ok=True)
    status=json.loads((root/"sync-status.json").read_text())
    if status.get("status")!="success" or status.get("schema_version")!="2.6":raise ValueError("verified sync required")
    pending={}; manifest={"schema_version":"2.6","status":"success","calculated_at_utc":datetime.now(timezone.utc).isoformat(),"sync_checked_at_utc":status["checked_at_utc"],"games":{}}
    for game in CONFIG:
        raw=(root/f"{game}.json").read_bytes(); h=digest(raw)
        report=status["games"][game]
        if h!=report["sha256"]:raise ValueError(f"source hash mismatch {game}")
        rows=json.loads(raw); index_rows(game,rows);validate_sequence(game,rows,datetime.now(TZ).date())
        if len(rows)!=report["count"] or rows[-1]!=report["last"]:raise ValueError(f"source report mismatch {game}")
        result=build(game,rows,h); payload=encode(result); path=out/f"{game}-stats.json";pending[path]=payload
        manifest["games"][game]={"count":len(rows),"last":rows[-1],"source_sha256":h,"stats_sha256":digest(payload),"path":str(path)}
        print(game,len(rows),"pairs",len(result["main"]["pair_lift"]),flush=True)
    pending[out/"manifest.json"]=encode(manifest)
    for path,payload in pending.items():
        tmp=path.with_suffix(".tmp");tmp.write_bytes(payload);tmp.replace(path)
if __name__=="__main__":main()
