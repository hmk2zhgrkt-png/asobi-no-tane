#!/usr/bin/env python3
"""Fetch only genuine publicly available race preview CSVs; keep an audit."""
import argparse,csv,datetime as dt,io,time,zipfile
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

ROOT="https://boatracecsv.github.io/data"
SOURCES={"stt":"previews/stt","sui":"previews/sui","tkz":"previews/tkz","od3":"previews/od3"}
def fetch(d,kind):
    url=f"{ROOT}/{SOURCES[kind]}/{d:%Y/%m/%d}.csv"
    for n in range(3):
        try:
            with urlopen(Request(url,headers={"User-Agent":"boat-history-research/1.0"}),timeout=25) as r: data=r.read()
            decoded=data.decode("utf-8-sig")
            rows=list(csv.reader(io.StringIO(decoded)))
            if not rows or "レースコード" not in rows[0]:return d,kind,"invalid",url,b"",0
            return d,kind,"ok" if len(rows)>1 else "empty",url,data,len(rows)-1
        except HTTPError as e:
            if e.code==404:return d,kind,"not_published",url,b"",0
            state=f"http_{e.code}"
        except (URLError,UnicodeError,TimeoutError,OSError) as e:state=str(e)[:100]
        time.sleep(n+1)
    return d,kind,"error:"+state,url,b"",0
def main():
    p=argparse.ArgumentParser();p.add_argument("--start",default="2025-11-01");p.add_argument("--end",default="2026-10-31");p.add_argument("--out",default="backfill.zip");p.add_argument("--workers",type=int,default=5);a=p.parse_args()
    start=dt.date.fromisoformat(a.start);end=dt.date.fromisoformat(a.end)
    if start>end or (end-start).days>430:raise SystemExit("Invalid date range")
    days=[start+dt.timedelta(days=i) for i in range((end-start).days+1)]
    jobs=[(d,k) for d in days for k in SOURCES]
    status=[]
    with zipfile.ZipFile(a.out,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        with ThreadPoolExecutor(max_workers=max(1,min(8,a.workers))) as ex:
            fut=[ex.submit(fetch,d,k) for d,k in jobs]
            for i,f in enumerate(as_completed(fut),1):
                d,k,s,url,data,n=f.result()
                if s=="ok":z.writestr(f"previews_{k}/{d.isoformat()}.csv",data)
                status.append([d.isoformat(),k,s,n,len(data),url])
                if i%100==0:print(f"{i}/{len(jobs)}",flush=True)
        buf=io.StringIO();w=csv.writer(buf);w.writerow(["date","kind","status","rows","bytes","url"]);w.writerows(sorted(status))
        z.writestr("取得監査.csv",buf.getvalue().encode("utf-8-sig"))
    good=sum(s[2]=="ok" for s in status)
    errors=sum(s[2].startswith("error") for s in status)
    print(f"Verified {good} real CSVs; {errors} errors; file {a.out}",flush=True)
    if errors:raise SystemExit(2)
if __name__=="__main__":main()
