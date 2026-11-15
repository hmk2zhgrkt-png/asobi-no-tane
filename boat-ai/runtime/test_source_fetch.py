#!/usr/bin/env python3
"""Offline regression: independent delivery paths and fail-closed schemas."""
import datetime as dt, io
from urllib.error import HTTPError
from source_fetch import fetch_csv, SourceUnavailable, boatcast_race_card_url, decode_csv

class Response:
    def __init__(self,data): self.buf=io.BytesIO(data)
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return self.buf.read()

origins=("https://one.example/data/","https://two.example/data/")
calls=[]
def opener(request,timeout):
    calls.append(request.full_url)
    if request.full_url.startswith(origins[0]):
        raise HTTPError(request.full_url,404,"Not Found",{},None)
    return Response("レースコード,艇1_登録番号,艇6_登録番号\n202611152408,4934,5055\n".encode())
rows,origin=fetch_csv('programs/race_cards',dt.date(2026,11,15),opener=opener,origins=origins)
assert origin==origins[1] and len(calls)==2 and rows[0]['レースコード']=='202611152408'
assert 'bc_j_str3_20261115_24_08.txt' in boatcast_race_card_url('2026-11-15',24,8)
try:
    decode_csv(b'<html>Oops</html>', 'programs/race_cards')
except ValueError: pass
else:raise AssertionError('Must reject HTML body')

def fail(request,timeout):
    raise HTTPError(request.full_url,404,"Not Found",{},None)
try:
    fetch_csv('programs/race_cards','2026-11-15',opener=fail,origins=origins)
except SourceUnavailable as e:
    assert 'all 2 delivery paths failed' in str(e)
else: raise AssertionError('Must fail closed')
print("PASS: failover after 404, race-card schema validation, official-source diagnostics, fail closed")
