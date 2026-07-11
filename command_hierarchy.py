"""
command_hierarchy.py
Version: V31.0
Role: CO Cross-Examination and Investigation Academy.

One-shot flow only:
Branch facts -> DSP review -> branch vote -> cross-examination ->
CO case file -> AI_MASTER. No background loops, timers, API calls,
or independent trading decisions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional


@dataclass(frozen=True)
class EvidenceItem:
    branch: str
    statement: str
    category: str
    weight: float
    verified_by: List[str] = field(default_factory=list)
    contradiction: bool = False


@dataclass(frozen=True)
class CrossExaminationItem:
    question_from: str
    question_to: str
    question: str
    answer: str
    verdict: str
    score: float


@dataclass(frozen=True)
class BranchReport:
    branch: str
    boss: str
    status: str
    confidence: float
    summary: str
    facts: Dict[str, Any] = field(default_factory=dict)
    evidence: List[EvidenceItem] = field(default_factory=list)
    reasoning: str = ""
    risk_note: str = ""
    recommendation: str = "INFORMATION_ONLY"
    branch_vote: str = "NEUTRAL"
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class COCaseFile:
    snapshot_id: str
    case_id: str
    accepted: bool
    command_status: str
    agreement_score: float
    data_quality_score: float
    case_strength: float
    department_readiness: float
    witness_score: float
    cross_exam_score: float
    consensus_direction: str
    branch_votes: Dict[str, str]
    cross_examinations: List[CrossExaminationItem]
    branch_reports: Dict[str, BranchReport]
    consolidated_evidence: List[str]
    accepted_evidence: List[str]
    rejected_evidence: List[str]
    missing_evidence: List[str]
    conflicts: List[str]
    warnings: List[str]
    court_brief: str


class BranchBoss:
    """Validates one department report and converts facts into a compact case note."""

    def __init__(self, branch: str, boss: str, minimum_confidence: float = 0.0):
        self.branch = branch
        self.boss = boss
        self.minimum_confidence = float(minimum_confidence)

    def review(self, report: Any) -> BranchReport:
        summary = str(self._read(report, "summary", "No report"))[:300]
        confidence = self._number(self._read(report, "confidence", 0.0))
        details = self._read(report, "details", {})
        if not isinstance(details, Mapping):
            details = {}
        facts = self._compact(details)

        warnings: List[str] = []
        if report is None:
            warnings.append("Report missing")
        if confidence < self.minimum_confidence:
            warnings.append("Low branch confidence")
        if not summary or summary == "No report":
            warnings.append("Summary missing")

        evidence = self._extract_evidence(facts, confidence)
        reasoning = self._reasoning(summary, evidence)
        risk_note = self._risk_note(facts, confidence)
        recommendation = self._recommendation(summary, facts)
        branch_vote = self._branch_vote(summary, facts, recommendation)
        status = "READY" if not warnings else "CAUTION"

        return BranchReport(
            branch=self.branch,
            boss=self.boss,
            status=status,
            confidence=round(max(0.0, min(100.0, confidence)), 1),
            summary=summary,
            facts=facts,
            evidence=evidence,
            reasoning=reasoning,
            risk_note=risk_note,
            recommendation=recommendation,
            branch_vote=branch_vote,
            warnings=warnings,
        )

    def _extract_evidence(self, facts: Mapping[str, Any], confidence: float) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        for key, value in facts.items():
            if len(items) >= 8:
                break
            text = self._fact_text(value)
            if not text or text.lower() in {"unknown", "none", "no report", ""}:
                continue
            category = "CRITICAL" if key in {"trend", "oi", "volume", "barrier", "vix", "news", "strategy"} else "SUPPORTING"
            weight = min(100.0, max(20.0, confidence * (1.0 if category == "CRITICAL" else 0.75)))
            items.append(EvidenceItem(self.branch, f"{key}: {text}"[:220], category, round(weight, 1)))
        return items

    @staticmethod
    def _fact_text(value: Any) -> str:
        if isinstance(value, Mapping):
            parts = []
            for key, item in list(value.items())[:4]:
                if item not in (None, "", "Unknown"):
                    parts.append(f"{key}={item}")
            return ", ".join(parts)
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in list(value)[:4])
        return str(value)

    @staticmethod
    def _reasoning(summary: str, evidence: List[EvidenceItem]) -> str:
        if not evidence:
            return "Insufficient structured evidence; keep informational."
        return f"{summary}. Supported by {len(evidence)} structured evidence item(s)."[:360]

    @staticmethod
    def _risk_note(facts: Mapping[str, Any], confidence: float) -> str:
        text = str(facts).lower()
        risks: List[str] = []
        if confidence < 55:
            risks.append("low confidence")
        for token, label in (
            ("high impact", "news risk"),
            ("high volatility", "volatility risk"),
            ("fake", "fake-move risk"),
            ("exhaust", "exhaustion risk"),
        ):
            if token in text:
                risks.append(label)
        return ", ".join(risks) if risks else "No material branch-specific risk flagged."

    @staticmethod
    def _recommendation(summary: str, facts: Mapping[str, Any]) -> str:
        text = (summary + " " + str(facts)).upper()
        for action in ("IRON CONDOR", "SELL CE", "SELL PE", "WAIT"):
            if action in text:
                return action
        return "INFORMATION_ONLY"

    @staticmethod
    def _branch_vote(summary: str, facts: Mapping[str, Any], recommendation: str) -> str:
        text = (summary + " " + str(facts) + " " + recommendation).lower()
        bullish_tokens = ("bullish", "buying", "pe support", "supporting market", "sell pe", "uptrend")
        bearish_tokens = ("bearish", "selling", "ce resistance", "pressuring market", "sell ce", "downtrend")
        risk_tokens = ("high impact", "high volatility", "fake breakout", "exhaustion", "wait")
        bullish = sum(token in text for token in bullish_tokens)
        bearish = sum(token in text for token in bearish_tokens)
        risk = sum(token in text for token in risk_tokens)
        if risk >= 2 or recommendation == "WAIT":
            return "CAUTION"
        if bullish >= bearish + 1:
            return "BULLISH"
        if bearish >= bullish + 1:
            return "BEARISH"
        return "NEUTRAL"

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
    """Cross-examines branches and prepares one explainable case file."""

    REQUIRED_BRANCHES = (
        "DATA", "OPTION", "PRICE_ACTION", "MARKET_BEHAVIOUR",
        "MARKET_PSYCHOLOGY", "SMART_MONEY", "RISK", "CANDIDATE", "STRATEGY",
    )

    def prepare_case_file(self, *, snapshot_id: str, data_quality_score: float, branches: Iterable[BranchReport]) -> COCaseFile:
        branch_map = {branch.branch: branch for branch in branches}
        warnings: List[str] = []
        conflicts: List[str] = []
        missing_evidence: List[str] = []

        missing = [name for name in self.REQUIRED_BRANCHES if name not in branch_map]
        if missing:
            warnings.append("Missing branches: " + ", ".join(missing))
        caution = [name for name, branch in branch_map.items() if branch.status != "READY"]
        if caution:
            warnings.append("Branches on caution: " + ", ".join(caution))

        price_text = self._branch_text(branch_map.get("PRICE_ACTION"))
        option_text = self._branch_text(branch_map.get("OPTION"))
        money_text = self._branch_text(branch_map.get("SMART_MONEY"))
        strategy_text = self._branch_text(branch_map.get("STRATEGY"))
        behaviour_text = self._branch_text(branch_map.get("MARKET_BEHAVIOUR"))

        if "bullish" in price_text and ("bearish" in option_text or "selling" in money_text):
            conflicts.append("Bullish price action conflicts with option/money flow")
        if "bearish" in price_text and ("bullish" in option_text or "buying" in money_text):
            conflicts.append("Bearish price action conflicts with option/money flow")
        if "breakout" in behaviour_text and "resistance" in option_text and "increasing" not in behaviour_text:
            conflicts.append("Breakout thesis lacks confirming option pressure")
        if "wait" not in strategy_text and conflicts:
            conflicts.append("Strategy recommendation exists despite cross-branch conflict")

        cross_examinations = self._cross_examine(branch_map)
        for item in cross_examinations:
            if item.verdict == "CONTRADICTED":
                conflicts.append(f"Cross-exam: {item.question_from} vs {item.question_to}")

        all_evidence = [evidence for branch in branch_map.values() for evidence in branch.evidence]
        accepted_evidence: List[str] = []
        rejected_evidence: List[str] = []
        for evidence in all_evidence:
            witnesses = self._witnesses(evidence, branch_map)
            statement = evidence.statement
            if evidence.weight >= 55 and (witnesses or evidence.category == "CRITICAL"):
                suffix = (" | verified by " + ", ".join(witnesses)) if witnesses else ""
                accepted_evidence.append(f"{evidence.branch}: {statement}{suffix}")
            else:
                rejected_evidence.append(f"{evidence.branch}: {statement} (weak/unverified)")

        for name in self.REQUIRED_BRANCHES:
            branch = branch_map.get(name)
            if branch is None or not branch.evidence:
                missing_evidence.append(f"{name}: no structured evidence")

        branch_votes = {name: branch.branch_vote for name, branch in branch_map.items()}
        # V36.1 Psychology is evidence-only during Phase-1. CO records it, but it
        # cannot tilt directional consensus until live accuracy is validated.
        _consensus_votes = {
            name: vote for name, vote in branch_votes.items()
            if name != "MARKET_PSYCHOLOGY"
        }
        consensus_direction, vote_agreement = self._consensus(_consensus_votes)
        ready_count = sum(1 for name in self.REQUIRED_BRANCHES if branch_map.get(name) and branch_map[name].status == "READY")
        readiness = ready_count / len(self.REQUIRED_BRANCHES) * 100
        confidences = [branch.confidence for branch in branch_map.values() if branch.status == "READY" and branch.confidence > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        witness_score = min(100.0, len(accepted_evidence) / max(1, len(all_evidence)) * 100)
        cross_exam_score = self._cross_exam_score(cross_examinations)
        agreement = max(0.0, min(100.0, avg_conf * 0.65 + vote_agreement * 0.35 - len(conflicts) * 8.0))
        quality = max(0.0, min(100.0, float(data_quality_score or 0)))
        case_strength = max(
            0.0,
            min(
                100.0,
                quality * 0.20
                + agreement * 0.25
                + readiness * 0.15
                + witness_score * 0.20
                + cross_exam_score * 0.20
                - len(conflicts) * 4.0,
            ),
        )

        severe_conflicts = sum("Cross-exam" in item for item in conflicts)
        accepted = (
            bool(snapshot_id)
            and not missing
            and quality >= 60
            and readiness >= 75
            and case_strength >= 58
            and len(conflicts) <= 3
            and severe_conflicts <= 1
        )
        command_status = "CASE_FILE_READY" if accepted else "CASE_FILE_HOLD"
        case_id = f"NIFTY-{str(snapshot_id).replace(':', '').replace('-', '')[-18:]}"
        court_brief = (
            f"{len(accepted_evidence)} evidence accepted, {len(rejected_evidence)} rejected, "
            f"{len(cross_examinations)} cross-exam(s), {len(conflicts)} conflict(s); "
            f"consensus {consensus_direction}, case strength {case_strength:.1f}%."
        )
        consolidated = [f"{name}: {branch_map[name].summary}" for name in self.REQUIRED_BRANCHES if name in branch_map]

        return COCaseFile(
            snapshot_id=snapshot_id or "UNKNOWN",
            case_id=case_id,
            accepted=accepted,
            command_status=command_status,
            agreement_score=round(agreement, 1),
            data_quality_score=round(quality, 1),
            case_strength=round(case_strength, 1),
            department_readiness=round(readiness, 1),
            witness_score=round(witness_score, 1),
            cross_exam_score=round(cross_exam_score, 1),
            consensus_direction=consensus_direction,
            branch_votes=branch_votes,
            cross_examinations=cross_examinations[:12],
            branch_reports=branch_map,
            consolidated_evidence=consolidated[:12],
            accepted_evidence=accepted_evidence[:16],
            rejected_evidence=rejected_evidence[:12],
            missing_evidence=missing_evidence[:8],
            conflicts=conflicts[:8],
            warnings=warnings[:8],
            court_brief=court_brief,
        )

    def _cross_examine(self, branches: Mapping[str, BranchReport]) -> List[CrossExaminationItem]:
        questions = [
            ("PRICE_ACTION", "OPTION", "Does option flow confirm the price direction?"),
            ("MARKET_BEHAVIOUR", "OPTION", "Does OI/volume confirm the barrier or breakout thesis?"),
            ("STRATEGY", "RISK", "Does the risk branch permit the proposed strategy?"),
            ("STRATEGY", "CANDIDATE", "Is a valid candidate available for the proposed strategy?"),
            ("CO", "DATA", "Is the snapshot quality sufficient for judgement?"),
            ("SMART_MONEY", "PRICE_ACTION", "Do heavyweights and price action point in the same direction?"),
        ]
        output: List[CrossExaminationItem] = []
        for source, target, question in questions:
            source_branch = branches.get(source) if source != "CO" else None
            target_branch = branches.get(target)
            if target_branch is None:
                output.append(CrossExaminationItem(source, target, question, "Target report missing", "INSUFFICIENT", 20.0))
                continue

            source_vote = source_branch.branch_vote if source_branch else "NEUTRAL"
            target_vote = target_branch.branch_vote
            answer = f"{target}: {target_branch.summary}"[:260]

            if target == "DATA":
                verdict = "CONFIRMED" if target_branch.status == "READY" and target_branch.confidence >= 60 else "INSUFFICIENT"
            elif source == "STRATEGY" and target == "RISK":
                risk_text = self._branch_text(target_branch)
                verdict = "CONTRADICTED" if any(token in risk_text for token in ("high impact", "high volatility", "high gap")) else "CONFIRMED"
            elif source == "STRATEGY" and target == "CANDIDATE":
                verdict = "CONFIRMED" if target_branch.confidence >= 55 and "none" not in self._branch_text(target_branch) else "INSUFFICIENT"
            elif source_vote in {"BULLISH", "BEARISH"} and target_vote in {"BULLISH", "BEARISH"}:
                verdict = "CONFIRMED" if source_vote == target_vote else "CONTRADICTED"
            elif target_vote == "CAUTION":
                verdict = "INSUFFICIENT"
            else:
                verdict = "PARTIAL"

            score = {"CONFIRMED": 100.0, "PARTIAL": 65.0, "INSUFFICIENT": 40.0, "CONTRADICTED": 10.0}[verdict]
            output.append(CrossExaminationItem(source, target, question, answer, verdict, score))
        return output

    @staticmethod
    def _consensus(votes: Mapping[str, str]) -> tuple[str, float]:
        directional = [vote for vote in votes.values() if vote in {"BULLISH", "BEARISH", "NEUTRAL", "CAUTION"}]
        if not directional:
            return "NEUTRAL", 0.0
        bullish = directional.count("BULLISH")
        bearish = directional.count("BEARISH")
        caution = directional.count("CAUTION")
        if caution >= max(bullish, bearish) and caution >= 2:
            direction = "CAUTION"
            winning = caution
        elif bullish > bearish:
            direction = "BULLISH"
            winning = bullish
        elif bearish > bullish:
            direction = "BEARISH"
            winning = bearish
        else:
            direction = "NEUTRAL"
            winning = directional.count("NEUTRAL")
        return direction, min(100.0, winning / max(1, len(directional)) * 100.0)

    @staticmethod
    def _cross_exam_score(items: List[CrossExaminationItem]) -> float:
        if not items:
            return 0.0
        return sum(item.score for item in items) / len(items)

    @staticmethod
    def _witnesses(evidence: EvidenceItem, branches: Mapping[str, BranchReport]) -> List[str]:
        tokens = {token for token in re_words(evidence.statement) if len(token) > 4}
        witnesses: List[str] = []
        for name, branch in branches.items():
            if name == evidence.branch:
                continue
            other = re_words(branch.summary + " " + str(branch.facts))
            if tokens.intersection(other):
                witnesses.append(name)
        return witnesses[:3]

    @staticmethod
    def _branch_text(branch: Optional[BranchReport]) -> str:
        return "" if branch is None else (branch.summary + " " + str(branch.facts)).lower()


def re_words(text: str) -> set[str]:
    import re
    return set(re.findall(r"[a-zA-Z_]+", str(text).lower()))


class AIOrganizationController:
    """One-shot orchestration: branches report -> CO cross-exam file -> sleep."""

    BOSSES = {
        "DATA": BranchBoss("DATA", "DSP Data Intelligence", 60),
        "OPTION": BranchBoss("OPTION", "DSP Option Intelligence", 0),
        "PRICE_ACTION": BranchBoss("PRICE_ACTION", "DSP Price Action", 0),
        "MARKET_BEHAVIOUR": BranchBoss("MARKET_BEHAVIOUR", "DSP Market Behaviour", 0),
        "MARKET_PSYCHOLOGY": BranchBoss("MARKET_PSYCHOLOGY", "DSP Market Psychology", 0),
        "SMART_MONEY": BranchBoss("SMART_MONEY", "DSP Smart Money", 0),
        "RISK": BranchBoss("RISK", "DSP Risk", 0),
        "CANDIDATE": BranchBoss("CANDIDATE", "DSP Candidate", 0),
        "STRATEGY": BranchBoss("STRATEGY", "DSP Strategy", 0),
    }

    def build_case_file(self, *, snapshot_id: str, data_quality_score: float, reports: Mapping[str, Any]) -> COCaseFile:
        reviewed = [boss.review(reports.get(name)) for name, boss in self.BOSSES.items()]
        return CommandingOfficer().prepare_case_file(
            snapshot_id=snapshot_id,
            data_quality_score=data_quality_score,
            branches=reviewed,
        )
