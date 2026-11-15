#!/usr/bin/env python3
"""Official-archive baseline + MIT-licensed BoatraceCSV updates -> 120-way model inference.

Only certified snapshots captured before the official deadline can produce paper-only
suggestions. A completed race is ALWAYS replay-only, regardless of EV.
"""
import argparse, base64, csv, datetime as dt, gzip, io, itertools, json, os, sys, time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import joblib

VENUES=['桐生','戸田','江戸川','平和島','多摩川','浜名湖','蒲郡','常滑','津','三国','びわこ','住之江','尼崎','鳴門','丸亀','児島','宮島','徳山','下関','若松','芦屋','福岡','唐津','大村']
BASE='https://boatracecsv.github.io/data/'
PERMS=list(itertools.permutations(range(1,7),3))
FEATURES=['racer_all_win_rate','racer_all_top3_rate','racer_venue_win_rate','racer_venue_top3_rate','racer_boat_win_rate','racer_boat_top3_rate','racer_30d_win_rate','racer_30d_top3_rate','motor_60d_win_rate','motor_60d_top3_rate','motor_prior_valid','exhibition_time_pre','exhibition_st','entry_course_pre','wind_speed_m_pre','wave_cm_pre','tilt_pre','cycle_prior_runs','cycle_prior_top2_mean','cycle_prior_exh_mean','last5_prior_runs','last5_prior_top2_mean','last5_prior_exh_mean','stint_prior_runs','stint_prior_top2_mean','stint_prior_exh_mean','last_stint_exh','stint_last_exh_change']
JST=dt.timezone(dt.timedelta(hours=9))


def csvday(kind,date,root=None,required=False):
    key=f'{kind}/{date:%Y/%m/%d}.csv'
    if root is not None:
        p=Path(root)/key
        if not p.exists():
            if required:raise FileNotFoundError(str(p))
            return []
        raw=p.read_bytes()
    else:
        url=BASE+key
        try:
            with urlopen(Request(url,headers={'User-Agent':'boat-ai-personal-analysis/1.0'}),timeout=20) as resp:
                raw=resp.read()
        except HTTPError as e:
            if e.code==404 and not required:return []
            raise RuntimeError(f'{kind} {date}: HTTP {e.code}') from e
        except URLError as e:
            if not required:return []
            raise RuntimeError(f'{kind} {date}: network failure') from e
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    return rows


def dateparse(s):
    try:return dt.date.fromisoformat(str(s))
    except (ValueError,TypeError):return None


def number(v):
    try:
        n=float(str(v).strip())
        return n if np.isfinite(n) else np.nan
    except (ValueError,TypeError):return np.nan


def mean(a):
    a=[float(x) for x in a if pd.notna(x)]
    return float(np.mean(a)) if a else np.nan


def pct(n,num):return float(num/n) if n else np.nan


def rate_from_counts(a,i):return pct(a[0],a[i]) if a and a[0] else np.nan


def snapshot(path):
    # Model data is base64-encoded gzip so GitHub connector can store it as UTF-8.
    return json.loads(gzip.decompress(base64.b64decode(Path(path).read_text().strip())).decode('utf-8'))


def get_by_code(rows,key):
    found=[r for r in rows if r.get('レースコード')==key]
    if len(found)!=1:raise ValueError(f'Expected exactly one {key} row, got {len(found)}')
    return found[0]


def datetime_jst(s):
    stamp=dt.datetime.fromisoformat(str(s))
    if stamp.tzinfo is None:raise ValueError('Unverified timezone')
    return stamp.astimezone(JST)


def recent_updates(start,end,root=None,workers=10):
    if end<start:return {}
    days=[start+dt.timedelta(days=i) for i in range((end-start).days+1)]
    tasks=[(k,d) for d in days for k in ('programs/race_cards','results/realtime','previews/tkz')]
    gathered={}
    def fetch(item):
        k,d=item
        try:return (k,d),csvday(k,d,root=root)
        except Exception:return (k,d),[]
    with ThreadPoolExecutor(max_workers=max(1,min(workers,20))) as pool:
        for key,value in pool.map(fetch,tasks):gathered[key]=value
    return gathered


