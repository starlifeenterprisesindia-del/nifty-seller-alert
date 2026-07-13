"""
ai_master.py
Version : V50.3
Role    : Final AI Authority
Status  : V50 Final Headquarters authority lock

Golden Rules:
- Only AI_MASTER can issue WAIT / SELL CE / SELL PE / IRON CONDOR.
- Departments provide reports; they never become final decision owners.
- One execution per verified snapshot.
- No background loop, timer, thread, or polling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from reasoning_engine import ReasoningEngine


ALLOWED_ACTIONS = {"WAIT", "SELL CE", "SELL PE", "IRON CONDOR"}


@dataclass(frozen=True)
class AIMasterDecision:
    snapshot_id: str
    created_at: str
    action: str
    confidence: float
    trade_allowed: bool
    market_bias: str
    reason: str
    strategy_scores: Dict[str, float] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    approved_candidate: Optional[Dict[str, Any]] = None
    watchlist: Dict[str, Optional[Dict[str, Any]]] = field(default_factory=dict)
    trace: Dict[str, Any] = field(default_factory=dict)
    reasoning_report: Dict[str, Any] = field(default_factory=dict)


def _details(report: Any) -> Dict[str, Any]:
    if report is None:
        return {}
    if isinstance(report, Mapping):
        value = report.get("details", report)
        return dict(value) if isinstance(value, Mapping) else {}
    value = getattr(report, "details", None)
    return dict(value) if isinstance(value, Mapping) else {}


def _confidence(report: Any) -> float:
    if report is None:
        return 0.0
    if isinstance(report, Mapping):
        value = report.get("confidence", 0)
    else:
        value = getattr(report, "confidence", 0)
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _candidate_to_dict(candidate: Any) -> Optional[Dict[str, Any]]:
    if candidate is None:
        return None
    if isinstance(candidate, Mapping):
        return dict(candidate)
    result: Dict[str, Any] = {}
    for key in (
        "option_type", "strike", "premium", "score", "status",
        "reasons", "hedge_strike"
    ):
        if hasattr(candidate, key):
            result[key] = getattr(candidate, key)
    return result or None


class AIMaster:
    """
    Final authority. It consumes already-prepared department reports.

    Expected inputs:
    - one verified snapshot_id
    - price_report
    - option_report
    - behaviour_report
    - smart_money_report
    - risk_report
    - strategy_report
    - candidate_report
    """

    VERSION = "V50.5_RECOVERY_AND_DATA_INTEGRITY_AUTHORITY"

    def decide(
        self,
        *,
        snapshot_id: str,
        data_quality_ok: bool,
        price_report: Any,
        option_report: Any,
        behaviour_report: Any,
        smart_money_report: Any,
        risk_report: Any,
        strategy_report: Any,
        candidate_report: Any,
        co_case_file: Any = None,
        master_intelligence_report: Any = None,
    ) -> AIMasterDecision:
        warnings: List[str] = []
        evidence: List[str] = []

        co_accepted = True
        co_case_strength = 0.0
        co_case_id = ""
        if co_case_file is not None:
            co_accepted = bool(getattr(co_case_file, "accepted", True))
            co_case_strength = float(getattr(co_case_file, "case_strength", 0.0) or 0.0)
            co_case_id = str(getattr(co_case_file, "case_id", ""))
            if not co_accepted:
                warnings.append("CO case file on HOLD")

        if not snapshot_id:
            warnings.append("Missing snapshot ID")
        if not data_quality_ok:
            warnings.append("Data quality failed")

        strategy_scores, recommended = self._strategy_view(strategy_report)
        market_bias = self._market_bias(
            price_report=price_report,
            option_report=option_report,
            smart_money_report=smart_money_report,
        )

        evidence.extend(
            self._collect_evidence(
                price_report=price_report,
                option_report=option_report,
                behaviour_report=behaviour_report,
                smart_money_report=smart_money_report,
                risk_report=risk_report,
            )
        )

        risk_block, risk_warnings = self._risk_gate(
            risk_report=risk_report,
            behaviour_report=behaviour_report,
        )
        warnings.extend(risk_warnings)

        score_gap = self._score_gap(strategy_scores)
        top_score = max(strategy_scores.values(), default=0.0)

        # Trade permission is decided before candidate approval.
        trade_allowed = (
            data_quality_ok
            and co_accepted
            and not risk_block
            and recommended in {"SELL CE", "SELL PE", "IRON CONDOR"}
            and top_score >= 65.0
            and score_gap >= 6.0
        )

        action = recommended if trade_allowed else "WAIT"
        if action not in ALLOWED_ACTIONS:
            action = "WAIT"
            trade_allowed = False
            warnings.append("Invalid strategy action normalized to WAIT")

        watchlist = self._watchlist(candidate_report)
        approved_candidate = self._approve_candidate(
            action=action,
            trade_allowed=trade_allowed,
            candidate_report=candidate_report,
        )

        confidence = self._final_confidence(
            action=action,
            top_score=top_score,
            score_gap=score_gap,
            reports=(
                price_report,
                option_report,
                behaviour_report,
                smart_money_report,
                risk_report,
            ),
            warnings=warnings,
        )
        if co_case_file is not None:
            confidence = round(max(0.0, min(100.0, confidence * 0.75 + co_case_strength * 0.25)), 1)

        reason = self._reason(
            action=action,
            trade_allowed=trade_allowed,
            market_bias=market_bias,
            evidence=evidence,
            warnings=warnings,
        )

        # V47 explanation is generated only after the final judgement exists.
        # It is a read-only certificate and has no feedback path into action,
        # confidence, candidates, rules, thresholds, or execution permission.
        reasoning_report = ReasoningEngine().explain(
            snapshot_id=snapshot_id or "UNKNOWN",
            action=action,
            confidence=confidence,
            trade_allowed=trade_allowed,
            market_bias=market_bias,
            strategy_scores=strategy_scores,
            evidence=evidence,
            warnings=warnings,
            data_quality_ok=data_quality_ok,
            risk_block=risk_block,
            score_gap=score_gap,
            top_score=top_score,
            approved_candidate=approved_candidate,
            co_case_file=co_case_file,
        ).to_compact_dict()
        master_view = self._master_intelligence_view(master_intelligence_report)
        if master_view:
            reasoning_report["master_intelligence"] = master_view
            authority_trace = list(reasoning_report.get("authority_trace", []) or [])
            marker = "AI_MASTER V49 MASTER DOSSIER (SHADOW MODE)"
            if marker not in authority_trace:
                insert_at = max(0, len(authority_trace) - 1)
                authority_trace.insert(insert_at, marker)
            reasoning_report["authority_trace"] = authority_trace
        reason = str(reasoning_report.get("primary_reason", reason))

        return AIMasterDecision(
            snapshot_id=snapshot_id or "UNKNOWN",
            created_at=datetime.now(timezone.utc).isoformat(),
            action=action,
            confidence=confidence,
            trade_allowed=trade_allowed,
            market_bias=market_bias,
            reason=reason,
            strategy_scores=strategy_scores,
            evidence=evidence[:8],
            warnings=warnings[:8],
            approved_candidate=approved_candidate,
            watchlist=watchlist,
            trace={
                "version": self.VERSION,
                "score_gap": score_gap,
                "top_strategy_score": top_score,
                "data_quality_ok": bool(data_quality_ok),
                "risk_block": risk_block,
                "co_case_id": co_case_id,
                "co_case_strength": co_case_strength,
                "co_accepted": co_accepted,
                "reasoning_version": reasoning_report.get("version", ""),
                "reasoning_explanation_only": True,
                "master_intelligence_version": master_view.get("version", "") if master_view else "",
                "master_intelligence_state": master_view.get("master_state", "") if master_view else "",
                "master_intelligence_shadow_mode": True,
            },
            reasoning_report=reasoning_report,
        )

    @staticmethod
    def _master_intelligence_view(report: Any) -> Dict[str, Any]:
        if report is None:
            return {}
        if isinstance(report, Mapping):
            value = dict(report)
        elif hasattr(report, "to_compact_dict"):
            try:
                value = dict(report.to_compact_dict())
            except Exception:
                return {}
        else:
            return {}
        # Hard safety contract: V49 remains explanation/shadow context only.
        value["shadow_mode"] = True
        value["execution_instruction"] = "NONE"
        value["automatic_decision_change"] = False
        value["automatic_confidence_change"] = False
        value["automatic_candidate_change"] = False
        return value

    def _strategy_view(self, report: Any) -> tuple[Dict[str, float], str]:
        scores: Dict[str, float] = {}
        recommended = "WAIT"

        if isinstance(report, Mapping):
            recommended = str(
                report.get("recommended_strategy", report.get("action", "WAIT"))
            ).upper()
            raw = report.get("strategies", {})
        else:
            recommended = str(
                getattr(report, "recommended_strategy", "WAIT")
            ).upper()
            raw = getattr(report, "strategies", {})

        if isinstance(raw, Mapping):
            for name, item in raw.items():
                if isinstance(item, Mapping):
                    value = item.get("score", 0)
                else:
                    value = getattr(item, "score", 0)
                try:
                    scores[str(name).upper()] = round(
                        max(0.0, min(100.0, float(value))), 1
                    )
                except (TypeError, ValueError):
                    scores[str(name).upper()] = 0.0

        for name in ALLOWED_ACTIONS:
            scores.setdefault(name, 0.0)

        if recommended not in ALLOWED_ACTIONS:
            recommended = max(scores, key=scores.get, default="WAIT")

        return scores, recommended

    def _market_bias(
        self,
        *,
        price_report: Any,
        option_report: Any,
        smart_money_report: Any,
    ) -> str:
        bullish = 0
        bearish = 0

        price = _details(price_report)
        option = _details(option_report)
        money = _details(smart_money_report)

        trend = str(price.get("trend", {}).get("trend", ""))
        structure = str(price.get("trend", {}).get("structure", ""))
        if structure in {"BULLISH", "MIXED_BULLISH"} or ("Bullish" in trend and "Pullback" not in trend):
            bullish += 2
        if structure in {"BEARISH", "MIXED_BEARISH"} or ("Bearish" in trend and "Recovery" not in trend):
            bearish += 2

        # Current impulse is separate from the broader EMA structure. A strong
        # recovery neutralizes a stale bearish continuation reading.
        movement = price.get("movement", {}) if isinstance(price.get("movement", {}), Mapping) else {}
        phase = str(movement.get("phase", ""))
        if phase == "STRONG_RECOVERY":
            bullish += 3
        elif phase == "RECOVERY":
            bullish += 2
        elif phase == "STRONG_PULLBACK_DOWN":
            bearish += 3
        elif phase == "PULLBACK_DOWN":
            bearish += 2

        pcr = str(option.get("pcr", {}).get("sentiment", ""))
        if "Bullish" in pcr and "Extreme" not in pcr:
            bullish += 1
        elif "Bearish" in pcr:
            bearish += 1

        pressure = str(option.get("strike", {}).get("pressure", ""))
        if pressure == "PE Support":
            bullish += 1
        elif pressure == "CE Resistance":
            bearish += 1
        elif pressure == "Two-Sided Writing / Range":
            bullish += 1
            bearish += 1

        fii = str(money.get("fii", {}).get("fii", ""))
        heavy = str(money.get("heavyweights", {}).get("heavyweights", ""))
        if fii == "Buying":
            bullish += 1
        elif fii == "Selling":
            bearish += 1
        if heavy == "Supporting Market":
            bullish += 1
        elif heavy == "Pressuring Market":
            bearish += 1

        if bullish >= bearish + 2:
            return "BULLISH"
        if bearish >= bullish + 2:
            return "BEARISH"
        return "NEUTRAL"

    def _risk_gate(
        self,
        *,
        risk_report: Any,
        behaviour_report: Any,
    ) -> tuple[bool, List[str]]:
        warnings: List[str] = []
        risk = _details(risk_report)
        behaviour = _details(behaviour_report)

        high_vix = str(risk.get("vix", {}).get("risk", "")) == "High"
        high_news = str(risk.get("news", {}).get("news", "")) == "High Impact"
        fake = str(
            behaviour.get("fake_breakout", {}).get("fake_breakout", "")
        ) == "Possible"
        reversal = str(
            behaviour.get("reversal", {}).get("reversal_risk", "")
        ) == "High"

        if high_vix:
            warnings.append("High VIX")
        if high_news:
            warnings.append("High-impact news")
        if fake:
            warnings.append("Possible fake breakout")
        if reversal:
            warnings.append("High reversal risk")

        # Hard block only for severe information/risk conflicts.
        return high_news or (high_vix and fake), warnings

    def _collect_evidence(self, **reports: Any) -> List[str]:
        evidence: List[str] = []

        price = _details(reports["price_report"])
        option = _details(reports["option_report"])
        behaviour = _details(reports["behaviour_report"])
        money = _details(reports["smart_money_report"])
        risk = _details(reports["risk_report"])

        mappings = [
            ("Trend", price.get("trend", {}).get("trend")),
            ("Move stage", price.get("move_stage", {}).get("stage")),
            ("Movement", price.get("movement", {}).get("label")),
            ("Recovery from low", price.get("movement", {}).get("recovery_from_low")),
            ("Barrier", price.get("barrier", {}).get("barrier_zone")),
            ("OI", option.get("oi", {}).get("signal")),
            ("OI flow", option.get("flow", {}).get("state")),
            ("Volume", option.get("volume", {}).get("status")),
            ("Strike pressure", option.get("strike", {}).get("pressure")),
            ("Market energy", behaviour.get("energy", {}).get("market_energy")),
            ("Move potential", behaviour.get("potential", {}).get("move_potential")),
            ("FII", money.get("fii", {}).get("fii")),
            ("Breadth", money.get("breadth", {}).get("breadth")),
            ("VIX risk", risk.get("vix", {}).get("risk")),
        ]

        for label, value in mappings:
            if value not in (None, "", "Unknown"):
                evidence.append(f"{label}: {value}")

        return evidence

    def _watchlist(self, report: Any) -> Dict[str, Optional[Dict[str, Any]]]:
        if isinstance(report, Mapping):
            best_ce = report.get("best_ce")
            best_pe = report.get("best_pe")
        else:
            best_ce = getattr(report, "best_ce", None)
            best_pe = getattr(report, "best_pe", None)

        return {
            "best_ce": _candidate_to_dict(best_ce),
            "best_pe": _candidate_to_dict(best_pe),
        }

    def _approve_candidate(
        self,
        *,
        action: str,
        trade_allowed: bool,
        candidate_report: Any,
    ) -> Optional[Dict[str, Any]]:
        if not trade_allowed:
            return None

        watchlist = self._watchlist(candidate_report)

        if action == "SELL CE":
            candidate = watchlist["best_ce"]
        elif action == "SELL PE":
            candidate = watchlist["best_pe"]
        elif action == "IRON CONDOR":
            ce = watchlist["best_ce"]
            pe = watchlist["best_pe"]
            if ce and pe:
                return {"strategy": "IRON CONDOR", "ce": ce, "pe": pe}
            return None
        else:
            return None

        if candidate and float(candidate.get("score", 0) or 0) >= 65:
            return candidate
        return None

    def _score_gap(self, scores: Mapping[str, float]) -> float:
        ordered = sorted(scores.values(), reverse=True)
        return round(ordered[0] - ordered[1], 1) if len(ordered) >= 2 else 0.0

    def _final_confidence(
        self,
        *,
        action: str,
        top_score: float,
        score_gap: float,
        reports: tuple[Any, ...],
        warnings: List[str],
    ) -> float:
        report_quality = sum(_confidence(r) for r in reports) / max(len(reports), 1)
        base = top_score * 0.65 + report_quality * 0.35
        base += min(score_gap, 20.0) * 0.35
        base -= len(warnings) * 3.0
        if action == "WAIT":
            base = max(base, top_score)
        return round(max(0.0, min(95.0, base)), 1)

    def _reason(
        self,
        *,
        action: str,
        trade_allowed: bool,
        market_bias: str,
        evidence: List[str],
        warnings: List[str],
    ) -> str:
        if not trade_allowed:
            reason = "WAIT: confirmation, score gap, data quality or risk gate is insufficient."
        else:
            reason = f"{action} approved by AI_MASTER with {market_bias.lower()} market bias."

        if evidence:
            reason += " Evidence: " + "; ".join(evidence[:3]) + "."
        if warnings:
            reason += " Caution: " + "; ".join(warnings[:3]) + "."
        return reason
