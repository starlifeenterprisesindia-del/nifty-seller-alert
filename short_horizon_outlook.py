"""Read-only Market Path Forecast derived strictly after AI_MASTER judgement.

V50.8.7 authority contract
--------------------------
This module is *not* a decision engine and it never fetches market data.  It
receives an immutable copy of the already-final AI_MASTER judgement plus the
same verified refresh snapshot.  It may express that evidence as 15/30 minute
UP/DOWN/RANGE probabilities, likely path zones and exhaustion risk, but it
cannot:

* issue BUY / SELL CE / SELL PE / IRON CONDOR;
* choose a strike, hedge, stop loss or target;
* change AI_MASTER action, confidence, strategy scores or execution readiness;
* feed any forecast output back into AI_MASTER or a DSP department.

The forecast is intentionally saved in shadow mode so its 15m/30m outcomes can
be calibrated without affecting live decisions.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import threading
from typing import Any, Mapping, MutableMapping, Optional

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None

_STORE = Path(os.environ.get("NIFTY_OUTLOOK_STORE", ".runtime_state/short_horizon_outlook.json"))
_LOCK = Path(os.environ.get("NIFTY_OUTLOOK_LOCK", ".runtime_state/short_horizon_outlook.lock"))
# Keep the old state key so V50.8.5 shadow cases survive the upgrade.
_STATE_KEY = "v5085_short_horizon_forecasts"
_MAX_RECORDS = 750
_THREAD_LOCK = threading.RLock()
_LOCKED_AUTHORITY_FIELDS = (
    "final_action",
    "execution_status",
    "confidence",
    "decision_confidence",
    "direction_confidence",
    "strategy",
    "strategy_scores",
    "ce_plan",
    "pe_plan",
    "candidate_rows",
    "strategy_rows",
)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _iso(value: Optional[datetime] = None) -> str:
    dt = value if isinstance(value, datetime) else datetime.now(timezone.utc)
    return dt.isoformat(timespec="seconds")


def _epoch(value: Any) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _stable_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _authority_fingerprint(master: Mapping[str, Any]) -> str:
    return _stable_hash({key: deepcopy(master.get(key)) for key in _LOCKED_AUTHORITY_FIELDS})


def _read() -> list[dict[str, Any]]:
    try:
        if not _STORE.exists():
            return []
        payload = json.loads(_STORE.read_text(encoding="utf-8"))
        rows = payload.get("records", []) if isinstance(payload, dict) else payload
        return [dict(x) for x in rows if isinstance(x, Mapping)]
    except Exception:
        return []


def _write(rows: list[dict[str, Any]]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE.with_name(f"{_STORE.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(
        json.dumps(
            {"schema_version": 2, "updated_at": _iso(), "records": rows[-_MAX_RECORDS:]},
            separators=(",", ":"),
            default=str,
        ),
        encoding="utf-8",
    )
    os.replace(tmp, _STORE)


class _FileLock:
    def __enter__(self):
        _LOCK.parent.mkdir(parents=True, exist_ok=True)
        _THREAD_LOCK.acquire()
        self.handle = _LOCK.open("a+", encoding="utf-8")
        if fcntl is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
        finally:
            _THREAD_LOCK.release()


def _merge_records(*groups: Any) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, Mapping):
                continue
            row = dict(item)
            identity = str(row.get("forecast_id") or f"{row.get('snapshot_id')}:{row.get('created_at')}")
            old = by_id.get(identity)
            if old is None or _epoch(row.get("updated_at", row.get("created_at"))) >= _epoch(old.get("updated_at", old.get("created_at"))):
                by_id[identity] = row
    rows = list(by_id.values())
    rows.sort(key=lambda x: _epoch(x.get("created_at")))
    return rows[-_MAX_RECORDS:]


def _probabilities(direction_score: float, range_score: float) -> tuple[int, int, int]:
    range_p = _clamp(range_score, 12.0, 74.0)
    directional_mass = 100.0 - range_p
    # +/-100 can create a strong view but never an artificial 100% certainty.
    up_share = 1.0 / (1.0 + math.exp(-_clamp(direction_score, -100, 100) / 24.0))
    up = directional_mass * up_share
    down = directional_mass - up
    rounded = [int(round(up)), int(round(down)), int(round(range_p))]
    rounded[2] += 100 - sum(rounded)
    return tuple(rounded)  # type: ignore[return-value]


def _dominant(up: int, down: int, range_p: int) -> str:
    values = {"UP": up, "DOWN": down, "RANGE": range_p}
    ordered = sorted(values.items(), key=lambda x: x[1], reverse=True)
    if ordered[0][1] - ordered[1][1] < 8:
        return f"{ordered[0][0]}/{ordered[1][0]}"
    return ordered[0][0]


def _leader_margin(up: int, down: int, range_p: int) -> int:
    ordered = sorted((up, down, range_p), reverse=True)
    return int(ordered[0] - ordered[1])


def _extract_conflicts(master: Mapping[str, Any]) -> list[str]:
    warnings = [str(x) for x in list(master.get("warnings", []) or []) + list(master.get("blockers", []) or [])]
    return [x for x in warnings if "conflict" in x.lower() or "hold" in x.lower()][:5]


def _candle_fallback_status(price_action_context: Optional[Mapping[str, Any]]) -> tuple[bool, dict[str, Any]]:
    """Return whether fresh current-session 5m candle structure can support a limited forecast.

    This is only a continuity fallback. It never replaces the authoritative live
    snapshot and it cannot upgrade a LIMITED forecast to FULL.
    """
    ctx = price_action_context if isinstance(price_action_context, Mapping) else {}
    success = bool(ctx.get("success", ctx.get("ready", False)))
    current_session = bool(ctx.get("current_session_available", False))
    candle_count = int(_num(ctx.get("current_session_candle_count", 0), 0))
    candle_age = _num(ctx.get("candle_age_seconds", 999999.0), 999999.0)
    source = str(ctx.get("source", "Dhan 5m candles"))
    ok = bool(success and current_session and candle_count >= 2 and 0 <= candle_age <= 720)
    return ok, {
        "ok": ok,
        "source": source,
        "current_session_candle_count": candle_count,
        "candle_age_seconds": round(candle_age, 1),
    }


def _availability_assessment(
    master: Mapping[str, Any],
    movement: Mapping[str, Any],
    quote_age: Optional[float],
    option_age: Optional[float],
    *,
    observed_at: datetime,
    market_open: bool,
    option_evidence_status: str,
    price_action_context: Optional[Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify forecast evidence as FULL, LIMITED or UNAVAILABLE.

    Hard failures protect the one-brain contract. Recoverable evidence gaps such
    as a refresh continuity reset or day-change-only OI now produce a capped,
    clearly labelled LIMITED forecast instead of a blank table.
    """
    hard: list[str] = []
    limited: list[str] = []
    if not market_open:
        hard.append("market closed")
    if str(master.get("data_flow_status", "")).upper() != "FRESH":
        hard.append("data flow not fresh")
    if str(master.get("oi_sync_status", "")).upper() not in {"OK", "SNAPSHOT_READY"}:
        hard.append("OI sync not ready")
    if quote_age is not None and quote_age > 12:
        hard.append("quote stale")
    if option_age is not None and option_age > 12:
        hard.append("option chain stale")

    integrity = master.get("department_integrity", {}) if isinstance(master.get("department_integrity", {}), Mapping) else {}
    if not bool(integrity.get("critical_ok", True)):
        hard.append("critical DSP integrity hold")

    recent_samples = int(_num(movement.get("recent_sample_count", 0), 0))
    continuity = str(movement.get("continuity_status", "UNKNOWN")).upper()
    candle_ok, candle_details = _candle_fallback_status(price_action_context)
    minute_of_day = observed_at.hour * 60 + observed_at.minute
    opening_shock = 9 * 60 + 15 <= minute_of_day < 9 * 60 + 20

    if continuity == "PREOPEN_BLOCKED":
        hard.append("pre-open movement blocked")
    elif continuity == "GAP_RESET":
        if candle_ok and recent_samples >= 1 and not opening_shock:
            limited.append("live movement continuity reset; fresh 5m candle fallback used")
        else:
            hard.append("movement continuity reset without sufficient candle fallback")
    elif continuity not in {"LIVE_SEQUENCE", "FIRST_SAMPLE"}:
        if candle_ok and recent_samples >= 1 and not opening_shock:
            limited.append(f"movement continuity {continuity or 'UNKNOWN'}; fresh 5m candle fallback used")
        elif recent_samples < 2:
            hard.append("movement continuity unavailable")

    if recent_samples < 2:
        if candle_ok and not opening_shock:
            limited.append("insufficient refresh samples; current-session 5m candle structure used")
        else:
            hard.append("insufficient recent movement samples")

    option_mode = str(option_evidence_status or "SNAPSHOT_READY").upper()
    if option_mode in {"MISSING", "FAILED", "UNAVAILABLE"}:
        hard.append("option evidence unavailable")
    elif option_mode in {"DAY_CHANGE_ONLY", "PREOPEN_DAY_CHANGE_ONLY"}:
        limited.append("option evidence is day-change-only; fresh second snapshot pending")
    elif option_mode not in {"SNAPSHOT_READY", "LIVE", "OK"}:
        limited.append(f"option evidence mode {option_mode}")

    # During the first five minutes, a broken refresh sequence must not be
    # converted into an apparently precise forecast from one forming candle.
    if opening_shock and continuity != "LIVE_SEQUENCE":
        hard.append("opening shock requires continuous live movement")

    # De-duplicate while preserving explanation order.
    hard = list(dict.fromkeys(hard))
    limited = [x for x in dict.fromkeys(limited) if x not in hard]
    mode = "UNAVAILABLE" if hard else ("LIMITED" if limited else "FULL")
    return {
        "mode": mode,
        "hard_reasons": hard,
        "limited_reasons": limited,
        "candle_fallback": candle_details,
        "recent_samples": recent_samples,
        "continuity_status": continuity,
        "option_evidence_status": option_mode,
    }


