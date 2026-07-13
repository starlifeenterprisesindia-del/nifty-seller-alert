"""
price_action.py
Version: V50.5
Department: Price Action

Reads chart structure plus same-day live movement memory. It never issues a
trade decision. Missing automatic data is reported as unavailable instead of
silently scoring stale manual defaults.
"""
from dataclasses import dataclass
from typing import Dict, Any, Mapping


@dataclass
class PriceActionReport:
    summary: str
    confidence: float
    details: Dict[str, Any]


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class TrendSpecialist:
    def analyze(self, price, ema20, ema50, movement=None):
        movement = movement if isinstance(movement, Mapping) else {}
        phase = str(movement.get("phase", "NORMAL"))
        if price > ema20 > ema50:
            trend = "Bullish Trend"
            structure = "BULLISH"
            strength = 85
        elif price < ema20 < ema50:
            trend = "Bearish Trend"
            structure = "BEARISH"
            strength = 85
        elif price > ema20 and ema20 < ema50:
            trend = "Recovering / Mixed Bullish"
            structure = "MIXED_BULLISH"
            strength = 60
        elif price < ema20 and ema20 > ema50:
            trend = "Weakening / Mixed Bearish"
            structure = "MIXED_BEARISH"
            strength = 60
        else:
            trend = "Sideways / Unclear"
            structure = "NEUTRAL"
            strength = 40

        # Structure and current impulse are intentionally kept separate.
        if phase == "STRONG_RECOVERY" and structure in {"BEARISH", "MIXED_BEARISH"}:
            trend = "Bearish Structure / Strong Recovery"
            strength = 72
        elif phase == "RECOVERY" and structure in {"BEARISH", "MIXED_BEARISH"}:
            trend = "Bearish Structure / Recovery Active"
            strength = 64
        elif phase == "STRONG_PULLBACK_DOWN" and structure in {"BULLISH", "MIXED_BULLISH"}:
            trend = "Bullish Structure / Strong Pullback"
            strength = 72
        elif phase == "PULLBACK_DOWN" and structure in {"BULLISH", "MIXED_BULLISH"}:
            trend = "Bullish Structure / Pullback Active"
            strength = 64

        return {"trend": trend, "structure": structure, "strength": strength}


class VWAPSpecialist:
    def analyze(self, price, vwap):
        if vwap is None or _num(vwap) == 0:
            return {"vwap_status": "Unknown", "strength": 0}
        vwap = _num(vwap)
        distance = ((price - vwap) / vwap) * 100
        status = "Above VWAP" if price > vwap else "Below VWAP" if price < vwap else "At VWAP"
        return {"vwap_status": status, "distance_pct": round(distance, 3), "strength": min(100, abs(distance) * 20)}


class ATRSpecialist:
    def analyze(self, current_range, atr):
        atr = _num(atr)
        if atr <= 0:
            return {"atr_status": "Unknown", "range_ratio": 0}
        ratio = _num(current_range) / atr
        status = "Expanded Move" if ratio >= 1.5 else "Normal Move" if ratio >= 0.8 else "Compressed / Low Energy"
        return {"atr_status": status, "range_ratio": round(ratio, 2)}


class BarrierSpecialist:
    def analyze(self, price, support, resistance):
        nearest = None
        zone = "No Major Barrier Nearby"
        distance = None
        if resistance is not None:
            resistance_distance = _num(resistance) - price
            if resistance_distance >= 0:
                nearest, distance = "Resistance", resistance_distance
                if resistance_distance <= 20:
                    zone = "Near Resistance"
        if support is not None:
            support_distance = price - _num(support)
            if support_distance >= 0 and (distance is None or support_distance < distance):
                nearest, distance = "Support", support_distance
                if support_distance <= 20:
                    zone = "Near Support"
        return {"nearest_barrier": nearest, "barrier_zone": zone, "distance_points": round(distance, 2) if distance is not None else None}


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
        return {"candle_type": candle, "body_ratio": round(body_ratio, 2)}


