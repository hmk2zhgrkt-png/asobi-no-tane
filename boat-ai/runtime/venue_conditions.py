#!/usr/bin/env python3
"""Auditable 24-venue environmental conditioning for BOTH prediction models.

Source separation:
* venue_context.VENUES: Kyoutei Navi 2021–2025 course priors, surface,
  water quality, and qualitative tide influence (editorial profile).
* COURSE_HEADING: 24-venue start-to-1st-turn bearings documented by
  boatrace-db.jp/about/data/ (8-way wind classifications).
* Miyajima tidal implications: primary venue's surface.html and Kyoutei
  Navi /place/miyajima/.
* Observed wind and tide must come from a PRE-CLOSE source. Never infer
  a day's wind from the month/hour nor guess tide phase from the location.

This bounded RULE-BASED RESEARCH CANDIDATE is NOT a learned or backtested
wind/tide response. Treat its outputs as sensitivity alternatives, NOT
calibrated probability. Existing production model outputs are unchanged.
"""
import math
from itertools import permutations
from venue_context import VENUES,context

HEADING_SOURCE="https://boatrace-db.jp/about/data/"
SOURCE_NAVI="https://kyoutei-navi.com/category/place/"
MIYAJIMA_SOURCE="https://www.boatrace-miyajima.com/surface.html"
# Heading of a boat travelling from start to 1M. Wind *comes from* direction.
COURSE_HEADING={
 "桐生":"SE","戸田":"E","江戸川":"N","平和島":"N","多摩川":"W",
 "浜名湖":"S","蒲郡":"SW","常滑":"W","津":"W","三国":"SE",
 "びわこ":"S","住之江":"S","尼崎":"W","鳴門":"SE",
 "丸亀":"NW","児島":"S","宮島":"SW","徳山":"NW","下関":"SW",
 "若松":"W","芦屋":"E","福岡":"E","唐津":"S","大村":"E"}
DEGREES={"N":0,"NE":45,"E":90,"SE":135,"S":180,"SW":225,"W":270,"NW":315}
ALIASES={"北":"N","北東":"NE","東":"E","南東":"SE","南":"S","南西":"SW","西":"W","北西":"NW",
         "N":"N","NE":"NE","E":"E","SE":"SE","S":"S","SW":"SW","W":"W","NW":"NW"}
WIND_RELATIVE={"headwind":"向かい風","tailwind":"追い風","crosswind":"横風",
               "向かい風":"向かい風","追い風":"追い風","横風":"横風"}
TIDE_PHASES={"high":"満潮","low":"干潮","rising":"上げ潮","falling":"下げ潮",
             "満潮":"満潮","干潮":"干潮","上げ潮":"上げ潮","下げ潮":"下げ潮"}
# Stable qualitative observation: derived from Kyoutei Navi's venue list.
OVERVIEW_NOTES={
 "桐生":"ナイター、寒暖差","戸田":"イン1着率低くまくり多い",
 "江戸川":"河川の難水面","平和島":"イン1着率低く高配当多い",
 "多摩川":"静水面でスタート・機力重視","浜名湖":"進入隊形が変化しやすい",
 "蒲郡":"ナイター、4コースに特徴","常滑":"海水のプール型",
 "津":"差しが多く季節で風向き変化","三国":"日本海側、モーニング",
 "びわこ":"水位変動と1マーク移設","住之江":"ナイター",
 "尼崎":"1マーク振り幅小さい","鳴門":"モーニング、難水面",
 "丸亀":"潮と風の影響大","児島":"潮汐の影響大",
 "宮島":"干満差大・風向き変化・スタート難",
 "徳山":"潮汐の影響大、イン1着率高め",
 "下関":"潮汐の影響は比較的小さい",
 "若松":"追潮・向潮の影響あり",
 "芦屋":"静水面、企画レース",
 "福岡":"うねり・まくりが特徴",
 "唐津":"進入隊形が変化しやすい","大村":"イン1着率高め"}
assert set(OVERVIEW_NOTES)==set(COURSE_HEADING)==set(VENUES) and len(VENUES)==24

def classify_wind(venue,wind_from=None,relative=None):
    """Return head/tail/cross, ±45° diagonal or None. Never infer arrows."""
    if wind_from is not None and relative is not None:
        raise ValueError("Specify an absolute compass OR observed relative wind, not both")
    if relative is not None:
        if relative not in WIND_RELATIVE:raise ValueError("Unknown relative wind direction")
        return WIND_RELATIVE[relative]
    if wind_from is None:return None
    wind=ALIASES.get(wind_from)
    if wind is None:raise ValueError("Unknown wind-from compass")
    angle=(DEGREES[wind]-DEGREES[COURSE_HEADING[venue]])%360
    if angle==0:return "向かい風"
    if angle==180:return "追い風"
    if angle in (45,315):return "斜め向かい風"
    if angle in (135,225):return "斜め追い風"
    if angle in (90,270):return "横風"
    raise AssertionError("8-way difference unaccounted for")

