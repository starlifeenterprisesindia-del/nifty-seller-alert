"""
reasoning_engine.py
Version: V47.3
Role: AI_MASTER post-judgement explanation certificate.

This module is explanation-only. It consumes the already-computed AI_MASTER
judgement and CO case file. It cannot change action, confidence, candidates,
rules, weights, thresholds, or execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, List, Mapping, Optional, Sequence


ACTIONS = ("WAIT", "SELL CE", "SELL PE", "IRON CONDOR")


@dataclass(frozen=True)
class ReasoningCertificate:
    version: str
    decision: str
    decision_status: str
    primary_reason: str
    supporting_evidence: List[str] = field(default_factory=list)
    opposing_evidence: List[str] = field(default_factory=list)
    uncertainty: List[str] = field(default_factory=list)
    rejected_alternatives: Dict[str, str] = field(default_factory=dict)
    risk_gates: List[str] = field(default_factory=list)
    evidence_balance: Dict[str, Any] = field(default_factory=dict)
    confidence_explanation: str = ""
    next_confirmation: List[str] = field(default_factory=list)
    authority_trace: List[str] = field(default_factory=list)
    decision_fingerprint: str = ""
    explanation_only: bool = True

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "decision": self.decision,
            "decision_status": self.decision_status,
            "primary_reason": self.primary_reason,
            "supporting_evidence": list(self.supporting_evidence),
            "opposing_evidence": list(self.opposing_evidence),
            "uncertainty": list(self.uncertainty),
            "rejected_alternatives": dict(self.rejected_alternatives),
            "risk_gates": list(self.risk_gates),
            "evidence_balance": dict(self.evidence_balance),
            "confidence_explanation": self.confidence_explanation,
            "next_confirmation": list(self.next_confirmation),
            "authority_trace": list(self.authority_trace),
            "decision_fingerprint": self.decision_fingerprint,
            "explanation_only": True,
            "automatic_decision_change": False,
            "automatic_rule_change": False,
        }


class ReasoningEngine:
    """Build one bounded, deterministic explanation after AI_MASTER decides."""

    VERSION = "V47.3_REASONING_CERTIFICATE"

    def explain(
        self,
        *,
        snapshot_id: str,
        action: str,
        confidence: float,
        trade_allowed: bool,
        market_bias: str,
        strategy_scores: Mapping[str, float],
        evidence: Sequence[str],
        warnings: Sequence[str],
        data_quality_ok: bool,
        risk_block: bool,
        score_gap: float,
        top_score: float,
        approved_candidate: Optional[Mapping[str, Any]],
        co_case_file: Any = None,
    ) -> ReasoningCertificate:
        action = action if action in ACTIONS else "WAIT"
        scores = {name: self._number(strategy_scores.get(name, 0.0)) for name in ACTIONS}
        case = self._case_view(co_case_file)

        all_evidence = self._unique(
            list(evidence)
            + list(case["accepted_evidence"])
            + ([case["court_brief"]] if case["court_brief"] else [])
        )
        supporting, opposing = self._split_evidence(
            action=action,
            market_bias=market_bias,
            items=all_evidence,
            conflicts=case["conflicts"],
            rejected=case["rejected_evidence"],
        )
        uncertainty = self._uncertainty(
            warnings=warnings,
            case=case,
            data_quality_ok=data_quality_ok,
            risk_block=risk_block,
            score_gap=score_gap,
            approved_candidate=approved_candidate,
            action=action,
            trade_allowed=trade_allowed,
        )
        primary_reason = self._primary_reason(
            action=action,
            trade_allowed=trade_allowed,
            market_bias=market_bias,
            risk_block=risk_block,
            data_quality_ok=data_quality_ok,
            top_score=top_score,
            score_gap=score_gap,
            co_accepted=case["accepted"],
            supporting=supporting,
            uncertainty=uncertainty,
        )
        rejected_alternatives = self._rejected_alternatives(
            selected=action,
            scores=scores,
            trade_allowed=trade_allowed,
            risk_block=risk_block,
            score_gap=score_gap,
            approved_candidate=approved_candidate,
        )
        risk_gates = self._risk_gates(
            warnings=warnings,
            risk_block=risk_block,
            data_quality_ok=data_quality_ok,
            co_accepted=case["accepted"],
        )
        balance = {
            "supporting_count": len(supporting),
            "opposing_count": len(opposing),
            "uncertainty_count": len(uncertainty),
            "co_case_strength": round(case["case_strength"], 1),
            "co_agreement": round(case["agreement_score"], 1),
            "strategy_top_score": round(top_score, 1),
            "strategy_score_gap": round(score_gap, 1),
            "market_bias": market_bias,
        }
        confidence_explanation = self._confidence_explanation(
            confidence=confidence,
            top_score=top_score,
            score_gap=score_gap,
            case_strength=case["case_strength"],
            supporting=len(supporting),
            opposing=len(opposing),
            uncertainty=len(uncertainty),
        )
        next_confirmation = self._next_confirmation(
            action=action,
            trade_allowed=trade_allowed,
            risk_block=risk_block,
            data_quality_ok=data_quality_ok,
            score_gap=score_gap,
            approved_candidate=approved_candidate,
            opposing=opposing,
            uncertainty=uncertainty,
        )
        fingerprint_source = "|".join(
            [
                str(snapshot_id), action, f"{confidence:.1f}", market_bias,
                f"{top_score:.1f}", f"{score_gap:.1f}", str(case["case_id"]),
                ";".join(supporting[:4]), ";".join(uncertainty[:4]),
            ]
        )
        fingerprint = sha256(fingerprint_source.encode("utf-8", errors="ignore")).hexdigest()[:16].upper()

        return ReasoningCertificate(
            version=self.VERSION,
            decision=action,
            decision_status="EXECUTION_APPROVED" if trade_allowed else "WAIT_OR_BLOCKED",
            primary_reason=primary_reason,
            supporting_evidence=supporting[:6],
            opposing_evidence=opposing[:6],
            uncertainty=uncertainty[:6],
            rejected_alternatives=rejected_alternatives,
            risk_gates=risk_gates[:6],
            evidence_balance=balance,
            confidence_explanation=confidence_explanation,
            next_confirmation=next_confirmation[:5],
            authority_trace=[
                "ONE VERIFIED SNAPSHOT",
                "DSP DEPARTMENT REPORTS",
                "CO CROSS-EXAMINED CASE FILE",
                "AI_MASTER FINAL JUDGEMENT",
                "V47 EXPLANATION CERTIFICATE (NO FEEDBACK TO DECISION)",
            ],
            decision_fingerprint=fingerprint,
        )

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _read(obj: Any, key: str, default: Any) -> Any:
        if obj is None:
            return default
        if isinstance(obj, Mapping):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _case_view(self, case: Any) -> Dict[str, Any]:
        return {
            "accepted": bool(self._read(case, "accepted", True)),
            "case_id": str(self._read(case, "case_id", "")),
            "case_strength": self._number(self._read(case, "case_strength", 0.0)),
            "agreement_score": self._number(self._read(case, "agreement_score", 0.0)),
            "court_brief": str(self._read(case, "court_brief", ""))[:300],
            "accepted_evidence": list(self._read(case, "accepted_evidence", []) or []),
            "rejected_evidence": list(self._read(case, "rejected_evidence", []) or []),
            "missing_evidence": list(self._read(case, "missing_evidence", []) or []),
            "conflicts": list(self._read(case, "conflicts", []) or []),
            "warnings": list(self._read(case, "warnings", []) or []),
        }

    @staticmethod
    def _unique(items: Sequence[Any]) -> List[str]:
        output: List[str] = []
        seen = set()
        for item in items:
            text = str(item or "").strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            output.append(text[:260])
        return output

    def _split_evidence(
        self,
        *,
        action: str,
        market_bias: str,
        items: Sequence[str],
        conflicts: Sequence[Any],
        rejected: Sequence[Any],
    ) -> tuple[List[str], List[str]]:
        bullish = ("bullish", "pe support", "buying", "supporting market", "uptrend", "risk_on", "long build")
        bearish = ("bearish", "ce resistance", "selling", "pressuring market", "downtrend", "risk_off", "short build")
        neutral = ("range", "neutral", "balanced", "iron condor", "low energy")
        support_tokens = neutral if action == "IRON CONDOR" else bullish if action == "SELL PE" else bearish if action == "SELL CE" else ()
        oppose_tokens = bearish if action == "SELL PE" else bullish if action == "SELL CE" else ()

        supporting: List[str] = []
        opposing: List[str] = []
        for item in items:
            low = item.lower()
            if action == "WAIT":
                if any(token in low for token in ("conflict", "risk", "hold", "missing", "caution", "neutral")):
                    supporting.append(item)
                elif len(supporting) < 3:
                    supporting.append(item)
            else:
                if any(token in low for token in support_tokens):
                    supporting.append(item)
                elif any(token in low for token in oppose_tokens):
                    opposing.append(item)
                elif len(supporting) < 3:
                    supporting.append(item)

        opposing.extend(str(x)[:260] for x in conflicts if x)
        opposing.extend(str(x)[:260] for x in rejected if x)
        if market_bias == "NEUTRAL" and action in {"SELL CE", "SELL PE"}:
            opposing.append("Market bias remained neutral against a directional strategy.")
        return self._unique(supporting), self._unique(opposing)

    def _uncertainty(
        self,
        *,
        warnings: Sequence[Any],
        case: Mapping[str, Any],
        data_quality_ok: bool,
        risk_block: bool,
        score_gap: float,
        approved_candidate: Optional[Mapping[str, Any]],
        action: str,
        trade_allowed: bool,
    ) -> List[str]:
        items = [str(x) for x in warnings if x]
        items.extend(str(x) for x in case["warnings"] if x)
        items.extend(f"Missing evidence: {x}" for x in case["missing_evidence"] if x)
        if not data_quality_ok:
            items.append("Verified data-quality gate is not clear.")
        if not case["accepted"]:
            items.append("CO has not accepted the case for execution.")
        if risk_block:
            items.append("Hard risk gate is active.")
        if score_gap < 6.0:
            items.append(f"Strategy separation is weak ({score_gap:.1f} points).")
        if trade_allowed and action != "WAIT" and not approved_candidate:
            items.append("Trade thesis passed but no candidate cleared the approval threshold.")
        return self._unique(items)

    @staticmethod
    def _primary_reason(
        *,
        action: str,
        trade_allowed: bool,
        market_bias: str,
        risk_block: bool,
        data_quality_ok: bool,
        top_score: float,
        score_gap: float,
        co_accepted: bool,
        supporting: Sequence[str],
        uncertainty: Sequence[str],
    ) -> str:
        if action == "WAIT" or not trade_allowed:
            blockers: List[str] = []
            if not data_quality_ok:
                blockers.append("data-quality gate")
            if not co_accepted:
                blockers.append("CO case hold")
            if risk_block:
                blockers.append("hard risk gate")
            if top_score < 65.0:
                blockers.append(f"top strategy score {top_score:.1f}<65")
            if score_gap < 6.0:
                blockers.append(f"score gap {score_gap:.1f}<6")
            if uncertainty and not blockers:
                blockers.append("unresolved uncertainty")
            return "WAIT because " + ", ".join(blockers or ["execution confirmation is incomplete"]) + "."
        lead = supporting[0] if supporting else f"{market_bias.lower()} evidence alignment"
        return f"{action} because CO-cleared evidence supports {market_bias.lower()} bias; lead evidence: {lead}."

    @staticmethod
    def _rejected_alternatives(
        *,
        selected: str,
        scores: Mapping[str, float],
        trade_allowed: bool,
        risk_block: bool,
        score_gap: float,
        approved_candidate: Optional[Mapping[str, Any]],
    ) -> Dict[str, str]:
        selected_score = float(scores.get(selected, 0.0))
        result: Dict[str, str] = {}
        for alternative in ACTIONS:
            if alternative == selected:
                continue
            alt_score = float(scores.get(alternative, 0.0))
            if selected == "WAIT":
                reason = f"{alternative} not approved: score {alt_score:.1f}"
                if risk_block:
                    reason += ", hard risk gate active"
                elif score_gap < 6.0:
                    reason += ", insufficient separation"
            else:
                reason = f"Lower strategy rank ({alt_score:.1f} vs selected {selected_score:.1f})"
                if alternative == "WAIT" and trade_allowed:
                    reason = "WAIT rejected because execution gates cleared with sufficient strategy separation."
            result[alternative] = reason[:220]
        return result

    @staticmethod
    def _risk_gates(*, warnings: Sequence[Any], risk_block: bool, data_quality_ok: bool, co_accepted: bool) -> List[str]:
        gates = [str(x) for x in warnings if x]
        gates.append("Hard risk gate: BLOCKED" if risk_block else "Hard risk gate: CLEAR")
        gates.append("Data-quality gate: CLEAR" if data_quality_ok else "Data-quality gate: NOT CLEAR")
        gates.append("CO authority gate: CLEAR" if co_accepted else "CO authority gate: HOLD")
        return ReasoningEngine._unique(gates)

    @staticmethod
    def _confidence_explanation(
        *,
        confidence: float,
        top_score: float,
        score_gap: float,
        case_strength: float,
        supporting: int,
        opposing: int,
        uncertainty: int,
    ) -> str:
        return (
            f"Final confidence {confidence:.1f}% reflects strategy score {top_score:.1f}, "
            f"score separation {score_gap:.1f}, CO case strength {case_strength:.1f}, "
            f"and evidence balance {supporting} support / {opposing} oppose / {uncertainty} uncertain."
        )

    @staticmethod
    def _next_confirmation(
        *,
        action: str,
        trade_allowed: bool,
        risk_block: bool,
        data_quality_ok: bool,
        score_gap: float,
        approved_candidate: Optional[Mapping[str, Any]],
        opposing: Sequence[str],
        uncertainty: Sequence[str],
    ) -> List[str]:
        items: List[str] = []
        if not data_quality_ok:
            items.append("Wait for one clean verified snapshot.")
        if risk_block:
            items.append("Wait for the hard risk condition to clear.")
        if score_gap < 6.0:
            items.append("Require stronger separation between the top two strategies.")
        if action != "WAIT" and trade_allowed and not approved_candidate:
            items.append("Require a candidate score of at least 65 before execution.")
        if opposing:
            items.append("Check whether opposing evidence persists on the next snapshot.")
        if uncertainty:
            items.append("Resolve the highest-priority uncertainty before increasing conviction.")
        if not items:
            items.append("Monitor next-snapshot persistence and barrier reaction; do not create a second decision.")
        return ReasoningEngine._unique(items)
