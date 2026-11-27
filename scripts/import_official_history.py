#!/usr/bin/env python3
"""One-time official history import. Fail closed; never alter existing draws on conflicts."""
import csv, io, json, re, time, zipfile, hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
API = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/ResultDownload"
GAMES = {"今彩539":("daily539",5,39), "大樂透":("lotto649",6,49), "威力彩":("superlotto638",6,38)}
def fetch(url):
    if urlparse(url).scheme != "https": raise ValueError("HTTPS required")
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent":"lottery-data-auto/2.6","Accept":"*/*"}),timeout=45) as r:
                data=r.read(100_000_001)
                if len(data)>100_000_000: raise ValueError("file too large")
                return data
        except Exception:
            if attempt==2: raise
            time.sleep(2**attempt)
def parse_date(s):
    parts=re.split(r"[-/]",s.strip().split(" ")[0])
    y,m,d=map(int,parts)
    if y<1911: y+=1911
    return date(y,m,d).isoformat()
def validate(game,item):
    period=item["period"]
    if not re.fullmatch(r"\d{9}",period): raise ValueError(f"invalid period {period}")
    d=date.fromisoformat(item["date"])
    if int(period[:3])!=d.year-1911: raise ValueError(f"year mismatch {item}")
    n,limit=next((n,limit) for _,(g,n,limit) in GAMES.items() if g==game)
    nums=item["first_zone" if game=="superlotto638" else "numbers"]
    if len(nums)!=n or len(set(nums))!=n or any(type(x)!=int or not 1<=x<=limit for x in nums): raise ValueError(f"invalid numbers {item}")
    if game=="lotto649" and (not 1<=item["special"]<=49 or item["special"] in nums): raise ValueError(f"invalid special {item}")
    if game=="superlotto638" and not 1<=item["second_zone"]<=8: raise ValueError(f"invalid second zone {item}")
    return item
def parse_zip(blob,year):
    out={}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for f in z.infolist():
            name=Path(f.filename.replace("\\","/")).name
            variants=[name]
            if not f.flag_bits & 0x800:
                for enc in ("cp950","big5","utf-8","gb18030"):
                    try: variants.append(name.encode("cp437").decode(enc))
                    except (UnicodeError,LookupError): pass
            print(f"ZIP {year}: {variants!r}",flush=True)
            for label,(game,n,limit) in GAMES.items():
                if not any(label in v and v.lower().endswith(".csv") for v in variants): continue
                if game in out: raise ValueError(f"duplicate CSV {year} {game}")
                raw=z.read(f)
                for enc in ("utf-8-sig","cp950","big5"):
                    try: content=raw.decode(enc); break
                    except UnicodeDecodeError: continue
                else: raise ValueError(f"unknown encoding {name}")
                rows={}
                for row in csv.DictReader(io.StringIO(content)):
                    row={str(k).strip():v for k,v in row.items() if k is not None}
                    if not any(v and v.strip() for v in row.values()): continue
                    p=str(int(row["期別"])).zfill(9)
                    d=parse_date(row["開獎日期"])
                    if int(d[:4])!=year: raise ValueError(f"wrong archive year {p}")
                    nums=sorted(int(row[f"獎號{i}"]) for i in range(1,n+1))
                    item={"period":p,"date":d}
                    if game=="superlotto638": item.update(first_zone=nums,second_zone=int(row["第二區"]))
                    else:
                        item["numbers"]=nums
                        if game=="lotto649": item["special"]=int(row["特別號"])
                    validate(game,item)
                    if p in rows: raise ValueError(f"duplicate archive period {game} {p}")
                    rows[p]=item
                out[game]=rows
    expected={g for _,(g,_,_) in GAMES.items() if year>=2008 or g!="superlotto638"}
    if not expected.issubset(out) or any(not out[g] for g in expected): raise ValueError(f"missing archive game {year}: {expected-set(out)}")
    return out
def main():
    root=Path("data")
    merged={g:{} for g,_,_ in GAMES.values()}
    report={"sources":[],"games":{}}
    for year in range(2007,date.today().year+1):
        meta=json.loads(fetch(f"{API}?year={year}"))
        if meta.get("rtCode")!=0 or not (meta.get("content") or {}).get("path"): raise ValueError(f"archive unavailable {year}")
        url=meta["content"]["path"]
        blob=fetch(url)
        archive=parse_zip(blob,year)
        report["sources"].append({"year":year,"url":url,"sha256":hashlib.sha256(blob).hexdigest(),"counts":{g:len(r) for g,r in archive.items()}})
        for g,rows in archive.items(): merged[g].update(rows)
        print(year,{g:len(r) for g,r in archive.items()},flush=True)
        time.sleep(.5)
    for g,rows in merged.items():
        old=json.loads((root/f"{g}.json").read_text(encoding="utf-8"))
        if not isinstance(old,list) or not old: raise ValueError(f"invalid existing {g}")
        seen=set()
        archive_periods=set(rows)
        for item in old:
            validate(g,item)
            p=item["period"]
            if p in seen: raise ValueError(f"duplicate existing {g} {p}")
            seen.add(p)
            if p in rows and rows[p]!=item: raise ValueError(f"conflict {g} {p}: archive={rows[p]} existing={item}")
            rows[p]=item
        result=sorted(rows.values(),key=lambda x:(x["date"],x["period"]))
        years={}
        for item in result:
            p=item["period"]; years.setdefault(p[:3],[]).append(int(p[3:]))
        for y,seq in years.items():
            if sorted(seq)!=list(range(1,max(seq)+1)): raise ValueError(f"missing periods {g} ROC {y}")
        expected_years=set(range(2008 if g=="superlotto638" else 2007,date.today().year+1))
        if {int(y)+1911 for y in years}!=expected_years: raise ValueError(f"missing years {g}")
        report["games"][g]={"count":len(result),"first":result[0],"last":result[-1],"existing_overlap":len(seen & archive_periods)}
        merged[g]=result
    report["checked_at_utc"]=datetime.now(timezone.utc).isoformat()
    report["status"]="success"
    for g,result in merged.items():
        (root/f"{g}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (root/"history-import-status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
