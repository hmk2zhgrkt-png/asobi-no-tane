#!/usr/bin/env python3
"""Compute motor-cycle/contiguous-rider-stint features from historical pre-close files.
No scraping. Race outcomes enter the feature history only AFTER each race.
"""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
KEY=['date','venue','race','boat','racer_id']
M=['venue','cycle_start','motor']
S=M+['stint_id']

def build(boat_csv,label_csv,starts_csv,preclose=True):
    if preclose:
        source=pd.read_csv(boat_csv,encoding='utf-8-sig',usecols=['race_key','date','venue','race','boat','racer_id','motor','exhibition_time_pre','tkz_observed','cutoff_jst'])
        label=pd.read_csv(label_csv,encoding='utf-8-sig',usecols=['race_key','boat','finish_position']).rename(columns={'finish_position':'rank'})
        d=source.merge(label,on=['race_key','boat'],how='left',validate='one_to_one').rename(columns={'exhibition_time_pre':'exhibition_time'})
        observed=pd.to_datetime(d.tkz_observed,errors='coerce',utc=True)
        cutoff=pd.to_datetime(d.cutoff_jst,errors='coerce').dt.tz_localize('Asia/Tokyo').dt.tz_convert('UTC')
        d.loc[(observed.isna())|(cutoff.isna())|(observed>cutoff),'exhibition_time']=np.nan
    else:
        source=pd.read_csv(boat_csv,encoding='utf-8-sig',usecols=KEY+['motor','exhibition_time'])
        label=pd.read_csv(label_csv,encoding='utf-8-sig',usecols=KEY+['rank'])
        d=source.merge(label,on=KEY,how='left',validate='one_to_one')
    starts=pd.read_csv(starts_csv,encoding='utf-8-sig',usecols=['venue','current_motor_generation_start','source']).rename(columns={'current_motor_generation_start':'cycle_start'})
    if starts.venue.duplicated().any():raise ValueError('Duplicate venue cycle record')
    d=d.merge(starts,on='venue',how='left',validate='many_to_one')
    if d.cycle_start.isna().any():raise ValueError('Unmapped venue')
    d=d.loc[(d.date>=d.cycle_start)&d.motor.notna()].copy()
    d.motor=pd.to_numeric(d.motor,errors='coerce')
    d=d.loc[d.motor.gt(0)].copy()
    d['finish']=pd.to_numeric(d['rank'],errors='coerce')
    d['top2']=np.where(d.finish.between(1,6),(d.finish<=2).astype(float),np.nan)
    d.exhibition_time=pd.to_numeric(d.exhibition_time,errors='coerce')
    rk=['date','venue','race']
    n=d.groupby(rk).boat.transform('size')
    ub=d.groupby(rk).boat.transform('nunique')
    um=d.groupby(rk).motor.transform('nunique')
    d=d[(n==6)&(ub==6)&(um==6)].copy()
    valid=d.exhibition_time.between(4,12)
    mean=d.exhibition_time.where(valid).groupby([d[c] for c in rk]).transform('mean')
    count=valid.groupby([d[c] for c in rk]).transform('sum')
    d['exhibition_relative']=np.where(valid&(count==6),d.exhibition_time-mean,np.nan)
    d['date_stamp']=pd.to_datetime(d.date)
    d=d.sort_values(M+['date_stamp','race','boat'],kind='stable').reset_index(drop=True)
    mg=d.groupby(M,sort=False)
    prev_racer=mg.racer_id.shift(1);days=(d.date_stamp-mg.date_stamp.shift(1)).dt.days
    changed=(d.racer_id!=prev_racer)|(days>2)|days.isna()
    d['stint_id']=changed.fillna(True).groupby([d[c] for c in M]).cumsum().astype('int32')
    sg=d.groupby(S,sort=False)
    for short,field in [('top2','top2'),('exh','exhibition_relative')]:
        d['cycle_prior_'+short+'_mean']=mg[field].transform(lambda x:x.shift().expanding().mean())
        d['last5_prior_'+short+'_mean']=mg[field].transform(lambda x:x.shift().rolling(5,min_periods=1).mean())
        d['stint_prior_'+short+'_mean']=sg[field].transform(lambda x:x.shift().expanding().mean())
        d['last_stint_'+short]=sg[field].shift(1)
    d['cycle_prior_runs']=mg.cumcount();d['last5_prior_runs']=d.cycle_prior_runs.clip(upper=5)
    d['stint_prior_runs']=sg.cumcount()
    d['stint_last_exh_change']=d['last_stint_exh']-sg.exhibition_relative.shift(2)
    columns=KEY+['motor','cycle_start','source','finish','exhibition_relative','cycle_prior_runs',
      'cycle_prior_top2_mean','cycle_prior_exh_mean','last5_prior_runs',
      'last5_prior_top2_mean','last5_prior_exh_mean','stint_id','stint_prior_runs',
      'stint_prior_top2_mean','stint_prior_exh_mean','last_stint_exh','stint_last_exh_change']
    return d[columns].sort_values(KEY,kind='stable')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--boat-csv',required=True);p.add_argument('--labels-csv',required=True)
    p.add_argument('--cycle-starts',required=True);p.add_argument('--out',required=True)
    p.add_argument('--preclose',action='store_true')
    a=p.parse_args()
    out=build(a.boat_csv,a.labels_csv,a.cycle_starts,a.preclose)
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(a.out,index=False,encoding='utf-8-sig')
    print(f'{len(out)} boats, {len(out)//6} races, {out.venue.nunique()} venues')
