"""
promotion_system.py
Version: V45.3
Role: Bounded personnel/service-board recommendations for AI departments.

Architecture and safety:
- Reads Department Academy service books and V44 completed-case self review.
- Produces experience, reliability, accuracy, SOP discipline, competency grade,
  promotion eligibility, demotion/probation review, and training recommendations.
- Command rank is never changed automatically. Grades are Academy competency
  recommendations only and do not replace DSP branch bosses in the hierarchy.
- Never changes AI weights, thresholds, SOPs, training status, or trade rules.
- Never issues BUY / SELL CE / SELL PE / IRON CONDOR / WAIT instructions.
- No API calls, threads, timers, or background jobs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence


GRADE_ORDER = ("RECRUIT", "HC", "ASI", "SI", "INSPECTOR", "DSP")
GRADE_INDEX = {name: index for index, name in enumerate(GRADE_ORDER)}


@dataclass(frozen=True)
class OfficerServiceProfile:
    branch: str
    boss: str
    current_grade: str
    recommended_grade: str
    observations: int
    validated_cases: int
    experience_score: float
    reliability_score: float
    accuracy: Optional[float]
    sop_pass_rate: float
    high_confidence_wrong: int
    competency_score: float
    evidence_maturity: str
    performance_status: str
    board_recommendation: str
    training_plan: List[str] = field(default_factory=list)
    review_reason: str = ""


@dataclass(frozen=True)
class PromotionBoardReport:
    snapshot_id: str
    review_date: str
    review_scope: str
    board_state: str
    officers_reviewed: int
    promotion_eligible: List[str] = field(default_factory=list)
    retain_current_grade: List[str] = field(default_factory=list)
    training_required: List[str] = field(default_factory=list)
    probation_review: List[str] = field(default_factory=list)
    demotion_review: List[str] = field(default_factory=list)
    collecting_evidence: List[str] = field(default_factory=list)
    top_service_records: List[str] = field(default_factory=list)
    officer_profiles: List[OfficerServiceProfile] = field(default_factory=list)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "review_date": self.review_date,
            "review_scope": self.review_scope,
            "board_state": self.board_state,
            "officers_reviewed": self.officers_reviewed,
            "promotion_eligible": list(self.promotion_eligible),
            "retain_current_grade": list(self.retain_current_grade),
            "training_required": list(self.training_required),
            "probation_review": list(self.probation_review),
            "demotion_review": list(self.demotion_review),
            "collecting_evidence": list(self.collecting_evidence),
            "top_service_records": list(self.top_service_records),
            "officer_profiles": [asdict(item) for item in self.officer_profiles],
            "confidence": self.confidence,
            "warnings": list(self.warnings),
            "authority": "DSP_PERSONNEL_BOARD_TO_CO_INFORMATION_ONLY",
            "execution_instruction": "NONE",
            "automatic_promotion": False,
            "automatic_demotion": False,
            "automatic_training": False,
            "automatic_rule_change": False,
            "automatic_weight_change": False,
            "grade_scope": "ACADEMY_COMPETENCY_GRADE_ONLY",
            "storage_scope": "BOUNDED_STREAMLIT_SESSION",
        }

    def to_department_report(self) -> Dict[str, Any]:
        details = self.to_compact_dict()
        details["officer_profiles"] = details["officer_profiles"][:18]
        return {
            "summary": (
                f"{self.board_state} | {self.officers_reviewed} service profile(s), "
                f"{len(self.promotion_eligible)} promotion review, "
                f"{len(self.training_required) + len(self.probation_review)} training/probation review"
            )[:300],
            "confidence": self.confidence,
            "details": details,
            "recommendation": "INFORMATION_ONLY",
            "branch_vote": "NEUTRAL",
            "execution_instruction": "NONE",
        }


class PromotionSystem:
    """One-shot personnel board based only on validated service evidence."""

    SERVICE_BOOK_KEY = "v29_branch_service_book"
    PROFILE_KEY = "v45_officer_service_profiles"
    ARCHIVE_KEY = "v45_promotion_board_archive"
    MAX_ARCHIVE_DAYS = 10

    BOSSES = {
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
        "SELF_REVIEW": "DSP AI Self Review",
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
        self_review: Optional[Mapping[str, Any]] = None,
    ) -> PromotionBoardReport:
        now = self._parse_datetime(observed_at)
        review_date = now.date().isoformat()
        final_scope = (not bool(market_open)) or (now.hour, now.minute) >= (15, 30)
        review_scope = "EVENING_BOARD" if final_scope else "LIVE_PROVISIONAL_BOARD"

        service_books = state.get(self.SERVICE_BOOK_KEY, {})
        service_books = service_books if isinstance(service_books, Mapping) else {}
        review_map = self._review_map(self_review or {})
        stored_profiles = state.get(self.PROFILE_KEY, {})
        stored_profiles = stored_profiles if isinstance(stored_profiles, Mapping) else {}

        branches = sorted((set(self.BOSSES) | set(service_books) | set(review_map)) - {"PROMOTION_BOARD"})
        profiles: List[OfficerServiceProfile] = []
        next_storage: Dict[str, Dict[str, Any]] = {
            str(key): dict(value) for key, value in stored_profiles.items() if isinstance(value, Mapping)
        }

        for branch in branches:
            book = service_books.get(branch, {})
            book = book if isinstance(book, Mapping) else {}
            review = review_map.get(branch, {})
            review = review if isinstance(review, Mapping) else {}
            old = stored_profiles.get(branch, {})
            old = old if isinstance(old, Mapping) else {}

            current_grade = self._valid_grade(old.get("current_grade", book.get("approved_grade", "RECRUIT")))
            profile = self._profile(branch, current_grade, book, review)
            profiles.append(profile)
            # Current grade is deliberately preserved. Only the board recommendation
            # and evidence summary are refreshed; nothing is auto-applied.
            next_storage[branch] = {
                "branch": branch,
                "current_grade": current_grade,
                "last_recommended_grade": profile.recommended_grade,
                "last_board_recommendation": profile.board_recommendation,
                "last_competency_score": profile.competency_score,
                "last_reviewed_at": now.isoformat(timespec="seconds"),
                "manual_approval_required": True,
            }

        state[self.PROFILE_KEY] = next_storage
        profiles = sorted(
            profiles,
            key=lambda item: (
                self._recommendation_order(item.board_recommendation),
                -item.competency_score,
                -item.validated_cases,
                item.branch,
            ),
        )

        promotion = [item.branch for item in profiles if item.board_recommendation == "PROMOTION_ELIGIBLE_REVIEW"]
        retain = [item.branch for item in profiles if item.board_recommendation == "RETAIN_CURRENT_GRADE"]
        training = [item.branch for item in profiles if item.board_recommendation == "TRAINING_REQUIRED"]
        probation = [item.branch for item in profiles if item.board_recommendation == "PROBATION_REVIEW"]
        demotion = [item.branch for item in profiles if item.board_recommendation == "DEMOTION_REVIEW_REQUIRED"]
        collecting = [item.branch for item in profiles if item.board_recommendation == "COLLECTING_EVIDENCE"]

        mature = [item for item in profiles if item.validated_cases >= 5 and item.observations >= 8]
        top = [
            f"{item.branch}: {item.competency_score:.1f}/100, {item.recommended_grade} review"
            for item in sorted(mature, key=lambda row: (-row.competency_score, -row.validated_cases, row.branch))[:5]
        ]

        if demotion:
            board_state = "DEMOTION_REVIEW_REQUIRED"
        elif probation:
            board_state = "PROBATION_AND_TRAINING_REVIEW"
        elif training:
            board_state = "TRAINING_REVIEW_REQUIRED"
        elif promotion:
            board_state = "PROMOTION_REVIEW_AVAILABLE"
        elif profiles and len(collecting) == len(profiles):
            board_state = "COLLECTING_SERVICE_EVIDENCE"
        else:
            board_state = "SERVICE_RECORDS_STABLE"

        mature_count = sum(item.evidence_maturity in {"VALIDATED", "MATURE"} for item in profiles)
        total_validated = sum(item.validated_cases for item in profiles)
        confidence = min(94.0, 20.0 + mature_count * 3.0 + min(total_validated, 80) * 0.45 + (8.0 if final_scope else 0.0))

        warnings: List[str] = []
        if not profiles:
            warnings.append("No department service records available yet.")
        if total_validated < 10:
            warnings.append("Fewer than 10 total validated department cases; board recommendations are provisional.")
        if not final_scope:
            warnings.append("Live personnel board is provisional; evening board is preferred for review.")
        warnings.append("Competency grades do not replace command ranks or DSP branch authority.")
        warnings.append("Promotion, demotion, training, rules, and weights require manual approval and live validation.")
        warnings.append("Session-bounded personnel records may reset after app restart or redeploy.")

        report = PromotionBoardReport(
            snapshot_id=str(snapshot_id or "UNKNOWN"),
            review_date=review_date,
            review_scope=review_scope,
            board_state=board_state,
            officers_reviewed=len(profiles),
            promotion_eligible=promotion[:10],
            retain_current_grade=retain[:10],
            training_required=training[:10],
            probation_review=probation[:10],
            demotion_review=demotion[:10],
            collecting_evidence=collecting[:12],
            top_service_records=top,
            officer_profiles=profiles[:18],
            confidence=round(confidence, 1),
            warnings=warnings[:6],
        )
        if final_scope:
            self._archive_final(state, report)
        return report

    def _profile(
        self,
        branch: str,
        current_grade: str,
        book: Mapping[str, Any],
        review: Mapping[str, Any],
    ) -> OfficerServiceProfile:
        observations = max(0, self._integer(book.get("observations", 0)))
        sop_passes = max(0, self._integer(book.get("sop_passes", 0)))
        sop_rate = min(100.0, sop_passes / max(1, observations) * 100.0) if observations else 0.0
        reliability = self._clamp(self._number(book.get("reliability_score", 0.0)))
        validated = max(0, self._integer(review.get("validated_samples", 0)))
        accuracy_raw = review.get("accuracy")
        accuracy = self._clamp(self._number(accuracy_raw)) if accuracy_raw is not None else None
        high_wrong = max(0, self._integer(review.get("high_confidence_wrong", 0)))
        performance_status = str(review.get("performance_status", "COLLECTING_EVIDENCE"))

        experience_score = min(100.0, observations * 1.6 + validated * 5.0)
        if validated >= 12 and observations >= 25:
            maturity = "MATURE"
        elif validated >= 5 and observations >= 10:
            maturity = "VALIDATED"
        elif validated >= 3 or observations >= 5:
            maturity = "DEVELOPING"
        else:
            maturity = "COLLECTING"

        accuracy_component = accuracy if accuracy is not None else 50.0
        competency = (
            reliability * 0.30
            + accuracy_component * 0.35
            + sop_rate * 0.20
            + experience_score * 0.15
            - min(25.0, high_wrong * 6.0)
        )
        # Evidence maturity caps prevent a few refreshes from creating a false
        # senior-grade recommendation.
        maturity_cap = {"COLLECTING": 49.0, "DEVELOPING": 64.0, "VALIDATED": 84.0, "MATURE": 100.0}[maturity]
        competency = round(min(maturity_cap, self._clamp(competency)), 1)

        recommended_grade = self._recommended_grade(
            observations=observations,
            validated=validated,
            reliability=reliability,
            accuracy=accuracy,
            sop_rate=sop_rate,
            high_wrong=high_wrong,
        )
        board_recommendation = self._board_recommendation(
            current_grade=current_grade,
            recommended_grade=recommended_grade,
            observations=observations,
            validated=validated,
            accuracy=accuracy,
            reliability=reliability,
            high_wrong=high_wrong,
            performance_status=performance_status,
        )
        training_plan = self._training_plan(
            observations=observations,
            validated=validated,
            accuracy=accuracy,
            reliability=reliability,
            sop_rate=sop_rate,
            high_wrong=high_wrong,
            performance_status=performance_status,
        )
        reason = self._reason(
            board_recommendation,
            current_grade,
            recommended_grade,
            observations,
            validated,
            reliability,
            accuracy,
            sop_rate,
            high_wrong,
        )

        return OfficerServiceProfile(
            branch=branch,
            boss=self.BOSSES.get(branch, f"DSP {branch.replace('_', ' ').title()}"),
            current_grade=current_grade,
            recommended_grade=recommended_grade,
            observations=observations,
            validated_cases=validated,
            experience_score=round(experience_score, 1),
            reliability_score=round(reliability, 1),
            accuracy=round(accuracy, 1) if accuracy is not None else None,
            sop_pass_rate=round(sop_rate, 1),
            high_confidence_wrong=high_wrong,
            competency_score=competency,
            evidence_maturity=maturity,
            performance_status=performance_status,
            board_recommendation=board_recommendation,
            training_plan=training_plan[:4],
            review_reason=reason,
        )

    @staticmethod
    def _recommended_grade(
        *,
        observations: int,
        validated: int,
        reliability: float,
        accuracy: Optional[float],
        sop_rate: float,
        high_wrong: int,
    ) -> str:
        accuracy_value = accuracy if accuracy is not None else -1.0
        if observations >= 40 and validated >= 20 and reliability >= 82 and accuracy_value >= 70 and sop_rate >= 90 and high_wrong <= 1:
            return "DSP"
        if observations >= 25 and validated >= 12 and reliability >= 75 and accuracy_value >= 62 and sop_rate >= 85 and high_wrong <= 2:
            return "INSPECTOR"
        if observations >= 15 and validated >= 6 and reliability >= 68 and accuracy_value >= 55 and sop_rate >= 78 and high_wrong <= 2:
            return "SI"
        if observations >= 8 and validated >= 3 and reliability >= 60 and accuracy_value >= 50 and sop_rate >= 70 and high_wrong <= 2:
            return "ASI"
        if observations >= 5 and reliability >= 55 and sop_rate >= 60:
            return "HC"
        return "RECRUIT"

    @staticmethod
    def _board_recommendation(
        *,
        current_grade: str,
        recommended_grade: str,
        observations: int,
        validated: int,
        accuracy: Optional[float],
        reliability: float,
        high_wrong: int,
        performance_status: str,
    ) -> str:
        current_index = GRADE_INDEX.get(current_grade, 0)
        recommended_index = GRADE_INDEX.get(recommended_grade, 0)
        severe_failure = validated >= 5 and ((accuracy is not None and accuracy < 40.0) or high_wrong >= 3 or reliability < 45.0)
        if severe_failure:
            return "DEMOTION_REVIEW_REQUIRED" if current_index > 0 else "PROBATION_REVIEW"
        if performance_status == "RETRAINING_RECOMMENDED" or (validated >= 3 and reliability < 55.0):
            return "TRAINING_REQUIRED"
        if observations < 5 or validated < 3:
            return "COLLECTING_EVIDENCE"
        if recommended_index > current_index:
            return "PROMOTION_ELIGIBLE_REVIEW"
        if recommended_index < current_index:
            return "DEMOTION_REVIEW_REQUIRED"
        return "RETAIN_CURRENT_GRADE"

    @staticmethod
    def _training_plan(
        *,
        observations: int,
        validated: int,
        accuracy: Optional[float],
        reliability: float,
        sop_rate: float,
        high_wrong: int,
        performance_status: str,
    ) -> List[str]:
        plan: List[str] = []
        if observations < 8 or validated < 3:
            plan.append("LIVE_CASE_COLLECTION")
        if sop_rate < 75:
            plan.append("SOP_DISCIPLINE_REFRESH")
        if reliability < 65:
            plan.append("CONSISTENCY_AND_STABILITY_TRAINING")
        if accuracy is not None and accuracy < 55:
            plan.append("PREDICTION_VS_REALITY_REVIEW")
        if high_wrong >= 2:
            plan.append("CONFIDENCE_CALIBRATION")
        if performance_status in {"MIXED_PERFORMANCE", "REVIEW_REQUIRED", "RETRAINING_RECOMMENDED"}:
            plan.append("CROSS_DEPARTMENT_CONTRADICTION_REVIEW")
        if not plan:
            plan.append("CONTINUE_VALIDATED_LIVE_SERVICE")
        return list(dict.fromkeys(plan))

    @staticmethod
    def _reason(
        recommendation: str,
        current_grade: str,
        recommended_grade: str,
        observations: int,
        validated: int,
        reliability: float,
        accuracy: Optional[float],
        sop_rate: float,
        high_wrong: int,
    ) -> str:
        accuracy_text = "Collecting" if accuracy is None else f"{accuracy:.1f}%"
        return (
            f"{recommendation}: current {current_grade}, evidence grade {recommended_grade}; "
            f"{observations} observations, {validated} validated cases, reliability {reliability:.1f}%, "
            f"accuracy {accuracy_text}, SOP {sop_rate:.1f}%, high-confidence wrong {high_wrong}."
        )[:360]

    @staticmethod
    def _review_map(self_review: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
        rows = self_review.get("department_reviews", []) if isinstance(self_review, Mapping) else []
        output: Dict[str, Mapping[str, Any]] = {}
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
            for item in rows:
                if isinstance(item, Mapping) and item.get("branch"):
                    output[str(item.get("branch"))] = item
        return output

    def _archive_final(self, state: MutableMapping[str, Any], report: PromotionBoardReport) -> None:
        archive = state.get(self.ARCHIVE_KEY, [])
        archive = list(archive) if isinstance(archive, list) else []
        compact = {
            "review_date": report.review_date,
            "board_state": report.board_state,
            "promotion_eligible": list(report.promotion_eligible),
            "training_required": list(report.training_required),
            "probation_review": list(report.probation_review),
            "demotion_review": list(report.demotion_review),
            "confidence": report.confidence,
        }
        archive = [item for item in archive if not (isinstance(item, Mapping) and item.get("review_date") == report.review_date)]
        archive.append(compact)
        state[self.ARCHIVE_KEY] = archive[-self.MAX_ARCHIVE_DAYS:]

    @staticmethod
    def _recommendation_order(value: str) -> int:
        return {
            "DEMOTION_REVIEW_REQUIRED": 0,
            "PROBATION_REVIEW": 1,
            "TRAINING_REQUIRED": 2,
            "PROMOTION_ELIGIBLE_REVIEW": 3,
            "COLLECTING_EVIDENCE": 4,
            "RETAIN_CURRENT_GRADE": 5,
        }.get(value, 9)

    @staticmethod
    def _valid_grade(value: Any) -> str:
        grade = str(value or "RECRUIT").upper().strip()
        return grade if grade in GRADE_INDEX else "RECRUIT"

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        text = str(value or "").strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
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
