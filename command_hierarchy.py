"""
command_hierarchy.py
Version: V26.0
Role: Department/Branch command-and-control layer

Hierarchy:
- Specialists/Employees prepare facts inside each department module.
- Branch Boss validates the department report.
- CO receives only validated branch summaries.
- CO creates one consolidated Case File.
- AI_MASTER remains the only final trading authority.

No background loops, threads, polling, API calls, or trading decisions exist here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional


@dataclass(frozen=True)
class BranchReport:
    branch: str
    boss: str
    status: str
    confidence: float
    summary: str
    facts: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class COCaseFile:
    snapshot_id: str
    accepted: bool
    command_status: str
    agreement_score: float
    data_quality_score: float
    branch_reports: Dict[str, BranchReport]
    consolidated_evidence: List[str]
    conflicts: List[str]
    warnings: List[str]


class BranchBoss:
    """Validates one department report and forwards only a compact summary."""

    def __init__(self, branch: str, boss: str, minimum_confidence: float = 0.0):
        self.branch = branch
        self.boss = boss
        self.minimum_confidence = float(minimum_confidence)

    def review(self, report: Any) -> BranchReport:
        summary = self._read(report, "summary", "No report")
        confidence = self._number(self._read(report, "confidence", 0.0))
        details = self._read(report, "details", {})
        if not isinstance(details, Mapping):
            details = {}

        warnings: List[str] = []
        if report is None:
            warnings.append("Report missing")
        if confidence < self.minimum_confidence:
            warnings.append("Low branch confidence")
        if not summary or summary == "No report":
            warnings.append("Summary missing")

        status = "READY" if not warnings else "CAUTION"
        return BranchReport(
            branch=self.branch,
            boss=self.boss,
            status=status,
            confidence=round(max(0.0, min(100.0, confidence)), 1),
            summary=str(summary)[:300],
            facts=self._compact(details),
            warnings=warnings,
        )

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

    def _compact(self, value: Any, depth: int = 0) -> Any:
        if depth > 3:
            return str(value)[:120]
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return value[:200]
        if isinstance(value, Mapping):
            result: Dict[str, Any] = {}
            for index, (key, item) in enumerate(value.items()):
                if index >= 20:
                    break
                result[str(key)] = self._compact(item, depth + 1)
            return result
        if isinstance(value, (list, tuple)):
            return [self._compact(item, depth + 1) for item in list(value)[:10]]
        return str(value)[:160]


class CommandingOfficer:
    """CO verifies branch readiness and prepares one case file for AI_MASTER."""

    REQUIRED_BRANCHES = (
        "DATA",
        "OPTION",
        "PRICE_ACTION",
        "MARKET_BEHAVIOUR",
        "SMART_MONEY",
        "RISK",
        "CANDIDATE",
        "STRATEGY",
    )

    def prepare_case_file(
        self,
        *,
        snapshot_id: str,
        data_quality_score: float,
        branches: Iterable[BranchReport],
    ) -> COCaseFile:
        branch_map = {branch.branch: branch for branch in branches}
        warnings: List[str] = []
        conflicts: List[str] = []
        evidence: List[str] = []

        missing = [name for name in self.REQUIRED_BRANCHES if name not in branch_map]
        if missing:
            warnings.append("Missing branches: " + ", ".join(missing))

        caution = [name for name, branch in branch_map.items() if branch.status != "READY"]
        if caution:
            warnings.append("Branches on caution: " + ", ".join(caution))

        for name in self.REQUIRED_BRANCHES:
            branch = branch_map.get(name)
            if branch:
                evidence.append(f"{name}: {branch.summary}")

        # Lightweight conflict checks. CO does not make a trade decision.
        price_text = self._branch_text(branch_map.get("PRICE_ACTION"))
        option_text = self._branch_text(branch_map.get("OPTION"))
        money_text = self._branch_text(branch_map.get("SMART_MONEY"))
        strategy_text = self._branch_text(branch_map.get("STRATEGY"))

        if "bullish" in price_text and ("bearish" in option_text or "selling" in money_text):
            conflicts.append("Bullish price action conflicts with option/money flow")
        if "bearish" in price_text and ("bullish" in option_text or "buying" in money_text):
            conflicts.append("Bearish price action conflicts with option/money flow")
        if "wait" not in strategy_text and conflicts:
            conflicts.append("Strategy recommendation exists despite cross-branch conflict")

        confidences = [
            branch.confidence for branch in branch_map.values()
            if branch.status == "READY" and branch.confidence > 0
        ]
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        agreement_score = max(0.0, min(100.0, average_confidence - len(conflicts) * 12.0))
        quality = max(0.0, min(100.0, float(data_quality_score or 0)))

        accepted = (
            bool(snapshot_id)
            and not missing
            and quality >= 60.0
            and len(conflicts) <= 2
        )
        command_status = "CASE_FILE_READY" if accepted else "CASE_FILE_HOLD"

        return COCaseFile(
            snapshot_id=snapshot_id or "UNKNOWN",
            accepted=accepted,
            command_status=command_status,
            agreement_score=round(agreement_score, 1),
            data_quality_score=round(quality, 1),
            branch_reports=branch_map,
            consolidated_evidence=evidence[:12],
            conflicts=conflicts[:8],
            warnings=warnings[:8],
        )

    @staticmethod
    def _branch_text(branch: Optional[BranchReport]) -> str:
        if branch is None:
            return ""
        return (branch.summary + " " + str(branch.facts)).lower()


class AIOrganizationController:
    """One-shot orchestration: branches report -> CO case file -> sleep."""

    BOSSES = {
        "DATA": BranchBoss("DATA", "DSP Data Intelligence", 60),
        "OPTION": BranchBoss("OPTION", "DSP Option Intelligence", 0),
        "PRICE_ACTION": BranchBoss("PRICE_ACTION", "DSP Price Action", 0),
        "MARKET_BEHAVIOUR": BranchBoss("MARKET_BEHAVIOUR", "DSP Market Behaviour", 0),
        "SMART_MONEY": BranchBoss("SMART_MONEY", "DSP Smart Money", 0),
        "RISK": BranchBoss("RISK", "DSP Risk", 0),
        "CANDIDATE": BranchBoss("CANDIDATE", "DSP Candidate", 0),
        "STRATEGY": BranchBoss("STRATEGY", "DSP Strategy", 0),
    }

    def build_case_file(
        self,
        *,
        snapshot_id: str,
        data_quality_score: float,
        reports: Mapping[str, Any],
    ) -> COCaseFile:
        reviewed = [
            boss.review(reports.get(name))
            for name, boss in self.BOSSES.items()
        ]
        return CommandingOfficer().prepare_case_file(
            snapshot_id=snapshot_id,
            data_quality_score=data_quality_score,
            branches=reviewed,
        )
