#!/usr/bin/env python3
"""Verified multi-origin BoatraceCSV reader.

Tries independent delivery paths (GitHub Pages, raw GitHub, jsDelivr), never
inventing data. Race-specific schema/completeness checks remain in auto_predict.
Boatcast is an upstream race-card provenance check ONLY; it is *not* an
interchangeable CSV representation and must not be passed to the trained model.
"""
import csv
import datetime as dt
import io
import os
import unicodedata
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ORIGINS = (
    "https://boatracecsv.github.io/data/",
    "https://raw.githubusercontent.com/BoatraceCSV/boatracecsv.github.io/main/data/",
    "https://cdn.jsdelivr.net/gh/BoatraceCSV/boatracecsv.github.io@main/data/",
)
# Guard against accidentally accepting an HTML error page returned as HTTP 200.
REQUIRED_COLUMNS = {
    "programs/race_cards": ("レースコード", "艇1_登録番号", "艇6_登録番号"),
    "programs/title": ("レースコード", "電話投票締切予定"),
    "programs/motor_stats": ("場コード", "モーター番号"),
    "previews/tkz": ("レースコード", "取得日時", "艇1_展示タイム"),
    "previews/stt": ("レースコード", "取得日時"),
    "previews/sui": ("レースコード", "取得日時"),
    "previews/od3": ("レースコード", "取得日時", "3連単_1-2-3"),
    "results/realtime": ("レースコード",),
    "results/payouts": ("レースコード", "3連単_組番"),
}

class SourceUnavailable(RuntimeError):
    pass

def decode_csv(raw, kind):
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("No CSV header")
    needed = REQUIRED_COLUMNS.get(kind, ("レースコード",))
    if not all(key in reader.fieldnames for key in needed):
        raise ValueError("Unexpected CSV schema, missing " + ",".join(set(needed)-set(reader.fieldnames)))
    rows = list(reader)
    if not rows:
        raise ValueError("Empty CSV data")
    return rows

def fetch_csv(kind, date, opener=urlopen, origins=ORIGINS):
    date = dt.date.fromisoformat(str(date)) if not isinstance(date, dt.date) else date
    rel = f"{kind}/{date:%Y/%m/%d}.csv"
    failures = []
    for origin in origins:
        url = origin + rel
        try:
            req = Request(url, headers={"User-Agent": "boat-ai-public-model/1.1", "Accept": "text/csv,*/*"})
            with opener(req, timeout=8) as response:
                raw = response.read()
            return decode_csv(raw,kind), origin
        except (HTTPError, URLError, TimeoutError, ValueError, UnicodeError, OSError) as exc:
            failures.append(f"{origin.split('/')[2]}: {type(exc).__name__} {getattr(exc,'code',str(exc))}")
    raise SourceUnavailable(f"{kind} {date}: all {len(origins)} delivery paths failed: " + " | ".join(failures))

def boatcast_race_card_url(date, venue, race):
    date = dt.date.fromisoformat(str(date)) if not isinstance(date,dt.date) else date
    if not (1<=int(venue)<=24 and 1<=int(race)<=12):
        raise ValueError("Invalid venue/race")
    jo=str(int(venue)).zfill(2)
    return f"https://race.boatcast.jp/hp_txt/{jo}/bc_j_str3_{date:%Y%m%d}_{jo}_{int(race):02d}.txt"

def check_upstream_card(date,venue,race,opener=urlopen):
    """Optional diagnostic: HTTP access to upstream Boatcast. No model feature substitution."""
    url=boatcast_race_card_url(date,venue,race)
    try:
        with opener(Request(url,headers={"User-Agent":"boat-ai-public-model/1.1"}),timeout=5) as response:
            raw=response.read()
        return {"source":"race.boatcast.jp","available":bool(raw),"bytes":len(raw),
                "usable_as_model_csv":False}
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        return {"source":"race.boatcast.jp","available":False,"error":type(e).__name__,
                "usable_as_model_csv":False}

