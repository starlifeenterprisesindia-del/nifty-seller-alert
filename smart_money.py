"""
smart_money.py
Version: V42.3
Department: Smart Money / Institutional Behaviour
Status: Combined institutional investigation bundle

Safety contract:
- Upgrades the existing SMART_MONEY branch; no duplicate institutional department.
- Reads already available FII/DII journal, futures positioning, breadth and heavyweight evidence.
- Preserves legacy FII/DII/heavyweight/breadth keys used by the existing strategy pipeline.
- Detailed institutional fields are evidence for DSP -> CO -> AI_MASTER.
- Never emits BUY/SELL, never fetches data, and never changes production weights automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional


@dataclass
class SmartMoneyReport:
    summary: str
    confidence: float
    details: Dict[str, Any]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: Any, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, _number(value)))


def _direction(value: float, threshold: float = 0.01) -> str:
    if value > threshold:
        return "BUYING"
    if value < -threshold:
        return "SELLING"
    return "NEUTRAL"


class FIISpecialist:
    """Legacy-compatible FII witness."""

    def analyze(self, fii_net: float) -> Dict[str, Any]:
        if fii_net > 0:
            return {"fii": "Buying", "score": 80}
        if fii_net < 0:
            return {"fii": "Selling", "score": 80}
        return {"fii": "Neutral", "score": 50}


class DIISpecialist:
    """Legacy-compatible DII witness."""

    def analyze(self, dii_net: float) -> Dict[str, Any]:
        if dii_net > 0:
            return {"dii": "Buying"}
        if dii_net < 0:
            return {"dii": "Selling"}
        return {"dii": "Neutral"}


class HeavyweightSpecialist:
    """Legacy-compatible heavyweight witness."""

    def analyze(self, advancing: int, declining: int) -> Dict[str, Any]:
        if advancing > declining:
            return {"heavyweights": "Supporting Market"}
        if declining > advancing:
            return {"heavyweights": "Pressuring Market"}
        return {"heavyweights": "Balanced"}


class BreadthSpecialist:
    """Legacy-compatible breadth witness."""

    def analyze(self, advance: int, decline: int) -> Dict[str, Any]:
        total = max(int(advance or 0) + int(decline or 0), 1)
        ratio = int(advance or 0) / total
        if ratio > 0.65:
            status = "Strong Breadth"
        elif ratio < 0.35:
            status = "Weak Breadth"
        else:
            status = "Neutral Breadth"
        return {"breadth": status, "ratio": round(ratio, 2)}


class SmartMoneyDirector:
    """One-shot institutional behaviour investigator.

    The first six positional parameters remain backward-compatible with V23.3.
    V42 fields are optional and are never allowed to create an execution action.
    """

    VERSION = "V42.3_INSTITUTIONAL_BEHAVIOUR"
    STATE_KEY = "v42_institutional_behaviour_history"
    MAX_HISTORY = 8

    def build_report(
        self,
        fii_net: float,
        dii_net: float,
        advancing: int,
        declining: int,
        advance: int,
        decline: int,
        *,
        state: Optional[MutableMapping[str, Any]] = None,
        fii_5day: float = 0.0,
        dii_5day: float = 0.0,
        fii_10day: float = 0.0,
        dii_10day: float = 0.0,
        futures_contracts: float = 0.0,
        fii_long_pct: float = 0.0,
        fii_short_pct: float = 0.0,
        futures_bias: str = "Neutral",
        options_bias: str = "Neutral",
        journal_records: Optional[Iterable[Mapping[str, Any]]] = None,
        nifty_change_pct: float = 0.0,
        heavyweight_report: Any = None,
        observed_at: str = "",
    ) -> SmartMoneyReport:
        fii_net = _number(fii_net)
        dii_net = _number(dii_net)
        fii_5day = _number(fii_5day)
        dii_5day = _number(dii_5day)
        fii_10day = _number(fii_10day)
        dii_10day = _number(dii_10day)
        futures_contracts = _number(futures_contracts)
        nifty_change_pct = _number(nifty_change_pct)

        # Legacy fields stay exactly compatible with StrategyDirector and AI_MASTER.
        fii = FIISpecialist().analyze(fii_net)
        dii = DIISpecialist().analyze(dii_net)
        hw = HeavyweightSpecialist().analyze(advancing, declining)
        br = BreadthSpecialist().analyze(advance, decline)

        futures = self._futures_positioning(
            long_pct=fii_long_pct,
            short_pct=fii_short_pct,
            contracts=futures_contracts,
            futures_bias=futures_bias,
            options_bias=options_bias,
        )
        rolling = self._rolling_journal(journal_records)
        cash = self._cash_flow(
            fii_today=fii_net,
            dii_today=dii_net,
            fii_5day=fii_5day,
            dii_5day=dii_5day,
            fii_10day=fii_10day,
            dii_10day=dii_10day,
            rolling=rolling,
        )
        heavy_details = self._details(heavyweight_report)
        heavy_alignment = str(
            heavy_details.get("alignment_state")
            or heavy_details.get("investigation_state")
            or hw.get("heavyweights", "Balanced")
        )

        conflict_score = self._conflict_score(cash, futures, dii_net)
        institutional_state = self._institutional_state(cash, futures, dii_net)
        pressure_score = self._pressure_score(
            cash=cash,
            futures=futures,
            breadth_ratio=_number(br.get("ratio"), 0.5),
            heavyweight_state=hw.get("heavyweights", "Balanced"),
            options_bias=options_bias,
        )
        market_alignment = self._market_alignment(pressure_score, nifty_change_pct)
        market_mood = self._market_mood(
            pressure_score=pressure_score,
            conflict_score=conflict_score,
            institutional_state=institutional_state,
        )
        persistence_state = self._update_persistence(
            state=state,
            institutional_state=institutional_state,
            pressure_score=pressure_score,
            observed_at=observed_at,
        )
        evidence = self._evidence(
            cash=cash,
            futures=futures,
            institutional_state=institutional_state,
            market_alignment=market_alignment,
            heavy_alignment=heavy_alignment,
        )
        next_confirmation = self._next_confirmation(
            cash=cash,
            futures=futures,
            institutional_state=institutional_state,
            market_alignment=market_alignment,
        )
        warnings = self._warnings(
            futures=futures,
            rolling=rolling,
            conflict_score=conflict_score,
            market_alignment=market_alignment,
        )
        institutional_confidence = self._institutional_confidence(
            futures=futures,
            rolling=rolling,
            fii_5day=fii_5day,
            fii_10day=fii_10day,
            conflict_score=conflict_score,
        )

        details: Dict[str, Any] = {
            # Legacy fields consumed by existing pipeline. Do not rename.
            "fii": fii,
            "dii": dii,
            "heavyweights": hw,
            "breadth": br,
            # Core V42 SOP facts stay near the front because CO stores compact facts.
            "version": self.VERSION,
            "institutional_state": institutional_state,
            "market_mood": market_mood,
            "cash_flow_state": cash["cash_flow_state"],
            "cash_alignment": cash["cash_alignment"],
            "futures_positioning": futures["positioning"],
            "futures_bias": futures["bias"],
            "fii_long_pct": futures["long_pct"],
            "fii_short_pct": futures["short_pct"],
            "institutional_pressure_score": pressure_score,
            "institutional_conflict_score": conflict_score,
            "market_alignment": market_alignment,
            "persistence_state": persistence_state,
            "institutional_confidence": institutional_confidence,
            "heavyweight_alignment": heavy_alignment,
            "futures_data_quality": futures["data_quality"],
            # V42.1 cash-flow detail.
            "fii_cash_today": round(fii_net, 1),
            "dii_cash_today": round(dii_net, 1),
            "fii_5day": round(fii_5day, 1),
            "dii_5day": round(dii_5day, 1),
            "fii_10day": round(fii_10day, 1),
            "dii_10day": round(dii_10day, 1),
            "domestic_absorption_pct": cash["domestic_absorption_pct"],
            "fii_cash_streak": rolling["fii_cash_streak"],
            "journal_days": rolling["journal_days"],
            "fii_buy_days": rolling["fii_buy_days"],
            "fii_sell_days": rolling["fii_sell_days"],
            # V42.2 futures detail.
            "futures_contracts": round(futures_contracts, 1),
            "long_short_spread": futures["long_short_spread"],
            "long_short_ratio": futures["long_short_ratio"],
            "long_pct_trend": rolling["long_pct_trend"],
            "options_bias": self._normalise_bias(options_bias),
            # Evidence-only communication fields.
            "evidence": evidence,
            "next_confirmation_required": next_confirmation,
            "warnings": warnings,
            "execution_instruction": "NONE",
            "authority": "DSP_SMART_MONEY_TO_CO_ONLY",
            "automatic_rule_change": False,
        }

        # Keep report confidence compatible with the old branch so V42 details do
        # not silently re-weight AI_MASTER before live validation.
        legacy_confidence = float(fii.get("score", 50))
        summary = (
            f'FII: {fii["fii"]} | DII: {dii["dii"]} | {br["breadth"]} | '
            f'Mood: {market_mood} | State: {institutional_state}'
        )
        return SmartMoneyReport(
            summary=summary,
            confidence=legacy_confidence,
            details=details,
        )

    @staticmethod
    def _normalise_bias(value: Any) -> str:
        text = str(value or "Neutral").strip().upper()
        if "BULL" in text or "LONG" in text:
            return "BULLISH"
        if "BEAR" in text or "SHORT" in text:
            return "BEARISH"
        return "NEUTRAL"

    def _futures_positioning(
        self,
        *,
        long_pct: float,
        short_pct: float,
        contracts: float,
        futures_bias: str,
        options_bias: str,
    ) -> Dict[str, Any]:
        raw_long = max(0.0, _number(long_pct))
        raw_short = max(0.0, _number(short_pct))
        total = raw_long + raw_short
        warnings: List[str] = []
        if total <= 0:
            long_value = 0.0
            short_value = 0.0
            quality = "UNAVAILABLE"
            positioning = "POSITIONING_DATA_UNAVAILABLE"
        else:
            long_value = raw_long / total * 100.0
            short_value = raw_short / total * 100.0
            quality = "COMPLETE" if 98.0 <= total <= 102.0 else "NORMALISED_PERCENTAGES"
            if quality != "COMPLETE":
                warnings.append("Long/short percentages were normalised to 100%.")
            spread = long_value - short_value
            if spread >= 35:
                positioning = "AGGRESSIVE_LONG_POSITIONING"
            elif spread >= 12:
                positioning = "LONG_LEAN_POSITIONING"
            elif spread <= -35:
                positioning = "AGGRESSIVE_SHORT_POSITIONING"
            elif spread <= -12:
                positioning = "SHORT_LEAN_POSITIONING"
            else:
                positioning = "BALANCED_POSITIONING"

        spread = long_value - short_value
        ratio = long_value / short_value if short_value > 0 else (99.0 if long_value > 0 else 0.0)
        derived_bias = "BULLISH" if spread >= 12 else "BEARISH" if spread <= -12 else "NEUTRAL"
        selected_bias = self._normalise_bias(futures_bias)
        if selected_bias == "NEUTRAL" and derived_bias != "NEUTRAL":
            selected_bias = derived_bias
        options = self._normalise_bias(options_bias)
        if options != "NEUTRAL" and selected_bias != "NEUTRAL" and options != selected_bias:
            warnings.append("Futures and options institutional bias conflict.")

        return {
            "positioning": positioning,
            "bias": selected_bias,
            "long_pct": round(long_value, 2),
            "short_pct": round(short_value, 2),
            "long_short_spread": round(spread, 2),
            "long_short_ratio": round(min(ratio, 99.0), 2),
            "contracts": round(_number(contracts), 1),
            "data_quality": quality,
            "warnings": warnings,
        }

    def _rolling_journal(self, records: Optional[Iterable[Mapping[str, Any]]]) -> Dict[str, Any]:
        rows: List[Mapping[str, Any]] = []
        if records is not None:
            try:
                rows = [row for row in records if isinstance(row, Mapping)][-10:]
            except TypeError:
                rows = []

        fii_values = [_number(row.get("FII Cash Cr")) for row in rows]
        long_values = [_number(row.get("FII Long %")) for row in rows if _number(row.get("FII Long %")) > 0]
        buy_days = sum(value > 0 for value in fii_values)
        sell_days = sum(value < 0 for value in fii_values)
        streak = 0
        streak_label = "NO_STREAK"
        if fii_values:
            last_sign = 1 if fii_values[-1] > 0 else -1 if fii_values[-1] < 0 else 0
            if last_sign:
                for value in reversed(fii_values):
                    sign = 1 if value > 0 else -1 if value < 0 else 0
                    if sign != last_sign:
                        break
                    streak += 1
                streak_label = f"{streak}D_BUYING" if last_sign > 0 else f"{streak}D_SELLING"

        if len(long_values) >= 2:
            delta = long_values[-1] - long_values[0]
            long_trend = "LONG_SHARE_RISING" if delta >= 3 else "LONG_SHARE_FALLING" if delta <= -3 else "LONG_SHARE_STABLE"
        else:
            long_trend = "INSUFFICIENT_HISTORY"

        return {
            "journal_days": len(rows),
            "fii_buy_days": buy_days,
            "fii_sell_days": sell_days,
            "fii_cash_streak": streak_label,
            "long_pct_trend": long_trend,
        }

    def _cash_flow(
        self,
        *,
        fii_today: float,
        dii_today: float,
        fii_5day: float,
        dii_5day: float,
        fii_10day: float,
        dii_10day: float,
        rolling: Mapping[str, Any],
    ) -> Dict[str, Any]:
        fii_today_dir = _direction(fii_today)
        dii_today_dir = _direction(dii_today)
        fii_5d_dir = _direction(fii_5day)
        fii_10d_dir = _direction(fii_10day)

        if fii_today_dir == "BUYING" and fii_5d_dir == "BUYING" and (fii_10d_dir in {"BUYING", "NEUTRAL"}):
            cash_state = "FII_ACCUMULATION"
        elif fii_today_dir == "SELLING" and fii_5d_dir == "SELLING" and (fii_10d_dir in {"SELLING", "NEUTRAL"}):
            cash_state = "FII_DISTRIBUTION"
        elif fii_today_dir != "NEUTRAL" and fii_5d_dir != "NEUTRAL" and fii_today_dir != fii_5d_dir:
            cash_state = "FII_DAILY_ROLLING_REVERSAL"
        elif fii_5d_dir == "BUYING":
            cash_state = "ROLLING_FII_BUYING"
        elif fii_5d_dir == "SELLING":
            cash_state = "ROLLING_FII_SELLING"
        else:
            cash_state = "CASH_FLOW_BALANCED"

        if fii_today_dir == dii_today_dir and fii_today_dir != "NEUTRAL":
            cash_alignment = "FII_DII_ALIGNED_" + fii_today_dir
        elif fii_today_dir == "SELLING" and dii_today_dir == "BUYING":
            cash_alignment = "DII_ABSORBING_FII_SELLING"
        elif fii_today_dir == "BUYING" and dii_today_dir == "SELLING":
            cash_alignment = "FII_BUYING_DII_PROFIT_BOOKING"
        else:
            cash_alignment = "FII_DII_MIXED_OR_NEUTRAL"

        absorption = 0.0
        if fii_today < 0 and dii_today > 0:
            absorption = min(200.0, abs(dii_today) / max(abs(fii_today), 1.0) * 100.0)

        return {
            "fii_today_direction": fii_today_dir,
            "dii_today_direction": dii_today_dir,
            "fii_5day_direction": fii_5d_dir,
            "fii_10day_direction": fii_10d_dir,
            "cash_flow_state": cash_state,
            "cash_alignment": cash_alignment,
            "domestic_absorption_pct": round(absorption, 1),
            "fii_cash_streak": rolling.get("fii_cash_streak", "NO_STREAK"),
        }

    @staticmethod
    def _institutional_state(cash: Mapping[str, Any], futures: Mapping[str, Any], dii_today: float) -> str:
        fii_dir = str(cash.get("fii_today_direction", "NEUTRAL"))
        cash_state = str(cash.get("cash_flow_state", "CASH_FLOW_BALANCED"))
        cash_alignment = str(cash.get("cash_alignment", "FII_DII_MIXED_OR_NEUTRAL"))
        positioning = str(futures.get("positioning", "POSITIONING_DATA_UNAVAILABLE"))
        fut_long = "LONG" in positioning and "SHORT" not in positioning
        fut_short = "SHORT" in positioning

        if fii_dir == "BUYING" and fut_long:
            return "FII_CASH_AND_FUTURES_ALIGNED_ACCUMULATION"
        if fii_dir == "SELLING" and fut_short:
            return "FII_CASH_AND_FUTURES_ALIGNED_DISTRIBUTION"
        if fii_dir == "BUYING" and fut_short:
            return "FII_CASH_BUYING_WITH_FUTURES_HEDGE_CONFLICT"
        if fii_dir == "SELLING" and fut_long:
            return "FII_CASH_SELLING_WITH_FUTURES_RECOVERY_CONFLICT"
        if cash_alignment == "DII_ABSORBING_FII_SELLING":
            return "DOMESTIC_INSTITUTIONAL_ABSORPTION"
        if cash_alignment == "FII_BUYING_DII_PROFIT_BOOKING":
            return "FOREIGN_ACCUMULATION_DOMESTIC_DISTRIBUTION"
        if cash_state == "FII_ACCUMULATION":
            return "FII_CASH_ACCUMULATION"
        if cash_state == "FII_DISTRIBUTION":
            return "FII_CASH_DISTRIBUTION"
        if positioning == "POSITIONING_DATA_UNAVAILABLE":
            return "INSTITUTIONAL_DATA_PARTIAL"
        return "INSTITUTIONAL_BALANCE_OR_MIXED_POSITIONING"

    @staticmethod
    def _conflict_score(cash: Mapping[str, Any], futures: Mapping[str, Any], dii_today: float) -> float:
        score = 10.0
        fii_dir = str(cash.get("fii_today_direction", "NEUTRAL"))
        alignment = str(cash.get("cash_alignment", ""))
        positioning = str(futures.get("positioning", ""))
        fut_long = "LONG" in positioning and "SHORT" not in positioning
        fut_short = "SHORT" in positioning
        if (fii_dir == "BUYING" and fut_short) or (fii_dir == "SELLING" and fut_long):
            score += 55
        if "ABSORBING" in alignment or "PROFIT_BOOKING" in alignment:
            score += 20
        if futures.get("data_quality") == "UNAVAILABLE":
            score += 10
        if any("conflict" in str(item).lower() for item in futures.get("warnings", [])):
            score += 15
        return round(_clamp(score, 0.0, 100.0), 1)

    @staticmethod
    def _pressure_score(
        *,
        cash: Mapping[str, Any],
        futures: Mapping[str, Any],
        breadth_ratio: float,
        heavyweight_state: str,
        options_bias: str,
    ) -> float:
        score = 0.0
        fii_dir = str(cash.get("fii_today_direction", "NEUTRAL"))
        fii_5d = str(cash.get("fii_5day_direction", "NEUTRAL"))
        score += 24 if fii_dir == "BUYING" else -24 if fii_dir == "SELLING" else 0
        score += 18 if fii_5d == "BUYING" else -18 if fii_5d == "SELLING" else 0
        spread = _number(futures.get("long_short_spread"))
        score += _clamp(spread * 0.55, -28.0, 28.0)
        bias = str(futures.get("bias", "NEUTRAL"))
        score += 8 if bias == "BULLISH" else -8 if bias == "BEARISH" else 0
        opt = str(options_bias or "").upper()
        score += 6 if "BULL" in opt else -6 if "BEAR" in opt else 0
        score += _clamp((breadth_ratio - 0.5) * 32.0, -8.0, 8.0)
        score += 7 if heavyweight_state == "Supporting Market" else -7 if heavyweight_state == "Pressuring Market" else 0
        return round(_clamp(score), 1)

    @staticmethod
    def _market_alignment(pressure_score: float, nifty_change_pct: float) -> str:
        if abs(nifty_change_pct) < 0.08 or abs(pressure_score) < 18:
            return "MARKET_ALIGNMENT_UNCLEAR"
        if pressure_score > 0 and nifty_change_pct > 0:
            return "INSTITUTIONAL_PRESSURE_CONFIRMS_UPMOVE"
        if pressure_score < 0 and nifty_change_pct < 0:
            return "INSTITUTIONAL_PRESSURE_CONFIRMS_DOWNMOVE"
        if pressure_score > 0 and nifty_change_pct < 0:
            return "POSITIVE_INSTITUTIONAL_PRESSURE_HIDDEN_UNDER_WEAK_INDEX"
        return "NEGATIVE_INSTITUTIONAL_PRESSURE_HIDDEN_UNDER_STRONG_INDEX"

    @staticmethod
    def _market_mood(*, pressure_score: float, conflict_score: float, institutional_state: str) -> str:
        if "ABSORPTION" in institutional_state:
            return "DOMESTIC_ABSORPTION"
        if conflict_score >= 55:
            return "HEDGED_OR_CONFLICTED"
        if pressure_score >= 35:
            return "RISK_ON"
        if pressure_score <= -35:
            return "RISK_OFF"
        if abs(pressure_score) >= 18:
            return "CAUTIOUS_RISK_ON" if pressure_score > 0 else "CAUTIOUS_RISK_OFF"
        return "NEUTRAL_INSTITUTIONAL_MOOD"

    def _update_persistence(
        self,
        *,
        state: Optional[MutableMapping[str, Any]],
        institutional_state: str,
        pressure_score: float,
        observed_at: str,
    ) -> str:
        if state is None:
            return "STATE_MEMORY_UNAVAILABLE"
        history = state.get(self.STATE_KEY)
        if not isinstance(history, list):
            history = []
        previous = history[-1] if history and isinstance(history[-1], Mapping) else {}
        previous_state = str(previous.get("institutional_state", ""))
        previous_score = _number(previous.get("pressure_score"))
        if not previous_state:
            persistence = "FIRST_OBSERVATION"
        elif previous_state == institutional_state and abs(pressure_score - previous_score) < 12:
            persistence = "INSTITUTIONAL_STATE_PERSISTING"
        elif previous_state == institutional_state and abs(pressure_score) > abs(previous_score) + 8:
            persistence = "INSTITUTIONAL_PRESSURE_STRENGTHENING"
        elif previous_state == institutional_state:
            persistence = "INSTITUTIONAL_PRESSURE_FADING"
        else:
            persistence = "INSTITUTIONAL_STATE_CHANGED"
        history.append({
            "observed_at": str(observed_at or "SESSION")[:40],
            "institutional_state": institutional_state,
            "pressure_score": round(pressure_score, 1),
        })
        state[self.STATE_KEY] = history[-self.MAX_HISTORY:]
        return persistence

    @staticmethod
    def _evidence(
        *,
        cash: Mapping[str, Any],
        futures: Mapping[str, Any],
        institutional_state: str,
        market_alignment: str,
        heavy_alignment: str,
    ) -> List[str]:
        return [
            f"Cash flow: {cash.get('cash_flow_state', 'UNKNOWN')}",
            f"FII-DII relation: {cash.get('cash_alignment', 'UNKNOWN')}",
            f"Futures positioning: {futures.get('positioning', 'UNKNOWN')}",
            f"Institutional case: {institutional_state}",
            f"Index alignment: {market_alignment}",
            f"Heavyweight witness: {heavy_alignment}",
        ]

    @staticmethod
    def _next_confirmation(
        *,
        cash: Mapping[str, Any],
        futures: Mapping[str, Any],
        institutional_state: str,
        market_alignment: str,
    ) -> List[str]:
        checks: List[str] = []
        if "CONFLICT" in institutional_state:
            checks.append("Check whether futures hedge persists with the next cash-flow update.")
        if "ABSORPTION" in institutional_state:
            checks.append("Verify whether DII absorption prevents a fresh index low.")
        if futures.get("data_quality") == "UNAVAILABLE":
            checks.append("Add FII long/short percentages before treating futures positioning as reliable.")
        if "HIDDEN" in market_alignment:
            checks.append("Require price and heavyweight follow-through before accepting hidden institutional pressure.")
        if not checks:
            checks.append("Confirm the same institutional state on the next available journal/session observation.")
        return checks[:3]

    @staticmethod
    def _warnings(
        *,
        futures: Mapping[str, Any],
        rolling: Mapping[str, Any],
        conflict_score: float,
        market_alignment: str,
    ) -> List[str]:
        warnings = list(futures.get("warnings", []))
        if futures.get("data_quality") == "UNAVAILABLE":
            warnings.append("FII futures long/short data unavailable; cash-only interpretation is partial.")
        if int(rolling.get("journal_days", 0) or 0) < 3:
            warnings.append("Less than three journal observations; persistence confidence is limited.")
        if conflict_score >= 55:
            warnings.append("Cash and derivatives positioning conflict; do not treat one side as confirmed direction.")
        if "HIDDEN" in market_alignment:
            warnings.append("Institutional pressure conflicts with current NIFTY move.")
        return list(dict.fromkeys(warnings))[:4]

    @staticmethod
    def _institutional_confidence(
        *,
        futures: Mapping[str, Any],
        rolling: Mapping[str, Any],
        fii_5day: float,
        fii_10day: float,
        conflict_score: float,
    ) -> float:
        score = 42.0
        score += 22 if futures.get("data_quality") in {"COMPLETE", "NORMALISED_PERCENTAGES"} else 0
        score += min(15.0, int(rolling.get("journal_days", 0) or 0) * 2.5)
        score += 8 if abs(fii_5day) > 0 else 0
        score += 6 if abs(fii_10day) > 0 else 0
        score -= 8 if conflict_score >= 55 else 0
        return round(_clamp(score, 35.0, 88.0), 1)

    @staticmethod
    def _details(report: Any) -> Dict[str, Any]:
        if report is None:
            return {}
        if isinstance(report, Mapping):
            details = report.get("details")
            return dict(details) if isinstance(details, Mapping) else dict(report)
        details = getattr(report, "details", None)
        if isinstance(details, Mapping):
            return dict(details)
        compact = getattr(report, "to_compact_dict", None)
        if callable(compact):
            try:
                value = compact()
                return dict(value) if isinstance(value, Mapping) else {}
            except Exception:
                return {}
        return {}
