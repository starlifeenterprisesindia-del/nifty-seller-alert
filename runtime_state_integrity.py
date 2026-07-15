"""Shared same-day runtime state integrity for Nifty Seller AI V50.8.3.

Purpose
-------
Streamlit ``session_state`` is browser-session scoped. Opening the app on a
phone and laptop, reconnecting, or a Streamlit worker restart can therefore
make bounded histories appear to move backwards even while live Dhan data is
fresh. This module maintains one compact same-day authoritative state file and
merges bounded history safely across sessions.

Safety
------
- No API calls, timers, threads, or background jobs.
- No trade action, confidence, threshold, weight, strategy, candidate, or risk
  logic is changed.
- Only bounded evidence/history keys are persisted.
- Cross-process file locking is used when available.
- State is date-scoped and old-day files are never loaded into a new session.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

try:  # Linux/Streamlit Cloud.
    import fcntl  # type: ignore
except Exception:  # pragma: no cover - Windows/local fallback.
    fcntl = None


_STATE_DIR = Path(os.environ.get("NIFTY_RUNTIME_STATE_DIR", ".runtime_state"))
_THREAD_LOCK = threading.RLock()
_SCHEMA_VERSION = 1
_MAX_FILE_AGE_SECONDS = 14 * 60 * 60

# Same-day bounded evidence/history. UI widget values and live market payloads
# are deliberately excluded.
PERSIST_KEYS = (
    "v14_memory",
    "v1913_market_memory",
    "v24_option_volume_history",
    "v24_compact_decision_history",
    "v29_branch_memory",
    "v29_branch_service_book",
    "v33_case_history_records",
    "v38_barrier_registry",
    "v39_time_phase_registry",
    "v40_heavyweight_history",
    "v41_news_intelligence_history",
    "v42_institutional_behaviour_history",
    "v43_experience_records",
    "v43_experience_sequence",
    "v43_experience_last_snapshot",
    "v43_last_registered_experience",
    "v44_self_review_daily_archive",
    "v45_officer_service_profiles",
    "v45_promotion_board_archive",
    "v46_true_learning_recommendations",
    "v46_true_learning_archive",
    "v49_master_intelligence_history",
    "v5085_fii_dii_journal_records",
    "v5085_short_horizon_forecasts",
)

LIST_LIMITS = {
    "v14_memory": 20,
    "v1913_market_memory": 20,
    "v24_option_volume_history": 5,
    "v24_compact_decision_history": 8,
    "v33_case_history_records": 200,
    "v40_heavyweight_history": 16,
    "v41_news_intelligence_history": 16,
    "v42_institutional_behaviour_history": 16,
    "v43_experience_records": 400,
    "v49_master_intelligence_history": 24,
    "v5085_fii_dii_journal_records": 60,
    "v5085_short_horizon_forecasts": 500,
}

_SEQUENCE_KEYS = {"v43_experience_sequence"}


def _now(value: Optional[datetime] = None) -> datetime:
    return value if isinstance(value, datetime) else datetime.now()


def _day(value: Optional[datetime] = None) -> str:
    return _now(value).strftime("%Y-%m-%d")


def _state_path(value: Optional[datetime] = None) -> Path:
    return _STATE_DIR / f"authoritative_state_{_day(value)}.json"


def _lock_path(value: Optional[datetime] = None) -> Path:
    return _STATE_DIR / f"authoritative_state_{_day(value)}.lock"


@contextmanager
def _file_lock(value: Optional[datetime] = None):
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    with _THREAD_LOCK:
        handle = _lock_path(value).open("a+", encoding="utf-8")
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


def _read(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write(path: Path, value: Mapping[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=True, separators=(",", ":"), default=str)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _iso_epoch(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _json_token(value: Any) -> str:
    try:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        payload = repr(value)
    return hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()


def _record_identity(item: Any) -> str:
    if not isinstance(item, Mapping):
        return "RAW:" + _json_token(item)
    for field in (
        "case_id",
        "snapshot_id",
        "message_id",
        "recommendation_id",
        "id",
        "review_date",
        "session_date",
        "observed_at",
        "timestamp",
        "time",
        "created_at",
        "Date",
        "forecast_id",
    ):
        value = item.get(field)
        if value not in (None, ""):
            # Case history may contain multiple records for one case/snapshot;
            # snapshot is the stronger identity when present.
            if field == "case_id" and item.get("snapshot_id"):
                continue
            return f"{field}:{value}"
    return "HASH:" + _json_token(item)


def _status_rank(value: Any) -> int:
    text = str(value or "").upper()
    ranks = {
        "PENDING": 1,
        "COLLECTING": 1,
        "COMPLETED": 4,
        "CORRECT": 5,
        "WRONG": 5,
        "NEUTRAL": 3,
        "CLOSED": 4,
        "VERIFIED": 4,
    }
    return ranks.get(text, 0)


def _record_score(item: Mapping[str, Any]) -> tuple:
    observations = item.get("observations", [])
    obs_count = len(observations) if isinstance(observations, list) else 0
    timestamp = max(
        _iso_epoch(item.get("completed_at")),
        _iso_epoch(item.get("updated_at")),
        _iso_epoch(item.get("observed_at")),
        _iso_epoch(item.get("created_at")),
        _iso_epoch(item.get("timestamp")),
        _iso_epoch(item.get("time")),
    )
    status = max(
        _status_rank(item.get("status")),
        _status_rank(item.get("outcome")),
        _status_rank(item.get("state")),
    )
    sequence = max(
        _number(item.get("last_observed_sequence")),
        _number(item.get("registered_sequence")),
        _number(item.get("sequence")),
    )
    return (status, obs_count, sequence, timestamp, len(item))


def _merge_observations(old: Any, new: Any, limit: int = 40) -> list:
    rows: Dict[str, Any] = {}
    for group in (old, new):
        if not isinstance(group, list):
            continue
        for item in group:
            identity = _record_identity(item)
            rows[identity] = deepcopy(item)
    values = list(rows.values())
    values.sort(key=lambda row: (
        _number(row.get("sequence"), 0.0) if isinstance(row, Mapping) else 0.0,
        _iso_epoch(row.get("time")) if isinstance(row, Mapping) else 0.0,
    ))
    return values[-limit:]


def _merge_record(old: Mapping[str, Any], new: Mapping[str, Any]) -> Dict[str, Any]:
    old_d, new_d = dict(old), dict(new)
    # Prefer the more mature/later record, then merge monotonic evidence fields.
    base = deepcopy(new_d if _record_score(new_d) >= _record_score(old_d) else old_d)
    other = old_d if base is not old_d else new_d

    # ``base is not old_d`` is unreliable after deepcopy; determine using score.
    preferred_new = _record_score(new_d) >= _record_score(old_d)
    base = deepcopy(new_d if preferred_new else old_d)
    other = old_d if preferred_new else new_d

    for key, value in other.items():
        if key not in base or base.get(key) in (None, "", [], {}):
            base[key] = deepcopy(value)

    if isinstance(old_d.get("observations"), list) or isinstance(new_d.get("observations"), list):
        base["observations"] = _merge_observations(old_d.get("observations"), new_d.get("observations"))

    for key in (
        "last_observed_sequence",
        "registered_sequence",
        "max_up_points",
        "max_down_points",
        "actual_move_points",
        "touches",
        "resolved",
        "bounce_count",
        "break_count",
        "observations_count",
        "validated_cases",
    ):
        if key in old_d or key in new_d:
            base[key] = max(_number(old_d.get(key)), _number(new_d.get(key)))
            if isinstance(old_d.get(key), int) and isinstance(new_d.get(key), int):
                base[key] = int(base[key])

    # Never downgrade a completed/correct/wrong state to pending.
    for key in ("status", "outcome", "state"):
        if key in old_d or key in new_d:
            old_v, new_v = old_d.get(key), new_d.get(key)
            base[key] = new_v if _status_rank(new_v) >= _status_rank(old_v) else old_v

    return base


def _merge_list(key: str, old: Any, new: Any) -> list:
    rows: Dict[str, Any] = {}
    order: list[str] = []
    for group in (old, new):
        if not isinstance(group, list):
            continue
        for item in group:
            identity = _record_identity(item)
            if identity not in rows:
                order.append(identity)
                rows[identity] = deepcopy(item)
            elif isinstance(rows[identity], Mapping) and isinstance(item, Mapping):
                rows[identity] = _merge_record(rows[identity], item)
            else:
                rows[identity] = deepcopy(item)

    values = [rows[identity] for identity in order if identity in rows]
    # Where timestamps/sequences exist, keep chronological order.
    def sort_key(item: Any) -> tuple:
        if not isinstance(item, Mapping):
            return (0.0, 0.0)
        return (
            max(
                _number(item.get("sequence")),
                _number(item.get("registered_sequence")),
                _number(item.get("last_observed_sequence")),
            ),
            max(
                _iso_epoch(item.get("completed_at")),
                _iso_epoch(item.get("updated_at")),
                _iso_epoch(item.get("observed_at")),
                _iso_epoch(item.get("created_at")),
                _iso_epoch(item.get("timestamp")),
                _iso_epoch(item.get("time")),
            ),
        )
    if any(sort_key(item) != (0.0, 0.0) for item in values):
        values.sort(key=sort_key)
    return values[-LIST_LIMITS.get(key, 80):]


def _merge_branch_service_book(old: Any, new: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    old_d = old if isinstance(old, Mapping) else {}
    new_d = new if isinstance(new, Mapping) else {}
    for branch in set(old_d) | set(new_d):
        a = old_d.get(branch, {}) if isinstance(old_d.get(branch, {}), Mapping) else {}
        b = new_d.get(branch, {}) if isinstance(new_d.get(branch, {}), Mapping) else {}
        merged = dict(a)
        merged.update({k: deepcopy(v) for k, v in b.items() if v not in (None, "")})
        for key in (
            "observations",
            "sop_passes",
            "stable",
            "changed",
            "rising",
            "falling",
            "confidence_total",
            "reliability_score",
        ):
            if key in a or key in b:
                merged[key] = max(_number(a.get(key)), _number(b.get(key)))
                if key not in {"confidence_total", "reliability_score"}:
                    merged[key] = int(merged[key])
        result[str(branch)] = merged
    return result


def _merge_branch_memory(old: Any, new: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    old_d = old if isinstance(old, Mapping) else {}
    new_d = new if isinstance(new, Mapping) else {}
    for branch in set(old_d) | set(new_d):
        result[str(branch)] = _merge_list(
            "v29_branch_memory",
            old_d.get(branch, []),
            new_d.get(branch, []),
        )[-15:]
    return result


def _merge_time_registry(old: Any, new: Any) -> Dict[str, Any]:
    """Merge time-phase evidence without treating a lower live price as older."""
    a = old if isinstance(old, Mapping) else {}
    b = new if isinstance(new, Mapping) else {}
    if a.get("session_date") and b.get("session_date") and a.get("session_date") != b.get("session_date"):
        return deepcopy(dict(b))
    phases_a = a.get("phases", {}) if isinstance(a.get("phases", {}), Mapping) else {}
    phases_b = b.get("phases", {}) if isinstance(b.get("phases", {}), Mapping) else {}
    phases: Dict[str, Any] = {}
    total_a = total_b = 0
    for code in set(phases_a) | set(phases_b):
        pa = phases_a.get(code, {}) if isinstance(phases_a.get(code, {}), Mapping) else {}
        pb = phases_b.get(code, {}) if isinstance(phases_b.get(code, {}), Mapping) else {}
        sa, sb = int(_number(pa.get("samples"))), int(_number(pb.get("samples")))
        total_a += sa
        total_b += sb
        newer = pb if sb >= sa else pa
        older = pa if sb >= sa else pb
        merged = dict(older)
        merged.update(deepcopy(dict(newer)))
        merged["samples"] = max(sa, sb)
        highs = [_number(x.get("high"), 0.0) for x in (pa, pb) if _number(x.get("high"), 0.0) > 0]
        lows = [_number(x.get("low"), 0.0) for x in (pa, pb) if _number(x.get("low"), 0.0) > 0]
        if highs:
            merged["high"] = max(highs)
        if lows:
            merged["low"] = min(lows)
        merged["direction_changes"] = max(int(_number(pa.get("direction_changes"))), int(_number(pb.get("direction_changes"))))
        # first_price belongs to the longer/older sequence; last_price/direction
        # belong to the sequence with more samples.
        if sa and sb:
            merged["first_price"] = pa.get("first_price") if sa >= sb else pb.get("first_price")
        phases[str(code)] = merged
    latest = b if total_b >= total_a else a
    return {
        "session_date": str(latest.get("session_date") or a.get("session_date") or b.get("session_date") or ""),
        "phases": phases,
        "last_price": latest.get("last_price"),
    }


def _merge_dict(old: Any, new: Any) -> Dict[str, Any]:
    old_d = old if isinstance(old, Mapping) else {}
    new_d = new if isinstance(new, Mapping) else {}
    result: Dict[str, Any] = deepcopy(dict(old_d))
    for key, value in new_d.items():
        if key not in result:
            result[key] = deepcopy(value)
            continue
        old_value = result[key]
        if isinstance(old_value, list) or isinstance(value, list):
            result[key] = _merge_list(str(key), old_value, value)
        elif isinstance(old_value, Mapping) or isinstance(value, Mapping):
            result[key] = _merge_dict(old_value, value)
        elif isinstance(old_value, (int, float)) and isinstance(value, (int, float)):
            # Registries mostly hold counters/reliability; monotonic max prevents
            # a second browser session from rolling evidence backwards.
            result[key] = max(old_value, value)
        elif value not in (None, ""):
            result[key] = deepcopy(value)
    return result


def _merge_value(key: str, old: Any, new: Any) -> Any:
    if key in _SEQUENCE_KEYS:
        return int(max(_number(old), _number(new)))
    if key == "v29_branch_service_book":
        return _merge_branch_service_book(old, new)
    if key == "v29_branch_memory":
        return _merge_branch_memory(old, new)
    if key == "v39_time_phase_registry":
        return _merge_time_registry(old, new)
    if isinstance(old, list) or isinstance(new, list):
        return _merge_list(key, old, new)
    if isinstance(old, Mapping) or isinstance(new, Mapping):
        return _merge_dict(old, new)
    if new not in (None, ""):
        return deepcopy(new)
    return deepcopy(old)


def _payload_valid(payload: Mapping[str, Any], observed_at: datetime) -> bool:
    if str(payload.get("date", "")) != observed_at.strftime("%Y-%m-%d"):
        return False
    updated_epoch = _number(payload.get("updated_epoch"), 0.0)
    if updated_epoch and observed_at.timestamp() - updated_epoch > _MAX_FILE_AGE_SECONDS:
        return False
    return isinstance(payload.get("keys", {}), Mapping)


def restore_authoritative_state(
    state: MutableMapping[str, Any],
    *,
    observed_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Restore/merge shared same-day evidence into the current Streamlit session."""
    now = _now(observed_at)
    path = _state_path(now)
    restored: list[str] = []
    with _file_lock(now):
        payload = _read(path)
        if not _payload_valid(payload, now):
            return {
                "status": "NEW_DAY_OR_EMPTY",
                "restored_keys": 0,
                "updated_at": "",
                "source": str(path),
            }
        stored = payload.get("keys", {})
        for key in PERSIST_KEYS:
            if key not in stored:
                continue
            current = state.get(key)
            merged = _merge_value(key, stored.get(key), current)
            state[key] = merged
            restored.append(key)

    report = {
        "status": "SHARED_STATE_RESTORED",
        "restored_keys": len(restored),
        "keys": restored,
        "updated_at": str(payload.get("updated_at", "")),
        "updated_epoch": _number(payload.get("updated_epoch"), 0.0),
        "snapshot_id": str(payload.get("snapshot_id", "")),
        "source": str(path),
    }
    state["_v5083_state_sync_boot"] = report
    return report


