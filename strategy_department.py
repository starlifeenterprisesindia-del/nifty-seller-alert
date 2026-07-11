"""
strategy_department.py
Version : V23.6
Department : Strategy Intelligence
Status : Phase-1 Professional Strategy Architecture

Purpose:
- Read department reports
- Score WAIT / SELL CE / SELL PE / IRON CONDOR
- Recommend strategies only
- Never issue the final trade decision
- AI_MASTER remains the only final authority
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
        return report
    details = getattr(report, "details", None)
    return details if isinstance(details, dict) else {}


class StrategyScoringSpecialist:
    """
    Converts department evidence into strategy scores.
    It does not approve a trade.
    """

    def score(
        self,
        price_report: Any,
        option_report: Any,
        behaviour_report: Any,
        smart_money_report: Any,
        risk_report: Any,
    ) -> Dict[str, StrategyScore]:

        price = _as_dict(price_report)
        option = _as_dict(option_report)
        behaviour = _as_dict(behaviour_report)
        money = _as_dict(smart_money_report)
        risk = _as_dict(risk_report)

        scores = {
            "WAIT": 50.0,
            "SELL CE": 35.0,
            "SELL PE": 35.0,
            "IRON CONDOR": 35.0,
        }
        reasons = {name: [] for name in scores}

        # Price Action evidence
        trend = str(price.get("trend", {}).get("trend", ""))
        stage = str(price.get("move_stage", {}).get("stage", ""))
        range_status = str(price.get("range", {}).get("range_status", ""))
        barrier_zone = str(price.get("barrier", {}).get("barrier_zone", ""))

        if "Bullish" in trend:
            scores["SELL PE"] += 22
            scores["SELL CE"] -= 10
            reasons["SELL PE"].append("Bullish price trend")
        elif "Bearish" in trend:
            scores["SELL CE"] += 22
            scores["SELL PE"] -= 10
            reasons["SELL CE"].append("Bearish price trend")
        else:
            scores["IRON CONDOR"] += 12
            scores["WAIT"] += 8
            reasons["IRON CONDOR"].append("Mixed/sideways trend")

        if stage in {"Late Move", "Exhaustion Move"}:
            scores["WAIT"] += 18
            scores["SELL CE"] -= 8
            scores["SELL PE"] -= 8
            reasons["WAIT"].append("Late/exhausted move")

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

        # Option Intelligence evidence
        pcr_sentiment = str(option.get("pcr", {}).get("sentiment", ""))
        strike_pressure = str(option.get("strike", {}).get("pressure", ""))
        volume_status = str(option.get("volume", {}).get("status", ""))
        ce_writing = str(option.get("ce", {}).get("ce", ""))
        pe_writing = str(option.get("pe", {}).get("pe", ""))

        if pcr_sentiment == "Bullish":
            scores["SELL PE"] += 12
            reasons["SELL PE"].append("Bullish PCR")
        elif pcr_sentiment == "Bearish":
            scores["SELL CE"] += 12
            reasons["SELL CE"].append("Bearish PCR")

        if strike_pressure == "CE Resistance":
            scores["SELL CE"] += 12
            reasons["SELL CE"].append("CE resistance pressure")
        elif strike_pressure == "PE Support":
            scores["SELL PE"] += 12
            reasons["SELL PE"].append("PE support pressure")
        else:
            scores["IRON CONDOR"] += 7

        if ce_writing == "Strong":
            scores["SELL CE"] += 8
            reasons["SELL CE"].append("Strong CE writing")
        if pe_writing == "Strong":
            scores["SELL PE"] += 8
            reasons["SELL PE"].append("Strong PE writing")

        if volume_status in {"High", "Spike", "High Volume", "Spike Volume"}:
            if "Bullish" in trend:
                scores["SELL PE"] += 7
            elif "Bearish" in trend:
                scores["SELL CE"] += 7
        elif volume_status in {"Weak", "Weak Volume"}:
            scores["WAIT"] += 10
            reasons["WAIT"].append("Weak participation")

        # Market Behaviour evidence
        reversal_risk = str(behaviour.get("reversal", {}).get("reversal_risk", ""))
        breakout_probability = str(
            behaviour.get("breakout", {}).get("breakout_probability", "")
        )
        market_energy = str(behaviour.get("energy", {}).get("market_energy", ""))
        fake_breakout = str(
            behaviour.get("fake_breakout", {}).get("fake_breakout", "")
        )

        if reversal_risk == "High":
            scores["WAIT"] += 12
            reasons["WAIT"].append("High reversal risk")

        if breakout_probability == "Increasing" and market_energy == "High":
            if "Bullish" in trend:
                scores["SELL PE"] += 8
            elif "Bearish" in trend:
                scores["SELL CE"] += 8

        if fake_breakout == "Possible":
            scores["WAIT"] += 15
            reasons["WAIT"].append("Possible fake breakout")

        # Smart Money evidence
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

        # Risk evidence
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

        result: Dict[str, StrategyScore] = {}
        for name, raw_score in scores.items():
            final_score = round(max(0.0, min(100.0, raw_score)), 1)

            if final_score >= 75:
                status = "Strong"
            elif final_score >= 60:
                status = "Watch"
            else:
                status = "Weak"

            result[name] = StrategyScore(
                name=name,
                score=final_score,
                status=status,
                reasons=reasons[name][:5],
            )

        return result


class StrategyDirector:
    """
    Produces strategy recommendations only.
    AI_MASTER may accept, reject or override the recommendation.
    """

    def __init__(self):
        self.scorer = StrategyScoringSpecialist()

    def build_report(
        self,
        price_report: Any,
        option_report: Any,
        behaviour_report: Any,
        smart_money_report: Any,
        risk_report: Any,
    ) -> StrategyReport:

        strategies = self.scorer.score(
            price_report=price_report,
            option_report=option_report,
            behaviour_report=behaviour_report,
            smart_money_report=smart_money_report,
            risk_report=risk_report,
        )

        ordered = sorted(
            strategies.values(),
            key=lambda item: item.score,
            reverse=True,
        )

        recommended = ordered[0].name if ordered else "WAIT"
        confidence = ordered[0].score if ordered else 0.0

        details = {
            "ranking": [item.name for item in ordered],
            "score_gap": (
                round(ordered[0].score - ordered[1].score, 1)
                if len(ordered) > 1
                else 0.0
            ),
        }

        return StrategyReport(
            summary=f"Recommended strategy: {recommended} ({confidence}%)",
            confidence=confidence,
            recommended_strategy=recommended,
            strategies=strategies,
            details=details,
        )