def prepare_conditions(venue,wind_speed_m=None,wind_from=None,
                       relative_wind=None,tide_phase=None,tide_height_cm=None,
                       observed_at_jst=None,cutoff_jst=None):
    if venue not in VENUES:raise ValueError("Unknown venue")
    wind=classify_wind(venue,wind_from,relative_wind)
    if tide_phase is not None and tide_phase not in TIDE_PHASES:
        raise ValueError("Invalid tide phase")
    phase=TIDE_PHASES.get(tide_phase)
    if wind_speed_m is not None:
        speed=float(wind_speed_m)
        if not math.isfinite(speed) or not 0<=speed<=35:raise ValueError("Invalid wind speed")
    else:speed=None
    if tide_height_cm is not None:
        height=float(tide_height_cm)
        if not math.isfinite(height) or not -1000<=height<=1000:
            raise ValueError("Invalid tide height")
    else:height=None
    # No change to valid probabilities until independently measured conditions.
    # Absolute height alone can't show rise/fall without a time series.
    verified_condition=wind is not None and speed is not None
    profile=context(venue)
    return {"venue":venue,"course_heading":COURSE_HEADING[venue],
        "venue_profile":profile,"overview_note":OVERVIEW_NOTES[venue],
        "wind_from":ALIASES.get(wind_from) if wind_from else None,
        "relative_wind":wind,"wind_speed_m":speed,
        "tide_phase":phase,"tide_height_cm":height,
        "wind_observed":verified_condition,"tide_phase_observed":phase is not None,
        "observed_at_jst":observed_at_jst,"cutoff_jst":cutoff_jst,
        "sources":[SOURCE_NAVI,HEADING_SOURCE]+([MIYAJIMA_SOURCE] if venue=="宮島" else []),
        "wind_effect_learned":False,"tide_effect_learned":False,
        "research_only":True}

def adjust_research(venue,course_by_boat,combinations,probabilities,condition):
    """Conservative bounded scenario, no unmeasured condition or retrospective leakage.

    This is a sensitivity analysis only, *not* a validated winner model.
    If absent wind/tide, unmodified input returned. Log all factors.
    Influences may change with other conditions; calibration needed.
    """
    if len(combinations)!=120 or len(probabilities)!=120:raise ValueError("Expected 120 combinations")
    if set(course_by_boat)!=set(range(1,7)) or set(course_by_boat.values())!=set(range(1,7)):
        raise ValueError("Verified boat/course map must be permutation 1..6")
    raw=[float(v) for v in probabilities]
    if any(not math.isfinite(v) or v<0 for v in raw) or sum(raw)<=0:
        raise ValueError("Invalid probabilities")
    if condition["venue"]!=venue:raise ValueError("Venue identity mismatch")
    # Countrywide wind effects are NOT claimed learned. Bounded <= 4% in a
    # single rank; metadata names each experimentally tested assumption.
    wind=condition.get("relative_wind")
    speed=condition.get("wind_speed_m")
    phase=condition.get("tide_phase")
    intensity=min(1.0,max(0.0,(speed-2.0)/4.0)) if speed is not None else 0.0
    first_factor={boat:1.0 for boat in range(1,7)}
    # Qualitative source: Kyoutei Navi Miyajima article provides general
    # conjecture, which we use only as an *explicitly unvalidated scenario*.
    if venue=="宮島" and wind is not None and intensity>0:
        head=wind in ("向かい風","斜め向かい風")
        tail=wind in ("追い風","斜め追い風")
        for boat,course in course_by_boat.items():
            if head and course in (3,4,5,6):
                first_factor[boat]*=1+0.04*intensity
            elif tail and course in (2,3,4):
                first_factor[boat]*=1+0.04*intensity
    tide_effect_applied=False
    if venue=="宮島" and phase in ("満潮","干潮","上げ潮","下げ潮"):
        tide_effect_applied=True
        for boat,course in course_by_boat.items():
            if phase in ("満潮","上げ潮") and course==1:
                first_factor[boat]*=1.04 if phase=="満潮" else 1.02
            elif phase in ("干潮","下げ潮") and course in (3,4,5):
                first_factor[boat]*=1.04 if phase=="干潮" else 1.02
    # Other venues: observed water/wind contextual metadata retained, but
    # no invented quantitative venue-specific physical response.
    weights=[p*first_factor[combo[0]] for combo,p in zip(combinations,raw)]
    total=sum(weights)
    return [v/total for v in weights],{
        "first_place_factors":first_factor,
        "wind_effect_applied":venue=="宮島" and wind is not None and intensity>0,
        "tide_effect_applied":tide_effect_applied,
        "other_venues_unverified_effects_not_invented":venue!="宮島",
        "research_not_a_proven_improvement":True,
        "uncalibrated":True}
