"""
core/data_intelligence.py
Version: V35.1 Foundation Repair
Department: Data Intelligence (Department 0)

Purpose:
- Create one compact, content-addressed market snapshot per refresh.
- Give every department the same snapshot identity.
- Never issue BUY/SELL/WAIT advice.
- Never call an API, start a loop, or create a second decision authority.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence


def _clip_score(value: Any) -> float:
    try:
        return round(max(0.0, min(100.0, float(value))), 1)
    except (TypeError, ValueError):
        return 0.0


def _json_safe(value: Any, *, depth: int = 0) -> Any:
    """Convert bounded snapshot data into deterministic JSON-safe values."""
    if depth > 8:
        return str(value)[:240]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if value != value:  # NaN
            return None
        if value in (float("inf"), float("-inf")):
            return str(value)
        return round(value, 8)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        output: Dict[str, Any] = {}
        for index, key in enumerate(sorted(value, key=lambda item: str(item))):
            if index >= 200:
                break
            output[str(key)] = _json_safe(value[key], depth=depth + 1)
        return output
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item, depth=depth + 1) for item in list(value)[:500]]

    # Handles numpy scalar-like values without importing heavy dependencies.
    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            return _json_safe(item_method(), depth=depth + 1)
        except Exception:
            pass
    return str(value)[:500]


@dataclass(frozen=True)
class MarketDataSnapshot:
    """Immutable snapshot envelope shared across the department hierarchy."""

    snapshot_id: str
    created_at: str
    quality_score: float
    raw_signature: str
    payload: Dict[str, Any]
    validation_errors: tuple[str, ...]

    @property
    def is_usable(self) -> bool:
        return self.quality_score >= 60.0 and not self.validation_errors

    def section(self, name: str, default: Optional[Any] = None) -> Any:
        """Return a defensive copy so departments cannot mutate the source snapshot."""
        return deepcopy(self.payload.get(name, default))

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "quality_score": self.quality_score,
            "raw_signature": self.raw_signature,
            "validation_errors": list(self.validation_errors),
            "sections": list(self.payload.keys()),
        }


class SnapshotManager:
    """Creates the single verified snapshot used by all AI departments."""

    VERSION = "V35.1_DATA_INTELLIGENCE_RESTORED"

    def create_snapshot(
        self,
        raw_payload: Mapping[str, Any],
        validation_errors: Optional[Iterable[Any]] = None,
        quality_score: Any = 0.0,
    ) -> MarketDataSnapshot:
        if not isinstance(raw_payload, Mapping):
            raise TypeError("raw_payload must be a mapping")

        safe_payload = _json_safe(raw_payload)
        if not isinstance(safe_payload, dict):
            raise TypeError("snapshot payload normalization failed")

        errors = tuple(
            str(item)[:240]
            for item in (validation_errors or [])
            if item not in (None, "")
        )[:50]
        quality = _clip_score(quality_score)

        signature_source = {
            "payload": safe_payload,
            "validation_errors": errors,
            "quality_score": quality,
        }
        canonical = json.dumps(
            signature_source,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        signature = sha256(canonical).hexdigest()

        return MarketDataSnapshot(
            snapshot_id=f"SNAP-{signature[:16].upper()}",
            created_at=datetime.now(timezone.utc).isoformat(),
            quality_score=quality,
            raw_signature=signature,
            payload=deepcopy(safe_payload),
            validation_errors=errors,
        )


class DataDistributor:
    """Read-only distributor for one snapshot; it performs no analysis."""

    def __init__(self, snapshot: MarketDataSnapshot):
        if not isinstance(snapshot, MarketDataSnapshot):
            raise TypeError("snapshot must be a MarketDataSnapshot")
        self._snapshot = snapshot

    @property
    def snapshot_id(self) -> str:
        return self._snapshot.snapshot_id

    @property
    def quality_score(self) -> float:
        return self._snapshot.quality_score

    def get_section(self, name: str, default: Optional[Any] = None) -> Any:
        return self._snapshot.section(name, default)

    def distribute(self, section_names: Sequence[str]) -> Dict[str, Any]:
        return {
            str(name): self._snapshot.section(str(name))
            for name in section_names
        }

    def audit_receipt(self) -> Dict[str, Any]:
        return self._snapshot.to_compact_dict()
