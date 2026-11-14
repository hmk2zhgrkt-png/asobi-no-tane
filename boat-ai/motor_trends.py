#!/usr/bin/env python3
"""Calculate pre-race motor form from authorized CSV observations. Does not scrape sites."""
import argparse,csv,datetime as dt,json
from collections import defaultdict
from pathlib import Path

NEED=('race_id','race_start','venue_code','motor_cycle','motor_number','meeting_id','boat','finish','exhibition_time')
def generate(rows):
    races=defaultdict(list)
    for n,r in enumerate(rows,2):
        for k in NEED:
            if not str(r.get(k,'')).strip():raise ValueError(f'row {n}: missing {k}')
        t=dt.datetime.fromisoformat(r['race_start'].replace('Z','+00:00'))
        if t.tzinfo is None:raise ValueError(f'row {n}: timezone required')
        boat,finish,motor=int(r['boat']),int(r['finish']),int(r['motor_number'])
        exhibition=float(r['exhibition_time'])
        if not (1<=boat<=6 and 1<=finish<=6 and motor>0 and 4<exhibition<12):
            raise ValueError(f'row {n}: implausible data')
        races[(t,r['venue_code'],r['race_id'])].append((r,boat,finish,motor,exhibition))
    hist=defaultdict(list);sessions=defaultdict(list);result=[]
    for rk in sorted(races):
        entries=races[rk]
        if len(entries)!=6 or {e[1] for e in entries}!={1,2,3,4,5,6}:
            raise ValueError(f'{rk}: not six distinct boats')
        if len({(e[0]['motor_cycle'],e[3]) for e in entries})!=6:
            raise ValueError(f'{rk}: duplicate motors')
        for r,boat,finish,motor,exh in entries:
            mk=(r['venue_code'],r['motor_cycle'],motor)
            past=hist[mk]; recent=past[-5:]; sess=sessions[mk+(r['meeting_id'],)]
            def rate(data):
                return round(sum(x[0]<=2 for x in data)/len(data),4) if data else None
            def relative(data):
                return round(sum(x[1] for x in data)/len(data),4) if data else None
            result.append(dict(race_id=r['race_id'],race_start=r['race_start'],
                venue_code=r['venue_code'],motor_cycle=r['motor_cycle'],
                motor_number=motor,meeting_id=r['meeting_id'],boat=boat,
                cycle_prior_runs=len(past),cycle_prior_top2_rate=rate(past),
                last5_prior_runs=len(recent),last5_prior_top2_rate=rate(recent),
                last5_prior_relative_exhibition=relative(recent),
                meeting_prior_runs=len(sess),meeting_prior_top2_rate=rate(sess),
                meeting_prior_relative_exhibition=relative(sess),
                meeting_last_relative_exhibition=sess[-1][1] if sess else None,
                meeting_relative_exhibition_change=round(sess[-1][1]-sess[-2][1],4) if len(sess)>1 else None))
        avg=sum(e[4] for e in entries)/6
        for r,boat,finish,motor,exh in entries:
            item=(finish,round(exh-avg,4))
            key=(r['venue_code'],r['motor_cycle'],motor)
            hist[key].append(item);sessions[key+(r['meeting_id'],)].append(item)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    a=p.parse_args()
    with open(a.input,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    out=generate(rows)
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Features: {len(out)} boat entries across {len(out)//6} races')
