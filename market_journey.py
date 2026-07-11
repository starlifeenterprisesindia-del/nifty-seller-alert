"""
market_journey.py
Version: V38.3
Department: Market Journey / Barrier Intelligence 2.0
Status: V38.1 bounded barrier registry + V38.2 outcome statistics + V38.3 probability/strength profile

Safety contract:
- Improves the existing V35 Market Journey module; no duplicate move engine.
- Evidence and bounded estimation only; never emits BUY/SELL or execution permission.
- Uses one verified snapshot and existing department reports only.
- Report must pass through DSP review -> CO case file -> AI_MASTER.
- Barrier history is bounded session evidence, not an execution rule.
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
    barrier_statistics: Dict[str, Any]
    tracked_barriers: list[Dict[str, Any]]
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
        bounce = float(self.barrier_statistics.get("bounce_probability", 50.0) or 50.0)
        break_prob = float(self.barrier_statistics.get("break_probability", 50.0) or 50.0)
        summary = (
            f"Move Remaining {signed} pts | up room {self.upside_remaining_points:.0f} | "
            f"down room {self.downside_remaining_points:.0f} | barrier bounce {bounce:.0f}% / "
            f"break {break_prob:.0f}% | reversal {self.reversal_risk}"
        )
        return {
            "summary": summary,
            "confidence": self.estimate_confidence,
            "details": self.to_compact_dict(),
        }


class MarketJourneyEngine:
    """One-snapshot market journey investigator.

    V38 does not create a second brain. It extends the existing V35 journey
    investigator with an independent upside/downside room estimate and then
    applies barrier and reversal-risk adjustments. The output is descriptive
    evidence for CO; AI_MASTER retains all decision authority.
    """

    VERSION = "V38.3_BARRIER_INTELLIGENCE_2"
    STATE_KEY = "v38_barrier_registry"

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
        observed_at: Optional[str] = None,
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
        time_phase = self._time_phase(hour)
        oi_signal = str(o.get("oi", {}).get("signal", "Neutral"))
        barrier_context = self._update_barrier_registry(
            state=state,
            price=price,
            atr=atr,
            support=support,
            resistance=resistance,
            active_type=barrier_type,
            active_level=barrier_level,
            volume_status=volume,
            oi_signal=oi_signal,
            strike_pressure=strike_pressure,
            time_phase=time_phase,
            observed_at=observed_at or "SESSION",
        )
        barrier_statistics = dict(barrier_context.get("active", {}))
        tracked_barriers = list(barrier_context.get("tracked", []))
        touch_count = int(barrier_statistics.get("touches", 0) or 0)

        breakout, reversal, strength, reasons, warnings = self._probabilities(
            direction=direction,
            stage=stage,
            energy=energy,
            volume=volume,
            strike_pressure=strike_pressure,
            barrier_type=barrier_type,
            touch_count=touch_count,
            barrier_profile=barrier_statistics,
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
            barrier_statistics=barrier_statistics,
            tracked_barriers=tracked_barriers,
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
        profile = k.get("barrier_profile", {}) if isinstance(k.get("barrier_profile", {}), Mapping) else {}

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

        resolved_tests = int(profile.get("resolved_tests", 0) or 0)
        history_confidence = float(profile.get("sample_confidence", 0) or 0)
        bounce_probability = float(profile.get("bounce_probability", 50) or 50)
        break_probability = float(profile.get("break_probability", 50) or 50)
        history_weight = self._clamp(history_confidence / 100.0, 0.0, 0.90)
        if resolved_tests >= 2 and history_weight > 0:
            if bounce_probability >= 56:
                delta = min(18.0, (bounce_probability - 50.0) * 0.45 * history_weight)
                reversal += delta
                breakout -= delta * 0.80
                reasons.append(
                    f"Barrier history: {bounce_probability:.0f}% bounce over {resolved_tests} resolved tests"
                )
            elif break_probability >= 56:
                delta = min(18.0, (break_probability - 50.0) * 0.45 * history_weight)
                breakout += delta
                reversal -= delta * 0.70
                reasons.append(
                    f"Barrier history: {break_probability:.0f}% break over {resolved_tests} resolved tests"
                )

        breakout, reversal = self._normalise_pair(breakout, reversal)
        history_strength = str(profile.get("strength", ""))
        if history_strength and history_strength != "COLLECTING EVIDENCE":
            strength = history_strength
        elif defended and reversal >= 58:
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
        if barrier_strength in {"STRONG DEFENCE", "DEFENCE LEAN"}:
            extension *= 0.35 if barrier_strength == "STRONG DEFENCE" else 0.60
        elif barrier_strength in {"HIGH BREAK RISK", "WEAKENING / BREAK RISK"}:
            extension *= 1.25
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

    def _update_barrier_registry(
        self,
        *,
        state: MutableMapping[str, Any],
        price: float,
        atr: float,
        support: Optional[float],
        resistance: Optional[float],
        active_type: str,
        active_level: Optional[float],
        volume_status: str,
        oi_signal: str,
        strike_pressure: str,
        time_phase: str,
        observed_at: str,
    ) -> Dict[str, Any]:
        store = state.get(self.STATE_KEY, {})
        if not isinstance(store, dict):
            store = {}
        records = [dict(item) for item in store.get("records", []) if isinstance(item, Mapping)]
        sequence = int(store.get("sequence", 0) or 0) + 1
        next_id = int(store.get("next_id", 1) or 1)
        merge_distance = max(6.0, min(25.0, atr * 0.12))

        current_ids: list[str] = []
        for barrier_type, level in (("SUPPORT", support), ("RESISTANCE", resistance)):
            if level is None:
                continue
            record, next_id = self._find_or_create_barrier(
                records=records,
                next_id=next_id,
                barrier_type=barrier_type,
                level=float(level),
                merge_distance=merge_distance,
                observed_at=observed_at,
                time_phase=time_phase,
                sequence=sequence,
            )
            self._observe_barrier(
                record=record,
                price=price,
                atr=atr,
                volume_status=volume_status,
                oi_signal=oi_signal,
                strike_pressure=strike_pressure,
                observed_at=observed_at,
                time_phase=time_phase,
                sequence=sequence,
            )
            current_ids.append(str(record.get("id", "")))

        # Keep the registry deliberately bounded. Current barriers are retained,
        # then the most recently seen records fill the remaining slots.
        records.sort(
            key=lambda item: (
                str(item.get("id", "")) in current_ids,
                int(item.get("last_sequence", 0) or 0),
                int(item.get("resolved_tests", 0) or 0),
            ),
            reverse=True,
        )
        records = records[:12]

        active_record = None
        if active_level is not None and active_type in {"SUPPORT", "RESISTANCE"}:
            candidates = [item for item in records if item.get("type") == active_type]
            if candidates:
                active_record = min(candidates, key=lambda item: abs(float(item.get("level", 0) or 0) - active_level))

        active_profile = self._barrier_profile(active_record, price)
        tracked = [self._barrier_profile(item, price) for item in records]
        tracked.sort(
            key=lambda item: (
                float(item.get("distance_points", 999999) or 999999),
                -float(item.get("sample_confidence", 0) or 0),
            )
        )
        store = {"sequence": sequence, "next_id": next_id, "records": records}
        state[self.STATE_KEY] = store
        active_profile["registry_size"] = len(records)
        return {"active": active_profile, "tracked": tracked[:6], "registry_size": len(records)}

    def _find_or_create_barrier(
        self,
        *,
        records: list[Dict[str, Any]],
        next_id: int,
        barrier_type: str,
        level: float,
        merge_distance: float,
        observed_at: str,
        time_phase: str,
        sequence: int,
    ) -> tuple[Dict[str, Any], int]:
        same_type = [item for item in records if item.get("type") == barrier_type]
        record = None
        if same_type:
            nearest = min(same_type, key=lambda item: abs(float(item.get("level", 0) or 0) - level))
            if abs(float(nearest.get("level", 0) or 0) - level) <= merge_distance:
                record = nearest
        if record is None:
            record = {
                "id": f"B{next_id}",
                "type": barrier_type,
                "level": round(level, 2),
                "first_seen": observed_at,
                "last_seen": observed_at,
                "last_time_phase": time_phase,
                "observations": 0,
                "touches": 0,
                "resolved_tests": 0,
                "bounces": 0,
                "breaks": 0,
                "volume_confirmed_bounces": 0,
                "volume_confirmed_breaks": 0,
                "oi_confirmed_bounces": 0,
                "oi_confirmed_breaks": 0,
                "last_relation": "UNSEEN",
                "last_outcome": "UNTESTED",
                "last_outcome_at": "",
                "pending": None,
                "last_sequence": sequence,
            }
            records.append(record)
            next_id += 1
        else:
            old_level = float(record.get("level", level) or level)
            record["level"] = round(old_level * 0.85 + level * 0.15, 2)
        record["last_seen"] = observed_at
        record["last_time_phase"] = time_phase
        record["last_sequence"] = sequence
        record["observations"] = min(500, int(record.get("observations", 0) or 0) + 1)
        return record, next_id

    def _observe_barrier(
        self,
        *,
        record: Dict[str, Any],
        price: float,
        atr: float,
        volume_status: str,
        oi_signal: str,
        strike_pressure: str,
        observed_at: str,
        time_phase: str,
        sequence: int,
    ) -> None:
        barrier_type = str(record.get("type", ""))
        level = float(record.get("level", 0) or 0)
        touch_zone = max(6.0, min(22.0, atr * 0.14))
        break_zone = max(touch_zone + 2.0, min(35.0, atr * 0.20))
        if barrier_type == "RESISTANCE":
            if price > level + break_zone:
                relation = "BROKEN_SIDE"
            elif price >= level - touch_zone:
                relation = "TOUCH"
            else:
                relation = "SAFE_SIDE"
        else:
            if price < level - break_zone:
                relation = "BROKEN_SIDE"
            elif price <= level + touch_zone:
                relation = "TOUCH"
            else:
                relation = "SAFE_SIDE"

        previous_relation = str(record.get("last_relation", "UNSEEN"))
        pending = record.get("pending") if isinstance(record.get("pending"), Mapping) else None
        just_started = False
        if relation == "TOUCH" and previous_relation != "TOUCH" and pending is None:
            record["touches"] = min(50, int(record.get("touches", 0) or 0) + 1)
            pending = {
                "age": 0,
                "started_at": observed_at,
                "time_phase": time_phase,
                "volume_status": volume_status,
                "oi_signal": oi_signal,
                "strike_pressure": strike_pressure,
            }
            record["pending"] = pending
            record["last_outcome"] = "TEST_IN_PROGRESS"
            just_started = True

        if pending is not None and not just_started:
            pending = dict(pending)
            pending["age"] = int(pending.get("age", 0) or 0) + 1
            record["pending"] = pending
            outcome = None
            if relation == "SAFE_SIDE":
                outcome = "BOUNCE"
            elif relation == "BROKEN_SIDE":
                outcome = "BREAK"
            if outcome:
                self._resolve_barrier_test(
                    record=record,
                    outcome=outcome,
                    pending=pending,
                    current_volume=volume_status,
                    current_oi_signal=oi_signal,
                    current_pressure=strike_pressure,
                    observed_at=observed_at,
                )
            elif int(pending.get("age", 0) or 0) > 12:
                record["pending"] = None
                record["last_outcome"] = "UNRESOLVED_TEST"
                record["last_outcome_at"] = observed_at

        record["last_relation"] = relation
        record["last_sequence"] = sequence

    def _resolve_barrier_test(
        self,
        *,
        record: Dict[str, Any],
        outcome: str,
        pending: Mapping[str, Any],
        current_volume: str,
        current_oi_signal: str,
        current_pressure: str,
        observed_at: str,
    ) -> None:
        record["resolved_tests"] = min(50, int(record.get("resolved_tests", 0) or 0) + 1)
        field = "bounces" if outcome == "BOUNCE" else "breaks"
        record[field] = min(50, int(record.get(field, 0) or 0) + 1)
        high_volume = any(
            status in {"High", "Spike", "High Volume", "Spike Volume"}
            for status in (str(pending.get("volume_status", "")), str(current_volume))
        )
        volume_field = "volume_confirmed_bounces" if outcome == "BOUNCE" else "volume_confirmed_breaks"
        if high_volume:
            record[volume_field] = min(50, int(record.get(volume_field, 0) or 0) + 1)

        barrier_type = str(record.get("type", ""))
        touch_pressure = str(pending.get("strike_pressure", ""))
        touch_oi = str(pending.get("oi_signal", ""))
        if outcome == "BOUNCE":
            oi_confirmed = (
                (barrier_type == "RESISTANCE" and (touch_pressure == "CE Resistance" or current_pressure == "CE Resistance"))
                or (barrier_type == "SUPPORT" and (touch_pressure == "PE Support" or current_pressure == "PE Support"))
            )
        elif barrier_type == "RESISTANCE":
            oi_confirmed = touch_oi in {"Long Build-up", "Short Covering"} or current_oi_signal in {"Long Build-up", "Short Covering"}
        else:
            oi_confirmed = touch_oi in {"Short Build-up", "Long Unwinding"} or current_oi_signal in {"Short Build-up", "Long Unwinding"}
        oi_field = "oi_confirmed_bounces" if outcome == "BOUNCE" else "oi_confirmed_breaks"
        if oi_confirmed:
            record[oi_field] = min(50, int(record.get(oi_field, 0) or 0) + 1)

        record["last_outcome"] = outcome
        record["last_outcome_at"] = observed_at
        record["pending"] = None

    def _barrier_profile(self, record: Optional[Mapping[str, Any]], price: float) -> Dict[str, Any]:
        if not isinstance(record, Mapping):
            return {
                "id": "NONE", "type": "NONE", "level": None, "touches": 0,
                "resolved_tests": 0, "bounces": 0, "breaks": 0,
                "bounce_probability": 50.0, "break_probability": 50.0,
                "sample_confidence": 0.0, "strength": "COLLECTING EVIDENCE",
                "last_outcome": "UNTESTED", "last_seen_at": "",
                "last_time_phase": "", "volume_context": "NO_RESOLVED_TEST",
                "oi_context": "NO_RESOLVED_TEST", "pending_status": "NONE",
                "distance_points": None,
            }
        resolved = int(record.get("resolved_tests", 0) or 0)
        bounces = int(record.get("bounces", 0) or 0)
        breaks = int(record.get("breaks", 0) or 0)
        touches = int(record.get("touches", 0) or 0)
        bounce_probability = (bounces + 1.25) / (resolved + 2.5) * 100.0
        break_probability = 100.0 - bounce_probability
        sample_confidence = min(92.0, 20.0 + resolved * 14.0 + min(touches, 8) * 3.0) if touches else 0.0
        if resolved < 2:
            strength = "COLLECTING EVIDENCE"
        elif bounce_probability >= 68 and sample_confidence >= 50:
            strength = "STRONG DEFENCE"
        elif bounce_probability >= 58:
            strength = "DEFENCE LEAN"
        elif break_probability >= 68 and sample_confidence >= 50:
            strength = "HIGH BREAK RISK"
        elif break_probability >= 58:
            strength = "WEAKENING / BREAK RISK"
        else:
            strength = "BALANCED"
        volume_confirmed = int(record.get("volume_confirmed_bounces", 0) or 0) + int(record.get("volume_confirmed_breaks", 0) or 0)
        oi_confirmed = int(record.get("oi_confirmed_bounces", 0) or 0) + int(record.get("oi_confirmed_breaks", 0) or 0)
        level = float(record.get("level", 0) or 0)
        return {
            "id": str(record.get("id", "")),
            "type": str(record.get("type", "NONE")),
            "level": round(level, 2),
            "touches": touches,
            "resolved_tests": resolved,
            "bounces": bounces,
            "breaks": breaks,
            "bounce_probability": round(bounce_probability, 1),
            "break_probability": round(break_probability, 1),
            "sample_confidence": round(sample_confidence, 1),
            "strength": strength,
            "last_outcome": str(record.get("last_outcome", "UNTESTED")),
            "last_outcome_at": str(record.get("last_outcome_at", "")),
            "last_seen_at": str(record.get("last_seen", "")),
            "last_time_phase": str(record.get("last_time_phase", "")),
            "volume_context": f"{volume_confirmed}/{resolved} outcomes volume-confirmed" if resolved else "NO_RESOLVED_TEST",
            "oi_context": f"{oi_confirmed}/{resolved} outcomes OI-confirmed" if resolved else "NO_RESOLVED_TEST",
            "pending_status": "TEST_IN_PROGRESS" if isinstance(record.get("pending"), Mapping) else "NONE",
            "distance_points": round(abs(price - level), 1),
        }

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
