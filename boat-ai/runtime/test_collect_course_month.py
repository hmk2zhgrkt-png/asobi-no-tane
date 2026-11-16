#!/usr/bin/env python3
import datetime as dt, tempfile
from pathlib import Path
from collect_course_month import bounds,collect
assert bounds('2023-11')==(dt.date(2023,11,1),dt.date(2023,11,30))
assert bounds('2024-02')==(dt.date(2024,2,1),dt.date(2024,2,29))
assert bounds('2026-10')==(dt.date(2026,10,1),dt.date(2026,10,31))
for invalid in ('2023-10','2026-11','not-a-month','2024-13'):
    try:bounds(invalid)
    except ValueError:pass
    else:raise AssertionError('Invalid month was accepted: '+invalid)
print('PASS: approved 36 calendar months, leap-year February, reject outside range')