def parse_boatcast_card(raw, date, venue, race):
    """Decode the upstream bc_j_str3 TSV into the exact BoatraceCSV card schema.

    This layout is documented by the BoatraceCSV race-card specification.
    Reject incomplete/shifted rows instead of substituting fake features.
    """
    date=dt.date.fromisoformat(str(date)) if not isinstance(date,dt.date) else date
    lines=raw.decode('utf-8-sig').splitlines()
    if len(lines)!=8 or lines[0].strip()!='data=' or lines[1].split()!=['1','6']:
        raise ValueError('Unexpected upstream race card header/length')
    def clean(x):
        return unicodedata.normalize('NFKC',str(x).strip()).replace('　',' ').strip()
    def numeric(x,decimal=False):
        t=clean(x)
        if not t:raise ValueError('Missing required upstream numeric field')
        try:return str(float(t)) if decimal else str(int(t))
        except ValueError:raise ValueError('Invalid upstream numeric field')
    code=f'{date:%Y%m%d}{int(venue):02d}{int(race):02d}'
    result={'レースコード':code,'レース日':date.isoformat(),'レース場コード':f'{int(venue):02d}','レース回':f'{int(race):02d}R'}
    for i,line in enumerate(lines[2:],1):
        cols=line.split(chr(9))
        if len(cols)<38:
            raise ValueError(f'Incomplete TSV boat {i}: only {len(cols)} columns')
        p=f'艇{i}_'
        result.update({
            p+'登録番号':numeric(cols[0]),p+'選手名':clean(cols[1]),
            p+'期別':clean(cols[2]),p+'年齢':numeric(cols[4]),
            p+'級別':clean(cols[5]),p+'賞除':clean(cols[6]),
            p+'F本数':clean(cols[7]) or '0',p+'L本数':clean(cols[8]) or '0',
            p+'全国平均ST':numeric(cols[9],True),
            p+'全国勝率':numeric(cols[10],True),p+'全国2連対率':numeric(cols[11],True),
            p+'全国3連対率':numeric(cols[12],True),
            p+'当地勝率':numeric(cols[13],True),p+'当地2連対率':numeric(cols[14],True),
            p+'当地3連対率':numeric(cols[15],True),
            p+'モーターフラグ':clean(cols[16]) or '0',
            p+'モーター番号':numeric(cols[17]),
            p+'モーター2連対率':numeric(cols[18],True),
            p+'モーター3連対率':numeric(cols[19],True),
            p+'ボートフラグ':clean(cols[20]) or '0',
            p+'ボート番号':numeric(cols[21]),
            p+'ボート2連対率':numeric(cols[22],True),
            p+'ボート3連対率':numeric(cols[23],True),
            p+'早見':clean(cols[24]).replace('R',''),
        })
        places=clean(cols[3]).split(':',1)
        if len(places)!=2:raise ValueError('Missing upstream racer branch/hometown')
        result[p+'支部'],result[p+'出身地']=places
        for slot in range(14):
            day=slot//2+1;run=slot%2+1
            prefix=f'{p}節D{day}走{run}_'
            record=clean(cols[25+slot]) if 25+slot<len(cols) else ''
            bits=['']*5 if record in ('','-') else record.split(',')
            if len(bits)!=5:raise ValueError(f'Malformed history slot boat {i} index {slot}')
            for label,val in zip(('R番号','進入','枠','ST','着順'),bits):
                val=val.strip()
                result[prefix+label]='' if val in ('-','') else val
        if not (1000<=int(result[p+'登録番号'])<=9999 and 1<=int(result[p+'モーター番号'])<=999):
            raise ValueError('Unrecognized racer or motor identifier')
    if len({result[f'艇{i}_登録番号'] for i in range(1,7)})!=6:
        raise ValueError('Duplicate upstream racer')
    return result

