"""
learning_department.py
Version : V24.0
Department : Learning & Validation
Status  : Controlled Learning

Purpose:
- Compare AI decisions with actual outcomes.
- Produce validation statistics and suggestions.
- Never modify live AI weights automatically.
- Never issue BUY/SELL/WAIT.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
from typing import Any, Deque, Dict, List, Optional


@dataclass(frozen=True)
class LearningRecord:
    snapshot_id: str
    action: str
    confidence: float
    entry_price: float
    evaluation_price: float
    points_change: float
    expected_direction_correct: Optional[bool]
    outcome: str


class LearningDepartment:
    """
    Safe learning:
    - records observations
    - calculates calibration
    - suggests review points
    - does NOT self-edit production logic
    """

    def __init__(self, max_records: int = 200) -> None:
        self.records: Deque[LearningRecord] = deque(maxlen=max(10, max_records))

    def evaluate(
        self,
        *,
        snapshot_id: str,
        action: str,
        confidence: float,
        entry_price: float,
        evaluation_price: float,
        neutral_band_points: float = 10.0,
    ) -> LearningRecord:
        action = str(action).upper()
        change = float(evaluation_price) - float(entry_price)

        correct: Optional[bool]
        if action == "SELL PE":
            correct = change > neutral_band_points
        elif action == "SELL CE":
            correct = change < -neutral_band_points
        elif action == "IRON CONDOR":
            correct = abs(change) <= neutral_band_points
        elif action == "WAIT":
            correct = None
        else:
            correct = None

        if correct is True:
            outcome = "CORRECT"
        elif correct is False:
            outcome = "WRONG"
        else:
            outcome = "OBSERVATION"

        record = LearningRecord(
            snapshot_id=snapshot_id,
            action=action,
            confidence=round(float(confidence), 1),
            entry_price=round(float(entry_price), 2),
            evaluation_price=round(float(evaluation_price), 2),
            points_change=round(change, 2),
            expected_direction_correct=correct,
            outcome=outcome,
        )
        self.records.append(record)
        return record

    def calibration_report(self) -> Dict[str, Any]:
        completed = [
            record for record in self.records
            if record.expected_direction_correct is not None
        ]

        if not completed:
            return {
                "sample_size": 0,
                "accuracy": None,
                "message": "Not enough completed samples.",
            }

        correct = sum(
            1 for record in completed
            if record.expected_direction_correct is True
        )
        accuracy = correct / len(completed) * 100.0

        buckets: Dict[str, Dict[str, int]] = {
            "50-59": {"total": 0, "correct": 0},
            "60-69": {"total": 0, "correct": 0},
            "70-79": {"total": 0, "correct": 0},
            "80-89": {"total": 0, "correct": 0},
            "90-100": {"total": 0, "correct": 0},
        }

        for record in completed:
            confidence = record.confidence
            if confidence < 60:
                bucket = "50-59"
            elif confidence < 70:
                bucket = "60-69"
            elif confidence < 80:
                bucket = "70-79"
            elif confidence < 90:
                bucket = "80-89"
            else:
                bucket = "90-100"

            buckets[bucket]["total"] += 1
            if record.expected_direction_correct:
                buckets[bucket]["correct"] += 1

        calibration = {}
        for name, values in buckets.items():
            total = values["total"]
            calibration[name] = {
                **values,
                "accuracy": round(values["correct"] / total * 100.0, 1)
                if total
                else None,
            }

        return {
            "sample_size": len(completed),
            "accuracy": round(accuracy, 1),
            "confidence_calibration": calibration,
            "review_suggestions": self.review_suggestions(),
        }

    def review_suggestions(self) -> List[str]:
        suggestions: List[str] = []
        completed = [
            record for record in self.records
            if record.expected_direction_correct is not None
        ]

        if len(completed) < 20:
            return ["Collect at least 20 validated samples before changing rules."]

        high_confidence_wrong = [
            record for record in completed
            if record.confidence >= 80
            and record.expected_direction_correct is False
        ]
        if len(high_confidence_wrong) / len(completed) >= 0.15:
            suggestions.append(
                "Review overconfidence: too many 80%+ decisions were wrong."
            )

        sell_pe = [r for r in completed if r.action == "SELL PE"]
        sell_ce = [r for r in completed if r.action == "SELL CE"]

        if len(sell_pe) >= 10:
            pe_accuracy = sum(bool(r.expected_direction_correct) for r in sell_pe) / len(sell_pe)
            if pe_accuracy < 0.55:
                suggestions.append("Review SELL PE permission and late-entry rules.")

        if len(sell_ce) >= 10:
            ce_accuracy = sum(bool(r.expected_direction_correct) for r in sell_ce) / len(sell_ce)
            if ce_accuracy < 0.55:
                suggestions.append("Review SELL CE permission and late-entry rules.")

        if not suggestions:
            suggestions.append("No automatic rule change recommended.")

        return suggestions

    def export_records(self) -> List[Dict[str, Any]]:
        return [asdict(record) for record in self.records]

    def clear(self) -> None:
        self.records.clear()
