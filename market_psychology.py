"""
market_psychology.py
Version: V36.1
Department: Market Psychology
Status: Phase-1 — Retail Fear / Retail Greed Evidence

Safety contract:
- Evidence and interpretation only.
- Never emits BUY, SELL CE, SELL PE, IRON CONDOR, or execution permission.
- Report must travel through DSP review -> CO case file -> AI_MASTER.
- Uses the existing verified market snapshot; no API calls, loops, or background work.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


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

        # 5) PCR is recorded as context only because extreme PCR can be interpreted
        # differently across regimes. It does not directly add fear/greed points.
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
            "authority": "EVIDENCE_ONLY_TO_CO",
        }


class MarketPsychologyDirector:
    """DSP Market Psychology: one report, no independent trade authority."""

    VERSION = "V36.1_RETAIL_EMOTION_EVIDENCE"

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
    ) -> MarketPsychologyReport:
        details = RetailEmotionSpecialist().analyze(
            price=price,
            change_pct=change_pct,
            vix=vix,
            ema20=ema20,
            vwap=vwap,
            day_high=day_high,
            day_low=day_low,
            pcr=pcr,
        )
        fear_score = float(details["retail_fear"]["score"])
        greed_score = float(details["retail_greed"]["score"])
        state = str(details["psychology_state"])
        confidence = float(details["confidence"])
        summary = (
            f"Market psychology evidence: {state} | "
            f"Retail Fear {fear_score:.0f}/100 | Retail Greed {greed_score:.0f}/100 | "
            "CO verification required"
        )
        return MarketPsychologyReport(
            summary=summary,
            confidence=confidence,
            details=details,
        )
