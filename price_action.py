"""
price_action.py
Version: V50.8.3
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
    def analyze(self, price, ema20, ema50, vwap=None, atr=None, movement=None):
        movement = movement if isinstance(movement, Mapping) else {}
        phase = str(movement.get("phase", "NORMAL"))
        sample_count = int(_num(movement.get("sample_count", 0), 0))
        price = _num(price)
        ema20 = _num(ema20)
        ema50 = _num(ema50)
        vwap_value = _num(vwap, 0.0)
        confirmation_buffer = max(2.0, _num(atr, 0.0) * 0.05)

        above_ema20 = price >= ema20 + confirmation_buffer
        above_ema50 = price >= ema50 + confirmation_buffer
        above_vwap = vwap_value <= 0 or price >= vwap_value + confirmation_buffer
        below_ema20 = price <= ema20 - confirmation_buffer
        below_ema50 = price <= ema50 - confirmation_buffer
        below_vwap = vwap_value <= 0 or price <= vwap_value - confirmation_buffer

        if above_ema20 and ema20 > ema50:
            trend = "Bullish Trend"
            structure = "BULLISH"
            strength = 85
        elif below_ema20 and ema20 < ema50:
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

        recovery_phase = phase in {"RECOVERY", "STRONG_RECOVERY"}
        pullback_phase = phase in {"PULLBACK_DOWN", "STRONG_PULLBACK_DOWN"}
        recovery_confirmed = bool(recovery_phase and sample_count >= 3 and above_ema20 and above_ema50 and above_vwap)
        pullback_confirmed = bool(pullback_phase and sample_count >= 3 and below_ema20 and below_ema50 and below_vwap)

        if recovery_confirmed:
            trend = "Bullish Recovery Confirmed"
            structure = "BULLISH"
            strength = max(strength, 85 if phase == "STRONG_RECOVERY" else 78)
        elif recovery_phase:
            trend = "Recovery Attempt / Confirmation Pending"
            structure = "MIXED_BULLISH" if price >= min(ema20, ema50) else structure
            strength = min(max(strength, 52), 58)
        elif pullback_confirmed:
            trend = "Bearish Pullback Confirmed"
            structure = "BEARISH"
            strength = max(strength, 85 if phase == "STRONG_PULLBACK_DOWN" else 78)
        elif pullback_phase:
            trend = "Pullback Attempt / Confirmation Pending"
            structure = "MIXED_BEARISH" if price <= max(ema20, ema50) else structure
            strength = min(max(strength, 52), 58)

        directional_confirmation = (
            "BULLISH_CONFIRMED" if recovery_confirmed or (above_ema20 and above_ema50 and above_vwap)
            else "BEARISH_CONFIRMED" if pullback_confirmed or (below_ema20 and below_ema50 and below_vwap)
            else "UNCONFIRMED"
        )
        return {
            "trend": trend,
            "structure": structure,
            "strength": strength,
            "directional_confirmation": directional_confirmation,
            "recovery_confirmed": recovery_confirmed,
            "pullback_confirmed": pullback_confirmed,
            "above_ema20": above_ema20,
            "above_ema50": above_ema50,
            "above_vwap": above_vwap,
            "below_ema20": below_ema20,
            "below_ema50": below_ema50,
            "below_vwap": below_vwap,
            "confirmation_buffer_points": round(confirmation_buffer, 2),
            "sample_count": sample_count,
        }


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
    def analyze(
        self,
        price,
        support,
        resistance,
        *,
        support_source="Structural Support",
        resistance_source="Structural Resistance",
        atr=None,
    ):
        price = _num(price)
        support_value = _num(support, 0.0) if support is not None else None
        resistance_value = _num(resistance, 0.0) if resistance is not None else None

        # A fixed 20-point gate was too brittle around daily pivots.  The bounded
        # ATR-aware threshold stays conservative while recognising a nearby R1/S1
        # barrier during normal intraday volatility.
        atr_value = max(_num(atr, 0.0), 0.0)
        near_threshold = min(35.0, max(20.0, atr_value * 1.5))

        support_distance = None
        resistance_distance = None
        if support_value is not None and support_value > 0 and support_value <= price:
            support_distance = price - support_value
        if resistance_value is not None and resistance_value > 0 and resistance_value >= price:
            resistance_distance = resistance_value - price

        near_support = support_distance is not None and support_distance <= near_threshold
        near_resistance = resistance_distance is not None and resistance_distance <= near_threshold

        if near_support and near_resistance:
            zone = "Near Resistance | Near Support"
            label = (
                f"Between {support_source} {support_value:.2f} support ({support_distance:.0f} pts) "
                f"and {resistance_source} {resistance_value:.2f} resistance ({resistance_distance:.0f} pts)"
            )
        elif near_resistance:
            zone = "Near Resistance"
            label = f"Near Resistance — {resistance_source} {resistance_value:.2f} ({resistance_distance:.0f} pts)"
        elif near_support:
            zone = "Near Support"
            label = f"Near Support — {support_source} {support_value:.2f} ({support_distance:.0f} pts)"
        else:
            zone = "No Major Barrier Nearby"
            candidates = []
            if support_distance is not None:
                candidates.append((support_distance, "Support", support_source, support_value))
            if resistance_distance is not None:
                candidates.append((resistance_distance, "Resistance", resistance_source, resistance_value))
            if candidates:
                distance, nearest, source, level = min(candidates, key=lambda item: item[0])
                label = f"No Major Barrier Nearby — nearest {nearest}: {source} {level:.2f} ({distance:.0f} pts)"
            else:
                distance, nearest = None, None
                label = zone

        if near_support or near_resistance:
            candidates = []
            if support_distance is not None:
                candidates.append((support_distance, "Support"))
            if resistance_distance is not None:
                candidates.append((resistance_distance, "Resistance"))
            distance, nearest = min(candidates, key=lambda item: item[0]) if candidates else (None, None)

        return {
            "nearest_barrier": nearest,
            "barrier_zone": zone,
            "barrier_label": label,
            "distance_points": round(distance, 2) if distance is not None else None,
            "support_level": round(support_value, 2) if support_value is not None and support_value > 0 else None,
            "support_source": str(support_source),
            "support_distance_points": round(support_distance, 2) if support_distance is not None else None,
            "resistance_level": round(resistance_value, 2) if resistance_value is not None and resistance_value > 0 else None,
            "resistance_source": str(resistance_source),
            "resistance_distance_points": round(resistance_distance, 2) if resistance_distance is not None else None,
            "near_threshold_points": round(near_threshold, 2),
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
                "barrier": {"nearest_barrier": None, "barrier_zone": "Unknown", "barrier_label": "Unknown", "distance_points": None},
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

        trend_details = self.trend.analyze(k["price"], k["ema20"], k["ema50"], k.get("vwap"), k.get("atr"), movement)
        movement_details = self.movement.analyze(movement)
        movement_details.update({
            "recovery_confirmed": bool(trend_details.get("recovery_confirmed", False)),
            "pullback_confirmed": bool(trend_details.get("pullback_confirmed", False)),
            "directional_confirmation": trend_details.get("directional_confirmation", "UNCONFIRMED"),
        })
        details = {
            "availability": {"status": "READY", "source": source, "used_for_direction": True},
            "trend": trend_details,
            "vwap": self.vwap.analyze(k["price"], k.get("vwap")),
            "atr": self.atr.analyze(k["current_range"], k.get("atr")),
            "barrier": self.barrier.analyze(
                k["price"],
                k.get("support"),
                k.get("resistance"),
                support_source=k.get("support_source", "Structural Support"),
                resistance_source=k.get("resistance_source", "Structural Resistance"),
                atr=k.get("atr"),
            ),
            "candle": self.candle.analyze(k["open_price"], k["high"], k["low"], k["close"]),
            "move_stage": self.stage.analyze(k["points_moved_from_open"], k.get("atr"), movement),
            "range": self.range.analyze(k["day_high"], k["day_low"], k.get("atr")),
            "movement": movement_details,
        }
        summary = f'{details["trend"]["trend"]} | {details["move_stage"]["stage"]} | {details["barrier"].get("barrier_label", details["barrier"]["barrier_zone"])}'
        confidence = details["trend"]["strength"]
        if str(source).lower().startswith("manual"):
            confidence = min(confidence, 45)
        return PriceActionReport(summary=summary, confidence=confidence, details=details)