def history_deltas(gathered,cutoff):
    racers=[];motors=[]
    for (k,day),cards in sorted(gathered.items(),key=lambda z:z[0][1]):
        if k!='programs/race_cards':continue
        results={r.get('レースコード'):r for r in gathered.get(('results/realtime',day),[])}
        tkz={r.get('レースコード'):r for r in gathered.get(('previews/tkz',day),[])}
        for card in cards:
            key=card.get('レースコード');res=results.get(key)
            if not res:continue
            finish={}
            for rank in range(1,7):
                boat=number(res.get(f'{rank}着_艇番'))
                if pd.notna(boat):finish[int(boat)]=rank
            if len(finish)!=6:continue
            exhibition=tkz.get(key)
            ex=[]
            if exhibition:
                ex=[number(exhibition.get(f'艇{b}_展示タイム')) for b in range(1,7)]
            avg=mean(ex) if len(ex)==6 and all(pd.notna(z) for z in ex) else np.nan
            venue=VENUES[int(card['レース場コード'])-1]
            for b in range(1,7):
                rid=number(card.get(f'艇{b}_登録番号'))
                motor=number(card.get(f'艇{b}_モーター番号'))
                if pd.isna(rid) or pd.isna(motor):continue
                racer=[day.isoformat(),str(int(rid)),venue,b,finish[b]]
                racers.append(racer)
                exrel=round(float(ex[b-1]-avg),5) if pd.notna(avg) else None
                motors.append([day.isoformat(),venue,int(motor),int(rid),finish[b],exrel,int(str(card['レース回']).rstrip('R'))])
    return racers,motors


def race_meeting_day(title_row):
    s=str(title_row.get('日次',''))
    if '初' in s and '日' in s:return 1
    for n,forms in enumerate(('１1一','２2二','３3三','４4四','５5五','６6六','７7七'),1):
        if any(c in s for c in forms):return n
    return None