def _direction_bias_label(direction_score: float, dominant: str) -> str:
    if dominant.startswith("RANGE") or dominant.endswith("/RANGE"):
        if direction_score >= 18:
            return "RANGE / UPSIDE LEAN"
        if direction_score <= -18:
            return "RANGE / DOWNSIDE LEAN"
        return "RANGE / TWO-WAY"
    if direction_score >= 48:
        return "BULLISH"
    if direction_score >= 15:
        return "EARLY BULLISH"
    if direction_score <= -48:
        return "BEARISH"
    if direction_score <= -15:
        return "EARLY BEARISH"
    return "BALANCED / UNCLEAR"


def _movement_budget(horizon: int, atr_points: float, movement: Mapping[str, Any]) -> float:
    atr = max(abs(atr_points), 1.0)
    m1 = abs(_num(movement.get("move_1m"), 0.0))
    m3 = abs(_num(movement.get("move_3m"), 0.0))
    m5 = abs(_num(movement.get("move_5m"), 0.0))
    velocity = max(m1 * 2.2, m3 * 0.95, m5 * 0.70)
    if horizon == 15:
        budget = atr * 0.62 + velocity * 0.38
        return _clamp(budget, 10.0, max(35.0, atr * 1.15))
    budget = atr * 0.92 + velocity * 0.46
    return _clamp(budget, 16.0, max(55.0, atr * 1.65))


