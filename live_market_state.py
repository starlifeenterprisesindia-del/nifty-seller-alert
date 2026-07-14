"""
Nifty Seller AI - V50.8.3 live market state.

Purpose:
- Preserve same-day compact price/snapshot memory across Streamlit reruns and
  browser reconnects.
- Calculate recent 1/3/5 minute movement, recovery from session low and pullback
  from session high.
- Persist the latest authoritative market snapshot and option-chain delta map.

This module never issues a trade instruction and never fetches market data.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional


_MAX_SAMPLES = 240
_STATE_DIR = Path(os.environ.get("NIFTY_RUNTIME_STATE_DIR", ".runtime_state"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _now(observed_at: Optional[datetime] = None) -> datetime:
    return observed_at if isinstance(observed_at, datetime) else datetime.now()


def _day_key(observed_at: Optional[datetime] = None) -> str:
    return _now(observed_at).strftime("%Y-%m-%d")


def _path(kind: str, observed_at: Optional[datetime] = None) -> Path:
    return _STATE_DIR / f"{kind}_{_day_key(observed_at)}.json"


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value
    except Exception:
        return default


def _write_json(path: Path, value: Any) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=True, separators=(",", ":"), default=str)
        tmp.replace(path)
        return True
    except Exception:
        return False


def _merge_samples(*groups: Any) -> list[dict]:
    """Merge same-day session/disk samples without allowing refresh history loss."""
    merged: Dict[tuple, dict] = {}
    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, Mapping):
                continue
            row = dict(item)
            ts = round(_safe_float(row.get("ts"), 0.0), 3)
            if ts <= 0:
                continue
            snapshot_id = str(row.get("snapshot_id", ""))
            price = round(_safe_float(row.get("price"), 0.0), 2)
            key = (ts, snapshot_id, price)
            merged[key] = row
    rows = sorted(merged.values(), key=lambda item: _safe_float(item.get("ts"), 0.0))
    return rows[-_MAX_SAMPLES:]


def _nearest_older(samples: list[dict], now_ts: float, seconds: int) -> Optional[dict]:
    """Return a genuinely nearby historical sample, never an hours-old fallback.

    A browser reconnect may restore the full same-day history. That history is
    useful for session high/low, but it must not be used as a 1/3/5-minute
    reference when the most recent prior sample is far away in time.
    """
    target = now_ts - seconds
    older = [item for item in samples if _safe_float(item.get("ts"), 0.0) <= target]
    if not older:
        return None
    candidate = min(older, key=lambda item: abs(_safe_float(item.get("ts"), 0.0) - target))
    candidate_ts = _safe_float(candidate.get("ts"), 0.0)
    tolerance = max(75.0, float(seconds) * 0.75)
    if candidate_ts <= 0 or abs(candidate_ts - target) > tolerance:
        return None
    if now_ts - candidate_ts > float(seconds) + tolerance:
        return None
    return candidate


def _window_move(samples: list[dict], price: float, now_ts: float, seconds: int) -> Optional[float]:
    previous = _nearest_older(samples, now_ts, seconds)
    if not previous:
        return None
    previous_price = _safe_float(previous.get("price"), 0.0)
    if previous_price <= 0:
        return None
    return round(price - previous_price, 2)


def _movement_phase(
    *,
    price: float,
    session_low: float,
    session_high: float,
    atr: float,
    move_1m: Optional[float],
    move_3m: Optional[float],
    move_5m: Optional[float],
) -> Dict[str, Any]:
    atr = max(_safe_float(atr, 0.0), 1.0)
    from_low = max(0.0, price - session_low) if session_low > 0 else 0.0
    from_high = max(0.0, session_high - price) if session_high > 0 else 0.0
    session_range = max(session_high - session_low, 1.0) if session_high > 0 and session_low > 0 else 1.0
    range_position = max(0.0, min(1.0, (price - session_low) / session_range)) if session_low > 0 else 0.5

    m1 = _safe_float(move_1m, 0.0)
    m3 = _safe_float(move_3m, 0.0)
    m5 = _safe_float(move_5m, 0.0)

    recovery_score = 0.0
    recovery_score += min(35.0, from_low / atr * 25.0)
    recovery_score += min(20.0, max(m1, 0.0) / atr * 35.0)
    recovery_score += min(25.0, max(m3, 0.0) / atr * 30.0)
    recovery_score += min(15.0, max(m5, 0.0) / atr * 18.0)
    recovery_score += max(0.0, range_position - 0.35) * 10.0

    pullback_score = 0.0
    pullback_score += min(35.0, from_high / atr * 25.0)
    pullback_score += min(20.0, max(-m1, 0.0) / atr * 35.0)
    pullback_score += min(25.0, max(-m3, 0.0) / atr * 30.0)
    pullback_score += min(15.0, max(-m5, 0.0) / atr * 18.0)
    pullback_score += max(0.0, 0.65 - range_position) * 10.0

    recovery_score = max(0.0, min(100.0, recovery_score))
    pullback_score = max(0.0, min(100.0, pullback_score))
    signed_bias = max(-85.0, min(85.0, recovery_score - pullback_score))

    threshold_points = max(28.0, atr * 0.55)
    recovery_hold_threshold = max(45.0, atr * 0.70)
    pullback_hold_threshold = max(45.0, atr * 0.70)
    sharp_down = m1 < -max(10.0, atr * 0.18) or m3 < -max(18.0, atr * 0.30)
    sharp_up = m1 > max(10.0, atr * 0.18) or m3 > max(18.0, atr * 0.30)

    if from_low >= threshold_points and (m3 >= max(12.0, atr * 0.22) or m5 >= max(18.0, atr * 0.30)):
        phase = "STRONG_RECOVERY"
        label = "Strong recovery from session low"
    elif from_high >= threshold_points and (m3 <= -max(12.0, atr * 0.22) or m5 <= -max(18.0, atr * 0.30)):
        phase = "STRONG_PULLBACK_DOWN"
        label = "Strong pullback from session high"
    elif from_low >= recovery_hold_threshold and range_position >= 0.68 and not sharp_down:
        # A completed 100+ point recovery must not become RANGE merely because
        # the latest three minutes paused near the session high.
        phase = "RECOVERY"
        label = "Recovery holding near session high"
    elif from_high >= pullback_hold_threshold and range_position <= 0.32 and not sharp_up:
        phase = "PULLBACK_DOWN"
        label = "Pullback holding near session low"
    elif from_low >= max(18.0, atr * 0.35) and (m1 > 0 or m3 > 0):
        phase = "RECOVERY"
        label = "Recovery / short-covering phase"
    elif from_high >= max(18.0, atr * 0.35) and (m1 < 0 or m3 < 0):
        phase = "PULLBACK_DOWN"
        label = "Downward pullback phase"
    elif abs(m3) <= max(8.0, atr * 0.15) and abs(m5) <= max(12.0, atr * 0.20):
        phase = "RANGE"
        label = "Range / low momentum"
    else:
        phase = "NORMAL"
        label = "Normal movement"

    return {
        "phase": phase,
        "label": label,
        "recovery_score": round(recovery_score, 1),
        "pullback_score": round(pullback_score, 1),
        "movement_bias": round(signed_bias, 1),
        "recovery_from_low": round(from_low, 2),
        "pullback_from_high": round(from_high, 2),
        "session_range": round(session_range, 2),
        "range_position_pct": round(range_position * 100.0, 1),
    }


def update_live_market_state(
    state: MutableMapping[str, Any],
    *,
    price: Any,
    atr: Any = 0.0,
    session_high: Any = 0.0,
    session_low: Any = 0.0,
    snapshot_id: str = "",
    option_bias: Any = 0.0,
    pcr: Any = 0.0,
    observed_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Update compact same-day movement memory and return movement facts."""
    now = _now(observed_at)
    price_f = _safe_float(price, 0.0)
    if price_f <= 0:
        return {
            "ready": False,
            "phase": "UNAVAILABLE",
            "label": "Price unavailable",
            "movement_bias": 0.0,
            "sample_count": 0,
        }

    day = now.strftime("%Y-%m-%d")
    state_key = "v505_live_market_memory"
    session_memory = state.get(state_key)
    if not isinstance(session_memory, Mapping) or str(session_memory.get("date", "")) != day:
        session_memory = {"date": day, "samples": []}
    disk_memory = _read_json(_path("market_memory", now), {"date": day, "samples": []})
    if not isinstance(disk_memory, Mapping) or str(disk_memory.get("date", "")) != day:
        disk_memory = {"date": day, "samples": []}

    # Always merge disk + current Streamlit session. A browser reconnect,
    # server rerun, or shortened session object can no longer reduce 7 samples
    # back to 3 while the same trading day is active.
    samples = _merge_samples(
        list(disk_memory.get("samples", []) or []),
        list(session_memory.get("samples", []) or []),
    )
    memory = {
        "date": day,
        "samples": samples,
        "session_low": min(
            [value for value in (
                _safe_float(disk_memory.get("session_low"), 0.0),
                _safe_float(session_memory.get("session_low"), 0.0),
            ) if value > 0] or [0.0]
        ),
        "session_high": max(
            _safe_float(disk_memory.get("session_high"), 0.0),
            _safe_float(session_memory.get("session_high"), 0.0),
        ),
    }

    ts = now.timestamp()
    current = {
        "ts": round(ts, 3),
        "time": now.isoformat(timespec="seconds"),
        "price": round(price_f, 2),
        "snapshot_id": str(snapshot_id or ""),
        "option_bias": round(_safe_float(option_bias, 0.0), 2),
        "pcr": round(_safe_float(pcr, 0.0), 4),
    }

    # Do not create duplicate samples for the same payload within a few seconds.
    if samples:
        last = samples[-1]
        same_payload = (
            abs(_safe_float(last.get("price"), 0.0) - price_f) < 0.01
            and str(last.get("snapshot_id", "")) == str(snapshot_id or "")
            and ts - _safe_float(last.get("ts"), 0.0) < 8.0
        )
        if same_payload:
            samples[-1] = current
        else:
            samples.append(current)
    else:
        samples.append(current)
    samples = samples[-_MAX_SAMPLES:]

    observed_prices = [_safe_float(item.get("price"), 0.0) for item in samples if _safe_float(item.get("price"), 0.0) > 0]
    supplied_low = _safe_float(session_low, 0.0)
    supplied_high = _safe_float(session_high, 0.0)
    remembered_low = _safe_float(memory.get("session_low"), 0.0)
    remembered_high = _safe_float(memory.get("session_high"), 0.0)
    low_candidates = observed_prices + ([supplied_low] if supplied_low > 0 else []) + ([remembered_low] if remembered_low > 0 else [])
    high_candidates = observed_prices + ([supplied_high] if supplied_high > 0 else []) + ([remembered_high] if remembered_high > 0 else [])
    session_low_f = min(low_candidates) if low_candidates else price_f
    session_high_f = max(high_candidates) if high_candidates else price_f

    previous_sample = samples[-2] if len(samples) >= 2 else None
    previous_age = ts - _safe_float(previous_sample.get("ts"), 0.0) if isinstance(previous_sample, Mapping) else 0.0
    continuity_ok = bool(previous_sample is not None and 0 <= previous_age <= 120.0)
    previous_price = _safe_float(previous_sample.get("price"), price_f) if continuity_ok else price_f
    last_move = round(price_f - previous_price, 2)
    move_1m = _window_move(samples, price_f, ts, 60)
    move_3m = _window_move(samples, price_f, ts, 180)
    move_5m = _window_move(samples, price_f, ts, 300)
    phase = _movement_phase(
        price=price_f,
        session_low=session_low_f,
        session_high=session_high_f,
        atr=_safe_float(atr, 0.0),
        move_1m=move_1m,
        move_3m=move_3m,
        move_5m=move_5m,
    )

    memory = {
        "date": day,
        "updated_at": now.isoformat(timespec="seconds"),
        "samples": samples,
        "session_low": round(session_low_f, 2),
        "session_high": round(session_high_f, 2),
    }
    state[state_key] = memory
    _write_json(_path("market_memory", now), memory)

    recent_sample_count = sum(1 for item in samples if ts - _safe_float(item.get("ts"), 0.0) <= 900.0)
    return {
        "ready": recent_sample_count >= 2,
        "sample_count": len(samples),
        "recent_sample_count": recent_sample_count,
        "continuity_status": "LIVE_SEQUENCE" if continuity_ok else ("GAP_RESET" if len(samples) >= 2 else "FIRST_SAMPLE"),
        "previous_sample_age_seconds": round(previous_age, 1) if previous_sample is not None else None,
        "last_move": last_move,
        "move_1m": move_1m,
        "move_3m": move_3m,
        "move_5m": move_5m,
        "session_low": round(session_low_f, 2),
        "session_high": round(session_high_f, 2),
        "observed_at": now.isoformat(timespec="seconds"),
        **phase,
    }


