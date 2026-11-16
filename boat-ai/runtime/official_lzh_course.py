#!/usr/bin/env python3
"""Produce six-way historical racer/course/place labels from BOAT RACE official K LZH.

Uses the MIT-licensed boatrace-lzh PerformanceParser (result entries contain
racer_number, boat_number, entrance_position, result_position, motor_number).
Official LZH files are downloaded into runner cache, not committed.
"""
import collections
import datetime as dt
import json

def join_official_performance(day, parsed):
    groups=collections.defaultdict(list)
    skipped=collections.Counter()
    for e in parsed.entries:
        try:
            if e.race_date and e.race_date!=day:
                skipped['wrong_date_entry']+=1
                continue
            venue=int(e.venue_code);race=int(e.race_number)
            if not (1<=venue<=24 and 1<=race<=12):
                skipped['bad_venue_race']+=1;continue
            groups[(venue,race)].append(e)
        except (TypeError,ValueError,AttributeError):
            skipped['bad_entry']+=1
    allrows=[]
    for (venue,race),entries in groups.items():
        if len(entries)!=6:
            skipped['non_six_boat_race']+=1;continue
        try:
            boats=[int(e.boat_number) for e in entries]
            racers=[int(e.racer_number) for e in entries]
            courses=[int(e.entrance_position) for e in entries]
            ranks=[int(e.result_position) for e in entries]
            motors=[int(e.motor_number) for e in entries]
            if not (set(boats)==set(range(1,7)) and set(courses)==set(range(1,7)) and
                    set(ranks)==set(range(1,7)) and len(set(racers))==6 and
                    all(1000<=x<=9999 for x in racers) and all(1<=x<=999 for x in motors)):
                raise ValueError("Race has incomplete/invalid entry")
            code=f"{day:%Y%m%d}{venue:02d}{race:02d}"
            for e in entries:
                st=e.st_timing
                allrows.append(dict(date=day.isoformat(),race_code=code,venue_code=venue,
                    race_number=race,boat=int(e.boat_number),racer_id=int(e.racer_number),
                    motor_number=int(e.motor_number),actual_course=int(e.entrance_position),
                    finish_place=int(e.result_position),
                    actual_st="" if st is None else str(st),
                    prior_observation_cutoff=day.isoformat(),
                    source="BOATRACE official K performance LZH"))
            skipped['complete_races']+=1
        except (ValueError,TypeError,AttributeError):
            skipped['invalid_or_disqualified_race']+=1
    return allrows,dict(skipped)

def official_day(day,downloader=None,parser=None):
    from boatrace_lzh import LzhDownloader,PerformanceParser
    dl=downloader or LzhDownloader(cache_dir="/tmp/boat-course-lzh",max_workers=2)
    parsed=(parser or PerformanceParser()).parse(dl.download(day,"performance"))
    if not getattr(parsed,"entries",None):
        raise ValueError(f"Official K result has no entries for {day}")
    return join_official_performance(day,parsed)
