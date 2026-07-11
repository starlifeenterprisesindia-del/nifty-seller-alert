"""
department_academy.py
Version: V28.0
Role: Branch SOP, bounded observation memory, and controlled learning review.

Safety rules:
- Never issues WAIT / SELL CE / SELL PE / IRON CONDOR.
- Never changes production weights automatically.
- Never starts loops, threads, timers, or API calls.
- Stores only compact plain dictionaries with strict limits.
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
    lessons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class DepartmentSOP:
    """Defines what each branch must report before its file is considered complete."""

    REQUIRED_FACT_KEYS: Dict[str, tuple[str, ...]] = {
        "DATA": ("snapshot_id", "quality_score"),
        "OPTION": ("oi", "volume", "pcr", "strike"),
        "PRICE_ACTION": ("trend", "barrier", "move_stage", "range"),
        "MARKET_BEHAVIOUR": ("barrier", "breakout", "reversal", "energy"),
        "SMART_MONEY": ("fii", "dii", "heavyweights", "breadth"),
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

    def __init__(self, storage: MutableMapping[str, Any], *, key: str = "v28_branch_memory", limit: int = 6):
        self.storage = storage
        self.key = key
        self.limit = max(2, min(int(limit), 12))
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


class DepartmentAcademy:
    """One-shot branch training review: SOP -> memory -> learning note -> sleep."""

    BOSSES = {
        "DATA": "DSP Data Intelligence",
        "OPTION": "DSP Option Intelligence",
        "PRICE_ACTION": "DSP Price Action",
        "MARKET_BEHAVIOUR": "DSP Market Behaviour",
        "SMART_MONEY": "DSP Smart Money",
        "RISK": "DSP Risk",
        "STRATEGY": "DSP Strategy",
        "CANDIDATE": "DSP Candidate",
    }

    def __init__(self, storage: MutableMapping[str, Any], *, memory_limit: int = 6):
        self.sop = DepartmentSOP()
        self.memory = BranchObservationMemory(storage, limit=memory_limit)

    def train_once(
        self,
        *,
        snapshot_id: str,
        branch_reports: Mapping[str, Any],
    ) -> Dict[str, BranchTrainingReport]:
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

            output[branch] = BranchTrainingReport(
                branch=branch,
                boss=boss,
                sop_status=sop_status,
                confidence=round(max(0.0, min(100.0, confidence)), 1),
                observation=summary,
                change_from_previous=change,
                memory_count=memory_count,
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
        return lessons or ["Observation recorded for future validation."]