def _active_leg_points(direction_score: float, movement: Mapping[str, Any], atr_points: float) -> float:
    m1 = _num(movement.get("move_1m"), 0.0)
    m3 = _num(movement.get("move_3m"), 0.0)
    m5 = _num(movement.get("move_5m"), 0.0)
    atr = max(abs(atr_points), 1.0)
    if direction_score >= 0:
        displacement = max(0.0, _num(movement.get("recovery_from_low"), 0.0))
        impulse = max(max(m1, 0.0) * 2.0, max(m3, 0.0) * 1.15, max(m5, 0.0), displacement * 0.34)
    else:
        displacement = max(0.0, _num(movement.get("pullback_from_high"), 0.0))
        impulse = max(max(-m1, 0.0) * 2.0, max(-m3, 0.0) * 1.15, max(-m5, 0.0), displacement * 0.34)
    return _clamp(impulse, 0.0, atr * 1.8)


def _move_consumed_pct(direction_score: float, movement: Mapping[str, Any], atr_points: float, horizon: int) -> float:
    active = _active_leg_points(direction_score, movement, atr_points)
    denominator = max(14.0, abs(atr_points) * (1.12 if horizon == 15 else 1.55))
    return _clamp(active / denominator * 100.0, 0.0, 95.0)


def _barrier_geometry(
    *,
    current_price: float,
    support_level: Optional[float],
    resistance_level: Optional[float],
) -> dict[str, Optional[float]]:
    support = _num(support_level, 0.0)
    resistance = _num(resistance_level, 0.0)
    if support <= 0 or support > current_price:
        support = 0.0
    if resistance <= 0 or resistance < current_price:
        resistance = 0.0
    return {
        "support": support or None,
        "resistance": resistance or None,
        "support_distance": round(current_price - support, 2) if support else None,
        "resistance_distance": round(resistance - current_price, 2) if resistance else None,
    }


def _reversal_risk(
    *,
    dominant: str,
    budget: float,
    consumed_pct: float,
    barriers: Mapping[str, Optional[float]],
    conflicts: list[str],
    movement: Mapping[str, Any],
    market_snapshot: Mapping[str, Any],
) -> int:
    risk = 18.0 + consumed_pct * 0.48 + len(conflicts) * 8.0
    direction = "UP" if dominant.startswith("UP") else "DOWN" if dominant.startswith("DOWN") else "RANGE"
    directional_distance = (
        barriers.get("resistance_distance") if direction == "UP"
        else barriers.get("support_distance") if direction == "DOWN"
        else min(
            [x for x in (barriers.get("support_distance"), barriers.get("resistance_distance")) if x is not None],
            default=None,
        )
    )
    if directional_distance is not None:
        ratio = _num(directional_distance) / max(budget, 1.0)
        if ratio <= 0.35:
            risk += 30
        elif ratio <= 0.70:
            risk += 19
        elif ratio <= 1.0:
            risk += 10

    phase = str(movement.get("phase", "")).upper()
    if phase in {"RANGE", "NORMAL"}:
        risk += 6
    if phase.startswith("STRONG_") and consumed_pct < 65:
        risk -= 6

    snapshot_risk = market_snapshot.get("risk", {}) if isinstance(market_snapshot.get("risk", {}), Mapping) else {}
    news = _num(snapshot_risk.get("news_risk"), 0)
    shock = _num(snapshot_risk.get("shock_risk"), 0)
    gamma = _num(snapshot_risk.get("gamma_risk"), 0)
    risk += max(0.0, news - 35.0) * 0.12
    risk += max(0.0, shock - 45.0) * 0.08
    risk += max(0.0, gamma - 55.0) * 0.05
    return int(round(_clamp(risk, 5.0, 95.0)))


def _invalidation_text(
    *,
    dominant: str,
    current_price: float,
    atr_points: float,
    barriers: Mapping[str, Optional[float]],
) -> tuple[str, float, str]:
    buffer_points = max(3.0, abs(atr_points) * 0.08)
    fallback = max(10.0, abs(atr_points) * 0.34)
    if dominant.startswith("UP"):
        support = barriers.get("support")
        level = (_num(support) - buffer_points) if support else current_price - fallback
        return f"Below {level:.0f}", level, "BELOW"
    if dominant.startswith("DOWN"):
        resistance = barriers.get("resistance")
        level = (_num(resistance) + buffer_points) if resistance else current_price + fallback
        return f"Above {level:.0f}", level, "ABOVE"
    support = barriers.get("support")
    resistance = barriers.get("resistance")
    if support and resistance:
        return f"Outside {support:.0f}–{resistance:.0f}", current_price, "OUTSIDE"
    return f"Outside {current_price-fallback:.0f}–{current_price+fallback:.0f}", current_price, "OUTSIDE"


