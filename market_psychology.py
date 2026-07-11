"""
market_psychology.py
Version: V36.5
Department: Market Psychology
Status: Phase-5 — Retail Emotion + Trap + Liquidity + Panic + Upside Participation Evidence

Safety contract:
- Evidence and interpretation only.
- Never emits BUY, SELL CE, SELL PE, IRON CONDOR, or execution permission.
- Never claims that a trap, stop hunt, panic, short-covering, or long-build-up event is confirmed from one snapshot/candle.
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


class LiquiditySweepSpecialist:
    """Detect conservative liquidity-grab / stop-hunt *evidence*.

    A real liquidity grab requires sequence confirmation across candles. This
    foundation only checks whether the current verified candle swept a known
    support/resistance area and closed back inside with rejection evidence.
    It never labels market manipulation as a fact and never emits a trade.
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
        price: Any,
        candle_open: Any,
        candle_high: Any,
        candle_low: Any,
        candle_close: Any,
        support: Any,
        resistance: Any,
        atr: Any,
        trap: Optional[Mapping[str, Any]] = None,
        option_intelligence: Optional[Mapping[str, Any]] = None,
        market_behaviour: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        trap = trap if isinstance(trap, Mapping) else {}
        option_intelligence = option_intelligence if isinstance(option_intelligence, Mapping) else {}
        market_behaviour = market_behaviour if isinstance(market_behaviour, Mapping) else {}

        price_n = self._number(price)
        open_n = self._number(candle_open)
        high_n = self._number(candle_high)
        low_n = self._number(candle_low)
        close_n = self._number(candle_close)
        support_n = self._number(support)
        resistance_n = self._number(resistance)
        atr_n = self._number(atr)

        upper_score = 0.0
        lower_score = 0.0
        upper_evidence: List[str] = []
        lower_evidence: List[str] = []
        cautions: List[str] = []
        available = 0
        possible = 6

        valid_candle = (
            open_n is not None and high_n is not None and low_n is not None
            and close_n is not None and high_n > low_n
        )
        if valid_candle:
            available += 1
            candle_range = max(high_n - low_n, 0.01)
            body_high = max(open_n, close_n)
            body_low = min(open_n, close_n)
            upper_wick = max(high_n - body_high, 0.0)
            lower_wick = max(body_low - low_n, 0.0)
            upper_wick_pct = upper_wick / candle_range * 100.0
            lower_wick_pct = lower_wick / candle_range * 100.0

            if upper_wick_pct >= 35:
                upper_score += 18 if upper_wick_pct < 55 else 25
                upper_evidence.append(f"Large upper rejection wick ({upper_wick_pct:.0f}% of candle range)")
            if lower_wick_pct >= 35:
                lower_score += 18 if lower_wick_pct < 55 else 25
                lower_evidence.append(f"Large lower rejection wick ({lower_wick_pct:.0f}% of candle range)")
        else:
            candle_range = None
            upper_wick_pct = None
            lower_wick_pct = None
            cautions.append("Verified candle OHLC unavailable; sweep confidence reduced")

        # Strongest evidence: price traded beyond a known barrier and closed back
        # inside it. A touch without a close-back is only a break attempt.
        upper_sweep = False
        lower_sweep = False
        if valid_candle and resistance_n is not None:
            available += 1
            if high_n > resistance_n and close_n < resistance_n:
                upper_sweep = True
                overshoot = high_n - resistance_n
                upper_score += 38
                upper_evidence.append(
                    f"Candle swept {overshoot:.1f} points above resistance and closed back below"
                )
            elif high_n >= resistance_n:
                upper_score += 8
                cautions.append("Resistance tested but close-back rejection is not established")

        if valid_candle and support_n is not None:
            available += 1
            if low_n < support_n and close_n > support_n:
                lower_sweep = True
                overshoot = support_n - low_n
                lower_score += 38
                lower_evidence.append(
                    f"Candle swept {overshoot:.1f} points below support and closed back above"
                )
            elif low_n <= support_n:
                lower_score += 8
                cautions.append("Support tested but close-back rejection is not established")

        # Overshoots that are enormous versus ATR may indicate stale/incorrect
        # barriers. They remain visible but confidence is reduced.
        if valid_candle and atr_n is not None and atr_n > 0:
            available += 1
            if upper_sweep and resistance_n is not None:
                upper_overshoot_atr = (high_n - resistance_n) / atr_n
                if upper_overshoot_atr <= 0.45:
                    upper_score += 10
                    upper_evidence.append("Upside sweep remained bounded relative to ATR")
                elif upper_overshoot_atr > 1.0:
                    upper_score -= 10
                    cautions.append("Upside overshoot is unusually large versus ATR; barrier may be stale")
            if lower_sweep and support_n is not None:
                lower_overshoot_atr = (support_n - low_n) / atr_n
                if lower_overshoot_atr <= 0.45:
                    lower_score += 10
                    lower_evidence.append("Downside sweep remained bounded relative to ATR")
                elif lower_overshoot_atr > 1.0:
                    lower_score -= 10
                    cautions.append("Downside overshoot is unusually large versus ATR; barrier may be stale")

        strike_pressure = self._text(option_intelligence, "strike", "pressure")
        barrier_reaction = self._text(option_intelligence, "barrier", "barrier")
        fake_breakout = self._text(market_behaviour, "fake_breakout", "fake_breakout")
        if strike_pressure or barrier_reaction:
            available += 1
            if strike_pressure == "CE Resistance":
                upper_score += 10
                upper_evidence.append("CE resistance supports upside rejection evidence")
            elif strike_pressure == "PE Support":
                lower_score += 10
                lower_evidence.append("PE support supports downside rejection evidence")
            if barrier_reaction == "Rejection":
                upper_score += 6
                lower_score += 6
                cautions.append("Option barrier specialist also reports rejection")

        trap_state = str(trap.get("state", ""))
        if trap_state:
            available += 1
            if trap_state == "POSSIBLE_BULL_TRAP_RISK":
                upper_score += 10
                upper_evidence.append("Bull-trap risk report supports upside sweep review")
            elif trap_state == "POSSIBLE_BEAR_TRAP_RISK":
                lower_score += 10
                lower_evidence.append("Bear-trap risk report supports downside sweep review")
            elif trap_state == "TWO_WAY_TRAP_RISK":
                upper_score += 7
                lower_score += 7

        if fake_breakout == "Possible":
            upper_score += 8
            lower_score += 8
            cautions.append("Possible fake-breakout evidence requires follow-through confirmation")

        upper_score = self._clamp(upper_score)
        lower_score = self._clamp(lower_score)

        # Candidate status requires an actual barrier sweep + close-back. A wick
        # alone may be rejection, but it is not enough to call a liquidity grab.
        upper_candidate = bool(upper_sweep and upper_score >= 55)
        lower_candidate = bool(lower_sweep and lower_score >= 55)

        if upper_candidate and lower_candidate:
            state = "TWO_SIDED_LIQUIDITY_SWEEP_RISK"
            stop_hunt_watch = "BOTH_SHORT_AND_LONG_STOP_SWEEP_WATCH"
        elif upper_candidate:
            state = "POSSIBLE_UPSIDE_LIQUIDITY_GRAB"
            stop_hunt_watch = "SHORT_STOP_SWEEP_WATCH"
        elif lower_candidate:
            state = "POSSIBLE_DOWNSIDE_LIQUIDITY_GRAB"
            stop_hunt_watch = "LONG_STOP_SWEEP_WATCH"
        elif max(upper_score, lower_score) >= 35:
            state = "WATCH_FOR_SWEEP_CONFIRMATION"
            stop_hunt_watch = "SEQUENCE_CONFIRMATION_REQUIRED"
        else:
            state = "LOW_LIQUIDITY_SWEEP_EVIDENCE"
            stop_hunt_watch = "NO_ACTIVE_STOP_SWEEP_EVIDENCE"

        coverage = self._clamp(available / possible * 100.0)
        confidence = self._clamp(20.0 + coverage * 0.35 + min(max(upper_score, lower_score), 75.0) * 0.30)
        confidence = min(confidence, 82.0)

        return {
            "state": state,
            "upside_liquidity_grab_risk": {
                "score": round(upper_score, 1),
                "evidence": list(dict.fromkeys(upper_evidence))[:6],
            },
            "downside_liquidity_grab_risk": {
                "score": round(lower_score, 1),
                "evidence": list(dict.fromkeys(lower_evidence))[:6],
            },
            "stop_hunt_watch": stop_hunt_watch,
            "shared_cautions": list(dict.fromkeys(cautions))[:6],
            "candle_metrics": {
                "range_points": round(candle_range, 2) if candle_range is not None else None,
                "upper_wick_pct": round(upper_wick_pct, 1) if upper_wick_pct is not None else None,
                "lower_wick_pct": round(lower_wick_pct, 1) if lower_wick_pct is not None else None,
            },
            "data_coverage": round(coverage, 1),
            "confidence": round(confidence, 1),
            "confirmation_status": "UNCONFIRMED_SINGLE_CANDLE_REQUIRES_NEXT_SNAPSHOT",
            "authority": "EVIDENCE_ONLY_TO_CO",
            "manipulation_claim": "NOT_ESTABLISHED",
        }


