"""
department_academy.py
Version: V48.3
Role: Branch Academy, bounded observation memory, SOP review, and service-book metrics.

Safety rules:
- Never issues WAIT / SELL CE / SELL PE / IRON CONDOR.
- Never changes production weights automatically.
- Never starts loops, threads, timers, or API calls.
- Stores only compact plain dictionaries with strict limits.
- Reliability is observation consistency, NOT trading accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, MutableMapping, Optional


@dataclass(frozen=True)
class BranchTrainingReport:
    branch: str
    boss: str
    sop_status: str
    confidence: float
    observation: str
    change_from_previous: str
    memory_count: int
    experience_count: int
    reliability_score: float
    training_status: str
    lessons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class DepartmentSOP:
    """Defines what each branch must report before its file is considered complete."""

    REQUIRED_FACT_KEYS: Dict[str, tuple[str, ...]] = {
        "DATA": ("snapshot_id", "quality_score"),
        "OPTION": ("oi", "volume", "pcr", "strike"),
        "PRICE_ACTION": ("trend", "barrier", "move_stage", "range"),
        "MARKET_BEHAVIOUR": ("barrier", "breakout", "reversal", "energy"),
        "MARKET_PSYCHOLOGY": ("psychology_state", "retail_fear", "retail_greed", "data_coverage", "psychology_case_report"),
        "TIME_INTELLIGENCE": ("phase_code", "phase_label", "observed_behaviour", "continuation_factor", "reversal_adjustment", "confidence_cap"),
        "MARKET_JOURNEY": ("upside_remaining_points", "downside_remaining_points", "primary_direction", "reversal_risk", "barrier_adjustment_points", "barrier_statistics", "tracked_barriers"),
        "HEAVYWEIGHT_INTELLIGENCE": ("investigation_state", "alignment_state", "coverage_count", "weighted_pressure", "estimated_nifty_points", "dominant_driver", "sector_map"),
        "NEWS_INTELLIGENCE": ("impact_level", "impact_score", "risk_state", "event_window", "market_confirmation", "source_mode", "uncertainty_score"),
        "SMART_MONEY": ("fii", "dii", "heavyweights", "breadth", "institutional_state", "market_mood", "cash_flow_state", "futures_positioning", "institutional_pressure_score", "market_alignment"),
        "EXPERIENCE": ("experience_state", "stored_cases", "pending_cases", "completed_cases", "similar_completed_cases", "replay_state", "replayed_cases", "historical_alignment", "automatic_decision_override", "automatic_rule_change"),
        "SELF_REVIEW": ("review_state", "review_scope", "completed_cases_reviewed", "department_reviews", "automatic_rule_change", "automatic_retraining"),
        "PROMOTION_BOARD": ("board_state", "review_scope", "officers_reviewed", "officer_profiles", "automatic_promotion", "automatic_demotion", "automatic_training"),
        "LEARNING": ("learning_state", "review_scope", "recommendations_count", "review_ready_count", "recommendations", "automatic_rule_change", "automatic_weight_change", "automatic_threshold_change"),
        "RISK": ("vix", "news", "expiry", "gap"),
        "STRATEGY": (),
        "CANDIDATE": (),
    }

    def inspect(self, branch: str, facts: Mapping[str, Any]) -> tuple[str, List[str]]:
        required = self.REQUIRED_FACT_KEYS.get(branch, ())
        missing = [key for key in required if key not in facts]
        warnings: List[str] = []
        if missing:
            warnings.append("Missing SOP facts: " + ", ".join(missing))
        status = "SOP_PASS" if not warnings else "SOP_CAUTION"
        return status, warnings


class BranchObservationMemory:
    """Bounded per-branch diary stored as plain dictionaries."""

    def __init__(self, storage: MutableMapping[str, Any], *, key: str = "v29_branch_memory", limit: int = 8):
        self.storage = storage
        self.key = key
        self.limit = max(3, min(int(limit), 15))
        if not isinstance(self.storage.get(self.key), dict):
            self.storage[self.key] = {}

    def append(self, branch: str, record: Dict[str, Any]) -> None:
        all_memory = self.storage[self.key]
        history = list(all_memory.get(branch, []))[-(self.limit - 1):]
        history.append(self._compact(record))
        all_memory[branch] = history[-self.limit:]
        self.storage[self.key] = all_memory

    def history(self, branch: str) -> List[Dict[str, Any]]:
        all_memory = self.storage.get(self.key, {})
        return list(all_memory.get(branch, []))[-self.limit:] if isinstance(all_memory, dict) else []

    def _compact(self, value: Any, depth: int = 0) -> Any:
        if depth > 3:
            return str(value)[:120]
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return value[:240]
        if isinstance(value, Mapping):
            out: Dict[str, Any] = {}
            for index, (key, item) in enumerate(value.items()):
                if index >= 20:
                    break
                out[str(key)] = self._compact(item, depth + 1)
            return out
        if isinstance(value, (list, tuple)):
            return [self._compact(item, depth + 1) for item in list(value)[:10]]
        return str(value)[:160]


class BranchServiceBook:
    """
    Compact service book for every DSP branch.

    It records experience and consistency only. It does not claim outcome accuracy
    until actual market outcomes are separately validated by the Learning Department.
    """

    def __init__(self, storage: MutableMapping[str, Any], *, key: str = "v29_branch_service_book"):
        self.storage = storage
        self.key = key
        if not isinstance(self.storage.get(self.key), dict):
            self.storage[self.key] = {}

    def update(self, branch: str, *, sop_status: str, change: str, confidence: float) -> Dict[str, Any]:
        books = self.storage[self.key]
        book = dict(books.get(branch, {})) if isinstance(books.get(branch), Mapping) else {}

        book.setdefault("observations", 0)
        book.setdefault("sop_passes", 0)
        book.setdefault("stable", 0)
        book.setdefault("changed", 0)
        book.setdefault("rising", 0)
        book.setdefault("falling", 0)
        book.setdefault("confidence_total", 0.0)

        book["observations"] += 1
        book["confidence_total"] += max(0.0, min(100.0, float(confidence)))
        if sop_status == "SOP_PASS":
            book["sop_passes"] += 1
        if change == "STABLE":
            book["stable"] += 1
        elif change == "CONFIDENCE_RISING":
            book["rising"] += 1
        elif change == "CONFIDENCE_FALLING":
            book["falling"] += 1
        elif change == "OBSERVATION_CHANGED":
            book["changed"] += 1

        observations = max(1, int(book["observations"]))
        sop_rate = book["sop_passes"] / observations
        avg_conf = book["confidence_total"] / observations
        consistency_events = book["stable"] + book["rising"] + book["falling"] + book["changed"]
        if consistency_events:
            controlled_rate = (book["stable"] + 0.75 * book["rising"] + 0.55 * book["changed"] + 0.35 * book["falling"]) / consistency_events
        else:
            controlled_rate = 0.5

        reliability = max(0.0, min(100.0, sop_rate * 40 + controlled_rate * 35 + avg_conf * 0.25))
        if observations < 5:
            training = "RECRUIT / COLLECTING EXPERIENCE"
        elif reliability >= 80:
            training = "PROFICIENT"
        elif reliability >= 65:
            training = "ACTIVE TRAINING"
        else:
            training = "RETRAINING REQUIRED"

        book["reliability_score"] = round(reliability, 1)
        book["training_status"] = training
        books[branch] = book
        self.storage[self.key] = books
        return dict(book)


class DepartmentAcademy:
    """One-shot branch review: SOP -> memory -> service book -> lesson -> sleep."""

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
        "EXPERIENCE": "DSP Experience, Validation & Replay",
        "SELF_REVIEW": "DSP AI Self Review",
        "PROMOTION_BOARD": "DSP Personnel & Promotion Board",
        "LEARNING": "DSP True Learning & Improvement",
        "RISK": "DSP Risk",
        "STRATEGY": "DSP Strategy",
        "CANDIDATE": "DSP Candidate",
    }

    def __init__(self, storage: MutableMapping[str, Any], *, memory_limit: int = 8):
        self.sop = DepartmentSOP()
        self.memory = BranchObservationMemory(storage, limit=memory_limit)
        self.service_book = BranchServiceBook(storage)

    def train_once(self, *, snapshot_id: str, branch_reports: Mapping[str, Any]) -> Dict[str, BranchTrainingReport]:
        output: Dict[str, BranchTrainingReport] = {}
        for branch, report in branch_reports.items():
            facts = self._read(report, "facts", {})
            if not isinstance(facts, Mapping):
                facts = {}
            summary = str(self._read(report, "summary", "No report"))[:240]
            confidence = self._number(self._read(report, "confidence", 0.0))
            boss = str(self._read(report, "boss", self.BOSSES.get(branch, "DSP Unassigned")))

            sop_status, warnings = self.sop.inspect(branch, facts)
            previous = self.memory.history(branch)
            change = self._compare(previous[-1] if previous else None, summary, confidence)
            lessons = self._lessons(branch, facts, confidence, change)

            self.memory.append(branch, {
                "snapshot_id": snapshot_id,
                "summary": summary,
                "confidence": round(confidence, 1),
                "sop_status": sop_status,
            })
            memory_count = len(self.memory.history(branch))
            service = self.service_book.update(
                branch,
                sop_status=sop_status,
                change=change,
                confidence=confidence,
            )

            output[branch] = BranchTrainingReport(
                branch=branch,
                boss=boss,
                sop_status=sop_status,
                confidence=round(max(0.0, min(100.0, confidence)), 1),
                observation=summary,
                change_from_previous=change,
                memory_count=memory_count,
                experience_count=int(service.get("observations", 0)),
                reliability_score=float(service.get("reliability_score", 0.0)),
                training_status=str(service.get("training_status", "RECRUIT")),
                lessons=lessons[:3],
                warnings=warnings[:3],
            )
        return output

    @staticmethod
    def _read(report: Any, key: str, default: Any) -> Any:
        if report is None:
            return default
        if isinstance(report, Mapping):
            return report.get(key, default)
        return getattr(report, key, default)

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _compare(previous: Optional[Mapping[str, Any]], summary: str, confidence: float) -> str:
        if not previous:
            return "FIRST_OBSERVATION"
        old_summary = str(previous.get("summary", ""))
        old_confidence = DepartmentAcademy._number(previous.get("confidence", 0.0))
        delta = confidence - old_confidence
        if old_summary == summary and abs(delta) < 3:
            return "STABLE"
        if delta >= 8:
            return "CONFIDENCE_RISING"
        if delta <= -8:
            return "CONFIDENCE_FALLING"
        return "OBSERVATION_CHANGED"

    @staticmethod
    def _lessons(branch: str, facts: Mapping[str, Any], confidence: float, change: str) -> List[str]:
        lessons: List[str] = []
        if change == "CONFIDENCE_RISING":
            lessons.append("Branch evidence is strengthening across snapshots.")
        elif change == "CONFIDENCE_FALLING":
            lessons.append("Branch evidence is weakening; CO should treat it cautiously.")
        elif change == "STABLE":
            lessons.append("Branch reading is stable; no fresh contradiction detected.")
        elif change == "OBSERVATION_CHANGED":
            lessons.append("Branch state changed; compare with price and option reaction.")

        if confidence < 45:
            lessons.append("Low-confidence report: keep informational, not decisive.")
        if branch == "OPTION" and "volume" in facts and "oi" in facts:
            lessons.append("OI and volume evidence available for combined interpretation.")
        if branch == "MARKET_BEHAVIOUR" and "barrier" in facts:
            lessons.append("Barrier response available for breakout/reversal learning.")
        if branch == "MARKET_PSYCHOLOGY" and "psychology_state" in facts:
            lessons.append("Consolidated psychology case recorded; outcome validation required before directional use.")
        if branch == "TIME_INTELLIGENCE" and "phase_code" in facts:
            lessons.append("Time-phase behaviour recorded; use only as bounded context until live validation.")
        if branch == "MARKET_JOURNEY" and "barrier_statistics" in facts:
            lessons.append("Barrier touch/bounce/break samples recorded; probability remains sample-size dependent.")
        if branch == "HEAVYWEIGHT_INTELLIGENCE" and "alignment_state" in facts:
            lessons.append("Driver alignment and contribution concentration recorded; next-snapshot persistence is required.")
        if branch == "NEWS_INTELLIGENCE" and "impact_level" in facts:
            lessons.append("Impact-only news evidence recorded; causal attribution requires source and market-reaction confirmation.")
        if branch == "SMART_MONEY" and "institutional_state" in facts:
            lessons.append("Cash, futures and DII-absorption evidence recorded; conflict states require next-session confirmation.")
        if branch == "EXPERIENCE" and "experience_state" in facts:
            lessons.append("Prediction-versus-reality evidence recorded; lessons are review-only and cannot auto-change production rules.")
        if branch == "EXPERIENCE" and "replay_state" in facts:
            lessons.append("Comparable completed cases replayed; historical alignment is information-only and cannot override CO/AI_MASTER.")
        if branch == "SELF_REVIEW" and "review_state" in facts:
            lessons.append("Department performance review recorded; retraining and calibration remain manual recommendations only.")
        if branch == "PROMOTION_BOARD" and "board_state" in facts:
            lessons.append("Personnel-board recommendation recorded; competency grades and training actions require manual approval.")
        if branch == "LEARNING" and "learning_state" in facts:
            lessons.append("Learning hypothesis recorded; AI_MASTER review is required and no production change may be auto-applied.")
        return lessons or ["Observation recorded for future validation."]
