"""
pattern_probability.py
Version: V34.0
Role: Historical pattern probability and confidence calibration.

Safety:
- Reads bounded compact V33 case history only.
- Does not call APIs, run threads, or change live AI weights.
- Returns probabilities only when enough completed cases exist.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Mapping, MutableMapping, Optional


@dataclass(frozen=True)
class ProbabilityReport:
    status: str
    sample_size: int
    matched_sample_size: int
    action: str
    market_bias: str
    historical_accuracy: Optional[float]
    matched_accuracy: Optional[float]
    confidence_gap: Optional[float]
    probability_label: str
    warnings: List[str]
    calibration: Dict[str, Any]

    def to_compact_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PatternProbabilityEngine:
    HISTORY_KEY = "v33_case_history_records"

    def __init__(self, minimum_samples: int = 8, strong_samples: int = 20) -> None:
        self.minimum_samples = max(5, int(minimum_samples))
        self.strong_samples = max(self.minimum_samples, int(strong_samples))

    def evaluate(
        self,
        *,
        state: MutableMapping[str, Any],
        action: str,
        market_bias: str,
        current_confidence: float,
        similar_cases: List[Mapping[str, Any]] | None = None,
    ) -> ProbabilityReport:
        history = state.get(self.HISTORY_KEY, [])
        if not isinstance(history, list):
            history = []

        action = str(action or "WAIT").upper()
        market_bias = str(market_bias or "NEUTRAL").upper()
        completed = [
            row for row in history
            if isinstance(row, dict) and str(row.get("outcome", "")).upper() in {"CORRECT", "WRONG"}
        ]

        same_context = [
            row for row in completed
            if str(row.get("action", "")).upper() == action
            and str(row.get("market_bias", "")).upper() == market_bias
        ]

        matched_ids = {
            str(item.get("case_id"))
            for item in (similar_cases or [])
            if isinstance(item, Mapping)
        }
        matched = [row for row in completed if str(row.get("case_id")) in matched_ids]

        overall_accuracy = self._accuracy(same_context)
        matched_accuracy = self._accuracy(matched)
        effective_accuracy = matched_accuracy if matched_accuracy is not None else overall_accuracy

        warnings: List[str] = []
        if len(completed) < self.minimum_samples:
            status = "COLLECTING_OUTCOMES"
            label = "Not enough validated cases"
            warnings.append(f"Need at least {self.minimum_samples} completed cases.")
        elif len(same_context) < self.minimum_samples:
            status = "LOW_CONTEXT_SAMPLE"
            label = "Context sample too small"
            warnings.append("Same action+bias history is still limited.")
        elif len(same_context) < self.strong_samples:
            status = "EARLY_PROBABILITY"
            label = self._label(effective_accuracy)
            warnings.append("Probability is early-stage; do not treat it as a guarantee.")
        else:
            status = "CALIBRATED_PROBABILITY"
            label = self._label(effective_accuracy)

        confidence_gap = None
        if effective_accuracy is not None:
            confidence_gap = round(float(current_confidence or 0.0) - effective_accuracy, 1)
            if confidence_gap >= 15:
                warnings.append("Current AI confidence may be over-calibrated versus history.")
            elif confidence_gap <= -15:
                warnings.append("Current AI confidence may be under-calibrated versus history.")

        calibration = self._calibration(completed)
        return ProbabilityReport(
            status=status,
            sample_size=len(same_context),
            matched_sample_size=len(matched),
            action=action,
            market_bias=market_bias,
            historical_accuracy=overall_accuracy,
            matched_accuracy=matched_accuracy,
            confidence_gap=confidence_gap,
            probability_label=label,
            warnings=warnings[:6],
            calibration=calibration,
        )

    def _accuracy(self, rows: List[Mapping[str, Any]]) -> Optional[float]:
        if not rows:
            return None
        correct = sum(1 for row in rows if str(row.get("outcome", "")).upper() == "CORRECT")
        return round(correct / len(rows) * 100.0, 1)

    def _label(self, accuracy: Optional[float]) -> str:
        if accuracy is None:
            return "Insufficient evidence"
        if accuracy >= 75:
            return "Strong historical support"
        if accuracy >= 60:
            return "Moderate historical support"
        if accuracy >= 50:
            return "Mixed historical support"
        return "Weak historical support"

    def _calibration(self, rows: List[Mapping[str, Any]]) -> Dict[str, Any]:
        buckets = {
            "50-59": {"total": 0, "correct": 0},
            "60-69": {"total": 0, "correct": 0},
            "70-79": {"total": 0, "correct": 0},
            "80-89": {"total": 0, "correct": 0},
            "90-100": {"total": 0, "correct": 0},
        }
        for row in rows:
            try:
                confidence = float(row.get("confidence", 0) or 0)
            except (TypeError, ValueError):
                confidence = 0.0
            if confidence < 60:
                key = "50-59"
            elif confidence < 70:
                key = "60-69"
            elif confidence < 80:
                key = "70-79"
            elif confidence < 90:
                key = "80-89"
            else:
                key = "90-100"
            buckets[key]["total"] += 1
            if str(row.get("outcome", "")).upper() == "CORRECT":
                buckets[key]["correct"] += 1

        result: Dict[str, Any] = {}
        for key, value in buckets.items():
            total = value["total"]
            result[key] = {
                **value,
                "accuracy": round(value["correct"] / total * 100.0, 1) if total else None,
            }
        return result