def _fresh_persisted_payload(
    kind: str,
    observed_at: Optional[datetime] = None,
    *,
    max_age_seconds: int = 600,
) -> Dict[str, Any]:
    """Load only a recent same-day comparison payload.

    Previous snapshots and OI maps are comparison evidence, not live authority.
    After a long browser/server gap they are discarded so an old comparison can
    never masquerade as a fresh refresh delta.
    """
    now = _now(observed_at)
    path = _path(kind, now)
    value = _read_json(path, {})
    if not isinstance(value, dict):
        return {}
    persisted_epoch = _safe_float(value.get("_persisted_at_epoch"), 0.0)
    if persisted_epoch <= 0:
        try:
            persisted_epoch = path.stat().st_mtime
        except Exception:
            return {}
    age = now.timestamp() - persisted_epoch
    if age < -30 or age > max(30, int(max_age_seconds)):
        return {}
    return value


def load_previous_snapshot(
    observed_at: Optional[datetime] = None,
    *,
    max_age_seconds: int = 600,
) -> Dict[str, Any]:
    return _fresh_persisted_payload("latest_snapshot", observed_at, max_age_seconds=max_age_seconds)


def save_latest_snapshot(snapshot: Mapping[str, Any], observed_at: Optional[datetime] = None) -> bool:
    if not isinstance(snapshot, Mapping):
        return False
    now = _now(observed_at)
    payload = dict(snapshot)
    payload["_persisted_at"] = now.isoformat(timespec="seconds")
    payload["_persisted_at_epoch"] = round(now.timestamp(), 3)
    return _write_json(_path("latest_snapshot", now), payload)


