"""
market_journey.py
Version: V37.3
Department: Market Journey / Move Remaining Intelligence
Status: V37.1 foundation + V37.2 two-sided estimate + V37.3 barrier/reversal adjustment

Safety contract:
- Improves the existing V35 Market Journey module; no duplicate move engine.
- Evidence and bounded estimation only; never emits BUY/SELL or execution permission.
- Uses one verified snapshot and existing department reports only.
- Report must pass through DSP review -> CO case file -> AI_MASTER.
- No API calls, loops, threads, timers, or automatic trading-rule changes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, MutableMapping, Optional


@dataclass(frozen=True)
class MarketJourneyReport:
    version: str
    status: str
    direction: str
    move_stage: str
    market_energy: str
    expected_zone_low: float
    expected_zone_high: float
    remaining_points_low: float
    remaining_points_high: float
    upside_remaining_points: float
    downside_remaining_points: float
    primary_direction: str
    primary_signed_points: float
    before_reversal_points: float
    estimate_confidence: float
    breakout_probability: float
    reversal_probability: float
    reversal_risk: str
    barrier_type: str
    barrier_level: Optional[float]
    barrier_distance_points: Optional[float]
    barrier_adjustment_points: float
    barrier_touch_count: int
    barrier_strength: str
    time_phase: str
    psychology_case_state: str
    authority: str
    execution_instruction: str
    reasons: list[str]
    warnings: list[str]

    def to_compact_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_department_report(self) -> Dict[str, Any]:
        signed = f"{self.primary_signed_points:+.0f}" if self.primary_direction in {"UP", "DOWN"} else "range"
        summary = (
            f"Move Remaining {signed} pts | up room {self.upside_remaining_points:.0f} | "
            f"down room {self.downside_remaining_points:.0f} | reversal {self.reversal_risk}"
        )
        return {
            "summary": summary,
            "confidence": self.estimate_confidence,
            "details": self.to_compact_dict(),
        }


class MarketJourneyEngine:
    """One-snapshot market journey investigator.

    V37 does not create a second brain. It extends the existing V35 journey
    investigator with an independent upside/downside room estimate and then
    applies barrier and reversal-risk adjustments. The output is descriptive
    evidence for CO; AI_MASTER retains all decision authority.
    """

    VERSION = "V37.3_MOVE_REMAINING_BARRIER_ADJUSTMENT"
    STATE_KEY = "v35_barrier_state"  # Preserve existing bounded touch history.

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
        psychology_report: Any = None,
    ) -> MarketJourneyReport:
        price = float(price or 0.0)
        atr = max(float(atr or 0.0), 1.0)
        support = self._number_or_none(support)
        resistance = self._number_or_none(resistance)

        p = self._details(price_report)
        o = self._details(option_report)
        b = self._details(behaviour_report)
        m = self._details(smart_money_report)
        psychology = self._details(psychology_report)

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

        psychology_state, psychology_up_factor, psychology_down_factor, psychology_reversal, psych_reasons, psych_warnings = (
            self._psychology_adjustment(psychology)
        )
        reversal = self._clamp(reversal + psychology_reversal, 5.0, 95.0)
        breakout = self._clamp(breakout - max(0.0, psychology_reversal * 0.45), 5.0, 95.0)
        breakout, reversal = self._normalise_pair(breakout, reversal)
        reasons.extend(psych_reasons)
        warnings.extend(psych_warnings)

        raw_up, raw_down = self._two_sided_room(
            atr=atr,
            stage=stage,
            energy=energy,
            direction=direction,
            breakout_probability=breakout,
            reversal_probability=reversal,
            psychology_up_factor=psychology_up_factor,
            psychology_down_factor=psychology_down_factor,
        )

        adjusted_up, up_adjustment, up_barrier_distance = self._apply_barrier_cap(
            raw_room=raw_up,
            price=price,
            barrier_level=resistance,
            side="UP",
            atr=atr,
            breakout_probability=breakout,
            barrier_strength=strength if barrier_type == "RESISTANCE" else "BALANCED",
        )
        adjusted_down, down_adjustment, down_barrier_distance = self._apply_barrier_cap(
            raw_room=raw_down,
            price=price,
            barrier_level=support,
            side="DOWN",
            atr=atr,
            breakout_probability=breakout,
            barrier_strength=strength if barrier_type == "SUPPORT" else "BALANCED",
        )

        # High reversal risk compresses continuation room but leaves counter-move
        # room visible. This is an estimate adjustment, not a trade direction.
        if reversal >= 68:
            if direction == "UP":
                before = adjusted_up
                adjusted_up *= 0.72
                up_adjustment += max(0.0, before - adjusted_up)
                adjusted_down *= 1.10
                warnings.append("High reversal probability compressed upside continuation room.")
            elif direction == "DOWN":
                before = adjusted_down
                adjusted_down *= 0.72
                down_adjustment += max(0.0, before - adjusted_down)
                adjusted_up *= 1.10
                warnings.append("High reversal probability compressed downside continuation room.")
            else:
                adjusted_up *= 0.88
                adjusted_down *= 0.88

        adjusted_up = max(1.0, adjusted_up)
        adjusted_down = max(1.0, adjusted_down)

        primary_direction = self._primary_direction(direction, adjusted_up, adjusted_down)
        if primary_direction == "UP":
            primary_points = adjusted_up
            signed_points = primary_points
            primary_adjustment = up_adjustment
            active_barrier_distance = up_barrier_distance
        elif primary_direction == "DOWN":
            primary_points = adjusted_down
            signed_points = -primary_points
            primary_adjustment = down_adjustment
            active_barrier_distance = down_barrier_distance
        else:
            primary_points = max(adjusted_up, adjusted_down)
            signed_points = 0.0
            primary_adjustment = max(up_adjustment, down_adjustment)
            active_barrier_distance = min(
                [distance for distance in (up_barrier_distance, down_barrier_distance) if distance is not None],
                default=None,
            )

        zone_low = price - adjusted_down
        zone_high = price + adjusted_up
        reversal_risk = self._risk_label(reversal)
        confidence = self._estimate_confidence(
            direction=direction,
            breakout=breakout,
            reversal=reversal,
            stage=stage,
            energy=energy,
            volume=volume,
            support=support,
            resistance=resistance,
            psychology=psychology,
        )

        if active_barrier_distance is not None and primary_adjustment > 0.5:
            reasons.append(
                f"Nearby barrier reduced the primary room estimate by {primary_adjustment:.1f} points"
            )

        time_phase = self._time_phase(hour)
        if time_phase in {"Opening Shock Zone", "Late Move Zone"}:
            warnings.append(f"{time_phase}: estimate can change quickly on the next snapshot.")
        if primary_direction == "RANGE":
            warnings.append("No dominant direction; use the two-sided room, not a single target.")

        status = "MOVE_REMAINING_READY" if price > 0 else "INSUFFICIENT_DATA"
        low_remaining = max(1.0, primary_points * 0.45)
        high_remaining = max(2.0, primary_points)

        return MarketJourneyReport(
            version=self.VERSION,
            status=status,
            direction=direction,
            move_stage=stage,
            market_energy=energy,
            expected_zone_low=round(zone_low, 2),
            expected_zone_high=round(zone_high, 2),
            remaining_points_low=round(low_remaining, 1),
            remaining_points_high=round(high_remaining, 1),
            upside_remaining_points=round(adjusted_up, 1),
            downside_remaining_points=round(adjusted_down, 1),
            primary_direction=primary_direction,
            primary_signed_points=round(signed_points, 1),
            before_reversal_points=round(primary_points, 1),
            estimate_confidence=round(confidence, 1),
            breakout_probability=round(breakout, 1),
            reversal_probability=round(reversal, 1),
            reversal_risk=reversal_risk,
            barrier_type=barrier_type,
            barrier_level=round(barrier_level, 2) if barrier_level is not None else None,
            barrier_distance_points=round(active_barrier_distance, 1) if active_barrier_distance is not None else None,
            barrier_adjustment_points=round(primary_adjustment, 1),
            barrier_touch_count=touch_count,
            barrier_strength=strength,
            time_phase=time_phase,
            psychology_case_state=psychology_state,
            authority="EVIDENCE_ONLY_TO_CO",
            execution_instruction="NONE",
            reasons=list(dict.fromkeys(reasons))[:8],
            warnings=list(dict.fromkeys(warnings))[:6],
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

        breakout, reversal = self._normalise_pair(breakout, reversal)
        if defended and reversal >= 58:
            strength = "STRONG DEFENCE"
        elif not defended and breakout >= 58:
            strength = "WEAKENING / BREAK RISK"
        else:
            strength = "BALANCED"

        if direction == "RANGE":
            warnings.append("Direction is mixed; estimate remains two-sided.")
        return breakout, reversal, strength, reasons, warnings

    def _two_sided_room(
        self,
        *,
        atr: float,
        stage: str,
        energy: str,
        direction: str,
        breakout_probability: float,
        reversal_probability: float,
        psychology_up_factor: float,
        psychology_down_factor: float,
    ) -> tuple[float, float]:
        primary_stage = {
            "Early Move": 0.72,
            "Mid Move": 0.50,
            "Late Move": 0.28,
            "Exhaustion Move": 0.14,
        }.get(stage, 0.38)
        counter_stage = {
            "Early Move": 0.28,
            "Mid Move": 0.34,
            "Late Move": 0.43,
            "Exhaustion Move": 0.56,
        }.get(stage, 0.34)
        energy_factor = {"High": 1.18, "Medium": 0.92, "Low": 0.68}.get(energy, 0.82)
        continuation_factor = self._clamp(breakout_probability / 58.0, 0.60, 1.30)
        reversal_factor = self._clamp(reversal_probability / 58.0, 0.60, 1.30)

        if direction == "UP":
            up = atr * primary_stage * energy_factor * continuation_factor
            down = atr * counter_stage * max(0.72, reversal_factor)
        elif direction == "DOWN":
            down = atr * primary_stage * energy_factor * continuation_factor
            up = atr * counter_stage * max(0.72, reversal_factor)
        else:
            balanced = atr * max(0.30, (primary_stage + counter_stage) / 2.0) * energy_factor
            up = balanced
            down = balanced

        up *= psychology_up_factor
        down *= psychology_down_factor
        return max(2.0, up), max(2.0, down)

    def _apply_barrier_cap(
        self,
        *,
        raw_room: float,
        price: float,
        barrier_level: Optional[float],
        side: str,
        atr: float,
        breakout_probability: float,
        barrier_strength: str,
    ) -> tuple[float, float, Optional[float]]:
        if barrier_level is None:
            return raw_room, 0.0, None
        if side == "UP":
            distance = barrier_level - price
        else:
            distance = price - barrier_level
        if distance <= 0:
            return raw_room, 0.0, None

        extension = 0.0
        if breakout_probability >= 58:
            extension = atr * self._clamp((breakout_probability - 55.0) / 100.0, 0.02, 0.24)
        if barrier_strength == "STRONG DEFENCE":
            extension *= 0.35
        cap = max(atr * 0.08, distance + extension)
        adjusted = min(raw_room, cap)
        return max(1.0, adjusted), max(0.0, raw_room - adjusted), distance

    def _psychology_adjustment(
        self, psychology: Mapping[str, Any]
    ) -> tuple[str, float, float, float, list[str], list[str]]:
        case = psychology.get("psychology_case_report", {}) if isinstance(psychology, Mapping) else {}
        state = str(case.get("case_state", "BALANCED_OBSERVATION"))
        up_factor = 1.0
        down_factor = 1.0
        reversal_delta = 0.0
        reasons: list[str] = []
        warnings: list[str] = []

        if state == "LONG_BUILDUP_OBSERVED":
            up_factor += 0.12
            reasons.append("Psychology case shows possible long build-up participation")
        elif state == "SHORT_COVERING_OBSERVED":
            up_factor += 0.08
            reversal_delta += 3
            reasons.append("Psychology case shows possible short covering")
        elif state == "FEAR_WITH_PANIC_PARTICIPATION":
            down_factor += 0.12
            reasons.append("Panic participation increases downside room evidence")
        elif state in {"DOWNSIDE_STOP_SWEEP_REVERSAL_WATCH", "BEAR_TRAP_REVERSAL_WATCH"}:
            down_factor *= 0.72
            up_factor += 0.14
            reversal_delta += 14
            warnings.append("Downside stop-sweep/bear-trap evidence raises reversal risk")
        elif state in {"UPMOVE_EXHAUSTION_TRAP_WATCH", "BULL_TRAP_REVERSAL_WATCH"}:
            up_factor *= 0.72
            down_factor += 0.14
            reversal_delta += 14
            warnings.append("Upside trap/exhaustion evidence raises reversal risk")
        elif state == "MIXED_PSYCHOLOGY_CONFLICT":
            up_factor *= 0.88
            down_factor *= 0.88
            reversal_delta += 8
            warnings.append("Conflicting psychology evidence reduces estimate conviction")

        panic = psychology.get("panic_selling", {}) if isinstance(psychology, Mapping) else {}
        panic_state = str(panic.get("state", ""))
        if "EXHAUSTION" in panic_state or "STOP_SWEEP" in panic_state:
            down_factor *= 0.82
            up_factor += 0.08
            reversal_delta += 8
            warnings.append("Panic exhaustion evidence may shorten further downside room")

        return state, self._clamp(up_factor, 0.55, 1.30), self._clamp(down_factor, 0.55, 1.30), reversal_delta, reasons, warnings

    def _estimate_confidence(
        self,
        *,
        direction: str,
        breakout: float,
        reversal: float,
        stage: str,
        energy: str,
        volume: str,
        support: Optional[float],
        resistance: Optional[float],
        psychology: Mapping[str, Any],
    ) -> float:
        coverage = 0
        possible = 7
        if direction in {"UP", "DOWN", "RANGE"}:
            coverage += 1
        if stage and stage != "Unknown":
            coverage += 1
        if energy and energy != "Unknown":
            coverage += 1
        if volume and volume != "Unknown":
            coverage += 1
        if support is not None:
            coverage += 1
        if resistance is not None:
            coverage += 1
        if psychology:
            coverage += 1
        separation = abs(breakout - reversal)
        confidence = 38.0 + (coverage / possible * 34.0) + min(16.0, separation * 0.22)
        if direction == "RANGE":
            confidence -= 6.0
        return self._clamp(confidence, 35.0, 88.0)

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
        # Bounded single active barrier record; no unbounded history growth.
        store = {key: {"inside": inside, "touches": min(count, 20)}}
        state[self.STATE_KEY] = store
        return count

    def _direction(self, trend, pcr, pressure, fii, heavy):
        up = down = 0
        if "Bullish" in trend:
            up += 3
        if "Bearish" in trend:
            down += 3
        if pcr == "Bullish":
            up += 1
        if pcr == "Bearish":
            down += 1
        if pressure == "PE Support":
            up += 1
        if pressure == "CE Resistance":
            down += 1
        if fii == "Buying":
            up += 1
        if fii == "Selling":
            down += 1
        if heavy == "Supporting Market":
            up += 1
        if heavy == "Pressuring Market":
            down += 1
        if up >= down + 2:
            return "UP"
        if down >= up + 2:
            return "DOWN"
        return "RANGE"

    @staticmethod
    def _primary_direction(direction: str, up_room: float, down_room: float) -> str:
        if direction in {"UP", "DOWN"}:
            return direction
        difference = abs(up_room - down_room)
        threshold = max(3.0, max(up_room, down_room) * 0.18)
        if difference < threshold:
            return "RANGE"
        return "UP" if up_room > down_room else "DOWN"

    def _nearest_barrier(self, price, support, resistance, direction):
        candidates = []
        if support is not None:
            candidates.append((abs(price - support), "SUPPORT", support))
        if resistance is not None:
            candidates.append((abs(resistance - price), "RESISTANCE", resistance))
        if not candidates:
            return "NONE", None
        if direction == "UP" and resistance is not None:
            return "RESISTANCE", resistance
        if direction == "DOWN" and support is not None:
            return "SUPPORT", support
        _, typ, level = min(candidates, key=lambda x: x[0])
        return typ, level

    @staticmethod
    def _risk_label(reversal_probability: float) -> str:
        if reversal_probability >= 68:
            return "HIGH"
        if reversal_probability >= 55:
            return "ELEVATED"
        if reversal_probability >= 42:
            return "MODERATE"
        return "LOW"

    @staticmethod
    def _time_phase(hour):
        if 9 <= hour < 10:
            return "Opening Shock Zone"
        if 11 <= hour < 12:
            return "Midday Decision Zone"
        if 12 <= hour < 14:
            return "Range / Lunch Zone"
        if 14 <= hour < 15:
            return "Late Move Zone"
        return "Normal Session"

    @staticmethod
    def _details(report):
        if isinstance(report, Mapping):
            value = report.get("details", report)
        else:
            value = getattr(report, "details", {})
        return dict(value) if isinstance(value, Mapping) else {}

    @staticmethod
    def _number_or_none(value):
        try:
            number = float(value)
            return number if number != 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))

    def _normalise_pair(self, first: float, second: float) -> tuple[float, float]:
        first = self._clamp(first, 5.0, 95.0)
        second = self._clamp(second, 5.0, 95.0)
        total = max(1.0, first + second)
        return first / total * 100.0, second / total * 100.0
