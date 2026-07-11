"""
market_psychology.py
Version: V36.2
Department: Market Psychology
Status: Phase-2 — Retail Emotion + Conservative Trap-Risk Evidence

Safety contract:
- Evidence and interpretation only.
- Never emits BUY, SELL CE, SELL PE, IRON CONDOR, or execution permission.
- Never claims that a trap is confirmed from one snapshot.
- Report must travel through DSP review -> CO case file -> AI_MASTER.
- Uses existing department reports and the verified snapshot; no API calls,
  loops, timers, or background work.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class MarketPsychologyReport:
    summary: str
    confidence: float
    details: Dict[str, Any]


class RetailEmotionSpecialist:
    """Build bounded fear/greed evidence from observable market behaviour."""

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number != number:  # NaN guard
            return None
        return number

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, float(value)))

    def analyze(
        self,
        *,
        price: Any,
        change_pct: Any,
        vix: Any,
        ema20: Any,
        vwap: Any,
        day_high: Any,
        day_low: Any,
        pcr: Any = None,
    ) -> Dict[str, Any]:
        price_n = self._number(price)
        change_n = self._number(change_pct)
        vix_n = self._number(vix)
        ema20_n = self._number(ema20)
        vwap_n = self._number(vwap)
        high_n = self._number(day_high)
        low_n = self._number(day_low)
        pcr_n = self._number(pcr)

        fear = 0.0
        greed = 0.0
        fear_evidence: List[str] = []
        greed_evidence: List[str] = []
        neutral_evidence: List[str] = []
        available = 0
        possible = 5

        # 1) Current percentage move — direct emotional pressure evidence.
        if change_n is not None:
            available += 1
            if change_n <= -0.75:
                fear += 28
                fear_evidence.append(f"Sharp negative move {change_n:.2f}%")
            elif change_n <= -0.30:
                fear += 17
                fear_evidence.append(f"Negative move {change_n:.2f}%")
            elif change_n >= 0.75:
                greed += 28
                greed_evidence.append(f"Sharp positive move +{change_n:.2f}%")
            elif change_n >= 0.30:
                greed += 17
                greed_evidence.append(f"Positive move +{change_n:.2f}%")
            else:
                neutral_evidence.append(f"Limited percentage move {change_n:+.2f}%")

        # 2) Price placement versus EMA20 and VWAP — participation behaviour.
        if price_n is not None and ema20_n not in (None, 0) and vwap_n not in (None, 0):
            available += 1
            if price_n < ema20_n and price_n < vwap_n:
                fear += 24
                fear_evidence.append("Price below EMA20 and VWAP")
            elif price_n > ema20_n and price_n > vwap_n:
                greed += 24
                greed_evidence.append("Price above EMA20 and VWAP")
            else:
                neutral_evidence.append("Price mixed around EMA20/VWAP")

        # 3) India VIX regime — fear or complacency evidence, never direction alone.
        if vix_n is not None and vix_n > 0:
            available += 1
            if vix_n >= 20:
                fear += 24
                fear_evidence.append(f"Elevated volatility regime, VIX {vix_n:.2f}")
            elif vix_n >= 16:
                fear += 13
                fear_evidence.append(f"Cautious volatility regime, VIX {vix_n:.2f}")
            elif vix_n <= 12:
                greed += 12
                greed_evidence.append(f"Very low volatility/complacency, VIX {vix_n:.2f}")
            else:
                neutral_evidence.append(f"Normal volatility regime, VIX {vix_n:.2f}")

        # 4) Location inside the day's range — panic near low / chase near high.
        if (
            price_n is not None
            and high_n is not None
            and low_n is not None
            and high_n > low_n
        ):
            available += 1
            day_position = self._clamp((price_n - low_n) / (high_n - low_n) * 100.0)
            if day_position <= 20:
                fear += 24
                fear_evidence.append(f"Price near day low ({day_position:.0f}% of range)")
            elif day_position >= 80:
                greed += 24
                greed_evidence.append(f"Price near day high ({day_position:.0f}% of range)")
            else:
                neutral_evidence.append(f"Price in middle of day range ({day_position:.0f}%)")
        else:
            day_position = None

        # 5) PCR is context only. Extreme PCR can mean sentiment or crowding,
        # therefore it never adds fear/greed points on its own.
        if pcr_n is not None and pcr_n > 0:
            available += 1
            if pcr_n >= 1.35:
                pcr_context = "High put concentration; crowding context requires CO verification"
            elif pcr_n <= 0.70:
                pcr_context = "High call concentration; crowding context requires CO verification"
            else:
                pcr_context = "PCR within non-extreme zone"
            neutral_evidence.append(f"PCR {pcr_n:.2f}: {pcr_context}")
        else:
            pcr_context = "PCR unavailable"

        fear = self._clamp(fear)
        greed = self._clamp(greed)
        separation = abs(fear - greed)

        if fear >= 45 and fear >= greed + 15:
            state = "FEAR_DOMINANT"
        elif greed >= 45 and greed >= fear + 15:
            state = "GREED_DOMINANT"
        elif fear >= 30 and greed >= 30:
            state = "MIXED_EMOTION"
        else:
            state = "BALANCED"

        coverage = self._clamp(available / possible * 100.0)
        confidence = self._clamp(35.0 + coverage * 0.40 + min(separation, 60.0) * 0.25, 35.0, 90.0)

        return {
            "psychology_state": state,
            "retail_fear": {
                "score": round(fear, 1),
                "evidence": fear_evidence[:5],
            },
            "retail_greed": {
                "score": round(greed, 1),
                "evidence": greed_evidence[:5],
            },
            "neutral_context": neutral_evidence[:6],
            "data_coverage": round(coverage, 1),
            "day_range_position_pct": round(day_position, 1) if day_position is not None else None,
            "pcr_context": pcr_context,
            "confidence": round(confidence, 1),
        }


class TrapDetectionSpecialist:
    """Detect contradictory evidence that may create a crowd trap.

    This specialist deliberately reports *risk*, not a confirmed trap. A single
    snapshot cannot prove liquidity engineering or stop hunting; confirmation
    remains a future multi-snapshot investigation task.
    """

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number != number:
            return None
        return number

    @staticmethod
    def _text(mapping: Mapping[str, Any], *path: str) -> str:
        current: Any = mapping
        for key in path:
            if not isinstance(current, Mapping):
                return ""
            current = current.get(key)
        return str(current or "")

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    def analyze(
        self,
        *,
        change_pct: Any,
        pcr: Any,
        emotion: Mapping[str, Any],
        price_action: Optional[Mapping[str, Any]] = None,
        option_intelligence: Optional[Mapping[str, Any]] = None,
        market_behaviour: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        price_action = price_action if isinstance(price_action, Mapping) else {}
        option_intelligence = option_intelligence if isinstance(option_intelligence, Mapping) else {}
        market_behaviour = market_behaviour if isinstance(market_behaviour, Mapping) else {}

        change_n = self._number(change_pct)
        pcr_n = self._number(pcr)
        day_position = self._number(emotion.get("day_range_position_pct"))
        fear_score = self._number((emotion.get("retail_fear") or {}).get("score")) or 0.0
        greed_score = self._number((emotion.get("retail_greed") or {}).get("score")) or 0.0

        barrier_zone = self._text(price_action, "barrier", "barrier_zone")
        candle_type = self._text(price_action, "candle", "candle_type")
        move_stage = self._text(price_action, "move_stage", "stage")
        volume_status = self._text(option_intelligence, "volume", "status")
        strike_pressure = self._text(option_intelligence, "strike", "pressure")
        barrier_reaction = self._text(option_intelligence, "barrier", "barrier")
        behaviour_barrier = self._text(market_behaviour, "barrier", "barrier_view")
        fake_breakout = self._text(market_behaviour, "fake_breakout", "fake_breakout")
        breakout_probability = self._text(market_behaviour, "breakout", "breakout_probability")

        bull_score = 0.0
        bear_score = 0.0
        bull_evidence: List[str] = []
        bear_evidence: List[str] = []
        shared_cautions: List[str] = []
        coverage = 0
        possible = 8

        # Crowd chasing upward/downward is the first prerequisite. Without crowd
        # extension, a normal barrier is not labelled as a trap.
        if change_n is not None:
            coverage += 1
            if change_n >= 0.30:
                bull_score += 14 if change_n < 0.75 else 20
                bull_evidence.append(f"Crowd chasing an upward move ({change_n:+.2f}%)")
            elif change_n <= -0.30:
                bear_score += 14 if change_n > -0.75 else 20
                bear_evidence.append(f"Crowd chasing a downward move ({change_n:+.2f}%)")

        if day_position is not None:
            coverage += 1
            if day_position >= 78:
                bull_score += 12
                bull_evidence.append(f"Price stretched near day high ({day_position:.0f}% of range)")
            elif day_position <= 22:
                bear_score += 12
                bear_evidence.append(f"Price stretched near day low ({day_position:.0f}% of range)")

        if max(fear_score, greed_score) > 0:
            coverage += 1
            if greed_score >= 45:
                bull_score += 10
                bull_evidence.append(f"Retail greed elevated ({greed_score:.0f}/100)")
            if fear_score >= 45:
                bear_score += 10
                bear_evidence.append(f"Retail fear elevated ({fear_score:.0f}/100)")

        if barrier_zone or behaviour_barrier:
            coverage += 1
            if "Resistance" in barrier_zone or "Resistance" in behaviour_barrier:
                bull_score += 20
                bull_evidence.append("Upward crowd faces nearby/strong resistance")
            if "Support" in barrier_zone or "Support" in behaviour_barrier:
                bear_score += 20
                bear_evidence.append("Downward crowd faces nearby/strong support")

        if strike_pressure:
            coverage += 1
            if strike_pressure == "CE Resistance":
                bull_score += 16
                bull_evidence.append("Option chain shows CE resistance against upside chase")
            elif strike_pressure == "PE Support":
                bear_score += 16
                bear_evidence.append("Option chain shows PE support against downside chase")

        if volume_status:
            coverage += 1
            if volume_status == "Weak":
                bull_score += 12
                bear_score += 12
                shared_cautions.append("Weak option volume reduces move confirmation")
            elif volume_status in {"High", "Spike"}:
                shared_cautions.append(f"{volume_status} option volume supports genuine participation")

        if candle_type or move_stage:
            coverage += 1
            if candle_type == "Indecision / Wick Candle":
                bull_score += 10
                bear_score += 10
                shared_cautions.append("Wick/indecision candle shows rejection risk")
            if move_stage in {"Late Move", "Exhaustion Move"}:
                points = 10 if move_stage == "Late Move" else 16
                bull_score += points
                bear_score += points
                shared_cautions.append(f"{move_stage} increases reversal vulnerability")

        if fake_breakout or breakout_probability or barrier_reaction:
            coverage += 1
            if fake_breakout == "Possible":
                bull_score += 18
                bear_score += 18
                shared_cautions.append("Market Behaviour reports possible fake breakout")
            if barrier_reaction == "Rejection":
                bull_score += 8
                bear_score += 8
                shared_cautions.append("Barrier rejection is visible")
            if breakout_probability == "Increasing" and volume_status == "Weak":
                bull_score += 8
                bear_score += 8

        # PCR is only a small contradiction witness and never establishes a trap.
        if pcr_n is not None and pcr_n > 0:
            if pcr_n <= 0.80:
                bull_score += 6
                bull_evidence.append(f"PCR {pcr_n:.2f} does not confirm broad upside comfort")
            elif pcr_n >= 1.20:
                bear_score += 6
                bear_evidence.append(f"PCR {pcr_n:.2f} does not confirm broad downside comfort")

        bull_score = self._clamp(bull_score)
        bear_score = self._clamp(bear_score)

        # Require both crowd extension and opposing defence. This prevents a plain
        # resistance/support reading from being mislabelled as a trap.
        upward_crowd = (change_n is not None and change_n >= 0.30) or greed_score >= 45 or (day_position or 0) >= 78
        downward_crowd = (change_n is not None and change_n <= -0.30) or fear_score >= 45 or (day_position is not None and day_position <= 22)
        upside_defence = (
            "Resistance" in barrier_zone
            or "Resistance" in behaviour_barrier
            or strike_pressure == "CE Resistance"
            or fake_breakout == "Possible"
        )
        downside_defence = (
            "Support" in barrier_zone
            or "Support" in behaviour_barrier
            or strike_pressure == "PE Support"
            or fake_breakout == "Possible"
        )

        bull_candidate = bool(upward_crowd and upside_defence and bull_score >= 45)
        bear_candidate = bool(downward_crowd and downside_defence and bear_score >= 45)

        if bull_candidate and bear_candidate:
            state = "TWO_WAY_TRAP_RISK"
        elif bull_candidate:
            state = "POSSIBLE_BULL_TRAP_RISK"
        elif bear_candidate:
            state = "POSSIBLE_BEAR_TRAP_RISK"
        elif max(bull_score, bear_score) >= 35:
            state = "WATCH_FOR_CONFIRMATION"
        else:
            state = "LOW_TRAP_EVIDENCE"

        coverage_pct = self._clamp(coverage / possible * 100.0)
        leading_score = max(bull_score, bear_score)
        confidence = self._clamp(25.0 + coverage_pct * 0.35 + min(leading_score, 70.0) * 0.25)
        confidence = min(confidence, 85.0)  # Single-snapshot foundation cap.

        return {
            "state": state,
            "bull_trap_risk": {
                "score": round(bull_score, 1),
                "evidence": bull_evidence[:6],
            },
            "bear_trap_risk": {
                "score": round(bear_score, 1),
                "evidence": bear_evidence[:6],
            },
            "shared_cautions": list(dict.fromkeys(shared_cautions))[:6],
            "data_coverage": round(coverage_pct, 1),
            "confidence": round(confidence, 1),
            "confirmation_status": "UNCONFIRMED_SINGLE_SNAPSHOT",
            "authority": "EVIDENCE_ONLY_TO_CO",
        }


class MarketPsychologyDirector:
    """DSP Market Psychology: one report, no independent trade authority."""

    VERSION = "V36.2_RETAIL_EMOTION_AND_TRAP_RISK_EVIDENCE"

    def build_report(
        self,
        *,
        price: Any,
        change_pct: Any,
        vix: Any,
        ema20: Any,
        vwap: Any,
        day_high: Any,
        day_low: Any,
        pcr: Any = None,
        price_action_details: Optional[Mapping[str, Any]] = None,
        option_details: Optional[Mapping[str, Any]] = None,
        behaviour_details: Optional[Mapping[str, Any]] = None,
    ) -> MarketPsychologyReport:
        emotion = RetailEmotionSpecialist().analyze(
            price=price,
            change_pct=change_pct,
            vix=vix,
            ema20=ema20,
            vwap=vwap,
            day_high=day_high,
            day_low=day_low,
            pcr=pcr,
        )
        trap = TrapDetectionSpecialist().analyze(
            change_pct=change_pct,
            pcr=pcr,
            emotion=emotion,
            price_action=price_action_details,
            option_intelligence=option_details,
            market_behaviour=behaviour_details,
        )

        fear_score = float(emotion["retail_fear"]["score"])
        greed_score = float(emotion["retail_greed"]["score"])
        state = str(emotion["psychology_state"])
        confidence = float(emotion["confidence"])
        trap_state = str(trap["state"])
        bull_trap = float(trap["bull_trap_risk"]["score"])
        bear_trap = float(trap["bear_trap_risk"]["score"])

        details = {
            **emotion,
            "trap_detection": trap,
            "authority": "EVIDENCE_ONLY_TO_CO",
            "phase_control": "OBSERVATION_ONLY_NOT_IN_DIRECTIONAL_CONSENSUS",
        }
        summary = (
            f"Market psychology evidence: {state} | Fear {fear_score:.0f}/100 | "
            f"Greed {greed_score:.0f}/100 | Trap review {trap_state} "
            f"(Bull {bull_trap:.0f}, Bear {bear_trap:.0f}) | CO verification required"
        )
        return MarketPsychologyReport(
            summary=summary,
            # Overall branch confidence remains the validated V36.1 emotion
            # confidence. Trap confidence is displayed separately and cannot
            # silently increase CO case strength during foundation testing.
            confidence=confidence,
            details=details,
        )
