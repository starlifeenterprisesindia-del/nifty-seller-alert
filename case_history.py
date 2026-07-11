"""
case_history.py
Version: V33.0
Role: Bounded case history and pattern matching for AI investigation cases.

Safety:
- No API calls, threads, timers, polling, or trade decisions.
- Stores compact plain dictionaries only.
- Never changes live AI weights automatically.
- Similarity is descriptive evidence, not a prediction guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Set


@dataclass(frozen=True)
class SimilarCase:
    case_id: str
    snapshot_id: str
    similarity: float
    action: str
    market_bias: str
    case_strength: float
    outcome: str
    shared_features: List[str]


@dataclass(frozen=True)
class CaseHistoryReport:
    current_case_id: str
    fingerprint: str
    stored_cases: int
    similar_cases: List[SimilarCase]
    best_similarity: float
    historical_accuracy: Optional[float]
    matched_completed_cases: int
    status: str

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "current_case_id": self.current_case_id,
            "fingerprint": self.fingerprint,
            "stored_cases": self.stored_cases,
            "similar_cases": [asdict(item) for item in self.similar_cases],
            "best_similarity": self.best_similarity,
            "historical_accuracy": self.historical_accuracy,
            "matched_completed_cases": self.matched_completed_cases,
            "status": self.status,
        }


class CaseHistoryEngine:
    SESSION_KEY = "v33_case_history_records"

    def __init__(self, max_cases: int = 80, max_matches: int = 5) -> None:
        self.max_cases = max(10, min(int(max_cases), 200))
        self.max_matches = max(1, min(int(max_matches), 10))

    def process_case(
        self,
        *,
        state: MutableMapping[str, Any],
        snapshot_id: str,
        case_id: str,
        action: str,
        confidence: float,
        market_bias: str,
        case_strength: float,
        consensus_direction: str,
        branch_votes: Mapping[str, Any],
        accepted_evidence: Sequence[Any],
        warnings: Sequence[Any],
        outcome: str = "PENDING",
    ) -> CaseHistoryReport:
        history = state.get(self.SESSION_KEY, [])
        if not isinstance(history, list):
            history = []

        current = self._make_record(
            snapshot_id=snapshot_id,
            case_id=case_id,
            action=action,
            confidence=confidence,
            market_bias=market_bias,
            case_strength=case_strength,
            consensus_direction=consensus_direction,
            branch_votes=branch_votes,
            accepted_evidence=accepted_evidence,
            warnings=warnings,
            outcome=outcome,
        )

        previous = [item for item in history if isinstance(item, dict) and item.get("snapshot_id") != snapshot_id]
        matches = self._find_matches(current, previous)

        # Store each snapshot once. Keep compact bounded history only.
        if not any(item.get("snapshot_id") == snapshot_id for item in history if isinstance(item, dict)):
            history.append(current)
        history = history[-self.max_cases:]
        state[self.SESSION_KEY] = history

        completed = [m for m in matches if m.outcome in {"CORRECT", "WRONG"}]
        accuracy = None
        if completed:
            accuracy = round(sum(1 for m in completed if m.outcome == "CORRECT") / len(completed) * 100.0, 1)

        best = matches[0].similarity if matches else 0.0
        if len(history) < 5:
            status = "COLLECTING_CASES"
        elif best >= 75:
            status = "STRONG_PATTERN_MATCH"
        elif best >= 55:
            status = "MODERATE_PATTERN_MATCH"
        else:
            status = "NO_STRONG_MATCH"

        return CaseHistoryReport(
            current_case_id=case_id,
            fingerprint=current["fingerprint"],
            stored_cases=len(history),
            similar_cases=matches,
            best_similarity=round(best, 1),
            historical_accuracy=accuracy,
            matched_completed_cases=len(completed),
            status=status,
        )

    def update_outcome(
        self,
        *,
        state: MutableMapping[str, Any],
        case_id: str,
        outcome: str,
    ) -> bool:
        outcome = str(outcome).upper()
        if outcome not in {"CORRECT", "WRONG", "NEUTRAL", "PENDING"}:
            return False
        history = state.get(self.SESSION_KEY, [])
        if not isinstance(history, list):
            return False
        updated = False
        for item in history:
            if isinstance(item, dict) and item.get("case_id") == case_id:
                item["outcome"] = outcome
                updated = True
                break
        state[self.SESSION_KEY] = history[-self.max_cases:]
        return updated

    def _make_record(self, **k: Any) -> Dict[str, Any]:
        features: Set[str] = set()
        bias = str(k.get("market_bias", "NEUTRAL")).upper()
        consensus = str(k.get("consensus_direction", "NEUTRAL")).upper()
        action = str(k.get("action", "WAIT")).upper()
        features.update({f"BIAS:{bias}", f"CONSENSUS:{consensus}", f"ACTION:{action}"})

        votes = k.get("branch_votes", {})
        if isinstance(votes, Mapping):
            for branch, vote in sorted(votes.items()):
                features.add(f"VOTE:{str(branch).upper()}:{str(vote).upper()}")

        for item in list(k.get("accepted_evidence", []) or [])[:10]:
            token = self._token(item)
            if token:
                features.add("EVIDENCE:" + token)

        for item in list(k.get("warnings", []) or [])[:8]:
            token = self._token(item)
            if token:
                features.add("WARNING:" + token)

        confidence = self._number(k.get("confidence", 0.0))
        strength = self._number(k.get("case_strength", 0.0))
        features.add(f"CONF_BUCKET:{int(confidence // 10) * 10}")
        features.add(f"STRENGTH_BUCKET:{int(strength // 10) * 10}")

        fingerprint = " | ".join(sorted(features))[:1200]
        return {
            "case_id": str(k.get("case_id", "UNKNOWN")),
            "snapshot_id": str(k.get("snapshot_id", "UNKNOWN")),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "confidence": round(confidence, 1),
            "market_bias": bias,
            "case_strength": round(strength, 1),
            "consensus_direction": consensus,
            "features": sorted(features)[:40],
            "fingerprint": fingerprint,
            "outcome": str(k.get("outcome", "PENDING")).upper(),
        }

    def _find_matches(self, current: Dict[str, Any], previous: List[Dict[str, Any]]) -> List[SimilarCase]:
        current_features = set(current.get("features", []))
        rows: List[SimilarCase] = []
        for old in previous[-self.max_cases:]:
            old_features = set(old.get("features", []))
            if not old_features:
                continue
            union = current_features | old_features
            shared = sorted(current_features & old_features)
            jaccard = len(shared) / max(1, len(union)) * 100.0
            strength_gap = abs(self._number(current.get("case_strength")) - self._number(old.get("case_strength")))
            confidence_gap = abs(self._number(current.get("confidence")) - self._number(old.get("confidence")))
            numeric_bonus = max(0.0, 20.0 - strength_gap * 0.25 - confidence_gap * 0.15)
            similarity = min(100.0, jaccard * 0.82 + numeric_bonus)
            if similarity < 35.0:
                continue
            rows.append(SimilarCase(
                case_id=str(old.get("case_id", "UNKNOWN")),
                snapshot_id=str(old.get("snapshot_id", "UNKNOWN")),
                similarity=round(similarity, 1),
                action=str(old.get("action", "WAIT")),
                market_bias=str(old.get("market_bias", "NEUTRAL")),
                case_strength=round(self._number(old.get("case_strength")), 1),
                outcome=str(old.get("outcome", "PENDING")),
                shared_features=shared[:8],
            ))
        return sorted(rows, key=lambda item: item.similarity, reverse=True)[:self.max_matches]

    def _token(self, value: Any) -> str:
        text = " ".join(str(value).upper().replace("_", " ").split())
        return text[:90]

    def _number(self, value: Any) -> float:
        try:
            return max(0.0, min(100.0, float(value or 0.0)))
        except (TypeError, ValueError):
            return 0.0