def persist_authoritative_state(
    state: MutableMapping[str, Any],
    *,
    snapshot_id: str = "",
    observed_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Merge current evidence into shared state without allowing count rollback."""
    now = _now(observed_at)
    path = _state_path(now)
    saved_keys: list[str] = []
    with _file_lock(now):
        existing = _read(path)
        existing_keys = existing.get("keys", {}) if _payload_valid(existing, now) else {}
        existing_keys = existing_keys if isinstance(existing_keys, Mapping) else {}
        merged_keys: Dict[str, Any] = {}
        for key in PERSIST_KEYS:
            old = existing_keys.get(key)
            current = state.get(key)
            if old is None and current is None:
                continue
            merged = _merge_value(key, old, current)
            merged_keys[key] = merged
            state[key] = deepcopy(merged)
            saved_keys.append(key)

        payload = {
            "schema": _SCHEMA_VERSION,
            "date": now.strftime("%Y-%m-%d"),
            "updated_at": now.isoformat(timespec="seconds"),
            "updated_epoch": round(now.timestamp(), 3),
            "snapshot_id": str(snapshot_id or ""),
            "keys": merged_keys,
        }
        ok = _write(path, payload)

    report = {
        "status": "SHARED_STATE_OK" if ok else "SHARED_STATE_WRITE_FAILED",
        "saved_keys": len(saved_keys),
        "updated_at": payload["updated_at"],
        "updated_epoch": payload["updated_epoch"],
        "snapshot_id": payload["snapshot_id"],
        "source": str(path),
    }
    state["_v5083_state_sync_last"] = report
    return report


def state_sync_summary(state: Mapping[str, Any]) -> Dict[str, Any]:
    value = state.get("_v5083_state_sync_last") or state.get("_v5083_state_sync_boot") or {}
    return dict(value) if isinstance(value, Mapping) else {}
