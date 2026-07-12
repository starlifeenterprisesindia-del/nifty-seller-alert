"""
self_review.py
Version: V44.3
Role: Session-bounded AI self review and department performance evidence.

Architecture and safety:
- Reviews only completed Experience Engine cases and department snapshots.
- Produces provisional live review and evening/final session review.
- Sends one neutral information-only report to CO.
- Never changes thresholds, weights, SOPs, promotions, demotions, or trade rules.
- Never issues BUY / SELL CE / SELL PE / IRON CONDOR / WAIT instructions.
- No API calls, threads, timers, or background jobs.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence


@dataclass(frozen=True)
class DepartmentReview:
    branch: str
    boss: str
    validated_samples: int
    supported_cases: int
    contradicted_cases: int
    unscored_cases: int
    accuracy: Optional[float]
    high_confidence_wrong: int
    average_confidence: float
    sop_reliability: float
    performance_status: str
    review_note: str
    recommendation: str


@dataclass(frozen=True)
class SelfReviewReport:
    snapshot_id: str
    review_date: str
    review_scope: str
    review_state: str
    completed_cases_reviewed: int
    daily_completed_cases: int
    newly_completed_cases: int
    scored_department_observations: int
    department_reviews: List[DepartmentReview] = field(default_factory=list)
    top_performers: List[str] = field(default_factory=list)
    stable_departments: List[str] = field(default_factory=list)
    review_required: List[str] = field(default_factory=list)
    retraining_recommended: List[str] = field(default_factory=list)
    dominant_mistakes: List[str] = field(default_factory=list)
    lessons: List[str] = field(default_factory=list)
    next_recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "review_date": self.review_date,
            "review_scope": self.review_scope,
            "review_state": self.review_state,
            "completed_cases_reviewed": self.completed_cases_reviewed,
            "daily_completed_cases": self.daily_completed_cases,
            "newly_completed_cases": self.newly_completed_cases,
            "scored_department_observations": self.scored_department_observations,
            "department_reviews": [asdict(item) for item in self.department_reviews],
            "top_performers": list(self.top_performers),
            "stable_departments": list(self.stable_departments),
            "review_required": list(self.review_required),
            "retraining_recommended": list(self.retraining_recommended),
            "dominant_mistakes": list(self.dominant_mistakes),
            "lessons": list(self.lessons),
            "next_recommendations": list(self.next_recommendations),
            "confidence": self.confidence,
            "warnings": list(self.warnings),
            "authority": "DSP_SELF_REVIEW_TO_CO_INFORMATION_ONLY",
            "execution_instruction": "NONE",
            "automatic_rule_change": False,
            "automatic_retraining": False,
            "automatic_promotion_or_demotion": False,
            "storage_scope": "BOUNDED_STREAMLIT_SESSION",
        }

    def to_department_report(self) -> Dict[str, Any]:
        details = self.to_compact_dict()
        details["department_reviews"] = details["department_reviews"][:16]
        return {
            "summary": (
                f"{self.review_state} | reviewed {self.completed_cases_reviewed} completed case(s), "
                f"{len(self.review_required)} review branch(es), "
                f"{len(self.retraining_recommended)} retraining recommendation(s)"
            )[:300],
            "confidence": self.confidence,
            "details": details,
            "recommendation": "INFORMATION_ONLY",
            "branch_vote": "NEUTRAL",
            "execution_instruction": "NONE",
        }


class SelfReviewEngine:
    """One-shot review of validated Experience Engine outcomes."""

    EXPERIENCE_KEY = "v43_experience_records"
    SERVICE_BOOK_KEY = "v29_branch_service_book"
    DAILY_ARCHIVE_KEY = "v44_self_review_daily_archive"
    MAX_COMPLETED_CASES = 160
    MAX_ARCHIVE_DAYS = 10

    BOSS_NAMES = {
        "DATA": "DSP Data Intelligence",
        "OPTION": "DSP Option Intelligence",
        "PRICE_ACTION": "DSP Price Action",
        "MARKET_BEHAVIOUR": "DSP Market Behaviour",
        "MARKET_PSYCHOLOGY": "DSP Market Psychology",
        "TIME_INTELLIGENCE": "DSP Time Intelligence",
        "MARKET_JOURNEY": "DSP Move & Barrier Intelligence",
        "HEAVYWEIGHT_INTELLIGENCE": "DSP Heavyweight Intelligence",
        "NEWS_INTELLIGENCE": "DSP News Intelligence",
        "SMART_MONEY": "DSP Smart Money / Institutional Behaviour",
        "EXPERIENCE": "DSP Experience & Validation",
        "RISK": "DSP Risk",
        "STRATEGY": "DSP Strategy",
        "CANDIDATE": "DSP Candidate",
    }

    def evaluate(
        self,
        *,
        state: MutableMapping[str, Any],
        snapshot_id: str,
        observed_at: Any,
        market_open: bool,
        newly_completed: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> SelfReviewReport:
        now = self._parse_datetime(observed_at)
        review_date = now.date().isoformat()
        final_scope = (not bool(market_open)) or (now.hour, now.minute) >= (15, 30)
        review_scope = "EVENING_FINAL" if final_scope else "LIVE_PROVISIONAL"

        raw_records = state.get(self.EXPERIENCE_KEY, [])
        records = [item for item in raw_records if isinstance(item, Mapping)] if isinstance(raw_records, list) else []
        completed = [item for item in records if str(item.get("status", "")).upper() == "COMPLETED"][-self.MAX_COMPLETED_CASES:]
        daily_completed = [
            item for item in completed
            if str(item.get("completed_at", item.get("created_at", "")))[:10] == review_date
        ]

        reviews = self._department_reviews(state, completed)
        scored_observations = sum(item.validated_samples for item in reviews)

        top = [item.branch for item in reviews if item.performance_status == "STRONG_PERFORMANCE"]
        stable = [item.branch for item in reviews if item.performance_status == "STABLE_PERFORMANCE"]
        review_required = [item.branch for item in reviews if item.performance_status in {"REVIEW_REQUIRED", "MIXED_PERFORMANCE"}]
        retraining = [item.branch for item in reviews if item.performance_status == "RETRAINING_RECOMMENDED"]

        mistakes = self._dominant_mistakes(completed)
        lessons = self._lessons(completed, reviews)
        recommendations = self._recommendations(reviews, mistakes)
        new_count = len(list(newly_completed or []))

        if not completed:
            review_state = "COLLECTING_COMPLETED_CASES"
        elif retraining:
            review_state = "RETRAINING_REVIEW_REQUIRED" if final_scope else "PROVISIONAL_RETRAINING_WATCH"
        elif review_required:
            review_state = "DEPARTMENT_REVIEW_REQUIRED" if final_scope else "PROVISIONAL_DEPARTMENT_REVIEW"
        elif final_scope:
            review_state = "EVENING_REVIEW_READY"
        else:
            review_state = "PROVISIONAL_LIVE_REVIEW"

        warnings: List[str] = []
        if len(completed) < 10:
            warnings.append("Fewer than 10 completed cases; department ranking is provisional.")
        if not any(item.validated_samples >= 3 for item in reviews):
            warnings.append("No department has three validated directional samples yet.")
        if not final_scope:
            warnings.append("Live review is provisional; evening review should be read after market close.")
        warnings.append("Self Review cannot change production rules, thresholds, promotions, or training automatically.")
        warnings.append("Session-bounded review history may reset after app restart or redeploy.")

        confidence = min(
            92.0,
            18.0
            + min(len(completed), 40) * 1.25
            + min(scored_observations, 80) * 0.35
            + (8.0 if final_scope else 0.0),
        )

        report = SelfReviewReport(
            snapshot_id=str(snapshot_id or "UNKNOWN"),
            review_date=review_date,
            review_scope=review_scope,
            review_state=review_state,
            completed_cases_reviewed=len(completed),
            daily_completed_cases=len(daily_completed),
            newly_completed_cases=new_count,
            scored_department_observations=scored_observations,
            department_reviews=reviews,
            top_performers=top[:5],
            stable_departments=stable[:8],
            review_required=review_required[:8],
            retraining_recommended=retraining[:8],
            dominant_mistakes=mistakes[:5],
            lessons=lessons[:6],
            next_recommendations=recommendations[:6],
            confidence=round(confidence, 1),
            warnings=warnings[:5],
        )
        if final_scope:
            self._archive_final(state, report)
        return report

    def _department_reviews(
        self,
        state: Mapping[str, Any],
        completed: Sequence[Mapping[str, Any]],
    ) -> List[DepartmentReview]:
        aggregate: Dict[str, Dict[str, Any]] = {}
        for record in completed:
            reality = str(record.get("reality", "UNKNOWN")).upper()
            snapshots = record.get("department_snapshot", {})
            if not isinstance(snapshots, Mapping):
                continue
            for branch, item in snapshots.items():
                if branch == "SELF_REVIEW" or not isinstance(item, Mapping):
                    continue
                row = aggregate.setdefault(str(branch), {
                    "supported": 0,
                    "contradicted": 0,
                    "unscored": 0,
                    "confidence_total": 0.0,
                    "confidence_count": 0,
                    "high_conf_wrong": 0,
                })
                direction = str(item.get("direction", "NEUTRAL")).upper()
                confidence = self._number(item.get("confidence", 0.0))
                verdict = self._verdict(direction, reality)
                if verdict == "SUPPORTED":
                    row["supported"] += 1
                elif verdict == "CONTRADICTED":
                    row["contradicted"] += 1
                    if confidence >= 70:
                        row["high_conf_wrong"] += 1
                else:
                    row["unscored"] += 1
                if direction in {"BULLISH", "BEARISH", "NEUTRAL"}:
                    row["confidence_total"] += confidence
                    row["confidence_count"] += 1

        service_books = state.get(self.SERVICE_BOOK_KEY, {})
        service_books = service_books if isinstance(service_books, Mapping) else {}
        branches = sorted(set(self.BOSS_NAMES) | set(aggregate))
        reviews: List[DepartmentReview] = []
        for branch in branches:
            row = aggregate.get(branch, {})
            supported = int(row.get("supported", 0) or 0)
            contradicted = int(row.get("contradicted", 0) or 0)
            unscored = int(row.get("unscored", 0) or 0)
            validated = supported + contradicted
            accuracy = round(supported / validated * 100.0, 1) if validated else None
            avg_conf = (
                float(row.get("confidence_total", 0.0) or 0.0)
                / max(1, int(row.get("confidence_count", 0) or 0))
            )
            book = service_books.get(branch, {})
            reliability = self._number(book.get("reliability_score", 0.0)) if isinstance(book, Mapping) else 0.0
            high_wrong = int(row.get("high_conf_wrong", 0) or 0)
            status = self._performance_status(validated, accuracy, high_wrong, reliability)
            note, recommendation = self._review_text(branch, status, validated, accuracy, high_wrong)
            reviews.append(DepartmentReview(
                branch=branch,
                boss=self.BOSS_NAMES.get(branch, f"DSP {branch.title()}"),
                validated_samples=validated,
                supported_cases=supported,
                contradicted_cases=contradicted,
                unscored_cases=unscored,
                accuracy=accuracy,
                high_confidence_wrong=high_wrong,
                average_confidence=round(avg_conf, 1),
                sop_reliability=round(reliability, 1),
                performance_status=status,
                review_note=note,
                recommendation=recommendation,
            ))
        order = {
            "RETRAINING_RECOMMENDED": 0,
            "REVIEW_REQUIRED": 1,
            "MIXED_PERFORMANCE": 2,
            "COLLECTING_EVIDENCE": 3,
            "STABLE_PERFORMANCE": 4,
            "STRONG_PERFORMANCE": 5,
        }
        return sorted(reviews, key=lambda item: (order.get(item.performance_status, 9), -item.validated_samples, item.branch))

    @staticmethod
    def _verdict(direction: str, reality: str) -> str:
        if reality == "UP_MOVE":
            return "SUPPORTED" if direction == "BULLISH" else "CONTRADICTED" if direction == "BEARISH" else "UNSCORED"
        if reality == "DOWN_MOVE":
            return "SUPPORTED" if direction == "BEARISH" else "CONTRADICTED" if direction == "BULLISH" else "UNSCORED"
        if reality == "RANGE_OR_NO_FOLLOW_THROUGH":
            return "SUPPORTED" if direction == "NEUTRAL" else "CONTRADICTED" if direction in {"BULLISH", "BEARISH"} else "UNSCORED"
        return "UNSCORED"

    @staticmethod
    def _performance_status(
        validated: int,
        accuracy: Optional[float],
        high_wrong: int,
        reliability: float,
    ) -> str:
        if validated < 3 or accuracy is None:
            return "COLLECTING_EVIDENCE"
        if validated >= 5 and (accuracy < 40.0 or high_wrong >= 3):
            return "RETRAINING_RECOMMENDED"
        if accuracy < 50.0 or high_wrong >= 2:
            return "REVIEW_REQUIRED"
        if accuracy >= 70.0 and validated >= 5 and reliability >= 60.0:
            return "STRONG_PERFORMANCE"
        if accuracy >= 55.0:
            return "STABLE_PERFORMANCE"
        return "MIXED_PERFORMANCE"

    @staticmethod
    def _review_text(
        branch: str,
        status: str,
        validated: int,
        accuracy: Optional[float],
        high_wrong: int,
    ) -> tuple[str, str]:
        accuracy_text = "NA" if accuracy is None else f"{accuracy:.1f}%"
        if status == "RETRAINING_RECOMMENDED":
            return (
                f"{validated} validated samples, accuracy {accuracy_text}, high-confidence wrong {high_wrong}.",
                "Recommend manual retraining review; no automatic rule or weight change.",
            )
        if status == "REVIEW_REQUIRED":
            return (
                f"Mixed validated performance: {validated} samples, accuracy {accuracy_text}.",
                "Review contradictions and confidence calibration before any future change.",
            )
        if status == "STRONG_PERFORMANCE":
            return (
                f"Repeated validated support with {validated} samples and {accuracy_text} accuracy.",
                "Retain as evidence; do not promote or re-weight automatically.",
            )
        if status == "STABLE_PERFORMANCE":
            return (
                f"Stable validated support across {validated} samples at {accuracy_text} accuracy.",
                "Continue live validation with unchanged production rules.",
            )
        if status == "MIXED_PERFORMANCE":
            return (
                f"Performance is mixed across {validated} validated samples at {accuracy_text} accuracy.",
                "Collect more cases and inspect conflicting departments.",
            )
        return (
            f"Only {validated} validated directional sample(s) available.",
            "Collect more completed cases before judging department performance.",
        )

    @staticmethod
    def _dominant_mistakes(completed: Sequence[Mapping[str, Any]]) -> List[str]:
        counts = Counter(
            str(item.get("mistake", "NONE_IDENTIFIED"))
            for item in completed
            if str(item.get("mistake", "")) not in {"", "NO_MATERIAL_MISTAKE", "NO_MISTAKE_VALIDATED", "PENDING_VALIDATION"}
        )
        return [f"{name}: {count} case(s)" for name, count in counts.most_common(5)]

    @staticmethod
    def _lessons(
        completed: Sequence[Mapping[str, Any]],
        reviews: Sequence[DepartmentReview],
    ) -> List[str]:
        lessons: List[str] = []
        for item in reversed(completed):
            lesson = str(item.get("lesson", "")).strip()
            if lesson and lesson not in lessons:
                lessons.append(lesson)
            if len(lessons) >= 4:
                break
        if any(item.high_confidence_wrong >= 2 for item in reviews):
            lessons.append("Repeated high-confidence contradictions require calibration review, not automatic threshold changes.")
        if not lessons:
            lessons.append("Completed-case lessons are still being collected.")
        return lessons

    @staticmethod
    def _recommendations(
        reviews: Sequence[DepartmentReview],
        mistakes: Sequence[str],
    ) -> List[str]:
        output: List[str] = []
        for item in reviews:
            if item.performance_status in {"RETRAINING_RECOMMENDED", "REVIEW_REQUIRED"}:
                output.append(f"{item.branch}: {item.recommendation}")
            if len(output) >= 4:
                break
        if mistakes:
            output.append("CO should compare dominant mistakes with price, option, timing, news, and institutional conflicts.")
        output.append("Keep all production rules unchanged until live validation sample size is sufficient.")
        return output

    def _archive_final(self, state: MutableMapping[str, Any], report: SelfReviewReport) -> None:
        archive = state.get(self.DAILY_ARCHIVE_KEY, {})
        archive = dict(archive) if isinstance(archive, Mapping) else {}
        archive[report.review_date] = {
            "review_state": report.review_state,
            "completed_cases_reviewed": report.completed_cases_reviewed,
            "daily_completed_cases": report.daily_completed_cases,
            "top_performers": list(report.top_performers),
            "review_required": list(report.review_required),
            "retraining_recommended": list(report.retraining_recommended),
            "dominant_mistakes": list(report.dominant_mistakes),
            "confidence": report.confidence,
        }
        keys = sorted(archive)[-self.MAX_ARCHIVE_DAYS:]
        state[self.DAILY_ARCHIVE_KEY] = {key: archive[key] for key in keys}

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