class PanicSellingSpecialist:
    """Detect conservative panic-selling *evidence* from one verified snapshot.

    Panic is not inferred from a red candle alone. The foundation requires a
    downward move plus several independent witnesses such as a strong bearish
    candle closing near its low, elevated volume, bearish trend/VWAP placement,
    fear concentration, volatility, or OI behaviour. Late/exhausted moves and
    downside stop sweeps are reported as reversal cautions rather than treated
    as clean continuation evidence.
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
        vix: Any,
        candle_open: Any,
        candle_high: Any,
        candle_low: Any,
        candle_close: Any,
        atr: Any,
        emotion: Optional[Mapping[str, Any]] = None,
        trap: Optional[Mapping[str, Any]] = None,
        liquidity: Optional[Mapping[str, Any]] = None,
        price_action: Optional[Mapping[str, Any]] = None,
        option_intelligence: Optional[Mapping[str, Any]] = None,
        market_behaviour: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        emotion = emotion if isinstance(emotion, Mapping) else {}
        trap = trap if isinstance(trap, Mapping) else {}
        liquidity = liquidity if isinstance(liquidity, Mapping) else {}
        price_action = price_action if isinstance(price_action, Mapping) else {}
        option_intelligence = option_intelligence if isinstance(option_intelligence, Mapping) else {}
        market_behaviour = market_behaviour if isinstance(market_behaviour, Mapping) else {}

        change_n = self._number(change_pct)
        vix_n = self._number(vix)
        open_n = self._number(candle_open)
        high_n = self._number(candle_high)
        low_n = self._number(candle_low)
        close_n = self._number(candle_close)
        atr_n = self._number(atr)
        fear_score = self._number((emotion.get("retail_fear") or {}).get("score")) or 0.0
        day_position = self._number(emotion.get("day_range_position_pct"))

        score = 0.0
        evidence: List[str] = []
        cautions: List[str] = []
        available = 0
        possible = 8

        # 1) A real downward impulse is mandatory. Without it, bearish context
        # cannot be labelled as panic-selling evidence.
        downward_impulse = False
        if change_n is not None:
            available += 1
            if change_n <= -1.25:
                score += 32
                downward_impulse = True
                evidence.append(f"Extreme negative move {change_n:.2f}%")
            elif change_n <= -0.75:
                score += 25
                downward_impulse = True
                evidence.append(f"Sharp negative move {change_n:.2f}%")
            elif change_n <= -0.35:
                score += 15
                downward_impulse = True
                evidence.append(f"Broad negative move {change_n:.2f}%")
            elif change_n < 0:
                score += 4
                cautions.append(f"Negative move is limited ({change_n:.2f}%)")

        # 2) Candle anatomy: a large red body and a close near the candle low are
        # stronger witnesses than colour alone.
        valid_candle = (
            open_n is not None and high_n is not None and low_n is not None
            and close_n is not None and high_n > low_n
        )
        if valid_candle:
            available += 1
            candle_range = max(high_n - low_n, 0.01)
            body_ratio = abs(close_n - open_n) / candle_range
            close_position = self._clamp((close_n - low_n) / candle_range * 100.0)
            if close_n < open_n and body_ratio >= 0.72:
                score += 22
                downward_impulse = True
                evidence.append(f"Large bearish candle body ({body_ratio * 100:.0f}% of range)")
            elif close_n < open_n and body_ratio >= 0.55:
                score += 14
                downward_impulse = True
                evidence.append(f"Strong bearish candle body ({body_ratio * 100:.0f}% of range)")
            elif close_n >= open_n:
                cautions.append("Current candle is not bearish")

            if close_position <= 15:
                score += 15
                evidence.append(f"Candle closed near its low ({close_position:.0f}% of range)")
            elif close_position <= 30:
                score += 8
                evidence.append(f"Candle closed in lower range ({close_position:.0f}%)")

            if atr_n is not None and atr_n > 0:
                candle_atr_ratio = candle_range / atr_n
                if candle_atr_ratio >= 1.0:
                    score += 12
                    evidence.append(f"Single candle expanded to {candle_atr_ratio:.2f} ATR")
                elif candle_atr_ratio >= 0.65:
                    score += 7
                    evidence.append(f"Single candle expanded to {candle_atr_ratio:.2f} ATR")
            else:
                candle_atr_ratio = None
        else:
            candle_range = None
            body_ratio = None
            close_position = None
            candle_atr_ratio = None
            cautions.append("Verified candle OHLC unavailable")

        # 3) Retail emotion and day placement.
        if fear_score > 0 or day_position is not None:
            available += 1
            if fear_score >= 65:
                score += 14
                evidence.append(f"Retail fear is extreme ({fear_score:.0f}/100)")
            elif fear_score >= 45:
                score += 9
                evidence.append(f"Retail fear is elevated ({fear_score:.0f}/100)")
            if day_position is not None and day_position <= 15:
                score += 10
                evidence.append(f"Price is pinned near day low ({day_position:.0f}% of range)")
            elif day_position is not None and day_position <= 25:
                score += 6
                evidence.append(f"Price remains in lower day range ({day_position:.0f}%)")

        # 4) Price-action alignment.
        trend = self._text(price_action, "trend", "trend")
        vwap_status = self._text(price_action, "vwap", "vwap_status")
        move_stage = self._text(price_action, "move_stage", "stage")
        if trend or vwap_status:
            available += 1
            if "Bearish" in trend:
                score += 10
                evidence.append(f"Price-action trend: {trend}")
            if vwap_status == "Below VWAP":
                score += 7
                evidence.append("Price trading below VWAP")

        # 5) Participation witness from option volume.
        volume_status = self._text(option_intelligence, "volume", "status")
        if volume_status:
            available += 1
            if volume_status == "Spike":
                score += 17
                evidence.append("Option volume spike confirms urgent participation")
            elif volume_status == "High":
                score += 11
                evidence.append("High option volume supports broad participation")
            elif volume_status == "Weak":
                score -= 8
                cautions.append("Weak option volume does not confirm panic participation")

        # 6) OI behaviour helps distinguish fresh shorts from position exits.
        oi_signal = self._text(option_intelligence, "oi", "signal")
        if oi_signal:
            available += 1
            if oi_signal == "Short Build-up":
                score += 12
                evidence.append("OI indicates fresh short build-up")
            elif oi_signal == "Long Unwinding":
                score += 10
                evidence.append("OI indicates long unwinding")
            elif oi_signal == "Short Covering":
                score -= 8
                cautions.append("Short covering conflicts with clean panic-selling evidence")

        # 7) Volatility regime is a witness, never a standalone panic label.
        if vix_n is not None and vix_n > 0:
            available += 1
            if vix_n >= 22:
                score += 12
                evidence.append(f"Very high volatility regime, VIX {vix_n:.2f}")
            elif vix_n >= 17:
                score += 7
                evidence.append(f"Elevated volatility regime, VIX {vix_n:.2f}")

        # 8) Sequence-risk context. A late/exhausted move, possible bear trap, or
        # downside liquidity grab may be capitulation/stop sweep rather than safe
        # downside continuation.
        liquidity_state = str(liquidity.get("state", ""))
        trap_state = str(trap.get("state", ""))
        reversal_risk = self._text(market_behaviour, "reversal", "reversal_risk")
        if move_stage or liquidity_state or trap_state or reversal_risk:
            available += 1

        exhaustion_caution = move_stage in {"Late Move", "Exhaustion Move"} or reversal_risk == "High"
        stop_sweep_caution = liquidity_state in {
            "POSSIBLE_DOWNSIDE_LIQUIDITY_GRAB",
            "TWO_SIDED_LIQUIDITY_SWEEP_RISK",
        }
        bear_trap_caution = trap_state in {"POSSIBLE_BEAR_TRAP_RISK", "TWO_WAY_TRAP_RISK"}

        if exhaustion_caution:
            score += 5
            cautions.append(f"{move_stage or 'Late move'} may represent panic exhaustion/reversal risk")
        if stop_sweep_caution:
            score += 4
            cautions.append("Downside liquidity sweep may be capitulation or a stop hunt")
        if bear_trap_caution:
            cautions.append("Bear-trap evidence conflicts with clean downside continuation")

        score = self._clamp(score)
        panic_candidate = bool(downward_impulse and score >= 58)

        if panic_candidate and (exhaustion_caution or stop_sweep_caution or bear_trap_caution):
            state = "PANIC_EXHAUSTION_OR_STOP_SWEEP_WATCH"
            continuation_quality = "UNCERTAIN_REVERSAL_RISK"
        elif panic_candidate:
            state = "POSSIBLE_PANIC_SELLING"
            continuation_quality = "DOWNSIDE_PARTICIPATION_VISIBLE"
        elif downward_impulse and score >= 35:
            state = "PANIC_SELLING_WATCH"
            continuation_quality = "MORE_CONFIRMATION_REQUIRED"
        else:
            state = "LOW_PANIC_EVIDENCE"
            continuation_quality = "NOT_ESTABLISHED"

        coverage = self._clamp(available / possible * 100.0)
        confidence = self._clamp(20.0 + coverage * 0.35 + min(score, 75.0) * 0.30)
        confidence = min(confidence, 84.0)

        return {
            "state": state,
            "score": round(score, 1),
            "evidence": list(dict.fromkeys(evidence))[:8],
            "cautions": list(dict.fromkeys(cautions))[:8],
            "continuation_quality": continuation_quality,
            "metrics": {
                "candle_body_ratio": round(body_ratio, 2) if body_ratio is not None else None,
                "candle_close_position_pct": round(close_position, 1) if close_position is not None else None,
                "candle_atr_ratio": round(candle_atr_ratio, 2) if candle_atr_ratio is not None else None,
                "move_stage": move_stage or "Unknown",
                "volume_status": volume_status or "Unknown",
                "oi_signal": oi_signal or "Unknown",
            },
            "data_coverage": round(coverage, 1),
            "confidence": round(confidence, 1),
            "confirmation_status": "UNCONFIRMED_SINGLE_SNAPSHOT_REQUIRES_FOLLOW_THROUGH",
            "authority": "EVIDENCE_ONLY_TO_CO",
            "execution_instruction": "NONE",
        }


class UpsideParticipationSpecialist:
    """Separate possible short covering from possible long build-up.

    Both mechanisms can lift price, but they have different OI meaning:
    short covering requires price up with OI contraction, while long build-up
    requires price up with OI expansion. The existing Option Intelligence OI
    classification is treated as the primary witness and is cross-checked with
    candle quality, VWAP/trend placement, volume, barriers, traps and liquidity
    sweeps. This remains a single-snapshot evidence report, not confirmation.
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
        candle_open: Any,
        candle_high: Any,
        candle_low: Any,
        candle_close: Any,
        emotion: Optional[Mapping[str, Any]] = None,
        trap: Optional[Mapping[str, Any]] = None,
        liquidity: Optional[Mapping[str, Any]] = None,
        panic: Optional[Mapping[str, Any]] = None,
        price_action: Optional[Mapping[str, Any]] = None,
        option_intelligence: Optional[Mapping[str, Any]] = None,
        market_behaviour: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        emotion = emotion if isinstance(emotion, Mapping) else {}
        trap = trap if isinstance(trap, Mapping) else {}
        liquidity = liquidity if isinstance(liquidity, Mapping) else {}
        panic = panic if isinstance(panic, Mapping) else {}
        price_action = price_action if isinstance(price_action, Mapping) else {}
        option_intelligence = option_intelligence if isinstance(option_intelligence, Mapping) else {}
        market_behaviour = market_behaviour if isinstance(market_behaviour, Mapping) else {}

        change_n = self._number(change_pct)
        open_n = self._number(candle_open)
        high_n = self._number(candle_high)
        low_n = self._number(candle_low)
        close_n = self._number(candle_close)

        short_cover_score = 0.0
        long_build_score = 0.0
        short_cover_evidence: List[str] = []
        long_build_evidence: List[str] = []
        shared_evidence: List[str] = []
        cautions: List[str] = []
        available = 0
        possible = 7
        upward_impulse = False

        # 1) Price must actually be advancing. OI classification without an
        # upward impulse is not accepted as clean short-covering/long-build-up.
        if change_n is not None:
            available += 1
            if change_n >= 0.80:
                upward_impulse = True
                short_cover_score += 18
                long_build_score += 18
                shared_evidence.append(f"Sharp positive move +{change_n:.2f}%")
            elif change_n >= 0.35:
                upward_impulse = True
                short_cover_score += 12
                long_build_score += 12
                shared_evidence.append(f"Positive move +{change_n:.2f}%")
            elif change_n > 0:
                upward_impulse = True
                short_cover_score += 5
                long_build_score += 5
                cautions.append(f"Upside move is limited (+{change_n:.2f}%)")
            else:
                cautions.append("No positive market impulse in current snapshot")

        # 2) OI-price classification is the differentiating witness.
        oi_signal = self._text(option_intelligence, "oi", "signal")
        if oi_signal:
            available += 1
            if oi_signal == "Short Covering":
                short_cover_score += 42
                short_cover_evidence.append("Option Intelligence reports price-up with OI contraction")
                long_build_score -= 10
            elif oi_signal == "Long Build-up":
                long_build_score += 42
                long_build_evidence.append("Option Intelligence reports price-up with OI expansion")
                short_cover_score -= 10
            elif oi_signal == "Short Build-up":
                cautions.append("Fresh short build-up conflicts with a clean upside participation thesis")
            elif oi_signal == "Long Unwinding":
                cautions.append("Long unwinding conflicts with a clean upside participation thesis")
            else:
                cautions.append("OI-price classification is neutral")
        else:
            cautions.append("OI-price classification unavailable")

        # 3) A bullish candle closing near its high supports real participation.
        valid_candle = (
            open_n is not None and high_n is not None and low_n is not None
            and close_n is not None and high_n > low_n
        )
        if valid_candle:
            available += 1
            candle_range = max(high_n - low_n, 0.01)
            body_ratio = abs(close_n - open_n) / candle_range
            close_position = self._clamp((close_n - low_n) / candle_range * 100.0)
            if close_n > open_n and body_ratio >= 0.60:
                short_cover_score += 10
                long_build_score += 10
                shared_evidence.append(f"Strong bullish candle body ({body_ratio * 100:.0f}% of range)")
            elif close_n <= open_n:
                cautions.append("Current candle does not show bullish body follow-through")
            if close_position >= 80:
                short_cover_score += 8
                long_build_score += 8
                shared_evidence.append(f"Candle closed near its high ({close_position:.0f}% of range)")
            elif close_position < 55:
                cautions.append(f"Candle close is not near the high ({close_position:.0f}% of range)")
        else:
            body_ratio = None
            close_position = None
            cautions.append("Verified candle OHLC unavailable")

        # 4) Trend and VWAP placement support continuation, but do not identify
        # whether the move is new buying or old shorts exiting.
        trend = self._text(price_action, "trend", "trend")
        vwap_status = self._text(price_action, "vwap", "vwap_status")
        move_stage = self._text(price_action, "move_stage", "stage")
        barrier_zone = self._text(price_action, "barrier", "barrier_zone")
        if trend or vwap_status:
            available += 1
            if "Bullish" in trend:
                short_cover_score += 8
                long_build_score += 8
                shared_evidence.append(f"Price-action trend: {trend}")
            if vwap_status == "Above VWAP":
                short_cover_score += 7
                long_build_score += 7
                shared_evidence.append("Price is trading above VWAP")

        # 5) Participation quality from volume.
        volume_status = self._text(option_intelligence, "volume", "status")
        if volume_status:
            available += 1
            if volume_status == "Spike":
                short_cover_score += 13
                long_build_score += 13
                shared_evidence.append("Option volume spike supports active participation")
            elif volume_status == "High":
                short_cover_score += 8
                long_build_score += 8
                shared_evidence.append("High option volume supports participation")
            elif volume_status == "Weak":
                short_cover_score -= 7
                long_build_score -= 7
                cautions.append("Weak volume does not verify the upside mechanism")

        # 6) Strike pressure helps distinguish sustainable support from overhead
        # supply. It is a supporting witness, not a direction command.
        strike_pressure = self._text(option_intelligence, "strike", "pressure")
        barrier_reaction = self._text(option_intelligence, "barrier", "barrier")
        if strike_pressure or barrier_reaction:
            available += 1
            if strike_pressure == "PE Support":
                long_build_score += 8
                long_build_evidence.append("PE support is consistent with fresh long participation")
            elif strike_pressure == "CE Resistance":
                cautions.append("CE resistance may cap an upside participation move")
            if barrier_reaction == "Rejection":
                cautions.append("Barrier rejection weakens clean upside follow-through")

        # 7) Trap/liquidity/exhaustion context prevents the branch from calling a
        # mature squeeze or stop sweep a healthy continuation move.
        trap_state = str(trap.get("state", ""))
        liquidity_state = str(liquidity.get("state", ""))
        panic_state = str(panic.get("state", ""))
        reversal_risk = self._text(market_behaviour, "reversal", "reversal_risk")
        behaviour_barrier = self._text(market_behaviour, "barrier", "barrier_view")
        if trap_state or liquidity_state or panic_state or reversal_risk or behaviour_barrier:
            available += 1

        barrier_caution = (
            "Resistance" in barrier_zone
            or "Resistance" in behaviour_barrier
            or barrier_reaction == "Rejection"
        )
        bull_trap_caution = trap_state in {"POSSIBLE_BULL_TRAP_RISK", "TWO_WAY_TRAP_RISK"}
        upside_sweep_caution = liquidity_state in {
            "POSSIBLE_UPSIDE_LIQUIDITY_GRAB",
            "TWO_SIDED_LIQUIDITY_SWEEP_RISK",
        }
        exhaustion_caution = move_stage in {"Late Move", "Exhaustion Move"} or reversal_risk == "High"

        if panic_state in {"POSSIBLE_PANIC_SELLING", "PANIC_EXHAUSTION_OR_STOP_SWEEP_WATCH"} and oi_signal == "Short Covering":
            short_cover_score += 6
            short_cover_evidence.append("Short covering may be a rebound after panic/forced exits")
        if barrier_caution:
            short_cover_score -= 4
            long_build_score -= 6
            cautions.append("Upside move is approaching or rejecting from resistance")
        if bull_trap_caution:
            short_cover_score -= 5
            long_build_score -= 8
            cautions.append("Bull-trap evidence conflicts with clean upside continuation")
        if upside_sweep_caution:
            short_cover_score -= 5
            long_build_score -= 8
            cautions.append("Upside liquidity sweep may be a stop run rather than sustainable buying")
        if exhaustion_caution:
            short_cover_score -= 3
            long_build_score -= 6
            cautions.append(f"{move_stage or 'High reversal risk'} may indicate upside exhaustion")

        short_cover_score = self._clamp(short_cover_score)
        long_build_score = self._clamp(long_build_score)
        caution_context = barrier_caution or bull_trap_caution or upside_sweep_caution or exhaustion_caution

        if upward_impulse and oi_signal == "Short Covering" and short_cover_score >= 58:
            if caution_context:
                state = "SHORT_COVERING_EXHAUSTION_WATCH"
                follow_through = "UPMOVE_VISIBLE_BUT_REVERSAL_RISK"
            else:
                state = "POSSIBLE_SHORT_COVERING"
                follow_through = "PRICE_UP_OI_DOWN_SEQUENCE_VISIBLE"
            dominant_mechanism = "SHORT_COVERING"
        elif upward_impulse and oi_signal == "Long Build-up" and long_build_score >= 58:
            if caution_context:
                state = "LONG_BUILDUP_AT_BARRIER_WATCH"
                follow_through = "FRESH_LONGS_VISIBLE_BUT_BARRIER_RISK"
            else:
                state = "POSSIBLE_LONG_BUILDUP"
                follow_through = "PRICE_UP_OI_UP_SEQUENCE_VISIBLE"
            dominant_mechanism = "LONG_BUILDUP"
        elif upward_impulse and max(short_cover_score, long_build_score) >= 32:
            state = "UPMOVE_PARTICIPATION_WATCH"
            dominant_mechanism = "UNRESOLVED"
            follow_through = "MORE_OI_AND_PRICE_CONFIRMATION_REQUIRED"
        else:
            state = "LOW_UPMOVE_PARTICIPATION_EVIDENCE"
            dominant_mechanism = "NOT_ESTABLISHED"
            follow_through = "NOT_ESTABLISHED"

        coverage = self._clamp(available / possible * 100.0)
        confidence = self._clamp(18.0 + coverage * 0.35 + min(max(short_cover_score, long_build_score), 78.0) * 0.32)
        confidence = min(confidence, 84.0)

        return {
            "state": state,
            "dominant_mechanism": dominant_mechanism,
            "short_covering": {
                "score": round(short_cover_score, 1),
                "evidence": list(dict.fromkeys(short_cover_evidence + shared_evidence))[:8],
            },
            "long_build_up": {
                "score": round(long_build_score, 1),
                "evidence": list(dict.fromkeys(long_build_evidence + shared_evidence))[:8],
            },
            "cautions": list(dict.fromkeys(cautions))[:8],
            "follow_through_status": follow_through,
            "metrics": {
                "oi_signal": oi_signal or "Unknown",
                "volume_status": volume_status or "Unknown",
                "move_stage": move_stage or "Unknown",
                "candle_body_ratio": round(body_ratio, 2) if body_ratio is not None else None,
                "candle_close_position_pct": round(close_position, 1) if close_position is not None else None,
            },
            "data_coverage": round(coverage, 1),
            "confidence": round(confidence, 1),
            "confirmation_status": "UNCONFIRMED_SINGLE_SNAPSHOT_REQUIRES_OI_PRICE_FOLLOW_THROUGH",
            "authority": "EVIDENCE_ONLY_TO_CO",
            "execution_instruction": "NONE",
        }


