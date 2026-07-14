"""Barrier-level synthesis for Nifty Seller AI V50.8.3.

This module is deliberately pure and side-effect free.  It combines chart
structure and traditional daily pivots, then returns the nearest valid support
and resistance around the current market price.  It never issues a trade
instruction.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Dict, Iterable, Mapping, Optional


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def traditional_pivots(previous_high: Any, previous_low: Any, previous_close: Any) -> Dict[str, float]:
    """Return classic floor-trader pivots from the previous session.

    Invalid or inverted inputs return an empty mapping so callers can fail
    closed without inventing levels.
    """

    high = _number(previous_high)
    low = _number(previous_low)
    close = _number(previous_close)
    if high is None or low is None or close is None or high <= low:
        return {}

    pivot = (high + low + close) / 3.0
    width = high - low
    levels = {
        "P": pivot,
        "R1": 2.0 * pivot - low,
        "S1": 2.0 * pivot - high,
        "R2": pivot + width,
        "S2": pivot - width,
    }
    return {key: round(value, 2) for key, value in levels.items()}


def build_barrier_candidates(
    *,
    previous_day_high: Any = None,
    previous_day_low: Any = None,
    today_high: Any = None,
    today_low: Any = None,
    opening_range_high: Any = None,
    opening_range_low: Any = None,
    pivot_levels: Optional[Mapping[str, Any]] = None,
) -> list[Dict[str, Any]]:
    """Build a bounded, labelled set of structural barrier candidates.

    ``roles`` controls whether a level may act as support, resistance, or both.
    Prior-session, opening-range and pivot levels can flip role after a clean
    break.  The current day's high/low remain one-sided to avoid treating a new
    intraday extreme as support and resistance simultaneously.
    """

    raw: list[tuple[Any, str, frozenset[str], int]] = [
        (previous_day_high, "Previous Day High", frozenset({"support", "resistance"}), 60),
        (previous_day_low, "Previous Day Low", frozenset({"support", "resistance"}), 60),
        (today_high, "Today High", frozenset({"resistance"}), 45),
        (today_low, "Today Low", frozenset({"support"}), 45),
        (opening_range_high, "Opening Range High", frozenset({"support", "resistance"}), 55),
        (opening_range_low, "Opening Range Low", frozenset({"support", "resistance"}), 55),
    ]

    pivots = dict(pivot_levels or {})
    for code, priority in (("P", 90), ("R1", 100), ("S1", 100), ("R2", 80), ("S2", 80)):
        raw.append((pivots.get(code), f"Pivot {code}", frozenset({"support", "resistance"}), priority))

    candidates: list[Dict[str, Any]] = []
    for value, source, roles, priority in raw:
        level = _number(value)
        if level is None or level <= 0:
            continue

        # Merge virtually identical levels so the UI stays concise.  Prefer the
        # higher-priority source (notably R1/S1) while preserving all valid roles.
        existing = next((item for item in candidates if abs(item["level"] - level) <= 0.75), None)
        if existing is not None:
            existing["roles"] = frozenset(set(existing["roles"]) | set(roles))
            if priority > int(existing.get("priority", 0)):
                existing.update({"level": level, "source": source, "priority": priority})
            continue

        candidates.append({
            "level": level,
            "source": source,
            "roles": roles,
            "priority": priority,
        })

    return sorted(candidates, key=lambda item: item["level"])


def select_nearest_barriers(price: Any, candidates: Iterable[Mapping[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Return nearest valid support below and resistance above ``price``."""

    spot = _number(price)
    if spot is None:
        return {"support": None, "resistance": None}

    supports: list[Dict[str, Any]] = []
    resistances: list[Dict[str, Any]] = []

    for candidate in candidates:
        level = _number(candidate.get("level"))
        if level is None:
            continue
        roles = set(candidate.get("roles") or {"support", "resistance"})
        base = {
            "level": level,
            "source": str(candidate.get("source", "Structural Level")),
            "priority": int(candidate.get("priority", 0) or 0),
        }
        if "support" in roles and level <= spot + 1e-9:
            supports.append({**base, "distance_points": max(spot - level, 0.0)})
        if "resistance" in roles and level >= spot - 1e-9:
            resistances.append({**base, "distance_points": max(level - spot, 0.0)})

    # Distance is primary.  For duplicate-distance candidates, prefer the more
    # authoritative level (e.g. Pivot R1 over a transient intraday high).
    support = min(supports, key=lambda item: (item["distance_points"], -item["priority"])) if supports else None
    resistance = min(resistances, key=lambda item: (item["distance_points"], -item["priority"])) if resistances else None

    for item in (support, resistance):
        if item is not None:
            item["level"] = round(float(item["level"]), 2)
            item["distance_points"] = round(float(item["distance_points"]), 2)

    return {"support": support, "resistance": resistance}
