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
from venue_context import adjust_120, context as venue_context
from source_fetch import fetch_csv, SourceUnavailable, check_upstream_card, fetch_official_card, official_txt, parse_official_preview, official_motor_cycle, official_race_title
from screenshot_input import read_screenshot, overlay_screenshot, odds_coverage
from course_adjust import rescore as rescore_course, report as course_adjust_report

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
        try:
            rows,origin=fetch_csv(kind,date)
            return rows
        except SourceUnavailable:
            if not required:return []
            raise
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


def calculate(date,venue_code,race,base_dir,model_dir,out_dir,source_root=None,lookback_workers=12,screenshot_path=None):
    if not (1<=venue_code<=24 and 1<=race<=12):raise ValueError('venue 1..24, race 1..12')
    if date<dt.date(2026,11,1):raise ValueError('baseline starts 2026-10-31; replay after this date only')
    name=VENUES[venue_code-1];code=f'{date:%Y%m%d}{venue_code:02d}{race:02d}'
    screenshot=read_screenshot(screenshot_path,date,venue_code,race)
    kinds=['programs/race_cards','programs/title','programs/motor_stats','previews/tkz','previews/stt','previews/sui','previews/od3']
    today={}
    for k in kinds:
        try:
            today[k]=csvday(k,date,root=source_root,required=k!='programs/title')
            if k=='programs/title' and not today[k] and source_root is None:
                try:
                    today[k]=[official_race_title(date,venue_code,race)]
                    print(f'OFFICIAL_FALLBACK: meeting title/deadline for {code}')
                except (ValueError,HTTPError,URLError,TimeoutError,OSError) as title_error:
                    print(f'OPTIONAL_TITLE_UNAVAILABLE: {type(title_error).__name__}: {title_error}')
        except SourceUnavailable as e:
            if screenshot and k=='previews/od3' and k not in screenshot['previews']:
                today[k]=[]
                print(f'NO_SCREENSHOT_ODDS: probability only for {code}')
                continue
            if screenshot and k in ('previews/sui','previews/od3') and k in screenshot['previews']:
                today[k]=[]
                print(f'SCREENSHOT_FALLBACK: {k} for {code}')
                continue
            if screenshot and k in ('previews/tkz','previews/stt') and k in screenshot['previews']:
                fields=screenshot['previews'][k]
                needed=('艇1_展示タイム','艇6_展示タイム','艇1_チルト','艇6_チルト') if k=='previews/tkz' else ('艇1_スタート展示','艇6_スタート展示','艇1_コース','艇6_コース')
                if all(field in fields for field in needed):
                    today[k]=[]
                    print(f'SCREENSHOT_FALLBACK: complete {k} for {code}')
                    continue
            if source_root is None and k=='programs/race_cards':
                try:
                    today[k]=[fetch_official_card(date,venue_code,race)]
                    print(f'OFFICIAL_FALLBACK: {code} race card from verified Boatcast TSV')
                    continue
                except (ValueError,HTTPError,URLError,TimeoutError,OSError) as upstream_error:
                    raise RuntimeError(f'CSV multi-origin failure: {e}; official card fallback failed: {type(upstream_error).__name__} {upstream_error}') from upstream_error
            if source_root is None and k=='programs/motor_stats':
                try:
                    period=official_motor_cycle(date,venue_code)
                    cards=get_by_code(today['programs/race_cards'],code)
                    today[k]=[{'場コード':f'{venue_code:02d}','モーター番号':str(int(cards[f"艇{boat}_モーター番号"])),
                               'モーター期起算日':period} for boat in range(1,7)]
                    print(f'OFFICIAL_FALLBACK: verified motor cycle {period} for {code}')
                    continue
                except (ValueError,HTTPError,URLError,TimeoutError,OSError) as upstream_error:
                    raise RuntimeError(f'CSV multi-origin failure: {e}; official motor start fallback failed: {type(upstream_error).__name__} {upstream_error}') from upstream_error
            if source_root is None and k in ('previews/tkz','previews/stt'):
                try:
                    # The official racing schedule is needed to certify deadline;
                    # never create a guessed pre-close snapshot timestamp.
                    title=get_by_code(today['programs/title'],code)
                    cutoff=str(title['電話投票締切予定']).strip()
                    if len(cutoff)!=5 or cutoff[2]!=':':
                        raise ValueError('Missing verified race deadline')
                    raw=official_txt(k.split('/')[-1],date,venue_code,race)
                    observed=dt.datetime.now(JST)
                    today[k]=[parse_official_preview(raw,k.split('/')[-1],date,venue_code,race,cutoff,observed)]
                    print(f'OFFICIAL_FALLBACK: {k} for {code} captured {observed.isoformat()}')
                    continue
                except (ValueError,HTTPError,URLError,TimeoutError,OSError) as upstream_error:
                    raise RuntimeError(f'CSV multi-origin failure: {e}; official preview fallback failed: {type(upstream_error).__name__} {upstream_error}') from upstream_error
            raise RuntimeError(f'CSV multi-origin failure: {e}') from e
    cards=get_by_code(today['programs/race_cards'],code)
    if screenshot:
        title_rows=[z for z in today['programs/title'] if z.get('レースコード')==code]
        if title_rows and ':' in str(title_rows[0].get('電話投票締切予定','')):
            verified_cutoff=str(title_rows[0]['電話投票締切予定'])
        else:
            verified_cutoff=str(screenshot.get('cutoff',''))
        if len(verified_cutoff)!=5 or verified_cutoff[2]!=':':
            raise ValueError('Screenshot overlay needs a verified official or screenshot cutoff')
        official_close=dt.datetime.combine(date,dt.time.fromisoformat(verified_cutoff),JST)
        for kind in ('previews/tkz','previews/stt','previews/sui','previews/od3'):
            today[kind]=overlay_screenshot(today[kind],screenshot,kind,code,official_close)
    if not today['previews/od3'] and screenshot and 'previews/od3' not in screenshot['previews']:
        today['previews/od3']=[{'レースコード':code,'取得日時':screenshot['observed'].isoformat()}]
    ts=[get_by_code(today[k],code) for k in ('previews/tkz','previews/stt','previews/sui','previews/od3')]
    t,st,weather,odds=ts
    close=dt.datetime.combine(date,dt.time.fromisoformat(t['締切時刻']),JST)
    obs=[datetime_jst(z['取得日時']) for z in ts]
    if any(x>close for x in obs):raise ValueError('Post-cutoff preview is not allowed')
    odds_values={c:number(odds.get('3連単_'+'-'.join(map(str,c)))) for c in PERMS}
    visible_odds=sum(1 for v in odds_values.values() if pd.notna(v) and v>1)
    if visible_odds==0 and not screenshot:raise ValueError('No verified odds were available in screenshots or live data')
    if any(pd.notna(v) and v<=1 for v in odds_values.values()):raise ValueError('Invalid nonpositive/low odds')
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
    if dayn is None and title and '最終' in str(title[0].get('日次','')):
        # The official card contains D1..D7 past-race slots even on the final day.
        # Infer only from recorded finished earlier-day races, not today's outcomes.
        completed=[]
        for boat_slot in range(1,7):
            for d in range(1,8):
                for slot in (1,2):
                    f=f'艇{boat_slot}_節D{d}走{slot}_'
                    n=number(cards.get(f+'R番号'))
                    rank=number(cards.get(f+'着順'))
                    if pd.notna(n) and pd.notna(rank) and 1<=rank<=6:
                        completed.append(d)
        if completed and max(completed)<7:
            dayn=max(completed)+1
    entries=[];audit=[]
    for b in range(1,7):
        rid=int(number(cards[f'艇{b}_登録番号']))
        motor=int(number(cards[f'艇{b}_モーター番号']))
        gen=motor_starts.get(motor)
        provenance='direct motor_stats row'
        if not gen:
            # motor_stats lists only a subset of motors at some venues. Fall back
            # only if ALL listed motors in this venue share one generation, and
            # the saved motor's own historical generation matches that date.
            cohort={v for v in motor_starts.values() if dateparse(v) is not None}
            prior=str(motors0['motor'].get(f'{name}|{motor}',{}).get('cycle',''))
            if len(cohort)!=1 or prior not in cohort:
                raise ValueError(f'Motor generation unavailable or ambiguous: {name} {motor}')
            gen=next(iter(cohort))
            provenance='unique venue cohort + matching historical cycle (inferred)'
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
            if match:
                exh=number(match[-1][3])
                if pd.notna(exh):meeting_exhs.append(float(exh))
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
                      'meeting_relative_exhibition_n':len(meeting_exhs),'base_motor_cycle_matches_source':base_cycle==gen_date,'motor_generation_provenance':provenance})
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
    # Preserve the trained model's original probabilities for an auditable baseline.
    p_before_venue=p.copy()
    entry_courses={int(row.boat):int(row.entry_course_pre) for row in df.itertuples(index=False)
                   if pd.notna(row.entry_course_pre) and float(row.entry_course_pre).is_integer()}
    p=np.asarray(adjust_120(name,entry_courses,PERMS,p_before_venue),dtype=float)
    outcome=[]
    for combo,prob,base_prob in zip(PERMS,p,p_before_venue):
        odds_value=odds_values[combo]
        outcome.append({'trifecta':'-'.join(map(str,combo)),'probability':float(prob),
                        'observed_odds':float(odds_value) if pd.notna(odds_value) else np.nan,
                        'estimated_roi_proxy_pct':float(prob*odds_value*100) if pd.notna(odds_value) else np.nan,
                        'base_model_probability':float(base_prob),
                        'base_model_estimated_roi_pct':float(base_prob*odds_value*100) if pd.notna(odds_value) else np.nan})
    course_adjusted=False
    course_report=None
    course_path=Path(__file__).with_name('course_context.json')
    if course_path.is_file():
        course_data=json.loads(course_path.read_text(encoding='utf-8'))
        verified_entries=[{'boat':int(x['boat']),'racer_id':int(x['racer_id']),
                           'entry_course':int(x['entry_course_pre'])} for x in entries]
        updated=rescore_course(outcome,course_data,date,venue_code,race,verified_entries)
        if updated is not None:
            outcome=updated
            course_adjusted=True
            course_report=course_adjust_report(outcome)
            print(f'COURSE_ADJUSTED: verified racer-entry course data for {code}; model NOT retrained')
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    df.to_csv(out/'features6.csv',index=False,encoding='utf-8-sig')
    pred=pd.DataFrame(outcome).sort_values('estimated_roi_proxy_pct',ascending=False)
    pred.to_csv(out/'predictions120.csv',index=False,encoding='utf-8-sig')
    # Both user-requested top-3 rankings are always saved, including paper skips.
    def json_records(frame):
        return frame.astype(object).where(pd.notna(frame),None).to_dict(orient='records')
    rankings={'venue':name,'date':date.isoformat(),'race':race,
              'venue_adjustment':venue_context(name),
              'racer_course_adjustment':course_report if course_adjusted else None,
              'hit_rate_top3':json_records(pred.sort_values('probability',ascending=False).head(3)),
              'hit_rate_top5':json_records(pred.sort_values('probability',ascending=False).head(5)),
              'expected_return_top3':json_records(pred.dropna(subset=['estimated_roi_proxy_pct']).head(3)),
              'odds_coverage':visible_odds,'expected_return_scope':'all_120' if visible_odds==120 else 'screenshot_visible_only'}
    (out/'rankings.json').write_text(json.dumps(rankings,ensure_ascii=False,indent=2),encoding='utf-8')
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
    live_critical=['exhibition_time_pre','exhibition_st','entry_course_pre','wind_speed_m_pre','wave_cm_pre','tilt_pre']
    complete_live_inputs=bool(X[live_critical].notna().all().all())
    source_ok=(not course_adjusted and visible_odds==120 and complete_live_inputs and not has_daily_gap and len(today['programs/motor_stats'])>0 and dayn is not None and all(len(a['cycle_source'])>0 for a in audit))
    # Structural NaNs (e.g. no previous meeting) are legitimate; missing baseline racer counts are rejected above.
    missing=sorted({k for k in FEATURES if df[k].isna().any()})
    skip_reasons=[]
    if date!=now.date():skip_reasons.append('not the current race day')
    if now>=close-dt.timedelta(minutes=1):skip_reasons.append('too late: within 1 minute of cutoff or postclose')
    if has_daily_gap:skip_reasons.append('missing daily archived results or race card downloads')
    if visible_odds<120:skip_reasons.append(f'only {visible_odds}/120 screenshot-visible odds: no full-odds paper bets')
    if not complete_live_inputs:skip_reasons.append('missing verified screenshot/exhibition/weather model inputs')
    if course_adjusted:skip_reasons.append('experimental per-racer actual-course adjustment is not backtested: no paper bets')
    if not today['programs/motor_stats']:skip_reasons.append('no motor stats source')
    if dayn is None:skip_reasons.append('unverified meeting day')
    if any(not a['cycle_source'] for a in audit):skip_reasons.append('unverified motor replacement cycle')
    status='PAPER_ONLY_CANDIDATES' if current and source_ok else 'REPLAY_OR_UNVERIFIED_NO_BETS'
    candidates=pred[pred.estimated_roi_proxy_pct>=120].head(3) if status=='PAPER_ONLY_CANDIDATES' else pred.iloc[0:0]
    candidates.to_csv(out/'paper_candidates.csv',index=False,encoding='utf-8-sig')
    manifest={'date':date.isoformat(),'venue':name,'venue_code':venue_code,'race':race,'race_code':code,
              'status':status,'preclose_snapshot_asof_jst':max(obs).isoformat(),'deadline_jst':close.isoformat(),
              'model_ran':True,'probability_sum':float(p.sum()),'estimated_inputs_present':int(X.notna().sum().sum()),
              'total_model_inputs':int(X.size),'structurally_missing_fields':missing,
              'all120_odds':visible_odds==120,'odds_count':visible_odds,'expected_return_scope':'all_120' if visible_odds==120 else 'screenshot_visible_only',
              'screenshot_data_used':bool(screenshot),'history_cutoff':racers0['asof'],'days_updated':days_total,
              'downloaded_result_days':downloaded,'missing_published_result_days':has_daily_gap,
              'motor_sources':audit,'venue_context':venue_context(name),
              'venue_adjustment_backtested':False,'course_adjustment_applied':course_adjusted,
              'course_adjustment_details':course_report,'model_retrained':False,'skip_reasons':skip_reasons,
              'paper_candidate_count':len(candidates),
              'note':'The venue-adjusted probabilities are experimental and NOT backtested or calibrated. Historical replays never become paper bets. No real-money betting.'}
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
    a.add_argument('--screenshot-input',default='boat-ai/runtime/screenshot_input.json')
    x=a.parse_args()
    try:
        calculate(dateparse(x.date),x.venue,x.race,x.snapshots,x.models,x.out,x.offline_source_root,x.workers,x.screenshot_input)
    except (ValueError,RuntimeError,FileNotFoundError,KeyError,TimeoutError) as e:
        out=Path(x.out);out.mkdir(parents=True,exist_ok=True)
        report={'date':x.date,'venue_code':x.venue,'race':x.race,'status':'DATA_NOT_READY_SKIP',
                'model_ran':False,'paper_candidate_count':0,'reason':f'{type(e).__name__}: {e}',
                'note':'No prediction or bet was made. Check freshness and required source fields.'}
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/'paper_candidates.csv').write_text('trifecta,probability,observed_odds,estimated_roi_proxy_pct\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
