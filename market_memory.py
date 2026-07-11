"""
market_memory.py
Version : V24.0
Department : Market Memory
Status  : Bounded Memory Guard

Purpose:
- Store a small, bounded history of snapshots and AI decisions.
- Never create decisions.
- Never run in the background.
- Prevent mobile RAM growth by enforcing strict limits.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Iterable, List, Optional


class MarketMemory:
    def __init__(
        self,
        *,
        max_snapshots: int = 5,
        max_decisions: int = 20,
        max_events: int = 50,
    ) -> None:
        self.snapshots: Deque[Dict[str, Any]] = deque(maxlen=max(1, max_snapshots))
        self.decisions: Deque[Dict[str, Any]] = deque(maxlen=max(1, max_decisions))
        self.events: Deque[Dict[str, Any]] = deque(maxlen=max(1, max_events))

    def remember_snapshot(
        self,
        snapshot_id: str,
        compact_snapshot: Dict[str, Any],
    ) -> None:
        self.snapshots.append(
            {
                "snapshot_id": snapshot_id,
                "time": datetime.now(timezone.utc).isoformat(),
                "data": self._compact(compact_snapshot),
            }
        )

    def remember_decision(self, decision: Any) -> None:
        payload = self._to_dict(decision)
        self.decisions.append(self._compact(payload))

    def remember_event(
        self,
        *,
        event_type: str,
        snapshot_id: str,
        facts: Dict[str, Any],
    ) -> None:
        self.events.append(
            {
                "event_type": event_type,
                "snapshot_id": snapshot_id,
                "time": datetime.now(timezone.utc).isoformat(),
                "facts": self._compact(facts),
            }
        )

    def latest_snapshot(self) -> Optional[Dict[str, Any]]:
        return deepcopy(self.snapshots[-1]) if self.snapshots else None

    def latest_decision(self) -> Optional[Dict[str, Any]]:
        return deepcopy(self.decisions[-1]) if self.decisions else None

    def recent_decisions(self, limit: int = 5) -> List[Dict[str, Any]]:
        limit = max(0, min(limit, len(self.decisions)))
        return deepcopy(list(self.decisions)[-limit:])

    def decision_flip_count(self, lookback: int = 8) -> int:
        recent = self.recent_decisions(lookback)
        actions = [str(item.get("action", "")) for item in recent]
        return sum(1 for a, b in zip(actions, actions[1:]) if a and b and a != b)

    def clear_transient(self) -> None:
        """
        Clears only temporary events. Keeps bounded snapshots/decisions.
        Call after UI render if event detail is no longer needed.
        """
        self.events.clear()

    def clear_all(self) -> None:
        self.snapshots.clear()
        self.decisions.clear()
        self.events.clear()

    def stats(self) -> Dict[str, int]:
        return {
            "snapshots": len(self.snapshots),
            "decisions": len(self.decisions),
            "events": len(self.events),
        }

    def _to_dict(self, value: Any) -> Dict[str, Any]:
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return dict(value)
        return {
            key: getattr(value, key)
            for key in dir(value)
            if not key.startswith("_")
            and not callable(getattr(value, key, None))
        }

    def _compact(self, value: Any, depth: int = 0) -> Any:
        """
        Keeps only compact JSON-like values.
        Large tables/dataframes must not be stored in memory.
        """
        if depth > 4:
            return str(value)[:200]

        if value is None or isinstance(value, (bool, int, float)):
            return value

        if isinstance(value, str):
            return value[:500]

        if isinstance(value, dict):
            result: Dict[str, Any] = {}
            for index, (key, item) in enumerate(value.items()):
                if index >= 50:
                    break
                result[str(key)] = self._compact(item, depth + 1)
            return result

        if isinstance(value, (list, tuple, deque)):
            return [self._compact(item, depth + 1) for item in list(value)[:30]]

        # Do not retain DataFrame/Series/large custom object references.
        shape = getattr(value, "shape", None)
        if shape is not None:
            return {"type": type(value).__name__, "shape": str(shape)}

        return str(value)[:300]
