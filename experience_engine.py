"""
experience_engine.py
Version: V48.3
Role: Bounded post-judgement experience registry and similar completed-case evidence.

Architecture and safety:
- Uses the already verified live snapshot; no API calls, timers, threads, or loops.
- Completes older pending cases only when a later snapshot arrives.
- Sends historical experience to CO as INFORMATION_ONLY / NEUTRAL evidence.
- Stores prediction, reality, mistake, lesson, and review recommendation.
- Never changes AI weights, thresholds, strategy rules, or execution permission.
- Never issues BUY / SELL CE / SELL PE / IRON CONDOR / WAIT instructions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class ExperienceMatch:
    case_id: str
    similarity: float
    action: str
    prediction: str
    reality: str
    outcome: str
    confidence: float
    actual_move_points: float
    mistake: str
    lesson: str


@dataclass(frozen=True)
class ExperienceReport:
    snapshot_id: str
    state: str
    statement: str
    stored_cases: int
    pending_cases: int
    completed_cases: int
    correct_cases: int
    wrong_cases: int
    observation_cases: int
    overall_accuracy: Optional[float]
    similar_completed_cases: int
    similar_accuracy: Optional[float]
    best_similarity: float
    matches: List[ExperienceMatch] = field(default_factory=list)
    recent_completed: List[Dict[str, Any]] = field(default_factory=list)
    dominant_mistakes: List[str] = field(default_factory=list)
    lessons: List[str] = field(default_factory=list)
    next_recommendations: List[str] = field(default_factory=list)
    newly_completed: List[Dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "experience_state": self.state,
            "statement": self.statement,
            "stored_cases": self.stored_cases,
            "pending_cases": self.pending_cases,
            "completed_cases": self.completed_cases,
            "correct_cases": self.correct_cases,
            "wrong_cases": self.wrong_cases,
            "observation_cases": self.observation_cases,
            "overall_accuracy": self.overall_accuracy,
            "similar_completed_cases": self.similar_completed_cases,
            "similar_accuracy": self.similar_accuracy,
            "best_similarity": self.best_similarity,
            "matches": [asdict(item) for item in self.matches],
            "recent_completed": list(self.recent_completed),
            "dominant_mistakes": list(self.dominant_mistakes),
            "lessons": list(self.lessons),
            "next_recommendations": list(self.next_recommendations),
            "newly_completed": list(self.newly_completed),
            "confidence": self.confidence,
            "warnings": list(self.warnings),
            "authority": "DSP_EXPERIENCE_TO_CO_INFORMATION_ONLY",
            "execution_instruction": "NONE",
            "automatic_rule_change": False,
            "storage_scope": "BOUNDED_STREAMLIT_SESSION",
        }

    def to_department_report(self) -> Dict[str, Any]:
        details = self.to_compact_dict()
        # Keep the CO branch payload compact. Full match rows remain in UI trace.
        details["matches"] = details["matches"][:5]
        details["recent_completed"] = details["recent_completed"][:5]
        details["newly_completed"] = details["newly_completed"][:8]
        return {
            "summary": (
                f"{self.statement} | completed {self.completed_cases}, pending {self.pending_cases} | "
                f"similar accuracy {self.similar_accuracy if self.similar_accuracy is not None else 'NA'}"
            )[:300],
            "confidence": self.confidence,
            "details": details,
            "recommendation": "INFORMATION_ONLY",
            "branch_vote": "NEUTRAL",
            "execution_instruction": "NONE",
        }


class ExperienceEngine:
    """One-shot bounded experience investigation for Streamlit reruns."""

    SESSION_KEY = "v43_experience_records"
    SEQUENCE_KEY = "v43_experience_sequence"
    LAST_SNAPSHOT_KEY = "v43_experience_last_snapshot"
    LAST_REGISTERED_KEY = "v43_last_registered_experience"

    def __init__(
        self,
        *,
        max_records: int = 400,
        max_matches: int = 8,
        evaluation_snapshots: int = 4,
    ) -> None:
        self.max_records = max(40, min(int(max_records), 500))
        self.max_matches = max(3, min(int(max_matches), 12))
        self.evaluation_snapshots = max(3, min(int(evaluation_snapshots), 12))

    def investigate(
        self,
        *,
        state: MutableMapping[str, Any],
        snapshot_id: str,
        current_price: float,
        atr_points: float,
        context: Mapping[str, Any],
        advance_snapshot: bool = True,
    ) -> ExperienceReport:
        records = self._records(state)
        sequence = self._sequence(state, snapshot_id, advance_snapshot)
        threshold = self._threshold(atr_points)
        newly_completed: List[Dict[str, str]] = []

        if advance_snapshot:
            for record in records:
                if not isinstance(record, dict) or record.get("status") != "PENDING":
                    continue
                self._observe_pending(record, sequence, current_price)
                if self._ready_to_complete(record, threshold):
                    self._complete_record(record, threshold)
                    newly_completed.append({
                        "case_id": str(record.get("case_id", "UNKNOWN")),
                        "outcome": self._history_outcome(str(record.get("outcome", "OBSERVATION"))),
                    })

        records = records[-self.max_records:]
        state[self.SESSION_KEY] = records
        fingerprint, current_features = self._fingerprint(context)
        completed = [item for item in records if isinstance(item, dict) and item.get("status") == "COMPLETED"]
        pending = [item for item in records if isinstance(item, dict) and item.get("status") == "PENDING"]
        matches = self._matches(current_features, completed)

        correct = sum(1 for item in completed if item.get("outcome") == "CORRECT")
        wrong = sum(1 for item in completed if item.get("outcome") == "WRONG")
        observation = sum(1 for item in completed if item.get("outcome") not in {"CORRECT", "WRONG"})
        validated = correct + wrong
        overall_accuracy = round(correct / validated * 100.0, 1) if validated else None

        matched_validated = [item for item in matches if item.outcome in {"CORRECT", "WRONG"}]
        similar_correct = sum(1 for item in matched_validated if item.outcome == "CORRECT")
        similar_accuracy = round(similar_correct / len(matched_validated) * 100.0, 1) if matched_validated else None
        best_similarity = matches[0].similarity if matches else 0.0

        if len(completed) < 5:
            experience_state = "COLLECTING_COMPLETED_CASES"
        elif len(matches) >= 3 and best_similarity >= 70:
            experience_state = "STRONG_SIMILAR_EXPERIENCE"
        elif matches and best_similarity >= 55:
            experience_state = "MODERATE_SIMILAR_EXPERIENCE"
        else:
            experience_state = "LIMITED_SIMILAR_EXPERIENCE"

        dominant_mistakes = self._dominant_mistakes(completed)
        lessons = self._lessons(matches, dominant_mistakes)
        recommendations = self._recommendations(matches, dominant_mistakes)
        warnings: List[str] = []
        if len(completed) < 20:
            warnings.append("Fewer than 20 completed cases; do not change production rules.")
        if similar_accuracy is None:
            warnings.append("Similar-case accuracy unavailable until matched cases are validated.")
        warnings.append("Session-bounded archive may reset after app restart or redeploy.")

        report_confidence = min(
            92.0,
            20.0 + min(len(completed), 40) * 1.2 + min(len(matches), 8) * 3.0 + best_similarity * 0.18,
        )
        statement = f"I have seen {len(matches)} similar completed case{'s' if len(matches) != 1 else ''}."

        recent_completed = [self._public_record(item) for item in completed[-6:]][::-1]
        return ExperienceReport(
            snapshot_id=str(snapshot_id or "UNKNOWN"),
            state=experience_state,
            statement=statement,
            stored_cases=len(records),
            pending_cases=len(pending),
            completed_cases=len(completed),
            correct_cases=correct,
            wrong_cases=wrong,
            observation_cases=observation,
            overall_accuracy=overall_accuracy,
            similar_completed_cases=len(matches),
            similar_accuracy=similar_accuracy,
            best_similarity=round(best_similarity, 1),
            matches=matches,
            recent_completed=recent_completed,
            dominant_mistakes=dominant_mistakes,
            lessons=lessons,
            next_recommendations=recommendations,
            newly_completed=newly_completed,
            confidence=round(report_confidence, 1),
            warnings=warnings[:4],
        )

    def register_judgement(
        self,
        *,
        state: MutableMapping[str, Any],
        snapshot_id: str,
        case_id: str,
        action: str,
        confidence: float,
        entry_price: float,
        market_bias: str,
        case_strength: float,
        consensus_direction: str,
        trade_allowed: bool,
        context: Mapping[str, Any],
        department_reports: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        records = self._records(state)
        if any(str(item.get("case_id")) == str(case_id) for item in records if isinstance(item, dict)):
            return False

        sequence = int(state.get(self.SEQUENCE_KEY, 0) or 0)
        action = str(action or "WAIT").upper()
        confidence_value = self._number(confidence)
        fingerprint, features = self._fingerprint(context)

        # Prevent refresh spam. Trade-approved judgements are always recorded;
        # informational WAIT cases are sampled only after a material state change
        # or at least three new verified snapshots.
        last = state.get(self.LAST_REGISTERED_KEY, {})
        if not isinstance(last, Mapping):
            last = {}
        same_state = (
            str(last.get("action", "")) == action
            and str(last.get("market_bias", "")) == str(market_bias).upper()
            and int(self._number(last.get("confidence", 0)) // 10) == int(confidence_value // 10)
            and str(last.get("fingerprint", "")) == fingerprint
        )
        sequence_gap = sequence - int(last.get("sequence", -999) or -999)
        if not trade_allowed and same_state and sequence_gap < 3:
            return False

        prediction = self._prediction(action, market_bias)
        record = {
            "case_id": str(case_id or "UNKNOWN"),
            "snapshot_id": str(snapshot_id or "UNKNOWN"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "registered_sequence": sequence,
            "last_observed_sequence": sequence,
            "action": action,
            "prediction": prediction,
            "confidence": round(confidence_value, 1),
            "entry_price": round(float(entry_price or 0.0), 2),
            "last_price": round(float(entry_price or 0.0), 2),
            "max_up_points": 0.0,
            "max_down_points": 0.0,
            "market_bias": str(market_bias or "NEUTRAL").upper(),
            "case_strength": round(self._number(case_strength), 1),
            "consensus_direction": str(consensus_direction or "NEUTRAL").upper(),
            "trade_allowed": bool(trade_allowed),
            "features": sorted(features)[:32],
            "fingerprint": fingerprint,
            "department_snapshot": self._department_snapshot(department_reports or {}),
            "status": "PENDING",
            "reality": "PENDING",
            "actual_move_points": 0.0,
            "outcome": "PENDING",
            "mistake": "PENDING_VALIDATION",
            "lesson": "Await later verified snapshots.",
            "next_recommendation": "No automatic rule change.",
            "observations": [{
                "sequence": sequence,
                "price": round(float(entry_price or 0.0), 2),
                "move_points": 0.0,
                "phase": "ENTRY",
            }],
        }
        records.append(record)
        state[self.SESSION_KEY] = records[-self.max_records:]
        state[self.LAST_REGISTERED_KEY] = {
            "action": action,
            "market_bias": str(market_bias or "NEUTRAL").upper(),
            "confidence": round(confidence_value, 1),
            "fingerprint": fingerprint,
            "sequence": sequence,
        }
        return True

    def _observe_pending(self, record: Dict[str, Any], sequence: int, current_price: float) -> None:
        entry = float(record.get("entry_price", 0.0) or 0.0)
        current = float(current_price or entry)
        move = current - entry
        record["last_price"] = round(current, 2)
        previous_sequence = int(record.get("last_observed_sequence", record.get("registered_sequence", 0)) or 0)
        record["last_observed_sequence"] = sequence
        record["max_up_points"] = round(max(float(record.get("max_up_points", 0.0) or 0.0), move), 2)
        record["max_down_points"] = round(min(float(record.get("max_down_points", 0.0) or 0.0), move), 2)
        record["actual_move_points"] = round(move, 2)

        # V48 compact replay path. Store at most ten verified snapshot points;
        # never retain option tables, candles, or large object graphs.
        observations = record.get("observations", [])
        if not isinstance(observations, list):
            observations = []
        if sequence != previous_sequence:
            age = max(0, sequence - int(record.get("registered_sequence", sequence) or sequence))
            observations.append({
                "sequence": sequence,
                "price": round(current, 2),
                "move_points": round(move, 2),
                "phase": f"SNAPSHOT_{age}",
            })
            record["observations"] = observations[-10:]

    def _ready_to_complete(self, record: Mapping[str, Any], threshold: float) -> bool:
        age = int(record.get("last_observed_sequence", 0) or 0) - int(record.get("registered_sequence", 0) or 0)
        max_move = max(
            abs(float(record.get("max_up_points", 0.0) or 0.0)),
            abs(float(record.get("max_down_points", 0.0) or 0.0)),
        )
        return age >= self.evaluation_snapshots or (age >= 2 and max_move >= threshold * 1.5)

    def _complete_record(self, record: Dict[str, Any], threshold: float) -> None:
        move = float(record.get("actual_move_points", 0.0) or 0.0)
        if move >= threshold:
            reality = "UP_MOVE"
        elif move <= -threshold:
            reality = "DOWN_MOVE"
        else:
            reality = "RANGE_OR_NO_FOLLOW_THROUGH"

        action = str(record.get("action", "WAIT")).upper()
        if action == "SELL PE":
            outcome = "WRONG" if reality == "DOWN_MOVE" else "CORRECT"
        elif action == "SELL CE":
            outcome = "WRONG" if reality == "UP_MOVE" else "CORRECT"
        elif action == "IRON CONDOR":
            outcome = "CORRECT" if reality == "RANGE_OR_NO_FOLLOW_THROUGH" else "WRONG"
        else:
            outcome = "OBSERVATION"

        mistake = self._mistake(action, outcome, reality, self._number(record.get("confidence", 0)), record)
        lesson = self._lesson(action, mistake, reality)
        recommendation = self._review_recommendation(mistake)
        record.update({
            "status": "COMPLETED",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "reality": reality,
            "outcome": outcome,
            "mistake": mistake,
            "lesson": lesson,
            "next_recommendation": recommendation,
        })

    def _matches(self, current_features: Set[str], completed: Sequence[Mapping[str, Any]]) -> List[ExperienceMatch]:
        rows: List[ExperienceMatch] = []
        for old in completed[-self.max_records:]:
            old_features = set(str(item) for item in list(old.get("features", []) or []))
            if not old_features:
                continue
            union = current_features | old_features
            shared = current_features & old_features
            similarity = len(shared) / max(1, len(union)) * 100.0
            # Exact market-regime overlap is more useful than generic metadata.
            if similarity < 40.0:
                continue
            rows.append(ExperienceMatch(
                case_id=str(old.get("case_id", "UNKNOWN")),
                similarity=round(similarity, 1),
                action=str(old.get("action", "WAIT")),
                prediction=str(old.get("prediction", "NO_TRADE_OBSERVATION")),
                reality=str(old.get("reality", "UNKNOWN")),
                outcome=str(old.get("outcome", "OBSERVATION")),
                confidence=round(self._number(old.get("confidence", 0)), 1),
                actual_move_points=round(float(old.get("actual_move_points", 0.0) or 0.0), 1),
                mistake=str(old.get("mistake", "NONE_IDENTIFIED")),
                lesson=str(old.get("lesson", "Observation stored."))[:220],
            ))
        return sorted(rows, key=lambda item: item.similarity, reverse=True)[:self.max_matches]

    def _department_snapshot(self, reports: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Store compact department evidence for later V44 outcome review.

        This snapshot is descriptive only. Observation-only branches remain
        non-voting in CO and AI_MASTER even when their directional evidence is
        later evaluated for accuracy.
        """
        output: Dict[str, Dict[str, Any]] = {}
        for branch, report in reports.items():
            name = str(branch or "UNKNOWN").upper()
            if name == "SELF_REVIEW":
                continue
            summary = str(self._read_report(report, "summary", ""))[:260]
            confidence = self._number(self._read_report(report, "confidence", 0.0))
            details = self._read_report(report, "details", {})
            recommendation = str(self._read_report(report, "recommendation", "INFORMATION_ONLY"))
            direction = self._infer_department_direction(summary, details, recommendation)
            output[name] = {
                "direction": direction,
                "confidence": round(max(0.0, min(100.0, confidence)), 1),
                "summary": summary,
                "recommendation": recommendation[:80],
            }
        return output

    @staticmethod
    def _read_report(report: Any, key: str, default: Any) -> Any:
        if isinstance(report, Mapping):
            return report.get(key, default)
        return getattr(report, key, default) if report is not None else default

    @staticmethod
    def _infer_department_direction(summary: str, details: Any, recommendation: str) -> str:
        text = f"{summary} {details} {recommendation}".lower()
        if "sell pe" in text:
            return "BULLISH"
        if "sell ce" in text:
            return "BEARISH"
        if "iron condor" in text:
            return "NEUTRAL"
        bullish_tokens = (
            "bullish", "uptrend", "risk_on", "risk on", "accumulation",
            "long build", "short covering", "upside participation", "up move",
            "domestic absorption", "positive pressure",
        )
        bearish_tokens = (
            "bearish", "downtrend", "risk_off", "risk off", "distribution",
            "panic selling", "downside participation", "down move",
            "negative pressure",
        )
        neutral_tokens = (
            "range", "balanced", "neutral", "mixed", "conflict", "collecting",
            "information_only", "information only", "wait", "uncertain",
        )
        bullish = sum(token in text for token in bullish_tokens)
        bearish = sum(token in text for token in bearish_tokens)
        neutral = sum(token in text for token in neutral_tokens)
        if bullish >= bearish + 1 and bullish >= neutral:
            return "BULLISH"
        if bearish >= bullish + 1 and bearish >= neutral:
            return "BEARISH"
        if neutral or bullish == bearish:
            return "NEUTRAL"
        return "CAUTION"

    def _fingerprint(self, context: Mapping[str, Any]) -> Tuple[str, Set[str]]:
        features: Set[str] = set()
        for key, value in sorted(context.items()):
            if value in (None, "", "UNKNOWN", "UNAVAILABLE"):
                continue
            token = self._token(value)
            if token:
                features.add(f"{str(key).upper()}:{token}")
        fingerprint = " | ".join(sorted(features))[:1200]
        return fingerprint, features

    @staticmethod
    def _prediction(action: str, market_bias: str) -> str:
        if action == "SELL PE":
            return "UP_OR_STABLE"
        if action == "SELL CE":
            return "DOWN_OR_STABLE"
        if action == "IRON CONDOR":
            return "RANGE"
        bias = str(market_bias or "NEUTRAL").upper()
        return f"NO_TRADE_{bias}_OBSERVATION"

    @staticmethod
    def _mistake(action: str, outcome: str, reality: str, confidence: float, record: Mapping[str, Any]) -> str:
        if action == "WAIT":
            if reality in {"UP_MOVE", "DOWN_MOVE"}:
                return "MISSED_DIRECTIONAL_MOVE_REVIEW"
            return "NO_MISTAKE_VALIDATED"
        if outcome == "CORRECT":
            max_up = abs(float(record.get("max_up_points", 0.0) or 0.0))
            max_down = abs(float(record.get("max_down_points", 0.0) or 0.0))
            if min(max_up, max_down) >= 12:
                return "ENTRY_TIMING_VOLATILITY_REVIEW"
            return "NO_MATERIAL_MISTAKE"
        if confidence >= 75:
            return "HIGH_CONFIDENCE_WRONG_DIRECTION"
        if action == "IRON CONDOR":
            return "RANGE_ASSUMPTION_FAILED"
        return "DIRECTIONAL_THESIS_FAILED"

    @staticmethod
    def _lesson(action: str, mistake: str, reality: str) -> str:
        if mistake == "HIGH_CONFIDENCE_WRONG_DIRECTION":
            return "High-confidence thesis failed; review conflicting barriers, institutional flow, and timing evidence."
        if mistake == "RANGE_ASSUMPTION_FAILED":
            return "Range thesis failed in a directional move; review expansion, news, and breakout evidence."
        if mistake == "DIRECTIONAL_THESIS_FAILED":
            return "Directional thesis failed; compare price follow-through with option and heavyweight confirmation."
        if mistake == "MISSED_DIRECTIONAL_MOVE_REVIEW":
            return "WAIT avoided execution but a directional move followed; review whether evidence was incomplete or overly cautious."
        if mistake == "ENTRY_TIMING_VOLATILITY_REVIEW":
            return "Direction survived but adverse excursion was meaningful; review entry timing and barrier distance."
        if reality == "RANGE_OR_NO_FOLLOW_THROUGH":
            return "The case produced limited follow-through; preserve caution until repeated evidence exists."
        return "Prediction aligned with later reality; retain as evidence, not as an automatic rule."

    @staticmethod
    def _review_recommendation(mistake: str) -> str:
        mapping = {
            "HIGH_CONFIDENCE_WRONG_DIRECTION": "Recommend AI_MASTER review confidence calibration; no automatic threshold change.",
            "RANGE_ASSUMPTION_FAILED": "Recommend review of breakout and event-risk evidence before future range cases.",
            "DIRECTIONAL_THESIS_FAILED": "Recommend cross-department review of direction confirmation; no automatic rule change.",
            "MISSED_DIRECTIONAL_MOVE_REVIEW": "Recommend review of excessive caution only after a larger validated sample.",
            "ENTRY_TIMING_VOLATILITY_REVIEW": "Recommend review of entry timing and adverse-excursion guard.",
        }
        return mapping.get(mistake, "No automatic rule change recommended.")

    def _dominant_mistakes(self, completed: Sequence[Mapping[str, Any]]) -> List[str]:
        counts: Dict[str, int] = {}
        for item in completed:
            mistake = str(item.get("mistake", "NONE_IDENTIFIED"))
            if mistake in {"NO_MATERIAL_MISTAKE", "NO_MISTAKE_VALIDATED", "PENDING_VALIDATION"}:
                continue
            counts[mistake] = counts.get(mistake, 0) + 1
        return [f"{name}: {count}" for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:4]]

    @staticmethod
    def _lessons(matches: Sequence[ExperienceMatch], mistakes: Sequence[str]) -> List[str]:
        lessons: List[str] = []
        for item in matches[:4]:
            if item.lesson and item.lesson not in lessons:
                lessons.append(item.lesson)
        if mistakes:
            lessons.append("Repeated mistake categories require manual review after sufficient samples.")
        return lessons[:5] or ["Collect completed cases before drawing historical lessons."]

    @staticmethod
    def _recommendations(matches: Sequence[ExperienceMatch], mistakes: Sequence[str]) -> List[str]:
        output = ["Keep experience evidence informational until live validation is complete."]
        if len(matches) < 3:
            output.append("Collect at least three similar completed cases before trusting a pattern.")
        if mistakes:
            output.append("Review dominant mistakes manually; do not auto-edit production logic.")
        else:
            output.append("No automatic rule change recommended.")
        return output[:4]

    @staticmethod
    def _public_record(item: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "case_id": str(item.get("case_id", "UNKNOWN")),
            "action": str(item.get("action", "WAIT")),
            "prediction": str(item.get("prediction", "UNKNOWN")),
            "reality": str(item.get("reality", "UNKNOWN")),
            "actual_move_points": round(float(item.get("actual_move_points", 0.0) or 0.0), 1),
            "outcome": str(item.get("outcome", "OBSERVATION")),
            "mistake": str(item.get("mistake", "NONE_IDENTIFIED")),
            "lesson": str(item.get("lesson", "Observation stored."))[:220],
            "next_recommendation": str(item.get("next_recommendation", "No automatic rule change."))[:220],
            "replay_observations": len(item.get("observations", []) or []) if isinstance(item.get("observations", []), list) else 0,
            "replay_ready": bool(isinstance(item.get("observations", []), list) and len(item.get("observations", [])) >= 2),
        }

    def _records(self, state: MutableMapping[str, Any]) -> List[Dict[str, Any]]:
        records = state.get(self.SESSION_KEY, [])
        if not isinstance(records, list):
            records = []
        return [dict(item) for item in records if isinstance(item, Mapping)][-self.max_records:]

    def _sequence(self, state: MutableMapping[str, Any], snapshot_id: str, advance: bool) -> int:
        sequence = int(state.get(self.SEQUENCE_KEY, 0) or 0)
        last_snapshot = str(state.get(self.LAST_SNAPSHOT_KEY, ""))
        if advance and str(snapshot_id) != last_snapshot:
            sequence += 1
            state[self.SEQUENCE_KEY] = sequence
            state[self.LAST_SNAPSHOT_KEY] = str(snapshot_id)
        return sequence

    @staticmethod
    def _threshold(atr_points: float) -> float:
        try:
            atr = abs(float(atr_points or 0.0))
        except (TypeError, ValueError):
            atr = 0.0
        return max(8.0, min(35.0, atr * 0.45 if atr else 12.0))

    @staticmethod
    def _history_outcome(outcome: str) -> str:
        if outcome in {"CORRECT", "WRONG"}:
            return outcome
        return "NEUTRAL"

    @staticmethod
    def _token(value: Any) -> str:
        if isinstance(value, Mapping):
            parts = [f"{key}={item}" for key, item in list(value.items())[:4] if item not in (None, "")]
            value = ",".join(parts)
        elif isinstance(value, (list, tuple)):
            value = ",".join(str(item) for item in list(value)[:4])
        return " ".join(str(value).upper().replace("_", " ").split())[:90]

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(0.0, min(100.0, float(value or 0.0)))
        except (TypeError, ValueError):
            return 0.0