def fetch_official_card(date,venue,race,opener=urlopen):
    url=boatcast_race_card_url(date,venue,race)
    req=Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with opener(req,timeout=7) as response:
        raw=response.read()
    return parse_boatcast_card(raw,date,venue,race)

def official_txt(kind,date,venue,race=None,opener=urlopen):
    """Fetch known actual upstream Boatcast endpoints. Never guess missing odds."""
    date=dt.date.fromisoformat(str(date)) if not isinstance(date,dt.date) else date
    jo=f'{int(venue):02d}'
    known={"tkz":"bc_j_tkz","stt":"bc_j_stt","motor_start":"bc_mst"}
    if kind not in known:raise ValueError('Unsupported upstream endpoint')
    if kind=="motor_start":
        filename=f'bc_mst_{jo}.txt'
    else:
        if not (1<=int(race)<=12):raise ValueError('Race out of range')
        filename=f'{known[kind]}_{date:%Y%m%d}_{jo}_{int(race):02d}.txt'
    url=f'https://race.boatcast.jp/hp_txt/{jo}/{filename}'
    with opener(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=7) as response:
        return response.read()

def parse_official_preview(raw,kind,date,venue,race,close,observed):
    """Validate exact six-boat TSV then expose same keys as BoatraceCSV snapshots."""
    if kind not in ("tkz","stt"):raise ValueError('Unsupported preview kind')
    date=dt.date.fromisoformat(str(date)) if not isinstance(date,dt.date) else date
    lines=raw.decode('utf-8-sig').splitlines()
    if len(lines)!=8 or lines[0].strip()!='data=' or lines[1].strip()!='1':
        raise ValueError(f'Bad {kind} source header')
    if not observed.tzinfo or observed.date()!=date:
        raise ValueError('Preview must be obtained on race day with verified timezone')
    result={'レースコード':f'{date:%Y%m%d}{int(venue):02d}{int(race):02d}',
            'レース日':date.isoformat(),'レース場':f'{int(venue):02d}',
            'レース回':f'{int(race):02d}R','締切時刻':close,
            '取得日時':observed.isoformat()}
    names=set()
    if kind=="tkz":
        for boat,line in enumerate(lines[2:],1):
            fields=line.split(chr(9))
            if len(fields)<7:raise ValueError('Short official exhibition row')
            name=unicodedata.normalize('NFKC',fields[0]).strip()
            if not name or name in names:raise ValueError('Duplicate/missing exhibition racer')
            names.add(name)
            ex=float(fields[1])
            if not 6.0<=ex<=8.5:raise ValueError('Exhibition time outside plausible range')
            tilt=float(fields[6].replace(' ',''))
            weight=float(fields[4])
            result.update({f'艇{boat}_展示タイム':str(ex),f'艇{boat}_体重(kg)':str(weight),
                           f'艇{boat}_チルト':str(tilt)})
    else:
        seen_boats=set();seen_courses=set()
        for line in lines[2:]:
            fields=line.split(chr(9))
            if len(fields)<5:raise ValueError('Short official start-exhibition row')
            course=int(fields[0]);boat=int(fields[1])
            if not (1<=boat<=6 and 1<=course<=6) or boat in seen_boats or course in seen_courses:
                raise ValueError('Unverified entry courses')
            seen_boats.add(boat);seen_courses.add(course)
            # 4th column is average ST; 5th column is exhibition ST.
            st=fields[4].strip()
            if st.startswith('F'): st='-'+st[1:]
            if st.startswith('L') or not st:raise ValueError('Missing start-exhibition ST')
            val=float(st)
            if not -1<=val<=1:raise ValueError('Invalid exhibition ST')
            result.update({f'艇{boat}_コース':str(course),f'艇{boat}_スタート展示':str(val)})
        if seen_boats!=set(range(1,7)) or seen_courses!=set(range(1,7)):
            raise ValueError('Expected all six entry courses')
    return result
