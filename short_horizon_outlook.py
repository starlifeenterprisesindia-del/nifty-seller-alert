"""Read-only 15/30 minute market outlook derived after AI_MASTER judgement.

This module is deliberately *not* a decision engine. It cannot issue BUY/SELL,
choose strikes, change confidence, or feed its output back into AI_MASTER. It
only expresses the already-approved snapshot evidence as calibrated-looking
UP/DOWN/RANGE percentages and records shadow outcomes for validation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
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
_STATE_KEY = "v5085_short_horizon_forecasts"
_MAX_RECORDS = 500
_THREAD_LOCK = threading.RLock()


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
        json.dumps({"schema_version": 1, "updated_at": _iso(), "records": rows[-_MAX_RECORDS:]}, separators=(",", ":"), default=str),
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
    range_p = _clamp(range_score, 12.0, 72.0)
    directional_mass = 100.0 - range_p
    # Stable sigmoid; score +/-100 maps to a strong but never absolute split.
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


def _extract_conflicts(master: Mapping[str, Any]) -> list[str]:
    warnings = [str(x) for x in list(master.get("warnings", []) or []) + list(master.get("blockers", []) or [])]
    return [x for x in warnings if "conflict" in x.lower() or "hold" in x.lower()][:5]


def _freshness_ok(master: Mapping[str, Any], movement: Mapping[str, Any], quote_age: Optional[float], option_age: Optional[float]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if str(master.get("data_flow_status", "")).upper() != "FRESH":
        reasons.append("data flow not fresh")
    if str(master.get("oi_sync_status", "")).upper() not in {"OK", "SNAPSHOT_READY"}:
        reasons.append("OI sync not ready")
    if quote_age is not None and quote_age > 12:
        reasons.append("quote stale")
    if option_age is not None and option_age > 12:
        reasons.append("option chain stale")
    if int(_num(movement.get("recent_sample_count", 0))) < 2:
        reasons.append("insufficient recent movement samples")
    if str(movement.get("continuity_status", "")).upper() in {"GAP_RESET", "PREOPEN_BLOCKED"}:
        reasons.append("movement continuity reset")
    integrity = master.get("department_integrity", {}) if isinstance(master.get("department_integrity", {}), Mapping) else {}
    if not bool(integrity.get("critical_ok", True)):
        reasons.append("critical DSP integrity hold")
    return not reasons, reasons


def _build_row(
    *,
    horizon: int,
    direction_score: float,
    range_score: float,
    reliability: float,
    current_price: float,
    atr_points: float,
) -> dict[str, Any]:
    up, down, range_p = _probabilities(direction_score, range_score)
    scale = 0.48 if horizon == 15 else 0.78
    half_width = max(10.0 if horizon == 15 else 16.0, abs(atr_points) * scale)
    centre_shift = direction_score / 100.0 * half_width * 0.35
    centre = current_price + centre_shift
    return {
        "Horizon": f"Next {horizon}m",
        "UP %": up,
        "DOWN %": down,
        "RANGE %": range_p,
        "Most Likely": _dominant(up, down, range_p),
        "Reliability %": int(round(_clamp(reliability, 0, 100))),
        "Expected Zone": f"{centre-half_width:.0f}–{centre+half_width:.0f}",
        "Status": "SHADOW / INFO ONLY",
    }


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
                    # A result is valid only near the requested horizon. If the
                    # app was closed for much longer, do not pretend the later
                    # price was the exact 15m/30m outcome.
                    if elapsed <= horizon * 60 + 360:
                        delta = round(price - start, 2)
                        outcome = _classify_move(delta, threshold)
                        probs = row.get(f"probabilities_{horizon}m", {}) if isinstance(row.get(f"probabilities_{horizon}m", {}), Mapping) else {}
                        predicted = max(("UP", "DOWN", "RANGE"), key=lambda k: _num(probs.get(k), 0))
                        row[result_key] = {
                            "resolved_at": _iso(now),
                            "end_price": round(price, 2),
                            "delta": delta,
                            "actual": outcome,
                            "predicted": predicted,
                            "correct": predicted == outcome,
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
        return {"completed": 0, "accuracy": None, "status": "PROVISIONAL"}
    correct = sum(1 for r in results if bool(r.get("correct")))
    accuracy = round(correct / len(results) * 100.0, 1)
    status = "VALIDATING" if len(results) < 50 else "CALIBRATION_READY"
    return {"completed": len(results), "accuracy": accuracy, "status": status}


def build_short_horizon_outlook(
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
) -> dict[str, Any]:
    """Create a read-only outlook and update shadow validation history."""
    with _FileLock():
        records = _merge_records(_read(), state.get(_STATE_KEY, []))
        records = _resolve(records, now=observed_at, price=current_price)

        projection = ai_master.get("projection", {}) if isinstance(ai_master.get("projection", {}), Mapping) else {}
        raw = _num(projection.get("raw"), 0.0)
        if raw == 0:
            bullish = _num(projection.get("bullish"), 50.0)
            raw = (bullish - 50.0) * 2.0
        move_bias = _num(movement.get("movement_bias"), 0.0)
        phase = str(movement.get("phase", "NORMAL")).upper()
        conflicts = _extract_conflicts(ai_master)
        fresh_ok, freshness_reasons = _freshness_ok(ai_master, movement, quote_age_seconds, option_age_seconds)

        integrity = ai_master.get("department_integrity", {}) if isinstance(ai_master.get("department_integrity", {}), Mapping) else {}
        integrity_score = _num(integrity.get("score"), 70)
        data_conf = _num(ai_master.get("data_confidence"), 0)
        direction_conf = _num(ai_master.get("direction_confidence"), 50)
        base_rel = data_conf * 0.40 + integrity_score * 0.25 + direction_conf * 0.20 + (15 if fresh_ok else 0)
        base_rel -= len(conflicts) * 6
        if phase == "RANGE":
            base_rel -= 5
        hour_min = observed_at.hour * 60 + observed_at.minute
        if 9 * 60 + 15 <= hour_min < 9 * 60 + 20:
            base_rel = min(base_rel, 50)
        if 12 * 60 + 15 <= hour_min < 13 * 60 + 30:
            base_rel = min(base_rel, 60)
        if not market_open:
            base_rel = 0

        dir15 = _clamp(raw * 0.62 + move_bias * 0.38, -100, 100)
        dir30 = _clamp(raw * 0.78 + move_bias * 0.22, -100, 100)
        range15 = 25 + len(conflicts) * 6 - abs(dir15) * 0.16
        range30 = 30 + len(conflicts) * 5 - abs(dir30) * 0.13
        if phase == "RANGE":
            range15 += 20
            range30 += 16
        elif phase in {"RECOVERY", "PULLBACK_DOWN"}:
            range15 -= 4

        status = "AVAILABLE" if market_open and fresh_ok else "UNAVAILABLE"
        if status == "AVAILABLE":
            row15 = _build_row(horizon=15, direction_score=dir15, range_score=range15, reliability=base_rel, current_price=current_price, atr_points=atr_points)
            row30 = _build_row(horizon=30, direction_score=dir30, range_score=range30, reliability=base_rel - 8, current_price=current_price, atr_points=atr_points)
            rows_ui = [row15, row30]

            # One official shadow forecast per five-minute bucket. A rerun can
            # update the visible table, but it never overwrites the saved case.
            bucket = observed_at.replace(minute=(observed_at.minute // 5) * 5, second=0, microsecond=0)
            forecast_id = f"SHORT_OUTLOOK:{bucket.isoformat()}"
            if not any(str(r.get("forecast_id")) == forecast_id for r in records):
                forecast = {
                    "forecast_id": forecast_id,
                    "snapshot_id": str(ai_master.get("snapshot_id", "NA")),
                    "created_at": _iso(observed_at),
                    "updated_at": _iso(observed_at),
                    "start_price": round(current_price, 2),
                    "validation_threshold": round(max(5.0, abs(atr_points) * 0.12), 2),
                    "probabilities_15m": {"UP": row15["UP %"], "DOWN": row15["DOWN %"], "RANGE": row15["RANGE %"]},
                    "probabilities_30m": {"UP": row30["UP %"], "DOWN": row30["DOWN %"], "RANGE": row30["RANGE %"]},
                    "reliability_15m": row15["Reliability %"],
                    "reliability_30m": row30["Reliability %"],
                    "authority": "READ_ONLY_AFTER_AI_MASTER",
                }
                records.append(forecast)
        else:
            rows_ui = [
                {"Horizon": "Next 15m", "UP %": "-", "DOWN %": "-", "RANGE %": "-", "Most Likely": "UNAVAILABLE", "Reliability %": 0, "Expected Zone": "-", "Status": " / ".join(freshness_reasons) or "MARKET CLOSED"},
                {"Horizon": "Next 30m", "UP %": "-", "DOWN %": "-", "RANGE %": "-", "Most Likely": "UNAVAILABLE", "Reliability %": 0, "Expected Zone": "-", "Status": " / ".join(freshness_reasons) or "MARKET CLOSED"},
            ]

        records = _merge_records(records)
        state[_STATE_KEY] = records
        _write(records)

    # Evidence text is descriptive and uses existing AI_MASTER fields only.
    evidence_rows = ai_master.get("evidence_rows", []) if isinstance(ai_master.get("evidence_rows", []), list) else []
    sorted_evidence = sorted(
        [r for r in evidence_rows if isinstance(r, Mapping)],
        key=lambda r: abs(_num(r.get("Bias"), 0)),
        reverse=True,
    )
    supporting = [f"{r.get('Signal')}: {_num(r.get('Bias')):+.0f}" for r in sorted_evidence[:3]]
    return {
        "version": "V50.8.5_SHORT_HORIZON_SHADOW",
        "status": status,
        "snapshot_id": str(ai_master.get("snapshot_id", "NA")),
        "rows": rows_ui,
        "supporting_evidence": supporting,
        "conflicts": conflicts,
        "freshness_reasons": freshness_reasons,
        "validation_15m": _accuracy(records, 15),
        "validation_30m": _accuracy(records, 30),
        "authority_note": "Information only — AI_MASTER controls execution; outlook cannot change action, strategy, strike, SL or target.",
    }
