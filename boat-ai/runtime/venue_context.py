"""Venue-specific course priors from Kyoutei Navi, source period 2021-01-01 to 2025-12-31.
Source: https://kyoutei-navi.com/category/place/
This is NOT a newly trained model. A deliberately conservative, UNVALIDATED
post-model first-place course-prior adjustment is applied for paper-only analysis.
Do not interpret adjusted probability/EV as calibrated until backtested.
"""
import math

SOURCE_URL = "https://kyoutei-navi.com/category/place/"
SOURCE_PERIOD = "2021-01-01/2025-12-31"
ADJUSTMENT_STRENGTH = 0.20
# venue: [course1..course6 first-place percentages], water condition, water quality, tidal influence
VENUES = {
    "桐生": ([52.4,12.9,13,12.6,7.2,2], "難水面", "淡水", "なし"),
    "戸田": ([43.8,15.8,16.2,14.6,6.9,2.6], "難水面", "淡水", "なし"),
    "江戸川": ([46.1,18.3,14.4,12.1,6.6,3], "難水面", "汽水", "大きい"),
    "平和島": ([45.1,17.4,13.9,12.9,7.6,3.3], "難水面", "海水", "普通"),
    "多摩川": ([52.9,15.1,12.6,11.3,6.4,1.7], "静水面", "淡水", "なし"),
    "浜名湖": ([52.5,14.8,14,10.4,6.6,1.7], "普通", "汽水", "小さい"),
    "蒲郡": ([55.3,12.1,12.7,12.2,6,1.6], "静水面", "汽水", "なし"),
    "常滑": ([57.6,12.1,10.9,11,6.6,1.9], "普通", "海水", "なし"),
    "津": ([57.1,14.1,11.8,9.9,5.4,1.6], "普通", "汽水", "なし"),
    "三国": ([54.1,15.6,14.1,9.7,5.2,1.3], "難水面", "淡水", "なし"),
    "びわこ": ([54.4,14.5,13.1,10.7,5.6,1.7], "普通", "淡水", "なし"),
    "住之江": ([58.6,13.8,11.6,9.5,5,1.4], "難水面", "淡水", "なし"),
    "尼崎": ([59.2,11.9,11.8,9.8,5.5,1.7], "静水面", "淡水", "なし"),
    "鳴門": ([48.1,15.7,14.8,11.7,7.7,2.1], "難水面", "海水", "大きい"),
    "丸亀": ([56.4,13.9,11.8,10.3,5.7,2], "普通", "海水", "大きい"),
    "児島": ([55.9,13.3,12.2,10.6,5.9,2], "普通", "海水", "大きい"),
    "宮島": ([56.8,12.5,12.5,9.8,6.4,1.9], "難水面", "海水", "大きい"),
    "徳山": ([63,13.5,9.4,8.4,4.6,1.1], "普通", "海水", "大きい"),
    "下関": ([60.5,11.6,10.5,9.5,5.6,2.2], "静水面", "海水", "小さい"),
    "若松": ([57.3,12.4,11.9,10.4,6,1.9], "難水面", "海水", "大きい"),
    "芦屋": ([61.2,10.7,10.7,10.5,5.2,1.7], "静水面", "淡水", "なし"),
    "福岡": ([55.3,15.4,14.9,9.4,4.1,1], "難水面", "汽水", "大きい"),
    "唐津": ([55,14.6,12.7,10.4,5.8,1.6], "静水面", "淡水", "なし"),
    "大村": ([62.7,12.2,10.8,8.5,4.5,1.3], "普通", "海水", "小さい"),
}
assert len(VENUES) == 24

def context(venue):
    rates, surface, water, tide = VENUES[venue]
    return {"source": SOURCE_URL, "source_period": SOURCE_PERIOD,
            "course_win_rates_pct": rates, "surface": surface, "water": water,
            "tidal_influence": tide, "method": "bounded first-place course prior",
            "adjustment_strength": ADJUSTMENT_STRENGTH,
            "validated_backtest": False}

def adjustment_factors(venue, boat_to_course):
    """Returns boat-indexed factors using relative venue vs equal-venue nationwide course rates.
    Course-specific base rates affect ONLY the predicted first-place boat;
    no fabricated tide height, wind-direction, or weight measurements are used.
    """
    if set(boat_to_course) != set(range(1, 7)) or set(boat_to_course.values()) != set(range(1, 7)):
        raise ValueError("Unverified six distinct entry courses")
    raw = VENUES[venue][0]
    totals = [sum(row[0][i] for row in VENUES.values()) for i in range(6)]
    nationwide = [v/sum(totals) for v in totals]
    local = [v/sum(raw) for v in raw]
    return {boat: (local[course-1]/nationwide[course-1])**ADJUSTMENT_STRENGTH
            for boat, course in boat_to_course.items()}

def adjust_120(venue, boat_to_course, permutations, base_probabilities):
    """Multiply existing model probability by venue first-place prior then normalize."""
    if len(permutations)!=120 or len(base_probabilities)!=120:
        raise ValueError("Expected 120 trifectas")
    factors=adjustment_factors(venue, boat_to_course)
    weighted=[float(p)*factors[combo[0]] for combo,p in zip(permutations,base_probabilities)]
    total=sum(weighted)
    if not math.isfinite(total) or total<=0:raise ValueError("Invalid prior adjustment")
    return [v/total for v in weighted]
