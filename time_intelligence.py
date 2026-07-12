"""
time_intelligence.py
Version: V39.3
Department: Time Intelligence
Status: V39.1 session clock + V39.2 phase behaviour + V39.3 time-conditioned evidence

Safety contract:
- One verified snapshot in, one evidence report out.
- No API calls, loops, timers, or background workers.
- Never emits BUY/SELL, candidate, or execution permission.
- Uses bounded intraday phase memory only; no automatic trading-rule changes.
- Report must pass through DSP Time Intelligence -> CO -> AI_MASTER.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Mapping, MutableMapping, Optional


@dataclass(frozen=True)
class TimeIntelligenceReport:
    version: str
    status: str
    session_date: str
    observed_time: str
    phase_code: str
    phase_label: str
    key_clock: str
    phase_progress_pct: float
    market_character: str
    expected_volatility: str
    false_break_risk: str
    continuation_reliability: str
    reversal_sensitivity: str
    snapshots_in_phase: int
    phase_change_points: float
    phase_range_points: float
    direction_stability: float
    observed_behaviour: str
    continuation_factor: float
    reversal_adjustment: float
    confidence_cap: float
    authority: str
    execution_instruction: str
    reasons: list[str]
    warnings: list[str]

    def to_compact_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_department_report(self) -> Dict[str, Any]:
        summary = (
            f"{self.phase_label} | behaviour {self.observed_behaviour} | "
            f"continuation reliability {self.continuation_reliability} | "
            f"false-break risk {self.false_break_risk} | confidence cap {self.confidence_cap:.0f}%"
        )
        confidence = min(self.confidence_cap, 35.0 + self.snapshots_in_phase * 7.0)
        if self.status != "TIME_INTELLIGENCE_READY":
            confidence = min(confidence, 35.0)
        return {
            "summary": summary,
            "confidence": round(max(0.0, min(100.0, confidence)), 1),
            "details": self.to_compact_dict(),
        }


class TimeIntelligenceDirector:
    """Classifies NIFTY intraday time behaviour without creating a decision brain."""

    VERSION = "V39.3_TIME_INTELLIGENCE"
    STATE_KEY = "v39_time_phase_registry"

    # start_minute, end_minute are minutes after midnight; end is exclusive.
    PHASES = (
        (555, 570, "OPENING_SHOCK", "9:15 Opening Shock", "9:15", "PRICE_DISCOVERY", "HIGH", "HIGH", "LOW", "HIGH", 0.78, 14.0, 56.0),
        (570, 600, "OPENING_DISCOVERY", "9:30 Opening Discovery", "9:30", "EARLY_DIRECTION_TEST", "HIGH", "HIGH", "LOW-MEDIUM", "HIGH", 0.86, 10.0, 62.0),
        (600, 645, "FIRST_CONFIRMATION", "10:00 First Confirmation", "10:00", "DIRECTION_CONFIRMATION", "MEDIUM-HIGH", "MEDIUM", "MEDIUM-HIGH", "MEDIUM", 1.04, -2.0, 74.0),
        (645, 690, "MID_MORNING", "10:45 Mid-Morning Follow-through", "10:45", "FOLLOW_THROUGH_OR_FADE", "MEDIUM", "MEDIUM", "MEDIUM", "MEDIUM", 0.98, 1.0, 71.0),
        (690, 735, "MIDDAY_DECISION", "11:30 Midday Decision", "11:30", "SECOND_DIRECTION_TEST", "MEDIUM", "MEDIUM-HIGH", "MEDIUM", "MEDIUM", 0.92, 4.0, 68.0),
        (735, 810, "LUNCH_RANGE", "12:15 Lunch / Range Zone", "13:00", "THETA_AND_RANGE", "LOW", "HIGH", "LOW", "MEDIUM-HIGH", 0.72, 10.0, 58.0),
        (810, 870, "AFTERNOON_REASSESSMENT", "13:30 Afternoon Reassessment", "13:30", "POSITION_REBUILD", "MEDIUM", "MEDIUM", "MEDIUM", "MEDIUM", 0.94, 3.0, 68.0),
        (870, 905, "LATE_MOVE", "14:30 Late Move Zone", "14:30", "LATE_EXPANSION_OR_TRAP", "HIGH", "MEDIUM-HIGH", "MEDIUM", "HIGH", 0.88, 8.0, 65.0),
        (905, 931, "CLOSING_PRESSURE", "15:05 Closing Pressure", "15:15", "CLOSING_REBALANCE", "HIGH", "HIGH", "LOW", "HIGH", 0.70, 15.0, 54.0),
    )

    def evaluate(
        self,
        *,
        state: MutableMapping[str, Any],
        observed_at: str,
        price: float,
        day_high: float,
        day_low: float,
        atr: float,
        change_pct: float,
        price_report: Any,
        behaviour_report: Any,
        option_report: Any,
        psychology_report: Any = None,
    ) -> TimeIntelligenceReport:
        dt = self._parse_datetime(observed_at)
        minute = dt.hour * 60 + dt.minute
        phase = self._phase(minute)
        session_date = dt.date().isoformat()
        price = float(price or 0.0)
        day_high = float(day_high or price)
        day_low = float(day_low or price)
        atr = max(float(atr or 0.0), 1.0)

        registry = state.get(self.STATE_KEY)
        if not isinstance(registry, dict) or registry.get("session_date") != session_date:
            registry = {"session_date": session_date, "phases": {}, "last_price": None}
            state[self.STATE_KEY] = registry

        phase_code = phase[2]
        phase_book = registry.setdefault("phases", {})
        record = phase_book.get(phase_code)
        if not isinstance(record, dict):
            record = {
                "samples": 0,
                "first_price": price,
                "last_price": price,
                "high": price,
                "low": price,
                "direction_changes": 0,
                "last_direction": "FLAT",
            }
            phase_book[phase_code] = record

        previous_price = self._number_or_none(registry.get("last_price"))
        direction = "FLAT"
        if previous_price is not None:
            threshold = max(0.5, atr * 0.025)
            if price > previous_price + threshold:
                direction = "UP"
            elif price < previous_price - threshold:
                direction = "DOWN"
        last_direction = str(record.get("last_direction", "FLAT"))
        if direction in {"UP", "DOWN"} and last_direction in {"UP", "DOWN"} and direction != last_direction:
            record["direction_changes"] = int(record.get("direction_changes", 0) or 0) + 1
        if direction in {"UP", "DOWN"}:
            record["last_direction"] = direction

        record["samples"] = int(record.get("samples", 0) or 0) + 1
        record["last_price"] = price
        record["high"] = max(float(record.get("high", price) or price), price)
        record["low"] = min(float(record.get("low", price) or price), price)
        registry["last_price"] = price

        samples = int(record.get("samples", 0) or 0)
        first_price = float(record.get("first_price", price) or price)
        phase_change = price - first_price
        phase_range = max(0.0, float(record.get("high", price)) - float(record.get("low", price)))
        reversals = int(record.get("direction_changes", 0) or 0)
        direction_stability = self._clamp(100.0 - reversals * 24.0 - max(0, samples - 2) * 1.5, 5.0, 100.0)
        if samples < 3:
            direction_stability = min(direction_stability, 55.0)

        observed_behaviour, observed_factor, observed_reversal, reasons, warnings = self._observed_behaviour(
            samples=samples,
            phase_change=phase_change,
            phase_range=phase_range,
            atr=atr,
            stability=direction_stability,
            price=price,
            day_high=day_high,
            day_low=day_low,
            change_pct=float(change_pct or 0.0),
            price_report=price_report,
            behaviour_report=behaviour_report,
            option_report=option_report,
            psychology_report=psychology_report,
        )

        base_factor = float(phase[10])
        base_reversal = float(phase[11])
        base_cap = float(phase[12])
        continuation_factor = self._clamp(base_factor * observed_factor, 0.62, 1.18)
        reversal_adjustment = self._clamp(base_reversal + observed_reversal, -8.0, 22.0)
        confidence_cap = self._clamp(base_cap + min(8.0, max(0, samples - 2) * 1.5), 45.0, 82.0)
        if observed_behaviour in {"TWO_WAY_WHIPSAW", "POSSIBLE_TIME_TRAP"}:
            confidence_cap = min(confidence_cap, 58.0)

        phase_progress = self._phase_progress(minute, int(phase[0]), int(phase[1]))
        reasons.insert(0, f"Clock profile: {phase[5]}")
        if samples < 3:
            warnings.append("Time phase evidence is still collecting; next snapshots are required.")

        status = "TIME_INTELLIGENCE_READY" if phase_code != "OFF_MARKET" and price > 0 else "OFF_MARKET_OR_INSUFFICIENT"
        return TimeIntelligenceReport(
            version=self.VERSION,
            status=status,
            session_date=session_date,
            observed_time=dt.strftime("%H:%M:%S"),
            phase_code=phase_code,
            phase_label=str(phase[3]),
            key_clock=str(phase[4]),
            phase_progress_pct=round(phase_progress, 1),
            market_character=str(phase[5]),
            expected_volatility=str(phase[6]),
            false_break_risk=str(phase[7]),
            continuation_reliability=str(phase[8]),
            reversal_sensitivity=str(phase[9]),
            snapshots_in_phase=samples,
            phase_change_points=round(phase_change, 1),
            phase_range_points=round(phase_range, 1),
            direction_stability=round(direction_stability, 1),
            observed_behaviour=observed_behaviour,
            continuation_factor=round(continuation_factor, 3),
            reversal_adjustment=round(reversal_adjustment, 1),
            confidence_cap=round(confidence_cap, 1),
            authority="EVIDENCE_ONLY_TO_CO",
            execution_instruction="NONE",
            reasons=list(dict.fromkeys(reasons))[:7],
            warnings=list(dict.fromkeys(warnings))[:5],
        )

    def _phase(self, minute: int):
        for phase in self.PHASES:
            if int(phase[0]) <= minute < int(phase[1]):
                return phase
        return (0, 1440, "OFF_MARKET", "Outside Regular NIFTY Session", "OFF", "NO_LIVE_SESSION", "NA", "NA", "NA", "NA", 0.65, 18.0, 45.0)

    def _observed_behaviour(self, **k: Any) -> tuple[str, float, float, list[str], list[str]]:
        samples = int(k["samples"])
        change = float(k["phase_change"])
        phase_range = float(k["phase_range"])
        atr = max(float(k["atr"]), 1.0)
        stability = float(k["stability"])
        price = float(k["price"])
        day_high = float(k["day_high"])
        day_low = float(k["day_low"])
        day_change_pct = float(k["change_pct"])
        p = self._details(k["price_report"])
        b = self._details(k["behaviour_report"])
        o = self._details(k["option_report"])
        psych = self._details(k.get("psychology_report"))

        trend = str(p.get("trend", {}).get("trend", "Unknown"))
        energy = str(b.get("energy", {}).get("market_energy", "Unknown"))
        volume = str(o.get("volume", {}).get("status", "Unknown"))
        psychology_state = str((psych.get("psychology_case_report", {}) or {}).get("case_state", "BALANCED_OBSERVATION"))

        net_ratio = abs(change) / atr
        range_ratio = phase_range / atr
        day_span = max(1.0, day_high - day_low)
        position = self._clamp((price - day_low) / day_span, 0.0, 1.0)
        reasons: list[str] = []
        warnings: list[str] = []

        if samples < 3:
            return "COLLECTING_PHASE_EVIDENCE", 0.94, 2.0, ["Less than three snapshots in current phase"], warnings

        if stability <= 45 and range_ratio >= 0.35:
            reasons.append(f"Direction changed repeatedly; stability {stability:.0f}%")
            return "TWO_WAY_WHIPSAW", 0.76, 10.0, reasons, ["Time-phase whipsaw can invalidate a one-snapshot continuation estimate."]

        trap_states = {
            "DOWNSIDE_STOP_SWEEP_REVERSAL_WATCH",
            "UPMOVE_EXHAUSTION_TRAP_WATCH",
            "MIXED_PSYCHOLOGY_CONFLICT",
        }
        if psychology_state in trap_states and range_ratio >= 0.25:
            reasons.append(f"Psychology case is {psychology_state}")
            return "POSSIBLE_TIME_TRAP", 0.78, 11.0, reasons, ["Wait for next-snapshot acceptance beyond the swept level."]

        aligned_up = change > 0 and ("Bull" in trend or position >= 0.68)
        aligned_down = change < 0 and ("Bear" in trend or position <= 0.32)
        participation = volume in {"High", "Spike", "High Volume", "Spike Volume"} or energy == "High"
        if (aligned_up or aligned_down) and stability >= 68 and net_ratio >= 0.18:
            factor = 1.08 if participation else 1.02
            reasons.append(f"Stable phase direction with {net_ratio:.2f} ATR net progress")
            if participation:
                reasons.append("Volume/energy supports phase follow-through")
            return "DIRECTIONAL_FOLLOW_THROUGH", factor, -4.0, reasons, warnings

        if range_ratio >= 0.55 and net_ratio <= 0.16:
            reasons.append("Large phase range but little net progress")
            return "RANGE_EXPANSION_WITHOUT_PROGRESS", 0.80, 8.0, reasons, ["Range expansion without progress raises false-break risk."]

        if abs(day_change_pct) >= 0.65 and net_ratio <= 0.10:
            reasons.append("Large day move is no longer progressing in this phase")
            return "MOVE_STALLING_BY_TIME", 0.84, 7.0, reasons, warnings

        reasons.append("No strong time-conditioned follow-through or trap evidence")
        return "PHASE_BALANCED", 0.96, 1.0, reasons, warnings

    @staticmethod
    def _phase_progress(minute: int, start: int, end: int) -> float:
        if end <= start:
            return 0.0
        return max(0.0, min(100.0, (minute - start) / (end - start) * 100.0))

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return datetime.now()

    @staticmethod
    def _details(report: Any) -> Dict[str, Any]:
        if report is None:
            return {}
        if isinstance(report, Mapping):
            value = report.get("details", report)
        else:
            value = getattr(report, "details", {})
        return dict(value) if isinstance(value, Mapping) else {}

    @staticmethod
    def _number_or_none(value: Any) -> Optional[float]:
        try:
            number = float(value)
            return number
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))
