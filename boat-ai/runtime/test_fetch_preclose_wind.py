#!/usr/bin/env python3
"""Wind-from preview must match exact race, be fresh, preclose, and time-safe."""
import datetime as dt
from fetch_preclose_wind import select_preclose_wind
JST=dt.timezone(dt.timedelta(hours=9))
date=dt.date(2026,11,17);deadline=dt.datetime(2026,11,17,12,1,tzinfo=JST)
now=dt.datetime(2026,11,17,11,58,tzinfo=JST)
code="202611171705"
def row(code,stamp,wind):
    return {"レースコード":code,"取得日時":stamp,"風向":wind}
ok=row(code,"2026-11-17T11:50:00+09:00","北東")
other=row("202611171704","2026-11-17T11:55:00+09:00","西")
late=row(code,"2026-11-17T12:05:00+09:00","南西")
future=row(code,"2026-11-17T12:00:00+09:00","南西")
stale=row(code,"2026-11-17T10:00:00+09:00","西")
observed=select_preclose_wind([other,stale,late,ok,future],code,date,deadline,now)
assert observed['wind_from']=="NE"
assert observed['source_observed_at_jst']=="2026-11-17T11:50:00+09:00"
assert select_preclose_wind([other,late,future],code,date,deadline,now) is None
assert select_preclose_wind([row(code,"2026-11-17T11:50:00","北東")],code,date,deadline,now) is None
try:select_preclose_wind([ok,row(code,"2026-11-17T11:50:00+09:00","西")],code,date,deadline,now)
except ValueError:pass
else:raise AssertionError("Conflicting sources accepted")
print("PASS preclose wind source exact race, 8-way observed direction, stale and postclose exclusion, timestamp conflict rejection")
