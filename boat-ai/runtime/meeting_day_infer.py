#!/usr/bin/env python3
"""Deduce official current meeting day with matched prior-day K results.

No guessing based on stale programme marks, calendar dates or same-day
finished races. Require two independently identified previous-day racers
whose last completed K record matches current official racecard prior-day
meeting D-slot race number, finishing position and (if present) entry course.
Never use K from target day or after. If ambiguous, return no meeting day.
"""
import collections,datetime as dt,math
from pathlib import Path
from live_course_history import iter_cache_rows

def number(raw):
    try:
        value=float(str(raw).strip())
        return int(value) if math.isfinite(value) and value.is_integer() else None
    except (TypeError,ValueError):return None

def infer_meeting_day(card,target_date,venue,cache):
    date=dt.date.fromisoformat(str(target_date))
    yesterday=(date-dt.timedelta(days=1)).isoformat()
    # Only one prior completed date; current-day labels are forbidden.
    source={(int(r['racer_id']),int(r['race_number']),int(r['finish_place'])):
            int(r['actual_course'])
            for r in iter_cache_rows(cache,date)
            if r['date']==yesterday and int(r['venue_code'])==int(venue)}
    evidence=collections.defaultdict(set)
    for boat in range(1,7):
        rid=number(card.get(f'艇{boat}_登録番号'))
        if rid is None:continue
        for day_slot in range(1,8):
            for run in (1,2):
                field=f'艇{boat}_節D{day_slot}走{run}_'
                race=number(card.get(field+'R番号'))
                position=number(card.get(field+'着順'))
                entry=number(card.get(field+'進入'))
                if race is None or position is None:continue
                actual=source.get((rid,race,position))
                if actual is not None and (entry is None or entry==actual):
                    evidence[day_slot].add(rid)
    eligible={d:len(racers) for d,racers in evidence.items() if len(racers)>=2 and d<=6}
    if not eligible or len(eligible)!=1:
        return None,{'verified':False,'reason':'no uniquely matched previous-day meeting slot',
                     'matching_slot_counts':eligible}
    previous=next(iter(eligible))
    return previous+1,{'verified':True,'prior_day':yesterday,
        'matched_previous_meeting_slot':previous,
        'independent_racers_matched':eligible[previous],
        'source':'official card prior-result slot matched to checksum-verified BOATRACE K from yesterday',
        'same_day_outcomes_used':False}
