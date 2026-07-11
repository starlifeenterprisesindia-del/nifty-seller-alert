"""
market_journey.py
Version: V35.0
Role: Market journey, barrier-pressure, and move-potential intelligence.

Safety:
- Descriptive evidence only; never overrides AI_MASTER.
- Uses one verified snapshot and bounded session state.
- No API calls, loops, threads, or automatic weight changes.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Mapping, MutableMapping, Optional


@dataclass(frozen=True)
class MarketJourneyReport:
    status: str
    direction: str
    move_stage: str
    market_energy: str
    expected_zone_low: float
    expected_zone_high: float
    remaining_points_low: float
    remaining_points_high: float
    breakout_probability: float
    reversal_probability: float
    barrier_type: str
    barrier_level: Optional[float]
    barrier_touch_count: int
    barrier_strength: str
    time_phase: str
    reasons: list[str]
    warnings: list[str]

    def to_compact_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MarketJourneyEngine:
    STATE_KEY = "v35_barrier_state"

    def evaluate(
        self,
        *,
        state: MutableMapping[str, Any],
        price: float,
        atr: float,
        support: Optional[float],
        resistance: Optional[float],
        price_report: Any,
        option_report: Any,
        behaviour_report: Any,
        smart_money_report: Any,
        hour: int,
    ) -> MarketJourneyReport:
        price = float(price or 0.0)
        atr = max(float(atr or 0.0), 1.0)
        support = self._number_or_none(support)
        resistance = self._number_or_none(resistance)

        p = self._details(price_report)
        o = self._details(option_report)
        b = self._details(behaviour_report)
        m = self._details(smart_money_report)

        trend = str(p.get("trend", {}).get("trend", ""))
        stage = str(p.get("move_stage", {}).get("stage", "Unknown"))
        energy = str(b.get("energy", {}).get("market_energy", "Unknown"))
        volume = str(o.get("volume", {}).get("status", "Unknown"))
        strike_pressure = str(o.get("strike", {}).get("pressure", "Balanced"))
        pcr = str(o.get("pcr", {}).get("sentiment", "Balanced"))
        fii = str(m.get("fii", {}).get("fii", "Neutral"))
        heavy = str(m.get("heavyweights", {}).get("heavyweights", "Balanced"))

        direction = self._direction(trend, pcr, strike_pressure, fii, heavy)
        barrier_type, barrier_level = self._nearest_barrier(price, support, resistance, direction)
        touch_count = self._update_touch_state(
            state=state,
            price=price,
            atr=atr,
            barrier_type=barrier_type,
            barrier_level=barrier_level,
        )

        breakout, reversal, strength, reasons, warnings = self._probabilities(
            direction=direction,
            stage=stage,
            energy=energy,
            volume=volume,
            strike_pressure=strike_pressure,
            barrier_type=barrier_type,
            touch_count=touch_count,
            fii=fii,
            heavy=heavy,
        )

        low_remaining, high_remaining = self._remaining_move(
            atr=atr,
            stage=stage,
            energy=energy,
            breakout_probability=breakout,
            reversal_probability=reversal,
            price=price,
            direction=direction,
            barrier_level=barrier_level,
        )

        if direction == "UP":
            zone_low = price + low_remaining
            zone_high = price + high_remaining
        elif direction == "DOWN":
            zone_low = price - high_remaining
            zone_high = price - low_remaining
        else:
            zone_low = price - high_remaining / 2.0
            zone_high = price + high_remaining / 2.0

        time_phase = self._time_phase(hour)
        if time_phase in {"Opening Shock Zone", "Late Move Zone"}:
            warnings.append(f"{time_phase}: confirmation can change quickly.")

        status = "JOURNEY_READY" if price > 0 else "INSUFFICIENT_DATA"
        return MarketJourneyReport(
            status=status,
            direction=direction,
            move_stage=stage,
            market_energy=energy,
            expected_zone_low=round(zone_low, 2),
            expected_zone_high=round(zone_high, 2),
            remaining_points_low=round(low_remaining, 1),
            remaining_points_high=round(high_remaining, 1),
            breakout_probability=round(breakout, 1),
            reversal_probability=round(reversal, 1),
            barrier_type=barrier_type,
            barrier_level=round(barrier_level, 2) if barrier_level is not None else None,
            barrier_touch_count=touch_count,
            barrier_strength=strength,
            time_phase=time_phase,
            reasons=reasons[:6],
            warnings=warnings[:5],
        )

    def _probabilities(self, **k: Any):
        breakout = 50.0
        reversal = 50.0
        reasons: list[str] = []
        warnings: list[str] = []

        direction = k["direction"]
        stage = k["stage"]
        energy = k["energy"]
        volume = k["volume"]
        pressure = k["strike_pressure"]
        barrier_type = k["barrier_type"]
        touches = int(k["touch_count"])
        fii = k["fii"]
        heavy = k["heavy"]

        if energy == "High":
            breakout += 12
            reversal -= 8
            reasons.append("Market energy high")
        elif energy == "Low":
            breakout -= 12
            reversal += 15
            reasons.append("Market energy low")

        if volume in {"High", "Spike", "High Volume", "Spike Volume"}:
            breakout += 10
            reasons.append("Participation strong")
        elif volume in {"Weak", "Weak Volume"}:
            breakout -= 12
            reversal += 8
            reasons.append("Participation weak")

        if stage in {"Late Move", "Exhaustion Move"}:
            breakout -= 12
            reversal += 18
            reasons.append("Move is late/exhausted")
        elif stage == "Early Move":
            breakout += 8
            reversal -= 5
            reasons.append("Move still early")

        # Repeated touches weaken a barrier only when pressure is not defending it.
        defended = (
            (barrier_type == "RESISTANCE" and pressure == "CE Resistance")
            or (barrier_type == "SUPPORT" and pressure == "PE Support")
        )
        if touches >= 3:
            if defended:
                reversal += min(18, touches * 3)
                breakout -= min(12, touches * 2)
                reasons.append(f"Barrier defended across {touches} touches")
            else:
                breakout += min(18, touches * 3)
                reversal -= min(10, touches * 2)
                reasons.append(f"Barrier weakening after {touches} touches")

        aligned_money = (
            direction == "UP" and fii == "Buying" and heavy == "Supporting Market"
        ) or (
            direction == "DOWN" and fii == "Selling" and heavy == "Pressuring Market"
        )
        if aligned_money:
            breakout += 8
            reasons.append("Smart money aligned")

        breakout = max(5.0, min(95.0, breakout))
        reversal = max(5.0, min(95.0, reversal))
        total = breakout + reversal
        breakout = breakout / total * 100.0
        reversal = reversal / total * 100.0

        if defended and reversal >= 58:
            strength = "STRONG DEFENCE"
        elif not defended and breakout >= 58:
            strength = "WEAKENING / BREAK RISK"
        else:
            strength = "BALANCED"

        if direction == "RANGE":
            warnings.append("Direction is mixed; zone estimate is range-based.")
        return breakout, reversal, strength, reasons, warnings

    def _remaining_move(self, **k: Any):
        atr = k["atr"]
        stage = k["stage"]
        energy = k["energy"]
        breakout = k["breakout_probability"]
        reversal = k["reversal_probability"]
        price = k["price"]
        direction = k["direction"]
        barrier_level = k["barrier_level"]

        stage_factor = {
            "Early Move": 0.65,
            "Mid Move": 0.42,
            "Late Move": 0.22,
            "Exhaustion Move": 0.10,
        }.get(stage, 0.30)
        energy_factor = {"High": 1.20, "Medium": 0.90, "Low": 0.60}.get(energy, 0.80)
        probability_factor = max(0.45, min(1.25, breakout / 60.0))

        high = atr * stage_factor * energy_factor * probability_factor
        low = high * 0.45

        # A nearby barrier caps the first expected journey zone unless breakout odds dominate.
        if barrier_level is not None and direction in {"UP", "DOWN"} and breakout < 62:
            distance = abs(barrier_level - price)
            if distance > 0:
                high = min(high, max(distance, atr * 0.08))
                low = min(low, high * 0.60)

        if reversal > 65:
            high *= 0.65
            low *= 0.55
        return max(1.0, low), max(2.0, high)

    def _update_touch_state(self, *, state, price, atr, barrier_type, barrier_level):
        store = state.get(self.STATE_KEY, {})
        if not isinstance(store, dict):
            store = {}
        key = f"{barrier_type}:{round(barrier_level or 0, 1)}"
        threshold = max(10.0, min(30.0, atr * 0.18))
        inside = barrier_level is not None and abs(price - barrier_level) <= threshold
        previous = store.get(key, {}) if isinstance(store.get(key), dict) else {}
        was_inside = bool(previous.get("inside", False))
        count = int(previous.get("touches", 0) or 0)
        if inside and not was_inside:
            count += 1
        store = {key: {"inside": inside, "touches": min(count, 20)}}
        state[self.STATE_KEY] = store
        return count

    def _direction(self, trend, pcr, pressure, fii, heavy):
        up = down = 0
        if "Bullish" in trend: up += 3
        if "Bearish" in trend: down += 3
        if pcr == "Bullish": up += 1
        if pcr == "Bearish": down += 1
        if pressure == "PE Support": up += 1
        if pressure == "CE Resistance": down += 1
        if fii == "Buying": up += 1
        if fii == "Selling": down += 1
        if heavy == "Supporting Market": up += 1
        if heavy == "Pressuring Market": down += 1
        if up >= down + 2: return "UP"
        if down >= up + 2: return "DOWN"
        return "RANGE"

    def _nearest_barrier(self, price, support, resistance, direction):
        candidates = []
        if support is not None: candidates.append((abs(price-support), "SUPPORT", support))
        if resistance is not None: candidates.append((abs(resistance-price), "RESISTANCE", resistance))
        if not candidates: return "NONE", None
        if direction == "UP" and resistance is not None: return "RESISTANCE", resistance
        if direction == "DOWN" and support is not None: return "SUPPORT", support
        _, typ, level = min(candidates, key=lambda x: x[0])
        return typ, level

    def _time_phase(self, hour):
        if 9 <= hour < 10: return "Opening Shock Zone"
        if 11 <= hour < 12: return "Midday Decision Zone"
        if 12 <= hour < 14: return "Range / Lunch Zone"
        if 14 <= hour < 15: return "Late Move Zone"
        return "Normal Session"

    def _details(self, report):
        if isinstance(report, Mapping):
            value = report.get("details", report)
        else:
            value = getattr(report, "details", {})
        return dict(value) if isinstance(value, Mapping) else {}

    def _number_or_none(self, value):
        try:
            number = float(value)
            return number if number != 0 else None
        except (TypeError, ValueError):
            return None