def _zone_plan(
    *,
    horizon: int,
    dominant: str,
    direction_score: float,
    current_price: float,
    atr_points: float,
    movement: Mapping[str, Any],
    barriers: Mapping[str, Optional[float]],
) -> dict[str, Any]:
    budget = _movement_budget(horizon, atr_points, movement)
    consumed_pct = _move_consumed_pct(direction_score, movement, atr_points, horizon)
    # Even after a large move, do not claim zero room.  The remaining factor is
    # deliberately bounded because this is a probabilistic destination zone.
    remaining_factor = _clamp(1.0 - consumed_pct * 0.0058, 0.38, 1.0)
    remaining = budget * remaining_factor
    strength = _clamp(abs(direction_score) / 100.0, 0.0, 1.0)

    if dominant.startswith("UP"):
        low_move = max(4.0, remaining * (0.32 + strength * 0.10))
        high_move = max(low_move + 3.0, remaining * (0.72 + strength * 0.22))
        resistance_distance = barriers.get("resistance_distance")
        if resistance_distance is not None and _num(resistance_distance) <= high_move * 1.15:
            high_move = min(high_move, _num(resistance_distance) + abs(atr_points) * 0.10)
            low_move = min(low_move, max(3.0, _num(resistance_distance) * 0.55))
        likely_low = current_price + low_move
        likely_high = current_price + max(low_move + 2.0, high_move)
        stretch_low = likely_high
        stretch_high = likely_high + max(5.0, remaining * 0.36)
        expected = f"+{low_move:.0f} to +{max(low_move, high_move):.0f} pts"
    elif dominant.startswith("DOWN"):
        low_move = max(4.0, remaining * (0.32 + strength * 0.10))
        high_move = max(low_move + 3.0, remaining * (0.72 + strength * 0.22))
        support_distance = barriers.get("support_distance")
        if support_distance is not None and _num(support_distance) <= high_move * 1.15:
            high_move = min(high_move, _num(support_distance) + abs(atr_points) * 0.10)
            low_move = min(low_move, max(3.0, _num(support_distance) * 0.55))
        likely_low = current_price - max(low_move, high_move)
        likely_high = current_price - low_move
        stretch_high = likely_low
        stretch_low = likely_low - max(5.0, remaining * 0.36)
        expected = f"-{low_move:.0f} to -{max(low_move, high_move):.0f} pts"
    else:
        half = max(5.0, remaining * 0.48)
        likely_low = current_price - half
        likely_high = current_price + half
        stretch_extension = max(5.0, remaining * 0.28)
        stretch_low = likely_low - stretch_extension
        stretch_high = likely_high + stretch_extension
        expected = f"±{half:.0f} pts"

    return {
        "budget": round(budget, 2),
        "remaining": round(remaining, 2),
        "consumed_pct": int(round(consumed_pct)),
        "expected_move": expected,
        "likely_low": round(min(likely_low, likely_high), 2),
        "likely_high": round(max(likely_low, likely_high), 2),
        "stretch_low": round(min(stretch_low, stretch_high), 2),
        "stretch_high": round(max(stretch_low, stretch_high), 2),
    }


def _path_label(
    *,
    dominant: str,
    reversal_risk: int,
    barriers: Mapping[str, Optional[float]],
    zone: Mapping[str, Any],
    direction_score: float,
) -> str:
    if dominant.startswith("UP"):
        resistance_distance = barriers.get("resistance_distance")
        directional_budget = _num(zone.get("budget"), 0.0)
        if reversal_risk >= 68:
            return "UP → REVERSAL RISK"
        if resistance_distance is not None and _num(resistance_distance) <= max(8.0, directional_budget * 1.05):
            return "UP → STALL / BREAKOUT TEST"
        return "UP → CONTINUATION"
    if dominant.startswith("DOWN"):
        support_distance = barriers.get("support_distance")
        directional_budget = _num(zone.get("budget"), 0.0)
        if reversal_risk >= 68:
            return "DOWN → SUPPORT BOUNCE RISK"
        if support_distance is not None and _num(support_distance) <= max(8.0, directional_budget * 1.05):
            return "DOWN → SUPPORT / BREAKDOWN TEST"
        return "DOWN → CONTINUATION"
    if direction_score >= 12:
        return "RANGE → UPSIDE BREAK TEST"
    if direction_score <= -12:
        return "RANGE → DOWNSIDE BREAK TEST"
    return "TWO-WAY WHIPSAW / RANGE"


def _forecast_status(
    *,
    dominant: str,
    reliability: float,
    reversal_risk: int,
    margin: int,
    recent_samples: int,
    previous_dominant: str,
) -> str:
    current_primary = dominant.split("/")[0]
    previous_primary = str(previous_dominant or "").split("/")[0]
    if previous_primary and previous_primary != current_primary and margin >= 10:
        return "FORECAST SHIFT"
    if reliability < 45:
        return "LOW RELIABILITY"
    if reversal_risk >= 70:
        return "EXHAUSTION RISK"
    if "/" in dominant or margin < 10:
        return "BUILDING"
    if reliability >= 60 and recent_samples >= 5 and margin >= 15:
        return "CONFIRMED PATH"
    return "EARLY OUTLOOK"


