"""
heavyweight_intelligence.py
Version: V40.3
Department: DSP Heavyweight Intelligence

Purpose
-------
Convert the existing heavyweight quote layer into a compact investigation report.
This module never fetches data, never starts a loop, never issues BUY/SELL, and
never changes AI_MASTER weights. It receives the same snapshot already collected
by app.py and reports evidence to CO only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence


SECTOR_MAP: Dict[str, str] = {
    "HDFCBANK": "BANKS",
    "ICICIBANK": "BANKS",
    "AXISBANK": "BANKS",
    "RELIANCE": "ENERGY",
    "INFY": "IT",
    "TCS": "IT",
    "LT": "INFRA",
    "BHARTIARTL": "TELECOM",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _direction(value: float, threshold: float) -> str:
    if value >= threshold:
        return "UP"
    if value <= -threshold:
        return "DOWN"
    return "FLAT"


@dataclass(frozen=True)
class HeavyweightIntelligenceReport:
    summary: str
    confidence: float
    details: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)

    def to_department_report(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "confidence": self.confidence,
            "details": dict(self.details),
            "warnings": list(self.warnings),
        }

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "confidence": self.confidence,
            **dict(self.details),
            "warnings": list(self.warnings),
        }


class HeavyweightIntelligenceDirector:
    """One-shot heavyweight investigation using already-fetched market rows."""

    VERSION = "V40.3_HEAVYWEIGHT_INTELLIGENCE"
    STATE_KEY = "v40_heavyweight_history"
    MAX_HISTORY = 8

    def evaluate(
        self,
        *,
        state: MutableMapping[str, Any],
        rows: Sequence[Mapping[str, Any]],
        nifty_level: float,
        nifty_change_pct: float,
        expected_symbols: Sequence[str],
        source: str = "Unknown",
        existing_analysis: Mapping[str, Any] | None = None,
        observed_at: str = "",
    ) -> HeavyweightIntelligenceReport:
        clean_rows = self._clean_rows(rows)
        expected = [str(symbol).upper() for symbol in expected_symbols]
        expected_count = max(1, len(expected))
        coverage_count = len({row["symbol"] for row in clean_rows if row["symbol"] in expected})
        coverage_pct = _clamp(coverage_count / expected_count * 100.0)
        warnings: List[str] = []

        if not clean_rows:
            details = {
                "version": self.VERSION,
                "investigation_state": "DATA_UNAVAILABLE",
                "alignment_state": "INSUFFICIENT_DATA",
                "coverage_count": 0,
                "expected_count": expected_count,
                "coverage_pct": 0.0,
                "tracked_weight_pct": 0.0,
                "weighted_pressure": 0.0,
                "estimated_nifty_points": 0.0,
                "advancing_count": 0,
                "declining_count": 0,
                "flat_count": 0,
                "dominant_driver": "NONE",
                "dominant_sector": "NONE",
                "concentration_risk": "UNKNOWN",
                "leadership_rotation": "COLLECTING",
                "sector_map": {},
                "driver_rows": [],
                "evidence": [],
                "next_confirmation_required": ["Fresh heavyweight quote snapshot required."],
                "execution_instruction": "NONE",
                "authority": "EVIDENCE_ONLY_TO_CO",
            }
            return HeavyweightIntelligenceReport(
                summary="Heavyweight evidence unavailable; CO should keep this branch informational.",
                confidence=0.0,
                details=details,
                warnings=["No usable heavyweight rows."],
            )

        tracked_weight = sum(max(0.0, row["weight"]) for row in clean_rows)
        weighted_return_numerator = sum(row["weight"] * row["change_pct"] for row in clean_rows)
        weighted_return = weighted_return_numerator / tracked_weight if tracked_weight > 0 else 0.0
        derived_pressure = _clamp(weighted_return * 75.0, -100.0, 100.0)
        analysis = existing_analysis if isinstance(existing_analysis, Mapping) else {}
        weighted_pressure = _number(analysis.get("pressure"), derived_pressure)

        contributions: List[Dict[str, Any]] = []
        for row in clean_rows:
            points = _number(nifty_level) * (row["weight"] / 100.0) * (row["change_pct"] / 100.0)
            contributions.append({
                **row,
                "sector": SECTOR_MAP.get(row["symbol"], "OTHER"),
                "estimated_nifty_points": round(points, 2),
                "move_direction": _direction(row["change_pct"], 0.05),
                "shock_direction": _direction(row["shock_delta_pct"], 0.12),
            })

        estimated_points = sum(row["estimated_nifty_points"] for row in contributions)
        advancing = sum(1 for row in contributions if row["change_pct"] > 0.05)
        declining = sum(1 for row in contributions if row["change_pct"] < -0.05)
        flat = len(contributions) - advancing - declining
        nifty_direction = _direction(_number(nifty_change_pct), 0.08)
        driver_direction = _direction(weighted_pressure, 15.0)

        alignment_state = self._alignment_state(
            nifty_direction=nifty_direction,
            driver_direction=driver_direction,
            pressure=weighted_pressure,
        )

        absolute_points = sum(abs(row["estimated_nifty_points"]) for row in contributions)
        sorted_by_impact = sorted(contributions, key=lambda row: abs(row["estimated_nifty_points"]), reverse=True)
        dominant = sorted_by_impact[0] if sorted_by_impact else {}
        top_one_share = abs(_number(dominant.get("estimated_nifty_points"))) / absolute_points * 100.0 if absolute_points > 0 else 0.0
        top_two_share = (
            sum(abs(_number(row.get("estimated_nifty_points"))) for row in sorted_by_impact[:2]) / absolute_points * 100.0
            if absolute_points > 0 else 0.0
        )
        concentration_risk = "HIGH_SINGLE_STOCK" if top_one_share >= 48 else "HIGH_TOP_TWO" if top_two_share >= 72 else "DIVERSIFIED"

        sector_rows = self._sector_rows(contributions)
        dominant_sector_row = max(sector_rows, key=lambda row: abs(row["estimated_nifty_points"]), default={})
        dominant_sector = str(dominant_sector_row.get("sector", "NONE"))
        sector_directions = {row["direction"] for row in sector_rows if row["direction"] in {"UP", "DOWN"}}
        sector_split = len(sector_directions) >= 2

        shock_rows = [
            row for row in contributions
            if abs(row["shock_delta_pct"]) >= 0.25
        ]
        positive_weight = sum(row["weight"] for row in contributions if row["change_pct"] > 0.05)
        negative_weight = sum(row["weight"] for row in contributions if row["change_pct"] < -0.05)
        participating_weight = positive_weight if driver_direction == "UP" else negative_weight if driver_direction == "DOWN" else max(positive_weight, negative_weight)
        participation_pct = participating_weight / tracked_weight * 100.0 if tracked_weight > 0 else 0.0

        prior = self._last_history(state)
        leadership_rotation = self._rotation_state(
            prior=prior,
            dominant_symbol=str(dominant.get("symbol", "NONE")),
            dominant_sector=dominant_sector,
            driver_direction=driver_direction,
        )

        investigation_state = self._investigation_state(
            alignment_state=alignment_state,
            participation_pct=participation_pct,
            concentration_risk=concentration_risk,
            sector_split=sector_split,
            coverage_pct=coverage_pct,
        )

        evidence = self._evidence(
            alignment_state=alignment_state,
            tracked_weight=tracked_weight,
            participation_pct=participation_pct,
            dominant=dominant,
            dominant_sector=dominant_sector,
            concentration_risk=concentration_risk,
            shock_rows=shock_rows,
            sector_split=sector_split,
        )
        next_confirmation = self._next_confirmation(
            investigation_state=investigation_state,
            shock_rows=shock_rows,
            coverage_pct=coverage_pct,
            leadership_rotation=leadership_rotation,
        )

        if coverage_pct < 75:
            warnings.append("Heavyweight coverage below 75%; sector conclusion is incomplete.")
        if concentration_risk != "DIVERSIFIED":
            warnings.append("Index contribution is concentrated; broad follow-through is not yet proven.")
        if sector_split:
            warnings.append("Major sectors are pulling NIFTY in opposite directions.")
        if shock_rows:
            warnings.append("Fresh constituent shock detected; require next-snapshot persistence.")

        confidence = self._confidence(
            coverage_pct=coverage_pct,
            participation_pct=participation_pct,
            alignment_state=alignment_state,
            sector_split=sector_split,
            shock_count=len(shock_rows),
        )

        history_record = {
            "observed_at": str(observed_at)[:32],
            "dominant_symbol": str(dominant.get("symbol", "NONE")),
            "dominant_sector": dominant_sector,
            "driver_direction": driver_direction,
            "weighted_pressure": round(weighted_pressure, 1),
            "investigation_state": investigation_state,
        }
        self._append_history(state, history_record)

        details = {
            "version": self.VERSION,
            "investigation_state": investigation_state,
            "alignment_state": alignment_state,
            "nifty_direction": nifty_direction,
            "driver_direction": driver_direction,
            "coverage_count": coverage_count,
            "expected_count": expected_count,
            "coverage_pct": round(coverage_pct, 1),
            "tracked_weight_pct": round(tracked_weight, 2),
            "weighted_pressure": round(weighted_pressure, 1),
            "weighted_return_pct": round(weighted_return, 3),
            "estimated_nifty_points": round(estimated_points, 1),
            "advancing_count": advancing,
            "declining_count": declining,
            "flat_count": flat,
            "participation_pct": round(participation_pct, 1),
            "dominant_driver": str(dominant.get("name", dominant.get("symbol", "NONE"))),
            "dominant_driver_symbol": str(dominant.get("symbol", "NONE")),
            "dominant_driver_points": round(_number(dominant.get("estimated_nifty_points")), 1),
            "dominant_sector": dominant_sector,
            "top_one_concentration_pct": round(top_one_share, 1),
            "top_two_concentration_pct": round(top_two_share, 1),
            "concentration_risk": concentration_risk,
            "leadership_rotation": leadership_rotation,
            "sector_split": sector_split,
            "shock_count": len(shock_rows),
            "shock_drivers": [row["symbol"] for row in shock_rows[:4]],
            "sector_map": {row["sector"]: row for row in sector_rows},
            "driver_rows": [self._compact_driver(row) for row in sorted_by_impact[:8]],
            "evidence": evidence[:6],
            "next_confirmation_required": next_confirmation[:4],
            "source": str(source)[:80],
            "execution_instruction": "NONE",
            "recommendation": "INFORMATION_ONLY",
            "authority": "EVIDENCE_ONLY_TO_CO",
        }
        summary = (
            f"{investigation_state} | {coverage_count}/{expected_count} drivers | "
            f"pressure {weighted_pressure:+.0f}/100 | contribution {estimated_points:+.1f} pts | "
            f"leader {details['dominant_driver']}"
        )
        return HeavyweightIntelligenceReport(
            summary=summary[:300],
            confidence=round(confidence, 1),
            details=details,
            warnings=warnings[:4],
        )

    @staticmethod
    def _clean_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for raw in rows:
            if not isinstance(raw, Mapping):
                continue
            symbol = str(raw.get("symbol", "")).upper().strip()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            output.append({
                "symbol": symbol,
                "name": str(raw.get("name", symbol))[:80],
                "weight": max(0.0, _number(raw.get("weight"))),
                "change_pct": _number(raw.get("change_pct")),
                "momentum_pct": _number(raw.get("momentum_pct")),
                "shock_delta_pct": _number(raw.get("shock_delta_pct")),
                "volume": max(0, int(_number(raw.get("volume")))),
            })
        return output[:12]

    @staticmethod
    def _alignment_state(*, nifty_direction: str, driver_direction: str, pressure: float) -> str:
        if nifty_direction == "UP" and driver_direction == "UP":
            return "NIFTY_UP_DRIVERS_CONFIRM"
        if nifty_direction == "DOWN" and driver_direction == "DOWN":
            return "NIFTY_DOWN_DRIVERS_CONFIRM"
        if nifty_direction == "UP" and driver_direction == "DOWN":
            return "NIFTY_UP_DRIVERS_CONFLICT"
        if nifty_direction == "DOWN" and driver_direction == "UP":
            return "NIFTY_DOWN_DRIVERS_CONFLICT"
        if nifty_direction == "FLAT" and abs(pressure) >= 25:
            return "HIDDEN_HEAVYWEIGHT_PRESSURE"
        return "MIXED_OR_BALANCED"

    @staticmethod
    def _sector_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        sectors: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            sector = str(row.get("sector", "OTHER"))
            record = sectors.setdefault(sector, {
                "sector": sector,
                "weight_pct": 0.0,
                "estimated_nifty_points": 0.0,
                "advancing": 0,
                "declining": 0,
                "members": [],
            })
            record["weight_pct"] += _number(row.get("weight"))
            record["estimated_nifty_points"] += _number(row.get("estimated_nifty_points"))
            if _number(row.get("change_pct")) > 0.05:
                record["advancing"] += 1
            elif _number(row.get("change_pct")) < -0.05:
                record["declining"] += 1
            record["members"].append(str(row.get("symbol", "")))
        output: List[Dict[str, Any]] = []
        for record in sectors.values():
            record["weight_pct"] = round(record["weight_pct"], 2)
            record["estimated_nifty_points"] = round(record["estimated_nifty_points"], 1)
            record["direction"] = _direction(record["estimated_nifty_points"], 0.5)
            record["members"] = record["members"][:4]
            output.append(record)
        return sorted(output, key=lambda row: abs(row["estimated_nifty_points"]), reverse=True)

    @staticmethod
    def _rotation_state(*, prior: Mapping[str, Any], dominant_symbol: str, dominant_sector: str, driver_direction: str) -> str:
        if not prior:
            return "COLLECTING"
        old_symbol = str(prior.get("dominant_symbol", "NONE"))
        old_sector = str(prior.get("dominant_sector", "NONE"))
        old_direction = str(prior.get("driver_direction", "FLAT"))
        if old_direction in {"UP", "DOWN"} and driver_direction in {"UP", "DOWN"} and old_direction != driver_direction:
            return "DIRECTION_FLIP"
        if old_sector != dominant_sector and old_sector != "NONE":
            return "SECTOR_LEADERSHIP_ROTATION"
        if old_symbol != dominant_symbol and old_symbol != "NONE":
            return "LEADER_ROTATION"
        return "LEADERSHIP_STABLE"

    @staticmethod
    def _investigation_state(
        *, alignment_state: str, participation_pct: float, concentration_risk: str,
        sector_split: bool, coverage_pct: float,
    ) -> str:
        if coverage_pct < 50:
            return "INCOMPLETE_DRIVER_COVERAGE"
        if "CONFLICT" in alignment_state:
            return "INDEX_HEAVYWEIGHT_CONFLICT"
        if alignment_state == "HIDDEN_HEAVYWEIGHT_PRESSURE":
            return "HIDDEN_DRIVER_PRESSURE"
        if concentration_risk != "DIVERSIFIED":
            return "CONCENTRATED_INDEX_MOVE"
        if sector_split:
            return "SECTOR_SPLIT_MOVE"
        if alignment_state == "NIFTY_UP_DRIVERS_CONFIRM" and participation_pct >= 62:
            return "BROAD_UPSIDE_PARTICIPATION"
        if alignment_state == "NIFTY_DOWN_DRIVERS_CONFIRM" and participation_pct >= 62:
            return "BROAD_DOWNSIDE_PARTICIPATION"
        if alignment_state in {"NIFTY_UP_DRIVERS_CONFIRM", "NIFTY_DOWN_DRIVERS_CONFIRM"}:
            return "PARTIAL_DRIVER_CONFIRMATION"
        return "BALANCED_DRIVER_EVIDENCE"

    @staticmethod
    def _evidence(
        *, alignment_state: str, tracked_weight: float, participation_pct: float,
        dominant: Mapping[str, Any], dominant_sector: str, concentration_risk: str,
        shock_rows: Sequence[Mapping[str, Any]], sector_split: bool,
    ) -> List[str]:
        evidence = [
            f"Tracked heavyweight weight {tracked_weight:.2f}%.",
            f"NIFTY-driver alignment: {alignment_state}.",
            f"Directional participation weight: {participation_pct:.1f}% of tracked basket.",
        ]
        if dominant:
            evidence.append(
                f"Largest contribution: {dominant.get('name', dominant.get('symbol','-'))} "
                f"{_number(dominant.get('estimated_nifty_points')):+.1f} pts."
            )
        if dominant_sector != "NONE":
            evidence.append(f"Dominant sector contribution: {dominant_sector}.")
        if concentration_risk != "DIVERSIFIED":
            evidence.append(f"Contribution concentration: {concentration_risk}.")
        if sector_split:
            evidence.append("Sector contributions are split in opposite directions.")
        if shock_rows:
            evidence.append("Fresh shock: " + ", ".join(str(row.get("symbol")) for row in shock_rows[:4]))
        return evidence

    @staticmethod
    def _next_confirmation(
        *, investigation_state: str, shock_rows: Sequence[Mapping[str, Any]],
        coverage_pct: float, leadership_rotation: str,
    ) -> List[str]:
        checks: List[str] = []
        if coverage_pct < 100:
            checks.append("Resolve remaining constituent quotes before treating basket as complete.")
        if "CONFLICT" in investigation_state or investigation_state in {"SECTOR_SPLIT_MOVE", "CONCENTRATED_INDEX_MOVE"}:
            checks.append("Require next snapshot to show broader sector participation.")
        if shock_rows:
            checks.append("Verify constituent shock persists beyond one refresh.")
        if leadership_rotation in {"DIRECTION_FLIP", "SECTOR_LEADERSHIP_ROTATION", "LEADER_ROTATION"}:
            checks.append("Verify new leader retains contribution on the next snapshot.")
        if not checks:
            checks.append("Confirm heavyweight direction remains aligned with price action and option flow.")
        return checks

    @staticmethod
    def _confidence(
        *, coverage_pct: float, participation_pct: float, alignment_state: str,
        sector_split: bool, shock_count: int,
    ) -> float:
        score = coverage_pct * 0.55 + min(100.0, participation_pct) * 0.25 + 15.0
        if "CONFIRM" in alignment_state:
            score += 8.0
        if "CONFLICT" in alignment_state:
            score -= 6.0
        if sector_split:
            score -= 6.0
        if shock_count:
            score -= min(10.0, shock_count * 3.0)
        return _clamp(score, 20.0, 88.0)

    @staticmethod
    def _compact_driver(row: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": str(row.get("symbol", "")),
            "name": str(row.get("name", ""))[:60],
            "sector": str(row.get("sector", "OTHER")),
            "weight_pct": round(_number(row.get("weight")), 2),
            "change_pct": round(_number(row.get("change_pct")), 2),
            "momentum_pct": round(_number(row.get("momentum_pct")), 2),
            "shock_delta_pct": round(_number(row.get("shock_delta_pct")), 2),
            "estimated_nifty_points": round(_number(row.get("estimated_nifty_points")), 1),
        }

    def _last_history(self, state: MutableMapping[str, Any]) -> Mapping[str, Any]:
        history = state.get(self.STATE_KEY, [])
        if isinstance(history, list) and history:
            item = history[-1]
            return item if isinstance(item, Mapping) else {}
        return {}

    def _append_history(self, state: MutableMapping[str, Any], record: Mapping[str, Any]) -> None:
        history = state.get(self.STATE_KEY, [])
        history = list(history) if isinstance(history, list) else []
        # Avoid duplicate records produced by the same fetched snapshot/time.
        if history and str(history[-1].get("observed_at", "")) == str(record.get("observed_at", "")):
            history[-1] = dict(record)
        else:
            history.append(dict(record))
        state[self.STATE_KEY] = history[-self.MAX_HISTORY:]
