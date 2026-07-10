"""
price_action.py
Version: V23.1
Department: Price Action
Status: Phase-1 Professional Architecture

Purpose:
- Read chart behaviour like a professional trader
- No BUY/SELL decision
- Only report facts + interpretation to AI_MASTER
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class PriceActionReport:
    summary: str
    confidence: float
    details: Dict[str, Any]


class TrendSpecialist:
    def analyze(self, price, ema20, ema50):
        if price > ema20 > ema50:
            trend = "Bullish Trend"
            strength = 85
        elif price < ema20 < ema50:
            trend = "Bearish Trend"
            strength = 85
        elif price > ema20 and ema20 < ema50:
            trend = "Recovering / Mixed Bullish"
            strength = 60
        elif price < ema20 and ema20 > ema50:
            trend = "Weakening / Mixed Bearish"
            strength = 60
        else:
            trend = "Sideways / Unclear"
            strength = 40

        return {
            "trend": trend,
            "strength": strength
        }


class VWAPSpecialist:
    def analyze(self, price, vwap):
        if vwap is None or vwap == 0:
            return {"vwap_status": "Unknown", "strength": 0}

        distance = ((price - vwap) / vwap) * 100

        if price > vwap:
            status = "Above VWAP"
        elif price < vwap:
            status = "Below VWAP"
        else:
            status = "At VWAP"

        return {
            "vwap_status": status,
            "distance_pct": round(distance, 3),
            "strength": min(100, abs(distance) * 20)
        }


class ATRSpecialist:
    def analyze(self, current_range, atr):
        if atr is None or atr <= 0:
            return {"atr_status": "Unknown", "range_ratio": 0}

        ratio = current_range / atr

        if ratio >= 1.5:
            status = "Expanded Move"
        elif ratio >= 0.8:
            status = "Normal Move"
        else:
            status = "Compressed / Low Energy"

        return {
            "atr_status": status,
            "range_ratio": round(ratio, 2)
        }


class BarrierSpecialist:
    def analyze(self, price, support, resistance):
        nearest = None
        zone = "No Major Barrier Nearby"
        distance = None

        if resistance is not None:
            resistance_distance = resistance - price
            if resistance_distance >= 0:
                nearest = "Resistance"
                distance = resistance_distance
                if resistance_distance <= 20:
                    zone = "Near Resistance"

        if support is not None:
            support_distance = price - support
            if support_distance >= 0:
                if distance is None or support_distance < distance:
                    nearest = "Support"
                    distance = support_distance
                    if support_distance <= 20:
                        zone = "Near Support"

        return {
            "nearest_barrier": nearest,
            "barrier_zone": zone,
            "distance_points": round(distance, 2) if distance is not None else None
        }


class CandleSpecialist:
    def analyze(self, open_price, high, low, close):
        body = abs(close - open_price)
        candle_range = max(high - low, 0.01)
        body_ratio = body / candle_range

        if close > open_price and body_ratio >= 0.6:
            candle = "Strong Bullish Candle"
        elif close < open_price and body_ratio >= 0.6:
            candle = "Strong Bearish Candle"
        elif body_ratio <= 0.25:
            candle = "Indecision / Wick Candle"
        else:
            candle = "Normal Candle"

        return {
            "candle_type": candle,
            "body_ratio": round(body_ratio, 2)
        }


class MoveStageSpecialist:
    def analyze(self, points_moved_from_open, atr):
        if atr is None or atr <= 0:
            return {"stage": "Unknown", "risk": "Unknown"}

        ratio = abs(points_moved_from_open) / atr

        if ratio < 0.35:
            stage = "Early Move"
            risk = "Low Exhaustion"
        elif ratio < 0.8:
            stage = "Mid Move"
            risk = "Moderate Exhaustion"
        elif ratio < 1.2:
            stage = "Late Move"
            risk = "High Exhaustion"
        else:
            stage = "Exhaustion Move"
            risk = "Very High Exhaustion"

        return {
            "stage": stage,
            "exhaustion_risk": risk,
            "move_atr_ratio": round(ratio, 2)
        }


class RangeSpecialist:
    def analyze(self, day_high, day_low, atr):
        if atr is None or atr <= 0:
            return {"range_status": "Unknown"}

        width = day_high - day_low
        ratio = width / atr

        if ratio < 0.5:
            status = "Tight Range"
        elif ratio < 1.0:
            status = "Normal Range"
        else:
            status = "Wide Range / Trend Day"

        return {
            "range_status": status,
            "range_width": round(width, 2),
            "range_atr_ratio": round(ratio, 2)
        }


class PriceActionDirector:
    def __init__(self):
        self.trend = TrendSpecialist()
        self.vwap = VWAPSpecialist()
        self.atr = ATRSpecialist()
        self.barrier = BarrierSpecialist()
        self.candle = CandleSpecialist()
        self.stage = MoveStageSpecialist()
        self.range = RangeSpecialist()

    def build_report(self, **k) -> PriceActionReport:
        details = {
            "trend": self.trend.analyze(k["price"], k["ema20"], k["ema50"]),
            "vwap": self.vwap.analyze(k["price"], k.get("vwap")),
            "atr": self.atr.analyze(k["current_range"], k.get("atr")),
            "barrier": self.barrier.analyze(k["price"], k.get("support"), k.get("resistance")),
            "candle": self.candle.analyze(k["open_price"], k["high"], k["low"], k["close"]),
            "move_stage": self.stage.analyze(k["points_moved_from_open"], k.get("atr")),
            "range": self.range.analyze(k["day_high"], k["day_low"], k.get("atr")),
        }

        trend_strength = details["trend"]["strength"]
        summary = (
            f'{details["trend"]["trend"]} | '
            f'{details["move_stage"]["stage"]} | '
            f'{details["barrier"]["barrier_zone"]}'
        )

        return PriceActionReport(
            summary=summary,
            confidence=trend_strength,
            details=details,
        )