def _build_horizon(
    *,
    horizon: int,
    direction_score: float,
    range_score: float,
    reliability: float,
    current_price: float,
    atr_points: float,
    movement: Mapping[str, Any],
    market_snapshot: Mapping[str, Any],
    barriers: Mapping[str, Optional[float]],
    conflicts: list[str],
    previous_dominant: str,
) -> dict[str, Any]:
    up, down, range_p = _probabilities(direction_score, range_score)
    dominant = _dominant(up, down, range_p)
    margin = _leader_margin(up, down, range_p)
    zone = _zone_plan(
        horizon=horizon,
        dominant=dominant,
        direction_score=direction_score,
        current_price=current_price,
        atr_points=atr_points,
        movement=movement,
        barriers=barriers,
    )
    reversal = _reversal_risk(
        dominant=dominant,
        budget=_num(zone.get("budget"), 1.0),
        consumed_pct=_num(zone.get("consumed_pct"), 0.0),
        barriers=barriers,
        conflicts=conflicts,
        movement=movement,
        market_snapshot=market_snapshot,
    )
    invalidation_text, invalidation_level, invalidation_mode = _invalidation_text(
        dominant=dominant,
        current_price=current_price,
        atr_points=atr_points,
        barriers=barriers,
    )
    rel = int(round(_clamp(reliability, 0, 100)))
    status = _forecast_status(
        dominant=dominant,
        reliability=rel,
        reversal_risk=reversal,
        margin=margin,
        recent_samples=int(_num(movement.get("recent_sample_count", 0))),
        previous_dominant=previous_dominant,
    )
    return {
        "horizon_minutes": horizon,
        "market_bias": _direction_bias_label(direction_score, dominant),
        "up_probability": up,
        "down_probability": down,
        "range_probability": range_p,
        "dominant": dominant,
        "leader_margin": margin,
        "direction_score": round(direction_score, 2),
        "expected_move": zone["expected_move"],
        "likely_low": zone["likely_low"],
        "likely_high": zone["likely_high"],
        "stretch_low": zone["stretch_low"],
        "stretch_high": zone["stretch_high"],
        "invalidation_text": invalidation_text,
        "invalidation_level": round(invalidation_level, 2),
        "invalidation_mode": invalidation_mode,
        "reversal_risk": reversal,
        "move_consumed": zone["consumed_pct"],
        "reliability": rel,
        "status": status,
        "path": _path_label(
            dominant=dominant,
            reversal_risk=reversal,
            barriers=barriers,
            zone=zone,
            direction_score=direction_score,
        ),
        "budget_points": zone["budget"],
        "remaining_budget_points": zone["remaining"],
    }


def _comparison_rows(
    h15: Mapping[str, Any],
    h30: Mapping[str, Any],
    *,
    current_price: float,
    barriers: Mapping[str, Optional[float]],
    support_source: str,
    resistance_source: str,
    evidence_mode: str = "FULL",
    evidence_note: str = "Fresh continuous same-snapshot evidence",
) -> list[dict[str, Any]]:
    def zone(row: Mapping[str, Any], prefix: str) -> str:
        return f"{_num(row.get(prefix + '_low')):.0f}–{_num(row.get(prefix + '_high')):.0f}"

    support = barriers.get("support")
    resistance = barriers.get("resistance")
    support_text = f"{_num(support):.0f} ({support_source})" if support else "Not available"
    resistance_text = f"{_num(resistance):.0f} ({resistance_source})" if resistance else "Not available"
    return [
        {"Field": "Current Nifty", "Next 15 Minutes": f"{current_price:.2f}", "Next 30 Minutes": f"{current_price:.2f}"},
        {"Field": "Evidence Mode", "Next 15 Minutes": evidence_mode, "Next 30 Minutes": evidence_mode},
        {"Field": "Evidence Note", "Next 15 Minutes": evidence_note, "Next 30 Minutes": evidence_note},
        {"Field": "Verified Support", "Next 15 Minutes": support_text, "Next 30 Minutes": support_text},
        {"Field": "Verified Resistance", "Next 15 Minutes": resistance_text, "Next 30 Minutes": resistance_text},
        {"Field": "Market Bias", "Next 15 Minutes": h15.get("market_bias"), "Next 30 Minutes": h30.get("market_bias")},
        {"Field": "UP Probability", "Next 15 Minutes": f"{h15.get('up_probability')}%", "Next 30 Minutes": f"{h30.get('up_probability')}%"},
        {"Field": "DOWN Probability", "Next 15 Minutes": f"{h15.get('down_probability')}%", "Next 30 Minutes": f"{h30.get('down_probability')}%"},
        {"Field": "RANGE Probability", "Next 15 Minutes": f"{h15.get('range_probability')}%", "Next 30 Minutes": f"{h30.get('range_probability')}%"},
        {"Field": "Expected Remaining Move", "Next 15 Minutes": h15.get("expected_move"), "Next 30 Minutes": h30.get("expected_move")},
        {"Field": "Likely Zone", "Next 15 Minutes": zone(h15, "likely"), "Next 30 Minutes": zone(h30, "likely")},
        {"Field": "Stretch Zone", "Next 15 Minutes": zone(h15, "stretch"), "Next 30 Minutes": zone(h30, "stretch")},
        {"Field": "Invalidation", "Next 15 Minutes": h15.get("invalidation_text"), "Next 30 Minutes": h30.get("invalidation_text")},
        {"Field": "Reversal Risk", "Next 15 Minutes": f"{h15.get('reversal_risk')}%", "Next 30 Minutes": f"{h30.get('reversal_risk')}%"},
        {"Field": "Move Consumed", "Next 15 Minutes": f"{h15.get('move_consumed')}%", "Next 30 Minutes": f"{h30.get('move_consumed')}%"},
        {"Field": "Reliability", "Next 15 Minutes": f"{h15.get('reliability')}%", "Next 30 Minutes": f"{h30.get('reliability')}%"},
        {"Field": "Most Likely Path", "Next 15 Minutes": h15.get("path"), "Next 30 Minutes": h30.get("path")},
        {"Field": "Forecast Status", "Next 15 Minutes": h15.get("status"), "Next 30 Minutes": h30.get("status")},
    ]


def _unavailable_rows(reason: str) -> list[dict[str, Any]]:
    return [
        {"Field": "Market Bias", "Next 15 Minutes": "UNAVAILABLE", "Next 30 Minutes": "UNAVAILABLE"},
        {"Field": "UP / DOWN / RANGE", "Next 15 Minutes": "- / - / -", "Next 30 Minutes": "- / - / -"},
        {"Field": "Expected Remaining Move", "Next 15 Minutes": "-", "Next 30 Minutes": "-"},
        {"Field": "Likely / Stretch Zone", "Next 15 Minutes": "-", "Next 30 Minutes": "-"},
        {"Field": "Forecast Status", "Next 15 Minutes": reason, "Next 30 Minutes": reason},
    ]


