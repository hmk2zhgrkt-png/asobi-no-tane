#!/usr/bin/env python3
"""Independent BOAT RACE Elo ratings built ONLY from official race result labels.

Six racers compete in one race, yielding 15 pairwise comparisons.
Each racer is updated by average pairwise surprise at K=24. This bounds
any one race to +/-24 points and prevents high-variance large field updates.
Updates are applied ONLY after an entire calendar day has been observed,
so same-day earlier races never leak into pre-race training.
No third-party ratings or licensed Elo values are imported.
"""
import collections, datetime as dt, math
import numpy as np

INITIAL=1500.0
K=24.0
SCALE=400.0
FEATURES=('elo_centered','elo_field_advantage','elo_rank_fraction','elo_log_races')

def expected(a,b):
    # E(a beats b), logistic Elo with standard 400pt denominator.
    return 1.0/(1.0+10.0**((b-a)/SCALE))

class Elo:
    def __init__(self):
        self.ratings={}
        self.starts=collections.Counter()
    def snapshot(self,race):
        if len(race)!=6:raise ValueError('Elo needs exactly six competitors')
        racers=[int(r['racer_id']) for r in race]
        if len(set(racers))!=6:raise ValueError('Duplicate racer')
        values=np.array([self.ratings.get(p,INITIAL) for p in racers],dtype=np.float32)
        ordered=np.argsort(-values,kind='stable')
        rank=np.empty(6,dtype=float)
        rank[ordered]=np.arange(6)
        return [[float((v-INITIAL)/SCALE),
                 float((v-values.mean())/SCALE),
                 float(rank[i]/5.0),
                 math.log1p(self.starts[racers[i]])] for i,v in enumerate(values)]
    def update_race(self,race):
        if len(race)!=6:raise ValueError('Incomplete race')
        ids=[int(r['racer_id']) for r in race]
        places=[int(r['finish_place']) for r in race]
        if len(set(ids))!=6 or set(places)!=set(range(1,7)):
            raise ValueError('Elo requires six different places/racers')
        before=[self.ratings.get(p,INITIAL) for p in ids]
        changes=[0.0]*6
        for i in range(6):
            for j in range(i+1,6):
                actual=1.0 if places[i]<places[j] else 0.0
                surprise=actual-expected(before[i],before[j])
                changes[i]+=surprise*K/5.0
                changes[j]-=surprise*K/5.0
        for i,rid in enumerate(ids):
            self.ratings[rid]=before[i]+changes[i]
            self.starts[rid]+=1
        if abs(sum(changes))>1e-8:raise AssertionError('Elo changes must be zero sum')

def elo_feature_rows(rows):
    """Yield original row order, four pre-date Elo predictors per boat.

    Entire day's ratings are frozen; postrace results are only applied after
    all pre-date predictors for that day are calculated.
    """
    rating=Elo()
    current=None
    buffer=[]
    def finalize(batch):
        race_groups=collections.defaultdict(list)
        for r in batch:
            race_groups[r['race_code']].append(r)
        features={}
        for code,race in race_groups.items():
            for r,x in zip(race,rating.snapshot(race)):
                features[(code,int(r['boat']))]=x
        result=[features[(r['race_code'],int(r['boat']))] for r in batch]
        for race in race_groups.values():
            rating.update_race(race)
        return result
    for row in rows:
        day=str(row['date'])
        if current is not None and day<current:
            raise ValueError('Official rows are not chronologically ordered')
        if current is not None and day!=current:
            yield from finalize(buffer)
            buffer=[]
        current=day
        buffer.append(row)
    if buffer:yield from finalize(buffer)
