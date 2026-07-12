"""
master_intelligence.py
Version: V49.3
Role: AI_MASTER pre-judgement master intelligence dossier.

This is not a department and not a second decision engine. It creates one
bounded synthesis for AI_MASTER after the CO case file is prepared. During
V49 live validation it is shadow-mode only: it cannot change action,
confidence, candidate, execution permission, rules, weights, or thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple


DIRECTIONS = {"BULLISH", "BEARISH", "RANGE", "CONFLICTED", "NEUTRAL"}


@dataclass(frozen=True)
class IntelligenceDimension:
    name: str
    direction: str
    confidence: float
    statement: str
    role: str = "CONTEXT"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "direction": self.direction,
            "confidence": self.confidence,
            "statement": self.statement,
            "role": self.role,
        }


@dataclass(frozen=True)
class MasterIntelligenceReport:
    snapshot_id: str
    version: str
    master_state: str
    statement: str
    current_market_state: str
    current_direction: str
    previous_market_state: str
    transition_state: str
    preliminary_strategy: str
    thesis_alignment: str
    historical_alignment: str
    experience_state: str
    behaviour_state: str
    risk_state: str
    convergence_score: float
    contradiction_score: float
    uncertainty_score: float
    continuity_score: float
    evidence_coverage: float
    dimensions: List[IntelligenceDimension] = field(default_factory=list)
    supporting_dimensions: List[str] = field(default_factory=list)
    opposing_dimensions: List[str] = field(default_factory=list)
    unresolved_dimensions: List[str] = field(default_factory=list)
    next_confirmation: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "version": self.version,
            "master_state": self.master_state,
            "statement": self.statement,
            "current_market_state": self.current_market_state,
            "current_direction": self.current_direction,
            "previous_market_state": self.previous_market_state,
            "transition_state": self.transition_state,
            "preliminary_strategy": self.preliminary_strategy,
            "thesis_alignment": self.thesis_alignment,
            "historical_alignment": self.historical_alignment,
            "experience_state": self.experience_state,
            "behaviour_state": self.behaviour_state,
            "risk_state": self.risk_state,
            "convergence_score": self.convergence_score,
            "contradiction_score": self.contradiction_score,
            "uncertainty_score": self.uncertainty_score,
            "continuity_score": self.continuity_score,
            "evidence_coverage": self.evidence_coverage,
            "dimensions": [item.to_dict() for item in self.dimensions],
            "supporting_dimensions": list(self.supporting_dimensions),
            "opposing_dimensions": list(self.opposing_dimensions),
            "unresolved_dimensions": list(self.unresolved_dimensions),
            "next_confirmation": list(self.next_confirmation),
            "warnings": list(self.warnings),
            "confidence": self.confidence,
            "authority": "AI_MASTER_PRE_JUDGEMENT_DOSSIER_SHADOW_MODE",
            "execution_instruction": "NONE",
            "automatic_decision_change": False,
            "automatic_confidence_change": False,
            "automatic_candidate_change": False,
            "automatic_rule_change": False,
            "automatic_weight_change": False,
            "automatic_threshold_change": False,
            "shadow_mode": True,
        }


class MasterIntelligenceEngine:
    """Build one deterministic, bounded synthesis before AI_MASTER judgement."""

    VERSION = "V49.3_MASTER_INTELLIGENCE_SHADOW_DOSSIER"
    HISTORY_KEY = "v49_master_intelligence_history"

    _DIRECTIONAL_BRANCHES: Tuple[Tuple[str, float], ...] = (
        ("PRICE_ACTION", 1.35),
        ("OPTION", 1.20),
        ("MARKET_BEHAVIOUR", 1.00),
        ("SMART_MONEY", 1.05),
        ("HEAVYWEIGHT_INTELLIGENCE", 0.90),
        ("MARKET_JOURNEY", 0.75),
        ("MARKET_PSYCHOLOGY", 0.55),
        ("TIME_INTELLIGENCE", 0.45),
    )

    def __init__(self, *, history_limit: int = 12) -> None:
        self.history_limit = max(4, min(int(history_limit), 24))

    def evaluate(
        self,
        *,
        state: MutableMapping[str, Any],
        snapshot_id: str,
        current_price: float,
        current_change_pct: float,
        co_case_file: Any,
        branch_reports: Mapping[str, Any],
        experience: Optional[Mapping[str, Any]] = None,
        replay: Optional[Mapping[str, Any]] = None,
    ) -> MasterIntelligenceReport:
        dimensions = self._dimensions(branch_reports, co_case_file)
        direction, convergence, contradiction, supporting, opposing, unresolved = self._synthesis(dimensions)
        experience_view = dict(experience or {})
        replay_view = dict(replay or {})
        historical_alignment = str(
            replay_view.get("historical_alignment", experience_view.get("historical_alignment", "INSUFFICIENT_HISTORY"))
        ).upper()
        experience_state = str(experience_view.get("experience_state", "COLLECTING_COMPLETED_CASES")).upper()
        behaviour_state = self._behaviour_state(branch_reports)
        risk_state = self._risk_state(branch_reports, co_case_file)
        preliminary_strategy = self._preliminary_strategy(branch_reports)
        thesis_alignment = self._thesis_alignment(preliminary_strategy, direction, historical_alignment)

        history = self._history(state)
        previous = history[-1] if history else None
        transition, continuity, previous_state = self._transition(
            previous=previous,
            direction=direction,
            convergence=convergence,
            contradiction=contradiction,
            risk_state=risk_state,
            current_price=current_price,
        )
        coverage = round(min(100.0, len([d for d in dimensions if d.direction != "NEUTRAL"]) / 10.0 * 100.0), 1)
        uncertainty = self._uncertainty(
            dimensions=dimensions,
            contradiction=contradiction,
            coverage=coverage,
            historical_alignment=historical_alignment,
            risk_state=risk_state,
            co_case_file=co_case_file,
        )
        master_state = self._master_state(
            convergence=convergence,
            contradiction=contradiction,
            coverage=coverage,
            historical_alignment=historical_alignment,
            risk_state=risk_state,
        )
        current_market_state = self._market_state(direction, convergence, contradiction, risk_state)
        confirmations = self._next_confirmation(
            direction=direction,
            transition=transition,
            historical_alignment=historical_alignment,
            risk_state=risk_state,
            unresolved=unresolved,
            thesis_alignment=thesis_alignment,
        )
        warnings = self._warnings(
            coverage=coverage,
            historical_alignment=historical_alignment,
            experience_state=experience_state,
            contradiction=contradiction,
        )
        confidence = self._confidence(
            coverage=coverage,
            convergence=convergence,
            contradiction=contradiction,
            continuity=continuity,
            historical_alignment=historical_alignment,
        )
        statement = (
            f"{master_state}: {direction} synthesis with {convergence:.0f}% convergence, "
            f"{contradiction:.0f}% contradiction and {historical_alignment} historical context."
        )
        report = MasterIntelligenceReport(
            snapshot_id=str(snapshot_id or "UNKNOWN"),
            version=self.VERSION,
            master_state=master_state,
            statement=statement,
            current_market_state=current_market_state,
            current_direction=direction,
            previous_market_state=previous_state,
            transition_state=transition,
            preliminary_strategy=preliminary_strategy,
            thesis_alignment=thesis_alignment,
            historical_alignment=historical_alignment,
            experience_state=experience_state,
            behaviour_state=behaviour_state,
            risk_state=risk_state,
            convergence_score=round(convergence, 1),
            contradiction_score=round(contradiction, 1),
            uncertainty_score=round(uncertainty, 1),
            continuity_score=round(continuity, 1),
            evidence_coverage=coverage,
            dimensions=dimensions[:12],
            supporting_dimensions=supporting[:8],
            opposing_dimensions=opposing[:8],
            unresolved_dimensions=unresolved[:8],
            next_confirmation=confirmations[:6],
            warnings=warnings[:5],
            confidence=round(confidence, 1),
        )
        self._store(
            state,
            {
                "snapshot_id": report.snapshot_id,
                "price": round(self._number(current_price), 2),
                "change_pct": round(self._number(current_change_pct), 3),
                "direction": direction,
                "master_state": master_state,
                "convergence": report.convergence_score,
                "contradiction": report.contradiction_score,
                "risk_state": risk_state,
            },
        )
        return report

    def _dimensions(self, reports: Mapping[str, Any], co_case_file: Any) -> List[IntelligenceDimension]:
        output: List[IntelligenceDimension] = []
        for name, _weight in self._DIRECTIONAL_BRANCHES:
            report = reports.get(name)
            summary, facts, confidence, branch_vote = self._report_view(report)
            direction = branch_vote if branch_vote in {"BULLISH", "BEARISH"} else self._infer_direction(summary + " " + str(facts))
            output.append(IntelligenceDimension(name, direction, confidence, summary[:220], "DIRECTION"))

        consensus = str(getattr(co_case_file, "consensus_direction", "NEUTRAL") or "NEUTRAL").upper()
        if consensus not in DIRECTIONS:
            consensus = "NEUTRAL"
        output.append(IntelligenceDimension(
            "CO_CONSENSUS", consensus, self._number(getattr(co_case_file, "case_strength", 0)),
            str(getattr(co_case_file, "court_brief", "CO case file unavailable"))[:220], "AUTHORITY_CONTEXT",
        ))

        strategy = reports.get("STRATEGY")
        summary, facts, confidence, _vote = self._report_view(strategy)
        action = self._strategy_from_text(summary + " " + str(facts))
        output.append(IntelligenceDimension(
            "STRATEGY_THESIS", self._action_direction(action), confidence,
            f"Preliminary strategy: {action}", "THESIS_CONTEXT",
        ))
        return output

    def _synthesis(
        self, dimensions: Sequence[IntelligenceDimension]
    ) -> Tuple[str, float, float, List[str], List[str], List[str]]:
        weights = dict(self._DIRECTIONAL_BRANCHES)
        weights.update({"CO_CONSENSUS": 1.40, "STRATEGY_THESIS": 1.25})
        bullish = bearish = range_score = total = 0.0
        for item in dimensions:
            weight = weights.get(item.name, 0.5) * max(0.30, item.confidence / 100.0)
            if item.direction == "BULLISH":
                bullish += weight
                total += weight
            elif item.direction == "BEARISH":
                bearish += weight
                total += weight
            elif item.direction == "RANGE":
                range_score += weight
                total += weight
        if total <= 0.01:
            return "NEUTRAL", 0.0, 0.0, [], [], [item.name for item in dimensions]

        scores = {"BULLISH": bullish, "BEARISH": bearish, "RANGE": range_score}
        ordered = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
        direction, top = ordered[0]
        second = ordered[1][1]
        convergence = top / total * 100.0
        contradiction = second / total * 100.0
        if top <= 0.01 or convergence < 42.0:
            direction = "CONFLICTED"

        supporting: List[str] = []
        opposing: List[str] = []
        unresolved: List[str] = []
        for item in dimensions:
            label = f"{item.name}: {item.direction} ({item.confidence:.0f}%)"
            if item.direction == "NEUTRAL":
                unresolved.append(label)
            elif direction == "CONFLICTED":
                opposing.append(label)
            elif item.direction == direction:
                supporting.append(label)
            else:
                opposing.append(label)
        return direction, convergence, contradiction, supporting, opposing, unresolved

    def _transition(
        self,
        *,
        previous: Optional[Mapping[str, Any]],
        direction: str,
        convergence: float,
        contradiction: float,
        risk_state: str,
        current_price: float,
    ) -> Tuple[str, float, str]:
        if not previous:
            return "FIRST_OBSERVATION", 0.0, "NO_PREVIOUS_MASTER_STATE"
        old_direction = str(previous.get("direction", "NEUTRAL"))
        old_convergence = self._number(previous.get("convergence", 0))
        old_contradiction = self._number(previous.get("contradiction", 0))
        old_risk = str(previous.get("risk_state", "NORMAL_RISK"))
        previous_state = str(previous.get("master_state", "UNKNOWN"))
        if old_direction in {"BULLISH", "BEARISH"} and direction in {"BULLISH", "BEARISH"} and old_direction != direction:
            transition = "DIRECTION_REVERSAL"
        elif risk_state == "HIGH_RISK" and old_risk != "HIGH_RISK":
            transition = "RISK_RISING"
        elif contradiction >= old_contradiction + 12:
            transition = "CONFLICT_RISING"
        elif direction == old_direction and convergence >= old_convergence + 8:
            transition = "THESIS_STRENGTHENING"
        elif direction == old_direction and convergence <= old_convergence - 8:
            transition = "THESIS_WEAKENING"
        elif direction == old_direction:
            transition = "STATE_STABLE"
        else:
            transition = "STATE_CHANGED"
        direction_match = 100.0 if direction == old_direction else (35.0 if "CONFLICTED" in {direction, old_direction} else 0.0)
        convergence_match = max(0.0, 100.0 - abs(convergence - old_convergence) * 2.0)
        price_move = abs(self._number(current_price) - self._number(previous.get("price", current_price)))
        price_continuity = max(0.0, 100.0 - min(price_move, 100.0))
        continuity = direction_match * 0.55 + convergence_match * 0.30 + price_continuity * 0.15
        return transition, max(0.0, min(100.0, continuity)), previous_state

    def _uncertainty(
        self,
        *,
        dimensions: Sequence[IntelligenceDimension],
        contradiction: float,
        coverage: float,
        historical_alignment: str,
        risk_state: str,
        co_case_file: Any,
    ) -> float:
        neutral = sum(item.direction == "NEUTRAL" for item in dimensions) / max(1, len(dimensions)) * 100.0
        missing_history = 25.0 if historical_alignment in {"INSUFFICIENT_HISTORY", "COLLECTING", "UNKNOWN"} else 0.0
        risk_add = 20.0 if risk_state == "HIGH_RISK" else (8.0 if risk_state == "ELEVATED_RISK" else 0.0)
        co_hold = 18.0 if not bool(getattr(co_case_file, "accepted", False)) else 0.0
        return max(0.0, min(100.0, contradiction * 0.45 + neutral * 0.20 + (100 - coverage) * 0.15 + missing_history + risk_add + co_hold))

    @staticmethod
    def _master_state(*, convergence: float, contradiction: float, coverage: float, historical_alignment: str, risk_state: str) -> str:
        if coverage < 35:
            return "COLLECTING_CONTEXT"
        if risk_state == "HIGH_RISK":
            return "RISK_DOMINANT"
        if historical_alignment in {"HISTORICAL_WARNING", "REPLAY_WARNING"} and convergence >= 55:
            return "HISTORY_WARNING"
        if contradiction >= 42 or convergence < 46:
            return "CONFLICTED_EVIDENCE"
        if convergence >= 72 and contradiction <= 22:
            return "STRONG_CONVERGENCE"
        if convergence >= 56:
            return "MODERATE_CONVERGENCE"
        return "MIXED_CONTEXT"

    @staticmethod
    def _market_state(direction: str, convergence: float, contradiction: float, risk_state: str) -> str:
        if risk_state == "HIGH_RISK":
            return f"{direction}_WITH_HIGH_RISK"
        if contradiction >= 42:
            return "CROSS_DEPARTMENT_CONFLICT"
        if convergence >= 72:
            return f"{direction}_BROAD_ALIGNMENT"
        return f"{direction}_PARTIAL_ALIGNMENT"

    def _risk_state(self, reports: Mapping[str, Any], co_case_file: Any) -> str:
        texts: List[str] = []
        for name in ("RISK", "NEWS_INTELLIGENCE", "MARKET_PSYCHOLOGY", "MARKET_BEHAVIOUR"):
            summary, facts, _confidence, _vote = self._report_view(reports.get(name))
            texts.append(summary + " " + str(facts))
        text = " ".join(texts).lower()
        # Remove common negated/low-risk phrases before token scoring so that
        # "no high-impact event" or "low panic risk" is not read as danger.
        for phrase in (
            "no high impact", "low impact", "not high risk", "no high risk",
            "no panic", "panic risk low", "no shock", "shock risk low",
            "no fake breakout", "fake breakout no", "reversal risk low",
        ):
            text = text.replace(phrase, "")
        conflicts = len(list(getattr(co_case_file, "conflicts", []) or []))
        high_tokens = ("high impact", "high risk", "risk blocked", "stop sweep", "market shock", "extreme")
        elevated_tokens = ("panic", "medium impact", "elevated", "trap", "fake", "exhaust", "caution", "volatile")
        if sum(token in text for token in high_tokens) >= 2 or conflicts >= 4:
            return "HIGH_RISK"
        if any(token in text for token in high_tokens) or sum(token in text for token in elevated_tokens) >= 2 or conflicts >= 2:
            return "ELEVATED_RISK"
        return "NORMAL_RISK"

    def _behaviour_state(self, reports: Mapping[str, Any]) -> str:
        summary, facts, _confidence, _vote = self._report_view(reports.get("MARKET_BEHAVIOUR"))
        text = (summary + " " + str(facts)).lower()
        if "breakout" in text:
            return "BREAKOUT_BEHAVIOUR"
        if "reversal" in text or "reject" in text:
            return "REVERSAL_BEHAVIOUR"
        if "range" in text or "sideways" in text:
            return "RANGE_BEHAVIOUR"
        if "volatile" in text or "whipsaw" in text:
            return "VOLATILE_BEHAVIOUR"
        return "BEHAVIOUR_UNCLASSIFIED"

    def _preliminary_strategy(self, reports: Mapping[str, Any]) -> str:
        summary, facts, _confidence, _vote = self._report_view(reports.get("STRATEGY"))
        return self._strategy_from_text(summary + " " + str(facts))

    @staticmethod
    def _thesis_alignment(strategy: str, direction: str, historical_alignment: str) -> str:
        target = MasterIntelligenceEngine._action_direction(strategy)
        history_warning = historical_alignment in {"HISTORICAL_WARNING", "REPLAY_WARNING"}
        if strategy == "WAIT":
            return "WAIT_CONTEXT_SUPPORTED" if direction in {"CONFLICTED", "NEUTRAL"} or history_warning else "WAIT_DESPITE_DIRECTIONAL_CONTEXT"
        if target == direction and not history_warning:
            return "THESIS_SUPPORTED"
        if target == direction and history_warning:
            return "THESIS_SUPPORTED_WITH_HISTORY_WARNING"
        if direction in {"CONFLICTED", "NEUTRAL"}:
            return "THESIS_UNCONFIRMED"
        return "THESIS_CONFLICTED"

    @staticmethod
    def _next_confirmation(*, direction: str, transition: str, historical_alignment: str, risk_state: str, unresolved: Sequence[str], thesis_alignment: str) -> List[str]:
        items: List[str] = []
        if direction == "BULLISH":
            items.append("Require price/option follow-through above the nearest resistance without immediate rejection.")
        elif direction == "BEARISH":
            items.append("Require price/option follow-through below the nearest support without immediate recovery.")
        elif direction == "RANGE":
            items.append("Require both barriers to continue holding before treating range behaviour as stable.")
        else:
            items.append("Require price, option flow and smart-money evidence to resolve directional conflict.")
        if transition in {"DIRECTION_REVERSAL", "CONFLICT_RISING", "RISK_RISING"}:
            items.append("Require one additional verified snapshot before trusting the changed master state.")
        if historical_alignment in {"HISTORICAL_WARNING", "REPLAY_WARNING", "MIXED_HISTORICAL_EVIDENCE"}:
            items.append("Require current-market evidence to disprove the historical warning.")
        if risk_state != "NORMAL_RISK":
            items.append("Require risk/news/volatility state to stabilise before execution confidence increases.")
        if thesis_alignment in {"THESIS_CONFLICTED", "THESIS_UNCONFIRMED"}:
            items.append("Require the preliminary strategy thesis to align with the dominant current evidence.")
        if unresolved:
            items.append("Resolve neutral or missing dimensions: " + ", ".join(item.split(":", 1)[0] for item in list(unresolved)[:3]) + ".")
        return items

    @staticmethod
    def _warnings(*, coverage: float, historical_alignment: str, experience_state: str, contradiction: float) -> List[str]:
        warnings: List[str] = []
        if coverage < 60:
            warnings.append("Master dossier coverage is incomplete; keep interpretation provisional.")
        if historical_alignment in {"INSUFFICIENT_HISTORY", "COLLECTING", "UNKNOWN"}:
            warnings.append("Historical comparison is immature until more completed cases exist.")
        if experience_state == "COLLECTING_COMPLETED_CASES":
            warnings.append("Experience Engine is still collecting validated outcomes.")
        if contradiction >= 42:
            warnings.append("Cross-department contradiction is material.")
        warnings.append("V49 is shadow mode: synthesis cannot alter the live AI_MASTER judgement.")
        return warnings

    @staticmethod
    def _confidence(*, coverage: float, convergence: float, contradiction: float, continuity: float, historical_alignment: str) -> float:
        history_bonus = 8.0 if historical_alignment in {"HISTORICAL_SUPPORT", "STRONG_REPLAY_MATCH"} else 0.0
        value = 18.0 + coverage * 0.28 + convergence * 0.32 + continuity * 0.12 + history_bonus - contradiction * 0.20
        return max(10.0, min(92.0, value))

    def _report_view(self, report: Any) -> Tuple[str, Mapping[str, Any], float, str]:
        if report is None:
            return "No report", {}, 0.0, "NEUTRAL"
        if isinstance(report, Mapping):
            summary = str(report.get("summary", "No report"))
            facts = report.get("facts", report.get("details", {}))
            confidence = self._number(report.get("confidence", 0))
            vote = str(report.get("branch_vote", "NEUTRAL")).upper()
        else:
            summary = str(getattr(report, "summary", "No report"))
            facts = getattr(report, "facts", getattr(report, "details", {}))
            confidence = self._number(getattr(report, "confidence", 0))
            vote = str(getattr(report, "branch_vote", "NEUTRAL")).upper()
        return summary, facts if isinstance(facts, Mapping) else {}, max(0.0, min(100.0, confidence)), vote

    @staticmethod
    def _infer_direction(text: str) -> str:
        text = str(text).lower()
        bullish_tokens = (
            "bullish", "uptrend", "buying", "long buildup", "long build-up", "short covering",
            "risk_on", "risk on", "broad_upside", "upside participation", "sell pe", "support holding",
        )
        bearish_tokens = (
            "bearish", "downtrend", "selling", "long unwinding", "short buildup", "short build-up",
            "risk_off", "risk off", "broad_downside", "downside participation", "sell ce", "resistance holding",
        )
        range_tokens = ("range", "sideways", "iron condor", "balanced observation", "neutral market")
        bull = sum(token in text for token in bullish_tokens)
        bear = sum(token in text for token in bearish_tokens)
        rang = sum(token in text for token in range_tokens)
        if bull >= bear + 1 and bull >= rang:
            return "BULLISH"
        if bear >= bull + 1 and bear >= rang:
            return "BEARISH"
        if rang > max(bull, bear):
            return "RANGE"
        if bull and bear:
            return "CONFLICTED"
        return "NEUTRAL"

    @staticmethod
    def _strategy_from_text(text: str) -> str:
        upper = str(text).upper()
        for action in ("IRON CONDOR", "SELL PE", "SELL CE", "WAIT"):
            if action in upper:
                return action
        return "WAIT"

    @staticmethod
    def _action_direction(action: str) -> str:
        return {
            "SELL PE": "BULLISH",
            "SELL CE": "BEARISH",
            "IRON CONDOR": "RANGE",
            "WAIT": "NEUTRAL",
        }.get(str(action).upper(), "NEUTRAL")

    def _history(self, state: Mapping[str, Any]) -> List[Dict[str, Any]]:
        value = state.get(self.HISTORY_KEY, [])
        if not isinstance(value, list):
            return []
        return [dict(item) for item in value if isinstance(item, Mapping)][-self.history_limit:]

    def _store(self, state: MutableMapping[str, Any], record: Dict[str, Any]) -> None:
        history = self._history(state)
        snapshot_id = str(record.get("snapshot_id", "UNKNOWN"))
        if history and str(history[-1].get("snapshot_id", "")) == snapshot_id:
            history[-1] = record
        elif not any(str(item.get("snapshot_id", "")) == snapshot_id for item in history):
            history.append(record)
        state[self.HISTORY_KEY] = history[-self.history_limit:]

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
