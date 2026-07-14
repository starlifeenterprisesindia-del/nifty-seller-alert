"""
strategy_department.py
Version : V50.8.4
Department : Strategy Intelligence

Scores WAIT / SELL CE / SELL PE / IRON CONDOR from department evidence only.
Current movement phase is separated from the broader market structure so a
strong recovery cannot be mistaken for fresh bearish continuation.
"""
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class StrategyScore:
    name: str
    score: float
    status: str
    reasons: List[str]


@dataclass
class StrategyReport:
    summary: str
    confidence: float
    recommended_strategy: str
    strategies: Dict[str, StrategyScore]
    details: Dict[str, Any]


def _as_dict(report: Any) -> Dict[str, Any]:
    if report is None:
        return {}
    if isinstance(report, dict):
        return report.get("details", report) if isinstance(report.get("details", report), dict) else {}
    details = getattr(report, "details", None)
    return details if isinstance(details, dict) else {}


class StrategyScoringSpecialist:
    def score(self, price_report: Any, option_report: Any, behaviour_report: Any, smart_money_report: Any, risk_report: Any) -> Dict[str, StrategyScore]:
        price = _as_dict(price_report)
        option = _as_dict(option_report)
        behaviour = _as_dict(behaviour_report)
        money = _as_dict(smart_money_report)
        risk = _as_dict(risk_report)

        scores = {"WAIT": 50.0, "SELL CE": 35.0, "SELL PE": 35.0, "IRON CONDOR": 35.0}
        reasons = {name: [] for name in scores}

        price_available = str(price.get("availability", {}).get("status", "READY")) == "READY"
        option_available = str(option.get("availability", {}).get("status", "READY")) == "READY"
        trend = str(price.get("trend", {}).get("trend", ""))
        structure = str(price.get("trend", {}).get("structure", ""))
        stage = str(price.get("move_stage", {}).get("stage", ""))
        range_status = str(price.get("range", {}).get("range_status", ""))
        barrier_zone = str(price.get("barrier", {}).get("barrier_zone", ""))
        movement = price.get("movement", {}) if isinstance(price.get("movement", {}), dict) else {}
        movement_phase = str(movement.get("phase", "NORMAL"))
        recovery_points = float(movement.get("recovery_from_low", 0) or 0)
        pullback_points = float(movement.get("pullback_from_high", 0) or 0)
        sample_count = int(float(movement.get("sample_count", 0) or 0))
        trend_details = price.get("trend", {}) if isinstance(price.get("trend", {}), dict) else {}
        recovery_confirmed = bool(trend_details.get("recovery_confirmed", movement.get("recovery_confirmed", False)))
        pullback_confirmed = bool(trend_details.get("pullback_confirmed", movement.get("pullback_confirmed", False)))
        directional_confirmation = str(trend_details.get("directional_confirmation", movement.get("directional_confirmation", "UNCONFIRMED")))

        if not price_available:
            scores["WAIT"] += 22
            scores["SELL CE"] -= 12
            scores["SELL PE"] -= 12
            reasons["WAIT"].append("Automatic price action unavailable")
        else:
            if structure in {"BULLISH", "MIXED_BULLISH"}:
                scores["SELL PE"] += 22
                scores["SELL CE"] -= 10
                reasons["SELL PE"].append("Bullish price structure")
            elif structure in {"BEARISH", "MIXED_BEARISH"}:
                scores["SELL CE"] += 22
                scores["SELL PE"] -= 10
                reasons["SELL CE"].append("Bearish price structure")
            else:
                scores["IRON CONDOR"] += 12
                scores["WAIT"] += 8
                reasons["IRON CONDOR"].append("Mixed/sideways structure")

        # Active movement phase and EMA/VWAP confirmation are separate.
        if movement_phase == "STRONG_RECOVERY":
            scores["WAIT"] += 20 if recovery_confirmed else 26
            scores["SELL CE"] -= 34
            scores["SELL PE"] += 6 if recovery_confirmed else 0
            reasons["WAIT"].append(
                f"Strong recovery confirmed ({recovery_points:.0f} pts from low)"
                if recovery_confirmed else f"Strong recovery attempt ({recovery_points:.0f} pts from low); EMA/VWAP confirmation pending"
            )
            reasons["SELL CE"].append("Fresh CE selling blocked during recovery")
        elif movement_phase == "RECOVERY":
            scores["WAIT"] += 10 if recovery_confirmed else 16
            scores["SELL CE"] -= 22
            if recovery_confirmed:
                scores["SELL PE"] += 4
                reasons["WAIT"].append("Recovery confirmed; entry still requires barrier and risk clearance")
            else:
                reasons["WAIT"].append("Recovery developing; EMA/VWAP confirmation incomplete")
        elif movement_phase == "STRONG_PULLBACK_DOWN":
            scores["WAIT"] += 20 if pullback_confirmed else 26
            scores["SELL PE"] -= 34
            scores["SELL CE"] += 6 if pullback_confirmed else 0
            reasons["WAIT"].append(
                f"Strong pullback confirmed ({pullback_points:.0f} pts from high)"
                if pullback_confirmed else f"Strong pullback attempt ({pullback_points:.0f} pts from high); EMA/VWAP confirmation pending"
            )
            reasons["SELL PE"].append("Fresh PE selling blocked during pullback")
        elif movement_phase == "PULLBACK_DOWN":
            scores["WAIT"] += 10 if pullback_confirmed else 16
            scores["SELL PE"] -= 22
            if pullback_confirmed:
                scores["SELL CE"] += 4
                reasons["WAIT"].append("Pullback confirmed; entry still requires barrier and risk clearance")
            else:
                reasons["WAIT"].append("Downward pullback developing; EMA/VWAP confirmation incomplete")

        if stage in {"Late Move", "Exhaustion Move"}:
            scores["WAIT"] += 18
            scores["SELL CE"] -= 8
            scores["SELL PE"] -= 8
            reasons["WAIT"].append("Late/exhausted move")
        elif stage in {"Recovery Leg", "Recovery Developing", "Pullback Down Leg", "Pullback Developing"}:
            scores["WAIT"] += 8

        if "Tight Range" in range_status:
            scores["IRON CONDOR"] += 18
            reasons["IRON CONDOR"].append("Tight range")
        elif "Wide Range" in range_status:
            scores["WAIT"] += 8
        if "Near Resistance" in barrier_zone:
            scores["SELL CE"] += 10
            reasons["SELL CE"].append("Price near resistance")
        if "Near Support" in barrier_zone:
            scores["SELL PE"] += 10
            reasons["SELL PE"].append("Price near support")

        pcr_sentiment = str(option.get("pcr", {}).get("sentiment", ""))
        strike_pressure = str(option.get("strike", {}).get("pressure", ""))
        volume_status = str(option.get("volume", {}).get("status", ""))
        ce_writing = str(option.get("ce", {}).get("ce", ""))
        pe_writing = str(option.get("pe", {}).get("pe", ""))
        flow = option.get("flow", {}) if isinstance(option.get("flow", {}), dict) else {}
        snapshot_ready = bool(flow.get("snapshot_ready", False))

        if not option_available:
            scores["WAIT"] += 25
            scores["SELL CE"] -= 15
            scores["SELL PE"] -= 15
            scores["IRON CONDOR"] -= 10
            reasons["WAIT"].append("Live option intelligence unavailable")
        else:
            if "Bullish" in pcr_sentiment and "Extreme" not in pcr_sentiment:
                scores["SELL PE"] += 8
                reasons["SELL PE"].append("PCR supportive")
            elif "Bearish" in pcr_sentiment:
                scores["SELL CE"] += 8
                reasons["SELL CE"].append("PCR bearish")
            if "Extreme" in pcr_sentiment or "Crowded" in pcr_sentiment:
                scores["WAIT"] += 7
                reasons["WAIT"].append("PCR crowding caution")

            if strike_pressure == "CE Resistance":
                scores["SELL CE"] += 12
                reasons["SELL CE"].append("CE resistance pressure")
            elif strike_pressure == "PE Support":
                scores["SELL PE"] += 12
                reasons["SELL PE"].append("PE support pressure")
            elif strike_pressure == "Two-Sided Writing / Range":
                scores["IRON CONDOR"] += 16
                scores["WAIT"] += 8
                scores["SELL CE"] -= 5
                scores["SELL PE"] -= 5
                reasons["IRON CONDOR"].append("Two-sided writing/range pressure")
                reasons["WAIT"].append("Directional option flow is mixed")
            else:
                scores["IRON CONDOR"] += 5

            if ce_writing == "Strong":
                scores["SELL CE"] += 7
                reasons["SELL CE"].append("Strong CE writing")
            if pe_writing == "Strong":
                scores["SELL PE"] += 7
                reasons["SELL PE"].append("Strong PE writing")

            if not snapshot_ready:
                scores["WAIT"] += 12
                scores["SELL CE"] -= 7
                scores["SELL PE"] -= 7
                reasons["WAIT"].append("OI uses day-change fallback; second fresh snapshot pending")

        if volume_status in {"High", "Spike", "High Volume", "Spike Volume"}:
            if "Bullish" in trend or movement_phase in {"RECOVERY", "STRONG_RECOVERY"}:
                scores["SELL PE"] += 5
            elif "Bearish" in trend or movement_phase in {"PULLBACK_DOWN", "STRONG_PULLBACK_DOWN"}:
                scores["SELL CE"] += 5
        elif volume_status in {"Weak", "Weak Volume"}:
            scores["WAIT"] += 10
            reasons["WAIT"].append("Weak participation")

        reversal_risk = str(behaviour.get("reversal", {}).get("reversal_risk", ""))
        breakout_probability = str(behaviour.get("breakout", {}).get("breakout_probability", ""))
        market_energy = str(behaviour.get("energy", {}).get("market_energy", ""))
        fake_breakout = str(behaviour.get("fake_breakout", {}).get("fake_breakout", ""))
        if reversal_risk == "High":
            scores["WAIT"] += 12
            reasons["WAIT"].append("High reversal risk")
        if breakout_probability == "Increasing" and market_energy == "High":
            if structure in {"BULLISH", "MIXED_BULLISH"}:
                scores["SELL PE"] += 8
            elif structure in {"BEARISH", "MIXED_BEARISH"}:
                scores["SELL CE"] += 8
        if fake_breakout == "Possible":
            scores["WAIT"] += 15
            reasons["WAIT"].append("Possible fake breakout")

        fii = str(money.get("fii", {}).get("fii", ""))
        heavyweights = str(money.get("heavyweights", {}).get("heavyweights", ""))
        breadth = str(money.get("breadth", {}).get("breadth", ""))
        if fii == "Buying" and heavyweights == "Supporting Market":
            scores["SELL PE"] += 10
            reasons["SELL PE"].append("FII and heavyweights supportive")
        elif fii == "Selling" and heavyweights == "Pressuring Market":
            scores["SELL CE"] += 10
            reasons["SELL CE"].append("FII and heavyweights weak")
        if breadth == "Strong Breadth":
            scores["SELL PE"] += 6
        elif breadth == "Weak Breadth":
            scores["SELL CE"] += 6

        vix_risk = str(risk.get("vix", {}).get("risk", ""))
        news = str(risk.get("news", {}).get("news", ""))
        expiry = str(risk.get("expiry", {}).get("expiry", ""))
        gap = str(risk.get("gap", {}).get("gap", ""))
        if vix_risk == "High":
            scores["WAIT"] += 18
            scores["IRON CONDOR"] -= 10
            reasons["WAIT"].append("High VIX")
        elif vix_risk == "Low":
            scores["IRON CONDOR"] += 6
        if news == "High Impact":
            scores["WAIT"] += 20
            reasons["WAIT"].append("High-impact news")
        if expiry == "Expiry Day":
            scores["WAIT"] += 5
            scores["IRON CONDOR"] -= 5
        if gap == "High Gap":
            scores["WAIT"] += 10
            reasons["WAIT"].append("High opening gap")

        # Final confirmation guard. OI/PCR can identify a future candidate, but
        # cannot by itself create an 80% directional execution score.
        if sample_count < 3:
            scores["SELL CE"] = min(scores["SELL CE"], 60.0)
            scores["SELL PE"] = min(scores["SELL PE"], 60.0)
            scores["WAIT"] = max(scores["WAIT"], 85.0)
            reasons["WAIT"].append("Fewer than three persisted movement samples")

        if movement_phase in {"RECOVERY", "STRONG_RECOVERY"} and not recovery_confirmed:
            scores["SELL PE"] = min(scores["SELL PE"], 62.0)
            scores["WAIT"] = max(scores["WAIT"], 82.0)
            reasons["SELL PE"].append("Directional fit capped until price clears EMA20/EMA50/VWAP")
        if movement_phase in {"PULLBACK_DOWN", "STRONG_PULLBACK_DOWN"} and not pullback_confirmed:
            scores["SELL CE"] = min(scores["SELL CE"], 62.0)
            scores["WAIT"] = max(scores["WAIT"], 82.0)
            reasons["SELL CE"].append("Directional fit capped until price confirms below EMA20/EMA50/VWAP")

        if "Near Resistance" in barrier_zone and movement_phase in {"RECOVERY", "STRONG_RECOVERY"}:
            scores["SELL PE"] = min(scores["SELL PE"], 69.0 if recovery_confirmed else 60.0)
            scores["WAIT"] = max(scores["WAIT"], 88.0 if stage in {"Late Move", "Exhaustion Move"} else 82.0)
            reasons["WAIT"].append("Recovery is at resistance; breakout hold is not yet execution-safe")
        if "Near Support" in barrier_zone and movement_phase in {"PULLBACK_DOWN", "STRONG_PULLBACK_DOWN"}:
            scores["SELL CE"] = min(scores["SELL CE"], 69.0 if pullback_confirmed else 60.0)
            scores["WAIT"] = max(scores["WAIT"], 88.0 if stage in {"Late Move", "Exhaustion Move"} else 82.0)
            reasons["WAIT"].append("Pullback is at support; breakdown hold is not yet execution-safe")

        result: Dict[str, StrategyScore] = {}
        for name, raw_score in scores.items():
            final_score = round(max(0.0, min(95.0, raw_score)), 1)
            status = "Strong" if final_score >= 75 else "Watch" if final_score >= 60 else "Weak"
            result[name] = StrategyScore(name=name, score=final_score, status=status, reasons=reasons[name][:7])
        return result


class StrategyDirector:
    def __init__(self):
        self.scorer = StrategyScoringSpecialist()

    def build_report(self, price_report: Any, option_report: Any, behaviour_report: Any, smart_money_report: Any, risk_report: Any) -> StrategyReport:
        strategies = self.scorer.score(price_report, option_report, behaviour_report, smart_money_report, risk_report)
        ordered = sorted(strategies.values(), key=lambda item: item.score, reverse=True)
        recommended = ordered[0].name if ordered else "WAIT"
        confidence = ordered[0].score if ordered else 0.0
        details = {
            "ranking": [item.name for item in ordered],
            "score_gap": round(ordered[0].score - ordered[1].score, 1) if len(ordered) > 1 else 0.0,
            "top_reasons": ordered[0].reasons if ordered else [],
        }
        return StrategyReport(
            summary=f"Recommended strategy: {recommended} ({confidence}%)",
            confidence=confidence,
            recommended_strategy=recommended,
            strategies=strategies,
            details=details,
        )