def _classify_move(delta: float, threshold: float) -> str:
    if delta >= threshold:
        return "UP"
    if delta <= -threshold:
        return "DOWN"
    return "RANGE"


def _resolve(rows: list[dict[str, Any]], *, now: datetime, price: float) -> list[dict[str, Any]]:
    ts = now.timestamp()
    out: list[dict[str, Any]] = []
    for item in rows:
        row = deepcopy(item)
        created = _epoch(row.get("created_at"))
        start = _num(row.get("start_price"), 0)
        threshold = max(5.0, _num(row.get("validation_threshold"), 5.0))
        if start > 0 and created > 0:
            for horizon in (15, 30):
                result_key = f"result_{horizon}m"
                if row.get(result_key):
                    continue
                elapsed = ts - created
                if elapsed >= horizon * 60:
                    if elapsed <= horizon * 60 + 360:
                        delta = round(price - start, 2)
                        outcome = _classify_move(delta, threshold)
                        probs = row.get(f"probabilities_{horizon}m", {}) if isinstance(row.get(f"probabilities_{horizon}m", {}), Mapping) else {}
                        predicted = max(("UP", "DOWN", "RANGE"), key=lambda k: _num(probs.get(k), 0))
                        expected = row.get(f"path_{horizon}m", {}) if isinstance(row.get(f"path_{horizon}m", {}), Mapping) else {}
                        likely_low = _num(expected.get("likely_low"), 0)
                        likely_high = _num(expected.get("likely_high"), 0)
                        row[result_key] = {
                            "resolved_at": _iso(now),
                            "end_price": round(price, 2),
                            "delta": delta,
                            "actual": outcome,
                            "predicted": predicted,
                            "correct": predicted == outcome,
                            "end_in_likely_zone": bool(likely_low > 0 and likely_low <= price <= likely_high),
                            "elapsed_seconds": round(elapsed, 1),
                        }
                    else:
                        row[result_key] = {
                            "resolved_at": _iso(now),
                            "status": "MISSED_WINDOW",
                            "elapsed_seconds": round(elapsed, 1),
                        }
                    row["updated_at"] = _iso(now)
        out.append(row)
    return out