def load_option_delta_state(
    observed_at: Optional[datetime] = None,
    *,
    max_age_seconds: int = 600,
) -> Dict[str, Any]:
    return _fresh_persisted_payload("option_delta", observed_at, max_age_seconds=max_age_seconds)


def save_option_delta_state(value: Mapping[str, Any], observed_at: Optional[datetime] = None) -> bool:
    now = _now(observed_at)
    payload = dict(value)
    payload["_persisted_at"] = now.isoformat(timespec="seconds")
    payload["_persisted_at_epoch"] = round(now.timestamp(), 3)
    return _write_json(_path("option_delta", now), payload)


def update_projection_memory(
    state: MutableMapping[str, Any],
    *,
    direction: str,
    probability: Any,
    observed_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = _now(observed_at)
    day = now.strftime("%Y-%m-%d")
    key = "v505_projection_memory"
    memory = state.get(key)
    if not isinstance(memory, Mapping) or str(memory.get("date", "")) != day:
        memory = _read_json(_path("projection_memory", now), {"date": day, "history": []})
    memory = dict(memory) if isinstance(memory, Mapping) else {"date": day, "history": []}
    history = [dict(item) for item in memory.get("history", []) if isinstance(item, Mapping)]
    current_probability = max(0, min(100, _safe_int(probability, 50)))
    previous = history[-1] if history else None
    current = {
        "time": now.isoformat(timespec="seconds"),
        "direction": str(direction or "RANGE"),
        "probability": current_probability,
    }
    if not history or previous.get("direction") != current["direction"] or _safe_int(previous.get("probability"), -1) != current_probability:
        history.append(current)
    history = history[-60:]
    memory = {"date": day, "history": history, "updated_at": current["time"]}
    state[key] = memory
    _write_json(_path("projection_memory", now), memory)
    return {
        "previous": previous,
        "current": current,
        "sample_count": len(history),
    }
