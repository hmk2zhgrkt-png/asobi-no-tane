#!/usr/bin/env python3
"""Experimental *exhibition-only* F.01–F.04 positive scoring adjustment.

At a user's instruction, an exhibition start that was 0.01–0.04 seconds
before the line is treated as a small *positive* signal, not a penalty.
Outside this range the rule is neutral, not automatically negative.

This is a post-model sensitivity experiment, NOT a historically trained or
calibrated relationship; independent evaluation is required. It never changes
actual race F records, history, model files, or betting permissions.
"""
import itertools
import math

MAX_EARLY_SEC = 0.04
# Mild role-sensitive multipliers; arbitrary prior hypothesis, NOT learned.
ROLE_MULTIPLIERS = (1.06, 1.04, 1.025)

def eligible_boats(exhibition_st):
    if len(exhibition_st) != 6:
        raise ValueError("Need six pre-start exhibition times")
    values = [float(x) for x in exhibition_st]
    if any(not math.isfinite(x) or abs(x) > 1 for x in values):
        raise ValueError("Bad exhibition ST")
    return [i+1 for i, x in enumerate(values) if -MAX_EARLY_SEC-1e-9 <= x < 0]

def adjust_combo_probs(combos, probs, exhibition_st):
    if len(combos) != len(probs) or len(combos) != 120:
        raise ValueError("All 120 unique trifecta probabilities required")
    identifiers = [tuple(map(int, c.split("-"))) if isinstance(c, str) else tuple(map(int,c)) for c in combos]
    expected = set(itertools.permutations(range(1,7),3))
    if set(identifiers) != expected or len(identifiers)!=120:
        raise ValueError("Incorrect trifecta universe")
    p = [float(x) for x in probs]
    if any(not math.isfinite(x) or x < 0 for x in p) or sum(p)<=0:
        raise ValueError("Invalid probabilities")
    eligible = set(eligible_boats(exhibition_st))
    updated = []
    for (a,b,c),val in zip(identifiers,p):
        factors = [(ROLE_MULTIPLIERS[i] if boat in eligible else 1.0) for i,boat in enumerate((a,b,c))]
        updated.append(val*math.prod(factors))
    total=sum(updated)
    if not total>0:raise ValueError("Invalid corrected mass")
    return [v/total for v in updated]

def details(exhibition_st):
    return {
        "enabled":True,
        "status":"UNVALIDATED_POSTMODEL_SENSITIVITY",
        "meaning":"Exhibition F.01 through F.04 is a SMALL positive indicator; other exhibition starts are neutral",
        "positive_exhibition_boats":eligible_boats(exhibition_st),
        "threshold_seconds":MAX_EARLY_SEC,
        "role_multipliers":{"first":ROLE_MULTIPLIERS[0],"second":ROLE_MULTIPLIERS[1],"third":ROLE_MULTIPLIERS[2]},
        "model_retrained":False,"backtested":False,
        "does_not_affect_actual_race_f":True,
        "no_bets":True
    }
