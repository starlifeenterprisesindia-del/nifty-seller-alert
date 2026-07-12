"""
market_replay.py
Version: V48.3
Role: Compact historical market replay inside the existing Experience Department.

Architecture and safety:
- Reads only bounded completed cases already stored by ExperienceEngine.
- Reconstructs a compact path from verified case observations; it is not tick replay.
- Compares current regime/department evidence with historical completed cases.
- Produces historical support, warning, conflict, and lessons for CO information only.
- Never changes AI_MASTER action, confidence, candidate, weights, thresholds, or rules.
- Never issues a live BUY/SELL instruction and never calls an API or background loop.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class ReplayPoint:
    step: str
    move_points: float
    note: str


@dataclass(frozen=True)
class ReplayedCase:
    case_id: str
    similarity: float
    regime_similarity: float
    department_alignment: float
    action_alignment: float
    historical_action: str
    prediction: str
    reality: str
    outcome: str
    confidence: float
    actual_move_points: float
    max_favourable_points: float
    max_adverse_points: float
    replay_quality: str
    replay_path: List[ReplayPoint] = field(default_factory=list)
    shared_evidence: List[str] = field(default_factory=list)
    conflicting_departments: List[str] = field(default_factory=list)
    historical_compatible_action: str = "OBSERVATION_ONLY"
    mistake: str = "NONE_IDENTIFIED"
    lesson: str = "Observation stored."


@dataclass(frozen=True)
class MarketReplayReport:
    snapshot_id: str
    replay_state: str
    statement: str
    preliminary_action: str
    stored_completed_cases: int
    eligible_cases: int
    replayed_cases: int
    best_similarity: float
    historical_alignment: str
    matched_accuracy: Optional[float]
    same_action_cases: int
    same_action_accuracy: Optional[float]
    historical_outcomes: Dict[str, int] = field(default_factory=dict)
    replay_cases: List[ReplayedCase] = field(default_factory=list)
    dominant_historical_mistakes: List[str] = field(default_factory=list)
    counterfactual_lessons: List[str] = field(default_factory=list)
    next_confirmation: List[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "replay_state": self.replay_state,
            "statement": self.statement,
            "preliminary_action": self.preliminary_action,
            "stored_completed_cases": self.stored_completed_cases,
            "eligible_cases": self.eligible_cases,
            "replayed_cases": self.replayed_cases,
            "best_similarity": self.best_similarity,
            "historical_alignment": self.historical_alignment,
            "matched_accuracy": self.matched_accuracy,
            "same_action_cases": self.same_action_cases,
            "same_action_accuracy": self.same_action_accuracy,
            "historical_outcomes": dict(self.historical_outcomes),
            "replay_cases": [
                {
                    **asdict(item),
                    "replay_path": [asdict(point) for point in item.replay_path],
                }
                for item in self.replay_cases
            ],
            "dominant_historical_mistakes": list(self.dominant_historical_mistakes),
            "counterfactual_lessons": list(self.counterfactual_lessons),
            "next_confirmation": list(self.next_confirmation),
            "confidence": self.confidence,
            "warnings": list(self.warnings),
            "authority": "DSP_EXPERIENCE_MARKET_REPLAY_TO_CO_INFORMATION_ONLY",
            "execution_instruction": "NONE",
            "automatic_decision_override": False,
            "automatic_rule_change": False,
            "replay_scope": "COMPACT_VERIFIED_SNAPSHOT_RECONSTRUCTION",
        }


class MarketReplayEngine:
    """One-shot replay comparison using the bounded V43 experience archive."""

    EXPERIENCE_SESSION_KEY = "v43_experience_records"

    def __init__(self, *, max_replays: int = 6, minimum_similarity: float = 38.0) -> None:
        self.max_replays = max(3, min(int(max_replays), 10))
        self.minimum_similarity = max(25.0, min(float(minimum_similarity), 70.0))

    def replay(
        self,
        *,
        state: MutableMapping[str, Any],
        snapshot_id: str,
        context: Mapping[str, Any],
        preliminary_action: str,
        current_department_reports: Optional[Mapping[str, Any]] = None,
    ) -> MarketReplayReport:
        completed = self._completed_records(state)
        current_features = self._features(context)
        current_departments = self._department_directions(current_department_reports or {})
        action = self._normal_action(preliminary_action)

        candidates: List[ReplayedCase] = []
        for record in completed:
            old_features = set(str(item) for item in list(record.get("features", []) or []))
            if not old_features:
                continue
            regime_similarity, shared = self._jaccard(current_features, old_features)
            department_alignment, conflicts = self._department_alignment(
                current_departments,
                record.get("department_snapshot", {}),
            )
            old_action = self._normal_action(record.get("action", "WAIT"))
            action_alignment = self._action_alignment(action, old_action)
            overall = regime_similarity * 0.65 + department_alignment * 0.25 + action_alignment * 0.10
            if overall < self.minimum_similarity:
                continue
            candidates.append(
                self._replayed_case(
                    record=record,
                    overall=overall,
                    regime_similarity=regime_similarity,
                    department_alignment=department_alignment,
                    action_alignment=action_alignment,
                    shared=shared,
                    conflicts=conflicts,
                )
            )

        candidates.sort(key=lambda item: (item.similarity, item.replay_quality == "VERIFIED_PATH"), reverse=True)
        selected = candidates[: self.max_replays]
        validated = [item for item in selected if item.outcome in {"CORRECT", "WRONG"}]
        correct = sum(item.outcome == "CORRECT" for item in validated)
        matched_accuracy = round(correct / len(validated) * 100.0, 1) if validated else None

        same_action = [item for item in selected if item.historical_action == action and item.outcome in {"CORRECT", "WRONG"}]
        same_action_correct = sum(item.outcome == "CORRECT" for item in same_action)
        same_action_accuracy = round(same_action_correct / len(same_action) * 100.0, 1) if same_action else None
        best_similarity = round(selected[0].similarity, 1) if selected else 0.0
        outcomes = {
            "CORRECT": sum(item.outcome == "CORRECT" for item in selected),
            "WRONG": sum(item.outcome == "WRONG" for item in selected),
            "OBSERVATION": sum(item.outcome not in {"CORRECT", "WRONG"} for item in selected),
        }
        alignment = self._historical_alignment(
            replayed=len(selected),
            matched_accuracy=matched_accuracy,
            same_action_cases=len(same_action),
            same_action_accuracy=same_action_accuracy,
            selected=selected,
        )
        replay_state = self._replay_state(len(completed), len(selected), best_similarity, alignment)
        mistakes = self._dominant_mistakes(selected)
        lessons = self._counterfactual_lessons(selected, action, alignment)
        confirmations = self._next_confirmation(selected, action, alignment)
        warnings: List[str] = []
        if len(completed) < 8:
            warnings.append("Fewer than eight completed cases; replay evidence is immature.")
        if len(selected) < 3:
            warnings.append("Fewer than three comparable replays; do not infer a stable pattern.")
        warnings.append("Replay is compact snapshot reconstruction, not tick-by-tick market playback.")
        warnings.append("Historical alignment cannot override the current CO/AI_MASTER judgement.")

        confidence = min(
            92.0,
            18.0
            + min(len(completed), 40) * 0.9
            + min(len(selected), 6) * 5.0
            + best_similarity * 0.22,
        )
        statement = (
            f"Replayed {len(selected)} comparable completed case"
            f"{'s' if len(selected) != 1 else ''}; historical alignment {alignment}."
        )
        return MarketReplayReport(
            snapshot_id=str(snapshot_id or "UNKNOWN"),
            replay_state=replay_state,
            statement=statement,
            preliminary_action=action,
            stored_completed_cases=len(completed),
            eligible_cases=len(candidates),
            replayed_cases=len(selected),
            best_similarity=best_similarity,
            historical_alignment=alignment,
            matched_accuracy=matched_accuracy,
            same_action_cases=len(same_action),
            same_action_accuracy=same_action_accuracy,
            historical_outcomes=outcomes,
            replay_cases=selected,
            dominant_historical_mistakes=mistakes,
            counterfactual_lessons=lessons,
            next_confirmation=confirmations,
            confidence=round(confidence, 1),
            warnings=warnings[:4],
        )

    def _completed_records(self, state: Mapping[str, Any]) -> List[Dict[str, Any]]:
        records = state.get(self.EXPERIENCE_SESSION_KEY, [])
        if not isinstance(records, list):
            return []
        return [
            dict(item)
            for item in records
            if isinstance(item, Mapping) and str(item.get("status", "")) == "COMPLETED"
        ][-400:]

    def _replayed_case(
        self,
        *,
        record: Mapping[str, Any],
        overall: float,
        regime_similarity: float,
        department_alignment: float,
        action_alignment: float,
        shared: Sequence[str],
        conflicts: Sequence[str],
    ) -> ReplayedCase:
        action = self._normal_action(record.get("action", "WAIT"))
        max_up = float(record.get("max_up_points", 0.0) or 0.0)
        max_down = float(record.get("max_down_points", 0.0) or 0.0)
        favourable, adverse = self._excursions(action, max_up, max_down)
        path, quality = self._replay_path(record, action)
        return ReplayedCase(
            case_id=str(record.get("case_id", "UNKNOWN")),
            similarity=round(overall, 1),
            regime_similarity=round(regime_similarity, 1),
            department_alignment=round(department_alignment, 1),
            action_alignment=round(action_alignment, 1),
            historical_action=action,
            prediction=str(record.get("prediction", "UNKNOWN")),
            reality=str(record.get("reality", "UNKNOWN")),
            outcome=str(record.get("outcome", "OBSERVATION")),
            confidence=round(self._number(record.get("confidence", 0)), 1),
            actual_move_points=round(float(record.get("actual_move_points", 0.0) or 0.0), 1),
            max_favourable_points=round(favourable, 1),
            max_adverse_points=round(adverse, 1),
            replay_quality=quality,
            replay_path=path,
            shared_evidence=[str(item)[:110] for item in list(shared)[:8]],
            conflicting_departments=[str(item)[:100] for item in list(conflicts)[:6]],
            historical_compatible_action=self._compatible_action(str(record.get("reality", "UNKNOWN"))),
            mistake=str(record.get("mistake", "NONE_IDENTIFIED")),
            lesson=str(record.get("lesson", "Observation stored."))[:240],
        )

    def _replay_path(self, record: Mapping[str, Any], action: str) -> Tuple[List[ReplayPoint], str]:
        observations = record.get("observations", [])
        points: List[ReplayPoint] = []
        if isinstance(observations, list) and len(observations) >= 2:
            for index, item in enumerate(observations[:10]):
                if not isinstance(item, Mapping):
                    continue
                move = round(float(item.get("move_points", 0.0) or 0.0), 1)
                step = str(item.get("phase", f"STEP_{index}"))
                points.append(ReplayPoint(step=step, move_points=move, note=self._path_note(action, move)))
            if points:
                return points, "VERIFIED_PATH"

        max_up = round(float(record.get("max_up_points", 0.0) or 0.0), 1)
        max_down = round(float(record.get("max_down_points", 0.0) or 0.0), 1)
        final = round(float(record.get("actual_move_points", 0.0) or 0.0), 1)
        reconstructed = [
            ReplayPoint("ENTRY", 0.0, "Historical case entry snapshot"),
            ReplayPoint("MAX_UP", max_up, self._path_note(action, max_up)),
            ReplayPoint("MAX_DOWN", max_down, self._path_note(action, max_down)),
            ReplayPoint("FINAL", final, self._path_note(action, final)),
        ]
        return reconstructed, "SUMMARY_RECONSTRUCTION"

    @staticmethod
    def _path_note(action: str, move: float) -> str:
        if action == "SELL PE":
            return "Favourable direction" if move >= 0 else "Adverse direction"
        if action == "SELL CE":
            return "Favourable direction" if move <= 0 else "Adverse direction"
        if action == "IRON CONDOR":
            return "Range pressure" if abs(move) <= 12 else "Directional expansion"
        return "Observation-only market movement"

    @staticmethod
    def _excursions(action: str, max_up: float, max_down: float) -> Tuple[float, float]:
        if action == "SELL PE":
            return max(0.0, max_up), abs(min(0.0, max_down))
        if action == "SELL CE":
            return abs(min(0.0, max_down)), max(0.0, max_up)
        if action == "IRON CONDOR":
            expansion = max(abs(max_up), abs(max_down))
            return max(0.0, 12.0 - expansion), max(0.0, expansion - 12.0)
        return 0.0, max(abs(max_up), abs(max_down))

    def _department_directions(self, reports: Mapping[str, Any]) -> Dict[str, str]:
        output: Dict[str, str] = {}
        for branch, report in reports.items():
            summary = str(self._read(report, "summary", ""))
            details = self._read(report, "details", {})
            recommendation = str(self._read(report, "recommendation", "INFORMATION_ONLY"))
            output[str(branch).upper()] = self._infer_direction(summary, details, recommendation)
        return output

    def _department_alignment(self, current: Mapping[str, str], old_snapshot: Any) -> Tuple[float, List[str]]:
        if not current or not isinstance(old_snapshot, Mapping):
            return 50.0, []
        comparable = 0
        aligned = 0
        conflicts: List[str] = []
        for branch, direction in current.items():
            old = old_snapshot.get(branch, {})
            if not isinstance(old, Mapping):
                continue
            old_direction = str(old.get("direction", "NEUTRAL")).upper()
            current_direction = str(direction).upper()
            if current_direction not in {"BULLISH", "BEARISH", "NEUTRAL", "CAUTION"}:
                continue
            if old_direction not in {"BULLISH", "BEARISH", "NEUTRAL", "CAUTION"}:
                continue
            comparable += 1
            if current_direction == old_direction:
                aligned += 1
            elif {current_direction, old_direction} == {"BULLISH", "BEARISH"}:
                conflicts.append(branch)
            elif current_direction in {"NEUTRAL", "CAUTION"} or old_direction in {"NEUTRAL", "CAUTION"}:
                aligned += 0.5
        if not comparable:
            return 50.0, []
        return aligned / comparable * 100.0, conflicts

    @staticmethod
    def _features(context: Mapping[str, Any]) -> Set[str]:
        features: Set[str] = set()
        for key, value in sorted(context.items()):
            if value in (None, "", "UNKNOWN", "UNAVAILABLE"):
                continue
            token = MarketReplayEngine._token(value)
            if token:
                features.add(f"{str(key).upper()}:{token}")
        return features

    @staticmethod
    def _jaccard(current: Set[str], old: Set[str]) -> Tuple[float, List[str]]:
        union = current | old
        shared = sorted(current & old)
        return len(shared) / max(1, len(union)) * 100.0, shared

    @staticmethod
    def _action_alignment(current: str, old: str) -> float:
        if current == old:
            return 100.0
        if "WAIT" in {current, old}:
            return 55.0
        if "IRON CONDOR" in {current, old}:
            return 40.0
        return 15.0

    @staticmethod
    def _compatible_action(reality: str) -> str:
        reality = str(reality).upper()
        if reality == "UP_MOVE":
            return "SELL PE (HISTORICAL COMPATIBILITY ONLY)"
        if reality == "DOWN_MOVE":
            return "SELL CE (HISTORICAL COMPATIBILITY ONLY)"
        if reality == "RANGE_OR_NO_FOLLOW_THROUGH":
            return "IRON CONDOR / WAIT (HISTORICAL COMPATIBILITY ONLY)"
        return "OBSERVATION_ONLY"

    @staticmethod
    def _historical_alignment(
        *,
        replayed: int,
        matched_accuracy: Optional[float],
        same_action_cases: int,
        same_action_accuracy: Optional[float],
        selected: Sequence[ReplayedCase],
    ) -> str:
        if replayed < 3 or matched_accuracy is None:
            return "INSUFFICIENT_HISTORY"
        high_conf_wrong = sum(item.outcome == "WRONG" and item.confidence >= 75 for item in selected)
        if same_action_cases >= 3 and same_action_accuracy is not None:
            if same_action_accuracy >= 70 and high_conf_wrong == 0:
                return "HISTORICAL_SUPPORT"
            if same_action_accuracy <= 40 or high_conf_wrong >= 2:
                return "HISTORICAL_WARNING"
        if matched_accuracy >= 65 and high_conf_wrong <= 1:
            return "CONTEXT_SUPPORT_WITH_ACTION_CAUTION"
        if matched_accuracy <= 40 or high_conf_wrong >= 2:
            return "HISTORICAL_WARNING"
        return "MIXED_HISTORICAL_EVIDENCE"

    @staticmethod
    def _replay_state(completed: int, replayed: int, best_similarity: float, alignment: str) -> str:
        if completed < 5:
            return "COLLECTING_COMPLETED_CASES"
        if replayed < 3:
            return "LIMITED_REPLAY_MATCHES"
        if best_similarity >= 75 and alignment == "HISTORICAL_SUPPORT":
            return "STRONG_REPLAY_MATCH"
        if alignment == "HISTORICAL_WARNING":
            return "REPLAY_WARNING"
        if best_similarity >= 58:
            return "MODERATE_REPLAY_MATCH"
        return "WEAK_REPLAY_MATCH"

    @staticmethod
    def _dominant_mistakes(selected: Sequence[ReplayedCase]) -> List[str]:
        counts: Dict[str, int] = {}
        for item in selected:
            if item.mistake in {"NO_MATERIAL_MISTAKE", "NO_MISTAKE_VALIDATED", "PENDING_VALIDATION"}:
                continue
            counts[item.mistake] = counts.get(item.mistake, 0) + 1
        return [
            f"{name}: {count}"
            for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:4]
        ]

    @staticmethod
    def _counterfactual_lessons(selected: Sequence[ReplayedCase], action: str, alignment: str) -> List[str]:
        lessons: List[str] = []
        for item in selected[:4]:
            if item.outcome == "WRONG":
                lessons.append(
                    f"{item.case_id}: {item.historical_action} failed; later reality was {item.reality}. "
                    f"Review {item.mistake}."
                )
            elif item.outcome == "CORRECT" and item.historical_action == action:
                lessons.append(
                    f"{item.case_id}: same historical action aligned with {item.reality}; retain as evidence, not a rule."
                )
        if alignment == "HISTORICAL_WARNING":
            lessons.append("Comparable history warns against overconfidence; current live evidence still controls the judgement.")
        return lessons[:5] or ["Collect more comparable completed cases before drawing counterfactual lessons."]

    @staticmethod
    def _next_confirmation(selected: Sequence[ReplayedCase], action: str, alignment: str) -> List[str]:
        output = ["Require current price and option evidence to persist on the next verified snapshot."]
        if alignment == "HISTORICAL_WARNING":
            output.append("Resolve the historical warning with fresh barrier, institutional, and timing confirmation.")
        if any(item.conflicting_departments for item in selected[:3]):
            output.append("Recheck departments that conflict with the closest historical replay.")
        if action == "WAIT":
            output.append("Confirm whether caution remains justified or a directional move develops without execution.")
        return output[:4]

    @staticmethod
    def _infer_direction(summary: str, details: Any, recommendation: str) -> str:
        text = f"{summary} {details} {recommendation}".lower()
        if "sell pe" in text:
            return "BULLISH"
        if "sell ce" in text:
            return "BEARISH"
        bullish = sum(token in text for token in (
            "bullish", "uptrend", "risk_on", "accumulation", "long build", "short covering", "up move"
        ))
        bearish = sum(token in text for token in (
            "bearish", "downtrend", "risk_off", "distribution", "panic selling", "down move"
        ))
        caution = sum(token in text for token in (
            "wait", "caution", "mixed", "conflict", "uncertain", "collecting", "range"
        ))
        if bullish >= bearish + 1 and bullish > caution:
            return "BULLISH"
        if bearish >= bullish + 1 and bearish > caution:
            return "BEARISH"
        return "CAUTION" if caution else "NEUTRAL"

    @staticmethod
    def _read(report: Any, key: str, default: Any) -> Any:
        if isinstance(report, Mapping):
            return report.get(key, default)
        return getattr(report, key, default) if report is not None else default

    @staticmethod
    def _normal_action(value: Any) -> str:
        action = " ".join(str(value or "WAIT").upper().split())
        return action if action in {"WAIT", "SELL CE", "SELL PE", "IRON CONDOR"} else "WAIT"

    @staticmethod
    def _token(value: Any) -> str:
        if isinstance(value, Mapping):
            value = ",".join(
                f"{key}={item}" for key, item in list(value.items())[:4] if item not in (None, "")
            )
        elif isinstance(value, (list, tuple)):
            value = ",".join(str(item) for item in list(value)[:4])
        return " ".join(str(value).upper().replace("_", " ").split())[:90]

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(0.0, min(100.0, float(value or 0.0)))
        except (TypeError, ValueError):
            return 0.0