class MoveStageSpecialist:
    def analyze(self, points_moved_from_open, atr, movement=None):
        movement = movement if isinstance(movement, Mapping) else {}
        phase = str(movement.get("phase", "NORMAL"))
        atr = _num(atr)
        if atr <= 0:
            return {"stage": "Unknown", "risk": "Unknown"}
        ratio = abs(_num(points_moved_from_open)) / atr
        if phase == "STRONG_RECOVERY":
            stage, risk = "Recovery Leg", "Bearish Continuation Unconfirmed"
        elif phase == "RECOVERY":
            stage, risk = "Recovery Developing", "Continuation Needs Confirmation"
        elif phase == "STRONG_PULLBACK_DOWN":
            stage, risk = "Pullback Down Leg", "Bullish Continuation Unconfirmed"
        elif phase == "PULLBACK_DOWN":
            stage, risk = "Pullback Developing", "Continuation Needs Confirmation"
        elif ratio < 0.35:
            stage, risk = "Early Move", "Low Exhaustion"
        elif ratio < 0.8:
            stage, risk = "Mid Move", "Moderate Exhaustion"
        elif ratio < 1.2:
            stage, risk = "Late Move", "High Exhaustion"
        else:
            stage, risk = "Exhaustion Move", "Very High Exhaustion"
        return {"stage": stage, "exhaustion_risk": risk, "move_atr_ratio": round(ratio, 2)}


class RangeSpecialist:
    def analyze(self, day_high, day_low, atr):
        atr = _num(atr)
        if atr <= 0:
            return {"range_status": "Unknown"}
        width = _num(day_high) - _num(day_low)
        ratio = width / atr
        status = "Tight Range" if ratio < 0.5 else "Normal Range" if ratio < 1.0 else "Wide Range / Trend Day"
        return {"range_status": status, "range_width": round(width, 2), "range_atr_ratio": round(ratio, 2)}


class MovementSpecialist:
    def analyze(self, movement):
        m = movement if isinstance(movement, Mapping) else {}
        return {
            "phase": str(m.get("phase", "UNAVAILABLE")),
            "label": str(m.get("label", "Movement memory unavailable")),
            "last_move": m.get("last_move"),
            "move_1m": m.get("move_1m"),
            "move_3m": m.get("move_3m"),
            "move_5m": m.get("move_5m"),
            "recovery_from_low": m.get("recovery_from_low", 0),
            "pullback_from_high": m.get("pullback_from_high", 0),
            "movement_bias": m.get("movement_bias", 0),
            "sample_count": m.get("sample_count", 0),
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
        self.movement = MovementSpecialist()

    def build_report(self, **k) -> PriceActionReport:
        data_available = bool(k.get("data_available", True))
        source = str(k.get("source", "Unknown"))
        movement = k.get("movement", {}) if isinstance(k.get("movement", {}), Mapping) else {}

        if not data_available:
            details = {
                "availability": {"status": "UNAVAILABLE", "source": source, "used_for_direction": False},
                "trend": {"trend": "Unknown - automatic price action unavailable", "structure": "UNKNOWN", "strength": 0},
                "vwap": {"vwap_status": "Unknown", "strength": 0},
                "atr": {"atr_status": "Unknown", "range_ratio": 0},
                "barrier": {"nearest_barrier": None, "barrier_zone": "Unknown", "distance_points": None},
                "candle": {"candle_type": "Unknown", "body_ratio": 0},
                "move_stage": {"stage": "Unknown", "exhaustion_risk": "Unknown", "move_atr_ratio": 0},
                "range": {"range_status": "Unknown"},
                "movement": self.movement.analyze(movement),
            }
            return PriceActionReport(
                summary="Price Action unavailable - stale manual defaults excluded from AI direction",
                confidence=0.0,
                details=details,
            )

        details = {
            "availability": {"status": "READY", "source": source, "used_for_direction": True},
            "trend": self.trend.analyze(k["price"], k["ema20"], k["ema50"], movement),
            "vwap": self.vwap.analyze(k["price"], k.get("vwap")),
            "atr": self.atr.analyze(k["current_range"], k.get("atr")),
            "barrier": self.barrier.analyze(k["price"], k.get("support"), k.get("resistance")),
            "candle": self.candle.analyze(k["open_price"], k["high"], k["low"], k["close"]),
            "move_stage": self.stage.analyze(k["points_moved_from_open"], k.get("atr"), movement),
            "range": self.range.analyze(k["day_high"], k["day_low"], k.get("atr")),
            "movement": self.movement.analyze(movement),
        }
        summary = f'{details["trend"]["trend"]} | {details["move_stage"]["stage"]} | {details["barrier"]["barrier_zone"]}'
        confidence = details["trend"]["strength"]
        if str(source).lower().startswith("manual"):
            confidence = min(confidence, 45)
        return PriceActionReport(summary=summary, confidence=confidence, details=details)
