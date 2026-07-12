"""
learning_department.py
Version: V46.3
Department: True Learning & Improvement Recommendation

Purpose:
- Convert completed-case experience, department self review, and service-board
  evidence into bounded improvement recommendations for CO and AI_MASTER review.
- Preserve the legacy calibration API used by earlier builds.

Golden-rule safety:
- Never changes production rules, weights, thresholds, SOPs, ranks, or training.
- Never issues BUY / SELL CE / SELL PE / IRON CONDOR / WAIT instructions.
- Recommendations are hypotheses for manual review, not a second decision brain.
- No API calls, threads, timers, background jobs, or self-editing code.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
from typing import Any, Deque, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class LearningRecord:
    """Legacy V24 calibration record retained for compatibility."""

    snapshot_id: str
    action: str
    confidence: float
    entry_price: float
    evaluation_price: float
    points_change: float
    expected_direction_correct: Optional[bool]
    outcome: str


@dataclass(frozen=True)
class ImprovementRecommendation:
    recommendation_id: str
    branch: str
    recommendation_type: str
    recommendation: str
    reason: str
    evidence_sources: List[str]
    validated_samples: int
    evidence_score: float
    occurrences: int
    status: str
    first_seen_at: str
    last_seen_at: str
    manual_review_required: bool = True


@dataclass(frozen=True)
class TrueLearningReport:
    snapshot_id: str
    review_date: str
    review_scope: str
    learning_state: str
    completed_cases_seen: int
    branches_observed: int
    recommendations_count: int
    review_ready_count: int
    collecting_count: int
    preserve_count: int
    recommendations: List[ImprovementRecommendation] = field(default_factory=list)
    priority_recommendations: List[str] = field(default_factory=list)
    preserved_behaviours: List[str] = field(default_factory=list)
    rejected_automation: List[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "review_date": self.review_date,
            "review_scope": self.review_scope,
            "learning_state": self.learning_state,
            "completed_cases_seen": self.completed_cases_seen,
            "branches_observed": self.branches_observed,
            "recommendations_count": self.recommendations_count,
            "review_ready_count": self.review_ready_count,
            "collecting_count": self.collecting_count,
            "preserve_count": self.preserve_count,
            "recommendations": [asdict(item) for item in self.recommendations],
            "priority_recommendations": list(self.priority_recommendations),
            "preserved_behaviours": list(self.preserved_behaviours),
            "rejected_automation": list(self.rejected_automation),
            "confidence": self.confidence,
            "warnings": list(self.warnings),
            "authority": "DSP_TRUE_LEARNING_TO_CO_INFORMATION_ONLY",
            "execution_instruction": "NONE",
            "automatic_rule_change": False,
            "automatic_weight_change": False,
            "automatic_threshold_change": False,
            "automatic_sop_change": False,
            "automatic_training": False,
            "automatic_promotion_or_demotion": False,
            "automatic_code_edit": False,
            "manual_ai_master_review_required": True,
            "storage_scope": "BOUNDED_STREAMLIT_SESSION",
        }

    def to_department_report(self) -> Dict[str, Any]:
        details = self.to_compact_dict()
        details["recommendations"] = details["recommendations"][:18]
        return {
            "summary": (
                f"{self.learning_state} | {self.recommendations_count} improvement hypothesis(es), "
                f"{self.review_ready_count} AI_MASTER review-ready, {self.collecting_count} collecting"
            )[:300],
            "confidence": self.confidence,
            "details": details,
            "recommendation": "INFORMATION_ONLY",
            "branch_vote": "NEUTRAL",
            "execution_instruction": "NONE",
        }


class LearningDepartment:
    """Existing Learning Department upgraded to V46 True Learning.

    The class deliberately retains V24 ``evaluate`` and ``calibration_report``
    methods while adding one controlled ``investigate`` path for V46.
    """

    RECOMMENDATION_KEY = "v46_true_learning_recommendations"
    ARCHIVE_KEY = "v46_true_learning_archive"
    MAX_RECOMMENDATIONS = 80
    MAX_ARCHIVE_DAYS = 10

    def __init__(self, max_records: int = 200, max_recommendations: int = 80) -> None:
        self.records: Deque[LearningRecord] = deque(maxlen=max(10, int(max_records)))
        self.max_recommendations = max(20, min(int(max_recommendations), self.MAX_RECOMMENDATIONS))

    # ------------------------------------------------------------------
    # Legacy calibration API
    # ------------------------------------------------------------------
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
        else:
            correct = None

        outcome = "CORRECT" if correct is True else "WRONG" if correct is False else "OBSERVATION"
        record = LearningRecord(
            snapshot_id=str(snapshot_id),
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
        completed = [item for item in self.records if item.expected_direction_correct is not None]
        if not completed:
            return {"sample_size": 0, "accuracy": None, "message": "Not enough completed samples."}
        correct = sum(item.expected_direction_correct is True for item in completed)
        buckets: Dict[str, Dict[str, Any]] = {
            "50-59": {"total": 0, "correct": 0},
            "60-69": {"total": 0, "correct": 0},
            "70-79": {"total": 0, "correct": 0},
            "80-89": {"total": 0, "correct": 0},
            "90-100": {"total": 0, "correct": 0},
        }
        for item in completed:
            bucket = (
                "50-59" if item.confidence < 60 else
                "60-69" if item.confidence < 70 else
                "70-79" if item.confidence < 80 else
                "80-89" if item.confidence < 90 else "90-100"
            )
            buckets[bucket]["total"] += 1
            buckets[bucket]["correct"] += int(item.expected_direction_correct is True)
        for values in buckets.values():
            total = int(values["total"])
            values["accuracy"] = round(values["correct"] / total * 100.0, 1) if total else None
        return {
            "sample_size": len(completed),
            "accuracy": round(correct / len(completed) * 100.0, 1),
            "confidence_calibration": buckets,
            "review_suggestions": self.review_suggestions(),
        }

    def review_suggestions(self) -> List[str]:
        completed = [item for item in self.records if item.expected_direction_correct is not None]
        if len(completed) < 20:
            return ["Collect at least 20 validated samples before changing rules."]
        suggestions: List[str] = []
        high_wrong = [item for item in completed if item.confidence >= 80 and item.expected_direction_correct is False]
        if len(high_wrong) / len(completed) >= 0.15:
            suggestions.append("Review overconfidence: too many 80%+ decisions were wrong.")
        for action, label in (("SELL PE", "SELL PE"), ("SELL CE", "SELL CE")):
            rows = [item for item in completed if item.action == action]
            if len(rows) >= 10:
                accuracy = sum(bool(item.expected_direction_correct) for item in rows) / len(rows)
                if accuracy < 0.55:
                    suggestions.append(f"Review {label} permission and late-entry rules.")
        return suggestions or ["No automatic rule change recommended."]

    def export_records(self) -> List[Dict[str, Any]]:
        return [asdict(item) for item in self.records]

    def clear(self) -> None:
        self.records.clear()

    # ------------------------------------------------------------------
    # V46 True Learning
    # ------------------------------------------------------------------
    def investigate(
        self,
        *,
        state: MutableMapping[str, Any],
        snapshot_id: str,
        observed_at: Any,
        market_open: bool,
        experience: Optional[Mapping[str, Any]] = None,
        self_review: Optional[Mapping[str, Any]] = None,
        promotion_board: Optional[Mapping[str, Any]] = None,
    ) -> TrueLearningReport:
        now = self._parse_datetime(observed_at)
        review_date = now.date().isoformat()
        final_scope = (not bool(market_open)) or (now.hour, now.minute) >= (15, 30)
        review_scope = "EVENING_RECOMMENDATION_REVIEW" if final_scope else "LIVE_PROVISIONAL_LEARNING"

        experience = experience if isinstance(experience, Mapping) else {}
        self_review = self_review if isinstance(self_review, Mapping) else {}
        promotion_board = promotion_board if isinstance(promotion_board, Mapping) else {}

        candidates = self._candidate_recommendations(experience, self_review, promotion_board)
        registry = self._registry(state)
        touched_ids: List[str] = []
        for candidate in candidates:
            record = self._merge_candidate(registry, candidate, snapshot_id=str(snapshot_id), observed_at=now)
            registry[record["recommendation_id"]] = record
            touched_ids.append(record["recommendation_id"])

        # Keep strongest/recent records only. Nothing here is applied to production.
        ordered_records = sorted(
            registry.values(),
            key=lambda item: (
                self._status_order(str(item.get("status", "COLLECTING_EVIDENCE"))),
                -self._number(item.get("evidence_score", 0)),
                -self._integer(item.get("validated_samples", 0)),
                str(item.get("branch", "")),
            ),
        )[: self.max_recommendations]
        state[self.RECOMMENDATION_KEY] = {
            str(item.get("recommendation_id")): dict(item) for item in ordered_records
        }

        public = [self._to_recommendation(item) for item in ordered_records]
        review_ready = [item for item in public if item.status == "AI_MASTER_REVIEW_READY"]
        collecting = [item for item in public if item.status in {"COLLECTING_EVIDENCE", "MANUAL_REVIEW_CANDIDATE"}]
        preserve = [item for item in public if item.recommendation_type == "PRESERVE_VALIDATED_BEHAVIOUR"]
        completed_cases = self._integer(self_review.get("completed_cases_reviewed", experience.get("completed_cases", 0)))
        branches = len({item.branch for item in public if item.branch})

        if not public:
            learning_state = "COLLECTING_COMPLETED_CASE_EVIDENCE"
        elif review_ready:
            learning_state = "AI_MASTER_REVIEW_RECOMMENDATIONS_READY"
        elif any(item.status == "MANUAL_REVIEW_CANDIDATE" for item in public):
            learning_state = "MANUAL_REVIEW_CANDIDATES_FORMING"
        else:
            learning_state = "LEARNING_HYPOTHESES_COLLECTING"

        priority = [
            f"{item.branch}: {item.recommendation}"
            for item in public
            if item.status in {"AI_MASTER_REVIEW_READY", "MANUAL_REVIEW_CANDIDATE"}
            and item.recommendation_type != "PRESERVE_VALIDATED_BEHAVIOUR"
        ][:6]
        preserved = [f"{item.branch}: {item.recommendation}" for item in preserve[:5]]
        rejected_automation = [
            "Automatic production-rule editing rejected.",
            "Automatic confidence/weight/threshold changes rejected.",
            "Automatic training, promotion, or demotion rejected.",
        ]
        warnings = []
        if completed_cases < 10:
            warnings.append("Fewer than 10 completed cases; all learning recommendations are provisional.")
        if not final_scope:
            warnings.append("Live learning report is provisional; evening evidence review is preferred.")
        warnings.append("A recommendation may become review-ready, but it is never auto-applied.")
        warnings.append("Session-bounded learning history may reset after app restart or redeploy.")

        evidence_total = sum(item.validated_samples for item in public)
        confidence = min(
            94.0,
            15.0 + min(completed_cases, 40) * 1.1 + min(evidence_total, 120) * 0.18 + len(review_ready) * 3.0 + (6.0 if final_scope else 0.0),
        )

        report = TrueLearningReport(
            snapshot_id=str(snapshot_id or "UNKNOWN"),
            review_date=review_date,
            review_scope=review_scope,
            learning_state=learning_state,
            completed_cases_seen=completed_cases,
            branches_observed=branches,
            recommendations_count=len(public),
            review_ready_count=len(review_ready),
            collecting_count=len(collecting),
            preserve_count=len(preserve),
            recommendations=public[:18],
            priority_recommendations=priority,
            preserved_behaviours=preserved,
            rejected_automation=rejected_automation,
            confidence=round(confidence, 1),
            warnings=warnings[:5],
        )
        if final_scope:
            self._archive_final(state, report)
        return report

    def _candidate_recommendations(
        self,
        experience: Mapping[str, Any],
        self_review: Mapping[str, Any],
        promotion_board: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []

        reviews = self_review.get("department_reviews", [])
        if isinstance(reviews, Sequence) and not isinstance(reviews, (str, bytes)):
            for item in reviews:
                if not isinstance(item, Mapping):
                    continue
                branch = str(item.get("branch", "UNKNOWN")).upper()
                validated = self._integer(item.get("validated_samples", 0))
                accuracy_raw = item.get("accuracy")
                accuracy = self._number(accuracy_raw) if accuracy_raw is not None else None
                high_wrong = self._integer(item.get("high_confidence_wrong", 0))
                reliability = self._number(item.get("sop_reliability", 0))
                status = str(item.get("performance_status", "COLLECTING_EVIDENCE"))

                if high_wrong >= 2:
                    output.append(self._candidate(
                        branch, "CONFIDENCE_CALIBRATION_REVIEW",
                        "Review confidence calibration against contradicted completed cases.",
                        f"{high_wrong} high-confidence contradiction(s) across {validated} validated sample(s).",
                        ["SELF_REVIEW", "COMPLETED_CASES"], validated,
                        min(95.0, 45.0 + high_wrong * 12.0 + validated * 1.5),
                        signature=(validated, high_wrong, accuracy, reliability),
                    ))
                if accuracy is not None and validated >= 3 and accuracy < 55.0:
                    output.append(self._candidate(
                        branch, "DIRECTION_EVIDENCE_REVIEW",
                        "Review which confirmations were missing before the department formed a directional view.",
                        f"Validated accuracy is {accuracy:.1f}% across {validated} sample(s).",
                        ["SELF_REVIEW", "PREDICTION_VS_REALITY"], validated,
                        min(92.0, 40.0 + (55.0 - accuracy) * 1.2 + validated * 1.2),
                        signature=(validated, accuracy, high_wrong),
                    ))
                if reliability < 65.0 and self._integer(item.get("unscored_cases", 0)) + validated >= 3:
                    output.append(self._candidate(
                        branch, "SOP_AND_CONSISTENCY_REVIEW",
                        "Review SOP completeness and observation stability before trusting repeated evidence.",
                        f"SOP/service reliability is {reliability:.1f}%.",
                        ["DEPARTMENT_ACADEMY", "SELF_REVIEW"], validated,
                        min(88.0, 42.0 + max(0.0, 65.0 - reliability) * 1.1 + validated),
                        signature=(validated, reliability, status),
                    ))
                if status in {"STRONG_PERFORMANCE", "STABLE_PERFORMANCE"} and validated >= 5 and accuracy is not None and accuracy >= 55.0:
                    output.append(self._candidate(
                        branch, "PRESERVE_VALIDATED_BEHAVIOUR",
                        "Preserve the current evidence process unchanged while live validation continues.",
                        f"{status}: {accuracy:.1f}% accuracy across {validated} validated sample(s).",
                        ["SELF_REVIEW", "SERVICE_BOOK"], validated,
                        min(90.0, 35.0 + accuracy * 0.45 + validated * 1.2),
                        signature=(validated, accuracy, reliability, status),
                    ))

        profiles = promotion_board.get("officer_profiles", [])
        if isinstance(profiles, Sequence) and not isinstance(profiles, (str, bytes)):
            for item in profiles:
                if not isinstance(item, Mapping):
                    continue
                branch = str(item.get("branch", "UNKNOWN")).upper()
                # Do not allow the Learning, Self Review, or Personnel Board
                # branches to generate circular recommendations about themselves.
                if branch in {"LEARNING", "SELF_REVIEW", "PROMOTION_BOARD"}:
                    continue
                validated = self._integer(item.get("validated_cases", 0))
                for plan in list(item.get("training_plan", []) or [])[:4]:
                    plan_name = str(plan).upper()
                    # Evidence collection is a status, not an improvement rule.
                    # True Learning waits for validated outcomes before creating
                    # a department-change hypothesis.
                    if plan_name in {"CONTINUE_VALIDATED_LIVE_SERVICE", "LIVE_CASE_COLLECTION"} or validated < 3:
                        continue
                    mapping = {
                        "LIVE_CASE_COLLECTION": ("LIVE_CASE_COLLECTION", "Collect more completed live cases before forming a learning conclusion."),
                        "SOP_DISCIPLINE_REFRESH": ("SOP_AND_CONSISTENCY_REVIEW", "Review missing SOP facts and reporting discipline."),
                        "CONSISTENCY_AND_STABILITY_TRAINING": ("SOP_AND_CONSISTENCY_REVIEW", "Review observation stability and contradictory state changes."),
                        "PREDICTION_VS_REALITY_REVIEW": ("DIRECTION_EVIDENCE_REVIEW", "Compare department evidence with later verified market reality."),
                        "CONFIDENCE_CALIBRATION": ("CONFIDENCE_CALIBRATION_REVIEW", "Review confidence calibration on wrong high-confidence cases."),
                        "CROSS_DEPARTMENT_CONTRADICTION_REVIEW": ("CROSS_DEPARTMENT_CONFLICT_REVIEW", "Review recurring contradictions with other departments."),
                    }
                    rec_type, text = mapping.get(plan_name, ("MANUAL_TRAINING_REVIEW", f"Review training item: {plan_name}."))
                    output.append(self._candidate(
                        branch, rec_type, text,
                        str(item.get("review_reason", "Personnel Board review evidence."))[:260],
                        ["PROMOTION_BOARD", "SERVICE_BOOK"], validated,
                        max(35.0, min(88.0, self._number(item.get("competency_score", 0)) + 18.0)),
                        signature=(validated, plan_name, item.get("board_recommendation"), item.get("competency_score")),
                    ))

        completed = self._integer(experience.get("completed_cases", 0))
        mistakes = list(experience.get("dominant_mistakes", []) or [])
        for value in mistakes[:5]:
            text = str(value).upper()
            count = self._count_from_text(text)
            if "HIGH_CONFIDENCE_WRONG_DIRECTION" in text:
                output.append(self._candidate(
                    "AI_MASTER", "CONFIDENCE_CALIBRATION_REVIEW",
                    "Review final confidence calibration when high-confidence direction failed.",
                    str(value), ["EXPERIENCE", "AI_MASTER_OUTCOME"], completed,
                    min(95.0, 50.0 + count * 10.0 + completed * 0.8), signature=(completed, text),
                ))
            elif "RANGE_ASSUMPTION_FAILED" in text:
                output.append(self._candidate(
                    "STRATEGY", "RANGE_BREAKOUT_EVIDENCE_REVIEW",
                    "Review breakout, news, option expansion, and barrier evidence before future range cases.",
                    str(value), ["EXPERIENCE", "MARKET_BEHAVIOUR", "NEWS_INTELLIGENCE"], completed,
                    min(92.0, 46.0 + count * 9.0 + completed * 0.7), signature=(completed, text),
                ))
            elif "DIRECTIONAL_THESIS_FAILED" in text:
                output.append(self._candidate(
                    "STRATEGY", "CROSS_DEPARTMENT_CONFIRMATION_REVIEW",
                    "Review price, option, heavyweight, and institutional confirmation before directional approval.",
                    str(value), ["EXPERIENCE", "PRICE_ACTION", "OPTION", "HEAVYWEIGHT_INTELLIGENCE", "SMART_MONEY"], completed,
                    min(92.0, 44.0 + count * 9.0 + completed * 0.7), signature=(completed, text),
                ))
            elif "MISSED_DIRECTIONAL_MOVE_REVIEW" in text:
                output.append(self._candidate(
                    "STRATEGY", "EXCESSIVE_CAUTION_REVIEW",
                    "Review whether incomplete evidence or excessive caution caused repeated missed moves.",
                    str(value), ["EXPERIENCE", "TIME_INTELLIGENCE", "CANDIDATE"], completed,
                    min(88.0, 40.0 + count * 8.0 + completed * 0.6), signature=(completed, text),
                ))
            elif "ENTRY_TIMING_VOLATILITY_REVIEW" in text:
                output.append(self._candidate(
                    "CANDIDATE", "ENTRY_TIMING_REVIEW",
                    "Review entry timing, adverse excursion, and barrier distance before execution approval.",
                    str(value), ["EXPERIENCE", "TIME_INTELLIGENCE", "RISK"], completed,
                    min(88.0, 42.0 + count * 8.0 + completed * 0.6), signature=(completed, text),
                ))

        # Deduplicate candidates in the current run; strongest evidence wins.
        dedup: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for item in output:
            key = (str(item["branch"]), str(item["recommendation_type"]))
            if key not in dedup or self._number(item.get("evidence_score", 0)) > self._number(dedup[key].get("evidence_score", 0)):
                dedup[key] = item
        return list(dedup.values())

    def _candidate(
        self,
        branch: str,
        recommendation_type: str,
        recommendation: str,
        reason: str,
        sources: Sequence[str],
        validated_samples: int,
        evidence_score: float,
        *,
        signature: Sequence[Any],
    ) -> Dict[str, Any]:
        branch = str(branch or "SYSTEM").upper()
        recommendation_type = str(recommendation_type).upper()
        raw = f"{branch}|{recommendation_type}".encode("utf-8")
        recommendation_id = "LRN-" + hashlib.sha1(raw).hexdigest()[:10].upper()
        evidence_signature = hashlib.sha1(repr(tuple(signature)).encode("utf-8")).hexdigest()[:16]
        return {
            "recommendation_id": recommendation_id,
            "branch": branch,
            "recommendation_type": recommendation_type,
            "recommendation": str(recommendation)[:320],
            "reason": str(reason)[:320],
            "evidence_sources": list(dict.fromkeys(str(item) for item in sources))[:8],
            "validated_samples": max(0, int(validated_samples)),
            "evidence_score": round(self._clamp(evidence_score), 1),
            "evidence_signature": evidence_signature,
        }

    def _merge_candidate(
        self,
        registry: Dict[str, Dict[str, Any]],
        candidate: Dict[str, Any],
        *,
        snapshot_id: str,
        observed_at: datetime,
    ) -> Dict[str, Any]:
        recommendation_id = str(candidate["recommendation_id"])
        old = dict(registry.get(recommendation_id, {}))
        first_seen = str(old.get("first_seen_at") or observed_at.isoformat(timespec="seconds"))
        old_signature = str(old.get("last_evidence_signature", ""))
        new_signature = str(candidate.get("evidence_signature", ""))
        occurrences = max(0, self._integer(old.get("occurrences", 0)))
        if not old or old_signature != new_signature:
            occurrences += 1
        validated = max(self._integer(old.get("validated_samples", 0)), self._integer(candidate.get("validated_samples", 0)))
        evidence_score = max(self._number(old.get("evidence_score", 0)), self._number(candidate.get("evidence_score", 0)))
        status = self._status(
            recommendation_type=str(candidate.get("recommendation_type", "")),
            validated_samples=validated,
            evidence_score=evidence_score,
            occurrences=occurrences,
        )
        return {
            **candidate,
            "validated_samples": validated,
            "evidence_score": round(evidence_score, 1),
            "occurrences": occurrences,
            "status": status,
            "first_seen_at": first_seen,
            "last_seen_at": observed_at.isoformat(timespec="seconds"),
            "last_snapshot_id": snapshot_id,
            "last_evidence_signature": new_signature,
            "manual_review_required": True,
            "auto_apply": False,
        }

    @staticmethod
    def _status(*, recommendation_type: str, validated_samples: int, evidence_score: float, occurrences: int) -> str:
        if recommendation_type == "PRESERVE_VALIDATED_BEHAVIOUR":
            return "PRESERVE_OBSERVATION" if validated_samples >= 5 and evidence_score >= 55 else "COLLECTING_EVIDENCE"
        if validated_samples >= 10 and evidence_score >= 70 and occurrences >= 2:
            return "AI_MASTER_REVIEW_READY"
        if validated_samples >= 3 and evidence_score >= 52:
            return "MANUAL_REVIEW_CANDIDATE"
        return "COLLECTING_EVIDENCE"

    def _registry(self, state: MutableMapping[str, Any]) -> Dict[str, Dict[str, Any]]:
        value = state.get(self.RECOMMENDATION_KEY, {})
        if not isinstance(value, Mapping):
            return {}
        return {str(key): dict(item) for key, item in value.items() if isinstance(item, Mapping)}

    @staticmethod
    def _to_recommendation(item: Mapping[str, Any]) -> ImprovementRecommendation:
        return ImprovementRecommendation(
            recommendation_id=str(item.get("recommendation_id", "UNKNOWN")),
            branch=str(item.get("branch", "SYSTEM")),
            recommendation_type=str(item.get("recommendation_type", "MANUAL_REVIEW")),
            recommendation=str(item.get("recommendation", "Review evidence manually."))[:320],
            reason=str(item.get("reason", "Evidence collecting."))[:320],
            evidence_sources=[str(value) for value in list(item.get("evidence_sources", []) or [])[:8]],
            validated_samples=max(0, LearningDepartment._integer(item.get("validated_samples", 0))),
            evidence_score=round(LearningDepartment._clamp(LearningDepartment._number(item.get("evidence_score", 0))), 1),
            occurrences=max(0, LearningDepartment._integer(item.get("occurrences", 0))),
            status=str(item.get("status", "COLLECTING_EVIDENCE")),
            first_seen_at=str(item.get("first_seen_at", "")),
            last_seen_at=str(item.get("last_seen_at", "")),
            manual_review_required=True,
        )

    def _archive_final(self, state: MutableMapping[str, Any], report: TrueLearningReport) -> None:
        archive = state.get(self.ARCHIVE_KEY, {})
        archive = dict(archive) if isinstance(archive, Mapping) else {}
        archive[report.review_date] = {
            "learning_state": report.learning_state,
            "completed_cases_seen": report.completed_cases_seen,
            "recommendations_count": report.recommendations_count,
            "review_ready_count": report.review_ready_count,
            "priority_recommendations": list(report.priority_recommendations),
            "confidence": report.confidence,
        }
        keys = sorted(archive)[-self.MAX_ARCHIVE_DAYS:]
        state[self.ARCHIVE_KEY] = {key: archive[key] for key in keys}

    @staticmethod
    def _status_order(value: str) -> int:
        return {
            "AI_MASTER_REVIEW_READY": 0,
            "MANUAL_REVIEW_CANDIDATE": 1,
            "PRESERVE_OBSERVATION": 2,
            "COLLECTING_EVIDENCE": 3,
        }.get(value, 9)

    @staticmethod
    def _count_from_text(value: str) -> int:
        for token in str(value).replace(":", " ").split():
            try:
                return max(1, int(token))
            except ValueError:
                continue
        return 1

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        text = str(value or "").strip()
        if text:
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now()

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))