def _accuracy(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    results = [
        r.get(f"result_{horizon}m") for r in rows
        if isinstance(r.get(f"result_{horizon}m"), Mapping)
        and str((r.get(f"result_{horizon}m") or {}).get("actual", "")) in {"UP", "DOWN", "RANGE"}
    ]
    if not results:
        return {"completed": 0, "accuracy": None, "zone_accuracy": None, "status": "PROVISIONAL"}
    correct = sum(1 for r in results if bool(r.get("correct")))
    zone_correct = sum(1 for r in results if bool(r.get("end_in_likely_zone")))
    accuracy = round(correct / len(results) * 100.0, 1)
    zone_accuracy = round(zone_correct / len(results) * 100.0, 1)
    status = "VALIDATING" if len(results) < 50 else "CALIBRATION_READY"
    return {"completed": len(results), "accuracy": accuracy, "zone_accuracy": zone_accuracy, "status": status}


def _latest_previous_dominant(records: list[dict[str, Any]], horizon: int) -> str:
    for row in reversed(records):
        path = row.get(f"path_{horizon}m", {}) if isinstance(row.get(f"path_{horizon}m", {}), Mapping) else {}
        dominant = str(path.get("dominant", ""))
        if dominant:
            return dominant
        probs = row.get(f"probabilities_{horizon}m", {}) if isinstance(row.get(f"probabilities_{horizon}m", {}), Mapping) else {}
        if probs:
            return max(("UP", "DOWN", "RANGE"), key=lambda k: _num(probs.get(k), 0))
    return ""


def _calibration_reliability_cap(completed: int, horizon: int) -> int:
    """Prevent unvalidated shadow forecasts from displaying false certainty."""
    if completed < 20:
        return 62 if horizon == 15 else 56
    if completed < 50:
        return 70 if horizon == 15 else 64
    if completed < 100:
        return 78 if horizon == 15 else 72
    return 88 if horizon == 15 else 82


def build_market_path_forecast(
    *,
    ai_master: Mapping[str, Any],
    market_snapshot: Mapping[str, Any],
    movement: Mapping[str, Any],
    current_price: float,
    atr_points: float,
    observed_at: datetime,
    market_open: bool,
    state: MutableMapping[str, Any],
    quote_age_seconds: Optional[float] = None,
    option_age_seconds: Optional[float] = None,
    option_evidence_status: str = "SNAPSHOT_READY",
    price_action_context: Optional[Mapping[str, Any]] = None,
    support_level: Optional[float] = None,
    resistance_level: Optional[float] = None,
    support_source: str = "Verified support",
    resistance_source: str = "Verified resistance",
) -> dict[str, Any]:
    """Build a post-AI_MASTER, read-only 15m/30m market path forecast."""
    master = deepcopy(dict(ai_master))
    snapshot = deepcopy(dict(market_snapshot))
    movement_copy = deepcopy(dict(movement))
    authority_before = _authority_fingerprint(master)
    snapshot_id = str(master.get("snapshot_id", "NA"))
    snapshot_match = snapshot_id == str(snapshot.get("snapshot_id", snapshot_id))

    with _FileLock():
        records = _merge_records(_read(), state.get(_STATE_KEY, []))
        records = _resolve(records, now=observed_at, price=current_price)

        projection = master.get("projection", {}) if isinstance(master.get("projection", {}), Mapping) else {}
        raw = _num(projection.get("raw"), 0.0)
        if raw == 0:
            bullish = _num(projection.get("bullish"), 50.0)
            raw = (bullish - 50.0) * 2.0
        move_bias = _num(movement_copy.get("movement_bias"), 0.0)
        phase = str(movement_copy.get("phase", "NORMAL")).upper()
        conflicts = _extract_conflicts(master)
        availability = _availability_assessment(
            master,
            movement_copy,
            quote_age_seconds,
            option_age_seconds,
            observed_at=observed_at,
            market_open=market_open,
            option_evidence_status=option_evidence_status,
            price_action_context=price_action_context,
        )
        hard_reasons = list(availability.get("hard_reasons", []) or [])
        limited_reasons = list(availability.get("limited_reasons", []) or [])
        if not snapshot_match:
            hard_reasons.append("snapshot ID mismatch")
        hard_reasons = list(dict.fromkeys(hard_reasons))
        availability_mode = "UNAVAILABLE" if hard_reasons else ("LIMITED" if limited_reasons else "FULL")
        freshness_reasons = hard_reasons + limited_reasons

        integrity = master.get("department_integrity", {}) if isinstance(master.get("department_integrity", {}), Mapping) else {}
        integrity_score = _num(integrity.get("score"), 70)
        data_conf = _num(master.get("data_confidence"), 0)
        direction_conf = _num(master.get("direction_confidence"), 50)
        recent_samples = int(_num(movement_copy.get("recent_sample_count", 0)))
        sample_score = _clamp(recent_samples / 8.0 * 100.0, 0.0, 100.0)
        evidence_bonus = 10 if availability_mode == "FULL" else (4 if availability_mode == "LIMITED" else 0)
        base_rel = data_conf * 0.35 + integrity_score * 0.25 + direction_conf * 0.20 + sample_score * 0.10 + evidence_bonus
        base_rel -= len(conflicts) * 6
        if availability_mode == "LIMITED":
            # Honest reliability reduction: a limited forecast is useful for
            # path awareness but must never look like full confirmation.
            base_rel -= 8 + min(12, max(0, len(limited_reasons) - 1) * 4)
        if phase == "RANGE":
            base_rel -= 5
        hour_min = observed_at.hour * 60 + observed_at.minute
        if 9 * 60 + 15 <= hour_min < 9 * 60 + 20:
            base_rel = min(base_rel, 50)
        if 12 * 60 + 15 <= hour_min < 13 * 60 + 30:
            base_rel = min(base_rel, 60)
        if not market_open:
            base_rel = 0

        # Direction always starts with the final AI_MASTER projection. Movement
        # is only a short-term timing adjustment; barriers never invent direction.
        # When continuity is limited, reduce movement timing weight so a stale or
        # discontinuous refresh cannot overpower the one final AI_MASTER view.
        if availability_mode == "LIMITED":
            dir15 = _clamp(raw * 0.88 + move_bias * 0.12, -100, 100)
            dir30 = _clamp(raw * 0.92 + move_bias * 0.08, -100, 100)
        else:
            dir15 = _clamp(raw * 0.72 + move_bias * 0.28, -100, 100)
            dir30 = _clamp(raw * 0.84 + move_bias * 0.16, -100, 100)
        range15 = 25 + len(conflicts) * 6 - abs(dir15) * 0.16
        range30 = 30 + len(conflicts) * 5 - abs(dir30) * 0.13
        if availability_mode == "LIMITED":
            range15 += 8
            range30 += 10
        if phase == "RANGE":
            range15 += 20
            range30 += 16
        elif phase in {"RECOVERY", "PULLBACK_DOWN"}:
            range15 -= 4

        barriers = _barrier_geometry(
            current_price=current_price,
            support_level=support_level,
            resistance_level=resistance_level,
        )
        status = "UNAVAILABLE" if availability_mode == "UNAVAILABLE" else ("LIMITED" if availability_mode == "LIMITED" else "AVAILABLE")

        if status in {"AVAILABLE", "LIMITED"}:
            previous15 = _latest_previous_dominant(records, 15)
            previous30 = _latest_previous_dominant(records, 30)
            validation15_pre = _accuracy(records, 15)
            validation30_pre = _accuracy(records, 30)
            reliability15 = min(base_rel, _calibration_reliability_cap(int(validation15_pre.get("completed", 0)), 15))
            reliability30 = min(base_rel - 8, _calibration_reliability_cap(int(validation30_pre.get("completed", 0)), 30))
            if availability_mode == "LIMITED":
                reliability15 = min(reliability15, 54)
                reliability30 = min(reliability30, 48)
            horizon15 = _build_horizon(
                horizon=15,
                direction_score=dir15,
                range_score=range15,
                reliability=reliability15,
                current_price=current_price,
                atr_points=atr_points,
                movement=movement_copy,
                market_snapshot=snapshot,
                barriers=barriers,
                conflicts=conflicts,
                previous_dominant=previous15,
            )
            horizon30 = _build_horizon(
                horizon=30,
                direction_score=dir30,
                range_score=range30,
                reliability=reliability30,
                current_price=current_price,
                atr_points=atr_points,
                movement=movement_copy,
                market_snapshot=snapshot,
                barriers=barriers,
                conflicts=conflicts,
                previous_dominant=previous30,
            )
            if int(validation15_pre.get("completed", 0)) < 20 and horizon15.get("status") == "CONFIRMED PATH":
                horizon15["status"] = "EARLY OUTLOOK / PROVISIONAL"
            if int(validation30_pre.get("completed", 0)) < 20 and horizon30.get("status") == "CONFIRMED PATH":
                horizon30["status"] = "EARLY OUTLOOK / PROVISIONAL"
            horizon15["evidence_mode"] = availability_mode
            horizon30["evidence_mode"] = availability_mode
            if availability_mode == "LIMITED":
                horizon15["status"] = "LIMITED OUTLOOK / LOW RELIABILITY"
                horizon30["status"] = "LIMITED CONFIRMATION / LOW RELIABILITY"
            evidence_note = (
                "; ".join(limited_reasons)
                if limited_reasons
                else "Fresh continuous same-snapshot evidence"
            )
            rows_ui = _comparison_rows(
                horizon15,
                horizon30,
                current_price=current_price,
                barriers=barriers,
                support_source=str(support_source),
                resistance_source=str(resistance_source),
                evidence_mode=availability_mode,
                evidence_note=evidence_note,
            )

            bucket = observed_at.replace(minute=(observed_at.minute // 5) * 5, second=0, microsecond=0)
            forecast_id = f"MARKET_PATH:{bucket.isoformat()}"
            if not any(str(r.get("forecast_id")) == forecast_id for r in records):
                forecast = {
                    "forecast_id": forecast_id,
                    "snapshot_id": snapshot_id,
                    "created_at": _iso(observed_at),
                    "updated_at": _iso(observed_at),
                    "start_price": round(current_price, 2),
                    "validation_threshold": round(max(5.0, abs(atr_points) * 0.12), 2),
                    "probabilities_15m": {
                        "UP": horizon15["up_probability"],
                        "DOWN": horizon15["down_probability"],
                        "RANGE": horizon15["range_probability"],
                    },
                    "probabilities_30m": {
                        "UP": horizon30["up_probability"],
                        "DOWN": horizon30["down_probability"],
                        "RANGE": horizon30["range_probability"],
                    },
                    "path_15m": horizon15,
                    "path_30m": horizon30,
                    "reliability_15m": horizon15["reliability"],
                    "reliability_30m": horizon30["reliability"],
                    "support_level": barriers.get("support"),
                    "resistance_level": barriers.get("resistance"),
                    "support_source": str(support_source),
                    "resistance_source": str(resistance_source),
                    "authority": "READ_ONLY_AFTER_AI_MASTER",
                    "authority_fingerprint": authority_before,
                    "availability_mode": availability_mode,
                    "degradation_reasons": list(limited_reasons),
                    "option_evidence_status": str(availability.get("option_evidence_status", option_evidence_status)),
                    "movement_continuity_status": str(availability.get("continuity_status", "UNKNOWN")),
                    "candle_fallback": deepcopy(availability.get("candle_fallback", {})),
                }
                records.append(forecast)
        else:
            horizon15 = {}
            horizon30 = {}
            rows_ui = _unavailable_rows(" / ".join(hard_reasons) or "MARKET CLOSED")

        records = _merge_records(records)
        state[_STATE_KEY] = records
        _write(records)

    # A second fingerprint proves the local immutable copy was not altered by
    # forecast calculations.  The caller also passes a deepcopy, so the live
    # AI_MASTER object has no feedback path from this module.
    authority_after = _authority_fingerprint(master)
    authority_intact = authority_before == authority_after

    evidence_rows = master.get("evidence_rows", []) if isinstance(master.get("evidence_rows", []), list) else []
    sorted_evidence = sorted(
        [r for r in evidence_rows if isinstance(r, Mapping)],
        key=lambda r: abs(_num(r.get("Bias"), 0)),
        reverse=True,
    )
    supporting = [f"{r.get('Signal')}: {_num(r.get('Bias')):+.0f}" for r in sorted_evidence[:3]]
    likely_path = ""
    if horizon15 and horizon30:
        mode_prefix = "LIMITED evidence — " if availability_mode == "LIMITED" else ""
        likely_path = (
            f"{mode_prefix}15m {horizon15.get('path')} toward {horizon15.get('likely_low'):.0f}–{horizon15.get('likely_high'):.0f}; "
            f"30m {horizon30.get('path')} toward {horizon30.get('likely_low'):.0f}–{horizon30.get('likely_high'):.0f}."
        )

    return {
        "version": "V50.8.7_MARKET_PATH_AVAILABILITY_SHADOW",
        "status": status,
        "availability_mode": availability_mode,
        "snapshot_id": snapshot_id,
        "rows": rows_ui,
        "horizon_15m": horizon15,
        "horizon_30m": horizon30,
        "likely_path_summary": likely_path,
        "supporting_evidence": supporting,
        "conflicts": conflicts,
        "freshness_reasons": freshness_reasons,
        "hard_block_reasons": hard_reasons,
        "degradation_reasons": limited_reasons,
        "availability_details": availability,
        "validation_15m": _accuracy(records, 15),
        "validation_30m": _accuracy(records, 30),
        "barrier_context": {
            "support_level": barriers.get("support"),
            "support_source": str(support_source),
            "resistance_level": barriers.get("resistance"),
            "resistance_source": str(resistance_source),
        },
        "authority_contract": {
            "mode": "READ_ONLY_AFTER_AI_MASTER",
            "same_snapshot": bool(snapshot_match),
            "authority_intact": bool(authority_intact),
            "independent_data_fetches": 0,
            "can_change_execution": False,
            "feedback_to_ai_master": False,
            "locked_fields": list(_LOCKED_AUTHORITY_FIELDS),
        },
        "authority_note": "Information only — same snapshot, one AI_MASTER, zero feedback; forecast cannot change action, strategy, strike, SL or target.",
    }


# Compatibility wrapper for earlier tests/imports.  It delegates to the one and
# only forecast implementation; it does not create a second engine.
def build_short_horizon_outlook(**kwargs: Any) -> dict[str, Any]:
    return build_market_path_forecast(**kwargs)