def calculate(date,venue_code,race,base_dir,model_dir,out_dir,source_root=None,lookback_workers=12):
    if not (1<=venue_code<=24 and 1<=race<=12):raise ValueError('venue 1..24, race 1..12')
    if date<dt.date(2026,11,1):raise ValueError('baseline starts 2026-10-31; replay after this date only')
    name=VENUES[venue_code-1];code=f'{date:%Y%m%d}{venue_code:02d}{race:02d}'
    kinds=['programs/race_cards','programs/title','programs/motor_stats','previews/tkz','previews/stt','previews/sui','previews/od3']
    today={k:csvday(k,date,root=source_root,required=k not in ['programs/title']) for k in kinds}
    cards=get_by_code(today['programs/race_cards'],code)
    ts=[get_by_code(today[k],code) for k in ('previews/tkz','previews/stt','previews/sui','previews/od3')]
    t,st,weather,odds=ts
    close=dt.datetime.combine(date,dt.time.fromisoformat(t['締切時刻']),JST)
    obs=[datetime_jst(z['取得日時']) for z in ts]
    if any(x>close for x in obs):raise ValueError('Post-cutoff preview is not allowed')
    odds_values={c:number(odds.get('3連単_'+'-'.join(map(str,c)))) for c in PERMS}
    if any(pd.isna(v) or v<=1 for v in odds_values.values()):raise ValueError('Full valid 120-way odds unavailable')
    # Motor generation verified against current-period snapshots; ignore old-cycle historical IDs.
    motor_starts={}
    for row in today['programs/motor_stats']:
        if str(row.get('場コード','')).zfill(2)!=f'{venue_code:02d}':continue
        no=number(row.get('モーター番号'))
        if pd.notna(no):motor_starts[int(no)]=str(row.get('モーター期起算日',''))
    baseline=Path(base_dir)
    racers0=snapshot(baseline/'racer_snapshot.gz.b64')
    motors0=snapshot(baseline/'motor_snapshot.gz.b64')
    start=dateparse(racers0['asof'])+dt.timedelta(days=1)
    gathered=recent_updates(start,date-dt.timedelta(days=1),source_root,workers=lookback_workers)
    newer_racers,newer_motors=history_deltas(gathered,date)
    new_by_racer={};new_by_motor={}
    for r in newer_racers:new_by_racer.setdefault(r[1],[]).append(r)
    for m in newer_motors:new_by_motor.setdefault((m[1],m[2]),[]).append(m)
    # Existing last30 has date+id+venue+boat+finish, older than 30d is removed by cutoff.
    prior30={}
    for r in racers0['last30']+newer_racers:
        d=dateparse(r[0])
        if d and date-dt.timedelta(days=30)<=d<date:prior30.setdefault(r[1],[]).append(r)
    title=today['programs/title']
    title=[z for z in title if z.get('レースコード')==code]
    dayn=race_meeting_day(title[0]) if title else None
    entries=[];audit=[]
    for b in range(1,7):
        rid=int(number(cards[f'艇{b}_登録番号']))
        motor=int(number(cards[f'艇{b}_モーター番号']))
        gen=motor_starts.get(motor)
        if not gen:raise ValueError(f'No verified motor generation for {name} motor {motor}')
        gen_date=dateparse(gen)
        if gen_date is None:raise ValueError(f'Invalid motor generation date: {gen}')
        base=motors0['motor'].get(f'{name}|{motor}',{})
        base_cycle=dateparse(base.get('cycle',''))
        earlier=[]
        if base_cycle==gen_date:
            earlier=[[x[0],x[1],x[2],x[3],x[4]] for x in base.get('runs',[]) if dateparse(x[0]) and dateparse(x[0])>=gen_date]
        delta=[[x[0],x[3],x[4],x[5],x[6]] for x in new_by_motor.get((name,motor),[]) if dateparse(x[0])>=gen_date]
        records=sorted(earlier+delta,key=lambda r:(r[0],r[4]))
        visits=new_by_racer.get(str(rid),[])
        rbase=racers0['racer'].get(str(rid))
        if not rbase:raise ValueError('New racer without historical baseline; cannot make trained-model-equivalent features')
        def counts(filterfn):
            base_value=filterfn(rbase,True)
            delta_value=[z for z in visits if filterfn(z,False)]
            return [base_value[0]+len(delta_value),base_value[1]+sum(x[4]==1 for x in delta_value),base_value[2]+sum(x[4]<=3 for x in delta_value)]
        allv=counts(lambda z,old:z['all'] if old else True)
        venuev=counts(lambda z,old:z['venue'].get(name,[0,0,0]) if old else z[2]==name)
        boatv=counts(lambda z,old:z['boat'].get(str(b),[0,0,0]) if old else z[3]==b)
        recent=prior30.get(str(rid),[])
        last60=[z for z in records if dateparse(z[0])>=date-dt.timedelta(days=60)]
        last5=records[-5:]
        # Pre-race meeting history on official race card, only prior days to avoid accidental same-day leakage.
        meeting=[]
        if dayn:
            for d in range(1,dayn):
                for slot in (1,2):
                    f=f'艇{b}_節D{d}走{slot}_'
                    rno=number(cards.get(f+'R番号'))
                    rank=number(cards.get(f+'着順'))
                    if pd.notna(rno) and pd.notna(rank) and 1<=rank<=6:
                        meeting.append((d,int(rno),int(rank)))
        session_num=len(meeting)
        # Slot results indicate previous race performance, but old exhibition deltas require matching archived records.
        meeting_exhs=[]
        for d,rno,_ in meeting:
            prevdate=date-dt.timedelta(days=dayn-d) if dayn else date
            match=[z for z in records if z[0]==prevdate.isoformat() and z[4]==rno and z[1]==rid]
            if match:meeting_exhs.append(match[-1][3])
        entry={'date':date.isoformat(),'venue':name,'race':race,'boat':b,'racer_id':rid,'motor':motor,
            'racer_all_win_rate':rate_from_counts(allv,1),'racer_all_top3_rate':rate_from_counts(allv,2),
            'racer_venue_win_rate':rate_from_counts(venuev,1),'racer_venue_top3_rate':rate_from_counts(venuev,2),
            'racer_boat_win_rate':rate_from_counts(boatv,1),'racer_boat_top3_rate':rate_from_counts(boatv,2),
            'racer_30d_win_rate':mean([z[4]==1 for z in recent]),'racer_30d_top3_rate':mean([z[4]<=3 for z in recent]),
            'motor_60d_win_rate':mean([z[2]==1 for z in last60]),'motor_60d_top3_rate':mean([z[2]<=3 for z in last60]),
            'motor_prior_valid':len(records),
            'exhibition_time_pre':number(t.get(f'艇{b}_展示タイム')),'exhibition_st':number(st.get(f'艇{b}_スタート展示')),
            'entry_course_pre':number(st.get(f'艇{b}_コース')),'wind_speed_m_pre':number(weather.get('風速(m)')),
            'wave_cm_pre':number(weather.get('波の高さ(cm)')),'tilt_pre':number(t.get(f'艇{b}_チルト')),
            'cycle_prior_runs':len(records),'cycle_prior_top2_mean':mean([z[2]<=2 for z in records]),
            'cycle_prior_exh_mean':mean([z[3] for z in records]),'last5_prior_runs':len(last5),
            'last5_prior_top2_mean':mean([z[2]<=2 for z in last5]),'last5_prior_exh_mean':mean([z[3] for z in last5]),
            'stint_prior_runs':session_num,'stint_prior_top2_mean':mean([z[2]<=2 for z in meeting]),
            'stint_prior_exh_mean':mean(meeting_exhs),'last_stint_exh':meeting_exhs[-1] if meeting_exhs else np.nan,
            'stint_last_exh_change':meeting_exhs[-1]-meeting_exhs[-2] if len(meeting_exhs)>=2 else np.nan,
            'cutoff_jst':close.isoformat(),'snapshot_jst':max(obs).isoformat(),'motor_cycle_start':gen_date.isoformat()}
        entries.append(entry)
        audit.append({'boat':b,'racer_id':rid,'motor':motor,'cycle_source':gen,'cycle_prior_runs':len(records),
                      'recent_racer_runs':len(recent),'meeting_prior_runs':session_num,
                      'meeting_relative_exhibition_n':len(meeting_exhs),'base_motor_cycle_matches_source':base_cycle==gen_date})
    df=pd.DataFrame(entries)
    model_root=Path(model_dir)
    models=[joblib.load(model_root/f'with_motor_rank{i}.joblib') for i in (1,2,3)]
    declared=list(models[0]['features'])
    if declared!=FEATURES or any(list(z['features'])!=FEATURES for z in models):raise ValueError('Model schema mismatch')
    X=df[FEATURES].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    s=np.maximum(np.column_stack([z['model'].predict_proba(X)[:,1] for z in models]),1e-12)
    s[:,0]/=s[:,0].sum()
    probs=[]
    for a,b,c in PERMS:
        i,j,k=a-1,b-1,c-1
        probs.append(s[i,0]*(s[j,1]/(s[:,1].sum()-s[i,1]))*(s[k,2]/(s[:,2].sum()-s[i,2]-s[j,2])))
    tmp=json.loads((model_root/'学習検証結果.json').read_text(encoding='utf-8'))
    temperature=float(tmp['with_motor']['calibration_temperature'])
    p=np.maximum(np.array(probs),1e-12)**(1/temperature);p/=p.sum()
    outcome=[]
    for combo,prob in zip(PERMS,p):
        odds_value=odds_values[combo]
        outcome.append({'trifecta':'-'.join(map(str,combo)),'probability':float(prob),
                        'observed_odds':float(odds_value),'estimated_roi_proxy_pct':float(prob*odds_value*100)})
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    df.to_csv(out/'features6.csv',index=False,encoding='utf-8-sig')
    pred=pd.DataFrame(outcome).sort_values('estimated_roi_proxy_pct',ascending=False)
    pred.to_csv(out/'predictions120.csv',index=False,encoding='utf-8-sig')
    now=dt.datetime.now(JST)
    current=(now<close-dt.timedelta(minutes=1) and date==now.date())
    # The extracted motor periods are confirmed vs current motor_stats, but daily updates must be complete.
    days_total=(date-start).days
    result_day_count=sum(1 for day in (start+dt.timedelta(days=i) for i in range(days_total)) if gathered.get(('results/realtime',day)))
    # Missing race results on legitimate no-race days are fine, but missing downloads are independently reported.
    downloaded=len([1 for (kind,_),v in gathered.items() if kind=='results/realtime' and v]);
    has_daily_gap=any(not gathered.get(('programs/race_cards',start+dt.timedelta(days=i))) or not gathered.get(('results/realtime',start+dt.timedelta(days=i))) for i in range(days_total))
    runner_coverage=X.notna().sum(axis=1).tolist()
    # Opt for safe PAPER_SKIP if any source cannot be verified, rather than treating a model's missing values as zero.
    source_ok=(not has_daily_gap and len(today['programs/motor_stats'])>0 and dayn is not None and all(len(a['cycle_source'])>0 for a in audit))
    # Structural NaNs (e.g. no previous meeting) are legitimate; missing baseline racer counts are rejected above.
    missing=sorted({k for k in FEATURES if df[k].isna().any()})
    status='PAPER_ONLY_CANDIDATES' if current and source_ok else 'REPLAY_OR_UNVERIFIED_NO_BETS'
    candidates=pred[pred.estimated_roi_proxy_pct>=120].head(3) if status=='PAPER_ONLY_CANDIDATES' else pred.iloc[0:0]
    candidates.to_csv(out/'paper_candidates.csv',index=False,encoding='utf-8-sig')
    manifest={'date':date.isoformat(),'venue':name,'venue_code':venue_code,'race':race,'race_code':code,
              'status':status,'preclose_snapshot_asof_jst':max(obs).isoformat(),'deadline_jst':close.isoformat(),
              'model_ran':True,'probability_sum':float(p.sum()),'estimated_inputs_present':int(X.notna().sum().sum()),
              'total_model_inputs':int(X.size),'structurally_missing_fields':missing,
              'all120_odds':True,'history_cutoff':racers0['asof'],'days_updated':days_total,
              'downloaded_result_days':downloaded,'missing_published_result_days':has_daily_gap,
              'motor_sources':audit,'paper_candidate_count':len(candidates),
              'note':'Historical replays do not count as live bets. EV is a calibrated model estimate, not a guarantee. No real-money betting.'}
    (out/'report.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
    return manifest

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--date',required=True);a.add_argument('--venue',required=True,type=int);a.add_argument('--race',required=True,type=int)
    a.add_argument('--snapshots',default=str(Path(__file__).parent/'data'))
    a.add_argument('--models',default=str(Path(__file__).parent/'model'))
    a.add_argument('--out',default='boat-ai/runtime/auto_out')
    a.add_argument('--offline-source-root',help='For deterministic tests only')
    a.add_argument('--workers',type=int,default=12)
    x=a.parse_args();calculate(dateparse(x.date),x.venue,x.race,x.snapshots,x.models,x.out,x.offline_source_root,x.workers)