class MarketPsychologyDirector:
    """DSP Market Psychology: one report, no independent trade authority."""

    VERSION = "V36.5_PSYCHOLOGY_WITH_UPSIDE_PARTICIPATION_EVIDENCE"

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
        candle_open: Any = None,
        candle_high: Any = None,
        candle_low: Any = None,
        candle_close: Any = None,
        support: Any = None,
        resistance: Any = None,
        atr: Any = None,
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
        liquidity = LiquiditySweepSpecialist().analyze(
            price=price,
            candle_open=candle_open,
            candle_high=candle_high,
            candle_low=candle_low,
            candle_close=candle_close,
            support=support,
            resistance=resistance,
            atr=atr,
            trap=trap,
            option_intelligence=option_details,
            market_behaviour=behaviour_details,
        )
        panic = PanicSellingSpecialist().analyze(
            change_pct=change_pct,
            vix=vix,
            candle_open=candle_open,
            candle_high=candle_high,
            candle_low=candle_low,
            candle_close=candle_close,
            atr=atr,
            emotion=emotion,
            trap=trap,
            liquidity=liquidity,
            price_action=price_action_details,
            option_intelligence=option_details,
            market_behaviour=behaviour_details,
        )
        participation = UpsideParticipationSpecialist().analyze(
            change_pct=change_pct,
            candle_open=candle_open,
            candle_high=candle_high,
            candle_low=candle_low,
            candle_close=candle_close,
            emotion=emotion,
            trap=trap,
            liquidity=liquidity,
            panic=panic,
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
        liquidity_state = str(liquidity["state"])
        upper_liquidity = float(liquidity["upside_liquidity_grab_risk"]["score"])
        lower_liquidity = float(liquidity["downside_liquidity_grab_risk"]["score"])
        panic_state = str(panic["state"])
        panic_score = float(panic["score"])
        participation_state = str(participation["state"])
        short_cover_score = float(participation["short_covering"]["score"])
        long_build_score = float(participation["long_build_up"]["score"])

        details = {
            **emotion,
            "trap_detection": trap,
            "liquidity_sweep": liquidity,
            "panic_selling": panic,
            "upside_participation": participation,
            "authority": "EVIDENCE_ONLY_TO_CO",
            "phase_control": "OBSERVATION_ONLY_NOT_IN_DIRECTIONAL_CONSENSUS",
        }
        summary = (
            f"Market psychology evidence: {state} | Fear {fear_score:.0f}/100 | "
            f"Greed {greed_score:.0f}/100 | Trap {trap_state} "
            f"(Bull {bull_trap:.0f}, Bear {bear_trap:.0f}) | "
            f"Liquidity {liquidity_state} (Up {upper_liquidity:.0f}, Down {lower_liquidity:.0f}) | "
            f"Panic {panic_state} ({panic_score:.0f}/100) | "
            f"Participation {participation_state} (SC {short_cover_score:.0f}, LB {long_build_score:.0f}) | "
            f"CO verification required"
        )
        return MarketPsychologyReport(
            summary=summary,
            # Overall branch confidence remains the validated V36.1 emotion
            # confidence. Trap, liquidity, panic and participation confidence
            # are displayed separately and cannot silently change CO case
            # strength during foundation testing.
            confidence=confidence,
            details=details,
        )
