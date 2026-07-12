"""
news_intelligence.py
Version: V41.3
Department: DSP News Intelligence

Purpose
-------
Investigate impact risk from the app's existing calendar/news-risk layer and
live market reaction. This module does not display headlines, fetch data,
start loops, issue BUY/SELL, or change AI_MASTER weights.

Flow
----
Existing source scores + live reaction -> DSP News Intelligence -> CO -> AI_MASTER.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, MutableMapping, Optional


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


@dataclass(frozen=True)
class NewsIntelligenceReport:
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


class NewsIntelligenceDirector:
    """One-shot impact investigation using already available app evidence."""

    VERSION = "V41.3_NEWS_INTELLIGENCE"
    STATE_KEY = "v41_news_intelligence_history"
    MAX_HISTORY = 6

    def evaluate(
        self,
        *,
        state: MutableMapping[str, Any],
        news_risk: Mapping[str, Any] | None,
        calendar_result: Mapping[str, Any] | None,
        headline_result: Mapping[str, Any] | None,
        manual_label: str,
        observed_at: str,
        nifty_change_pct: float = 0.0,
        vix_change_pct: float = 0.0,
        heavyweight_report: Any = None,
        time_report: Any = None,
    ) -> NewsIntelligenceReport:
        risk = news_risk if isinstance(news_risk, Mapping) else {}
        calendar = calendar_result if isinstance(calendar_result, Mapping) else {}
        headlines = headline_result if isinstance(headline_result, Mapping) else {}

        impact_score = int(round(_clamp(_number(risk.get("score")))))
        scheduled_score = int(round(_clamp(_number(risk.get("scheduled")))))
        breaking_score = int(round(_clamp(_number(risk.get("breaking")))))
        reaction_score = int(round(_clamp(_number(risk.get("reaction")))))
        shock_score = int(round(_clamp(_number(risk.get("shock")))))
        source_score = max(scheduled_score, breaking_score)
        market_score = int(round(_clamp(max(reaction_score, shock_score))))

        calendar_auto = bool(risk.get("auto_calendar") or calendar.get("success"))
        news_auto = bool(risk.get("auto_news") or headlines.get("success"))
        source_mode = self._source_mode(calendar_auto, news_auto)
        data_coverage = self._coverage(calendar_auto, news_auto)
        nearest_minutes = self._optional_number(calendar.get("nearest_minutes"))
        event_window = self._event_window(nearest_minutes, scheduled_score)
        impact_level = self._impact_level(impact_score)
        market_confirmation = self._market_confirmation(source_score, market_score)
        risk_state = self._risk_state(
            impact_level=impact_level,
            event_window=event_window,
            market_confirmation=market_confirmation,
            source_score=source_score,
            market_score=market_score,
        )

        heavy = self._details(heavyweight_report)
        time_details = self._details(time_report)
        heavyweight_state = str(heavy.get("investigation_state", "UNKNOWN"))
        heavyweight_shocks = int(_number(heavy.get("shock_count"), 0))
        time_phase = str(time_details.get("phase_code", "UNKNOWN"))

        uncertainty_score = self._uncertainty(
            source_mode=source_mode,
            market_confirmation=market_confirmation,
            impact_level=impact_level,
            event_window=event_window,
        )
        persistence_state = self._persistence(state, impact_score, market_score, observed_at)
        evidence = self._evidence(
            impact_level=impact_level,
            source_score=source_score,
            scheduled_score=scheduled_score,
            breaking_score=breaking_score,
            market_score=market_score,
            event_window=event_window,
            market_confirmation=market_confirmation,
            nifty_change_pct=_number(nifty_change_pct),
            vix_change_pct=_number(vix_change_pct),
            heavyweight_shocks=heavyweight_shocks,
        )
        next_confirmation = self._next_confirmation(
            risk_state=risk_state,
            event_window=event_window,
            source_mode=source_mode,
            market_confirmation=market_confirmation,
        )
        warnings = self._warnings(
            source_mode=source_mode,
            risk_state=risk_state,
            market_confirmation=market_confirmation,
            uncertainty_score=uncertainty_score,
        )
        confidence = self._confidence(
            source_mode=source_mode,
            market_confirmation=market_confirmation,
            uncertainty_score=uncertainty_score,
            impact_level=impact_level,
        )

        summary = self._summary(
            impact_level=impact_level,
            impact_score=impact_score,
            risk_state=risk_state,
            event_window=event_window,
            market_confirmation=market_confirmation,
        )
        details: Dict[str, Any] = {
            "version": self.VERSION,
            "impact_level": impact_level,
            "impact_score": impact_score,
            "risk_state": risk_state,
            "event_window": event_window,
            "nearest_event_minutes": nearest_minutes,
            "market_confirmation": market_confirmation,
            "scheduled_score": scheduled_score,
            "breaking_score": breaking_score,
            "reaction_score": reaction_score,
            "shock_score": shock_score,
            "source_score": source_score,
            "market_score": market_score,
            "source_mode": source_mode,
            "data_coverage": data_coverage,
            "uncertainty_score": uncertainty_score,
            "persistence_state": persistence_state,
            "calendar_event_count": int(_number(calendar.get("events"), 0)),
            "recent_items_scanned": int(_number(headlines.get("items"), 0)),
            "manual_fallback_label": str(manual_label or "Low"),
            "nifty_change_pct": round(_number(nifty_change_pct), 3),
            "vix_change_pct": round(_number(vix_change_pct), 3),
            "heavyweight_state": heavyweight_state,
            "heavyweight_shock_count": heavyweight_shocks,
            "time_phase": time_phase,
            "evidence": evidence,
            "next_confirmation_required": next_confirmation,
            "headlines_exposed": False,
            "news_reading_mode": "IMPACT_ONLY",
            "execution_instruction": "NONE",
            "authority": "EVIDENCE_ONLY_TO_CO",
        }
        return NewsIntelligenceReport(
            summary=summary,
            confidence=round(confidence, 1),
            details=details,
            warnings=warnings,
        )

    @staticmethod
    def _source_mode(calendar_auto: bool, news_auto: bool) -> str:
        if calendar_auto and news_auto:
            return "CALENDAR_AND_NEWS_AUTO"
        if calendar_auto:
            return "CALENDAR_AUTO_NEWS_FALLBACK"
        if news_auto:
            return "NEWS_AUTO_CALENDAR_FALLBACK"
        return "MANUAL_FALLBACK_PLUS_MARKET_REACTION"

    @staticmethod
    def _coverage(calendar_auto: bool, news_auto: bool) -> str:
        if calendar_auto and news_auto:
            return "FULL_AVAILABLE_COVERAGE"
        if calendar_auto or news_auto:
            return "PARTIAL_AUTO_COVERAGE"
        return "LIMITED_MANUAL_COVERAGE"

    @staticmethod
    def _optional_number(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return round(float(value), 1)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _event_window(nearest_minutes: Optional[float], scheduled_score: float) -> str:
        if nearest_minutes is None:
            return "NO_SCHEDULED_WINDOW" if scheduled_score < 60 else "SCHEDULED_RISK_TIME_UNKNOWN"
        if nearest_minutes < -30:
            return "POST_EVENT_REACTION"
        if -30 <= nearest_minutes <= 15:
            return "EVENT_ACTIVE"
        if nearest_minutes <= 45:
            return "PRE_EVENT_45M"
        if nearest_minutes <= 120:
            return "PRE_EVENT_2H"
        if nearest_minutes <= 240:
            return "PRE_EVENT_4H"
        return "FUTURE_EVENT"

    @staticmethod
    def _impact_level(score: float) -> str:
        if score >= 60:
            return "HIGH"
        if score >= 30:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _market_confirmation(source_score: float, market_score: float) -> str:
        if source_score >= 60 and market_score >= 55:
            return "SOURCE_AND_MARKET_CONFIRMED"
        if source_score >= 60 and market_score < 35:
            return "EVENT_RISK_NOT_YET_MARKET_CONFIRMED"
        if source_score < 30 and market_score >= 60:
            return "UNSCHEDULED_MARKET_SHOCK"
        if source_score >= 30 and market_score >= 35:
            return "PARTIAL_MARKET_CONFIRMATION"
        if market_score >= 45:
            return "MARKET_REACTION_WATCH"
        return "NO_MATERIAL_MARKET_CONFIRMATION"

    @staticmethod
    def _risk_state(*, impact_level: str, event_window: str, market_confirmation: str, source_score: float, market_score: float) -> str:
        if market_confirmation == "UNSCHEDULED_MARKET_SHOCK":
            return "UNSCHEDULED_HIGH_IMPACT_SHOCK_WATCH"
        if impact_level == "HIGH" and event_window in {"EVENT_ACTIVE", "PRE_EVENT_45M", "POST_EVENT_REACTION"}:
            return "HIGH_IMPACT_EVENT_WINDOW"
        if impact_level == "HIGH" and market_confirmation == "SOURCE_AND_MARKET_CONFIRMED":
            return "HIGH_IMPACT_CONFIRMED"
        if impact_level == "HIGH":
            return "HIGH_IMPACT_WATCH"
        if impact_level == "MEDIUM" and market_score >= 45:
            return "MEDIUM_IMPACT_WITH_REACTION"
        if impact_level == "MEDIUM" or source_score >= 30:
            return "MEDIUM_IMPACT_WATCH"
        return "LOW_IMPACT_MONITOR"

    def _persistence(self, state: MutableMapping[str, Any], impact_score: int, market_score: int, observed_at: str) -> str:
        history = state.get(self.STATE_KEY)
        if not isinstance(history, list):
            history = []
        previous = history[-1] if history else None
        if not isinstance(previous, Mapping):
            persistence = "FIRST_OBSERVATION"
        else:
            prior_score = _number(previous.get("impact_score"))
            prior_market = _number(previous.get("market_score"))
            delta = impact_score - prior_score
            if impact_score >= 60 and prior_score >= 60:
                persistence = "PERSISTENT_HIGH_RISK"
            elif delta >= 15 or market_score - prior_market >= 20:
                persistence = "RISING_RISK"
            elif delta <= -15 and market_score <= prior_market:
                persistence = "FADING_RISK"
            elif abs(delta) < 10 and abs(market_score - prior_market) < 15:
                persistence = "STABLE_RISK"
            else:
                persistence = "CHANGING_RISK"
        history.append({
            "observed_at": str(observed_at)[:32],
            "impact_score": int(impact_score),
            "market_score": int(market_score),
        })
        state[self.STATE_KEY] = history[-self.MAX_HISTORY:]
        return persistence

    @staticmethod
    def _uncertainty(*, source_mode: str, market_confirmation: str, impact_level: str, event_window: str) -> int:
        score = 15.0
        if source_mode == "MANUAL_FALLBACK_PLUS_MARKET_REACTION":
            score += 32
        elif "FALLBACK" in source_mode:
            score += 18
        if market_confirmation in {"EVENT_RISK_NOT_YET_MARKET_CONFIRMED", "UNSCHEDULED_MARKET_SHOCK"}:
            score += 20
        elif market_confirmation == "PARTIAL_MARKET_CONFIRMATION":
            score += 10
        elif market_confirmation == "SOURCE_AND_MARKET_CONFIRMED":
            score -= 8
        if impact_level == "HIGH" and event_window in {"NO_SCHEDULED_WINDOW", "SCHEDULED_RISK_TIME_UNKNOWN"}:
            score += 10
        return int(round(_clamp(score)))

    @staticmethod
    def _evidence(
        *,
        impact_level: str,
        source_score: int,
        scheduled_score: int,
        breaking_score: int,
        market_score: int,
        event_window: str,
        market_confirmation: str,
        nifty_change_pct: float,
        vix_change_pct: float,
        heavyweight_shocks: int,
    ) -> List[str]:
        evidence = [
            f"Combined impact score {impact_level} ({max(source_score, market_score)}/100 evidence peak).",
            f"Scheduled {scheduled_score}/100, breaking-risk {breaking_score}/100, market reaction {market_score}/100.",
            f"Event window {event_window}; confirmation state {market_confirmation}.",
        ]
        if abs(nifty_change_pct) >= 0.35:
            evidence.append(f"NIFTY reaction is material at {nifty_change_pct:+.2f}%.")
        if vix_change_pct >= 2.0:
            evidence.append(f"India VIX expansion is material at {vix_change_pct:+.2f}%.")
        if heavyweight_shocks:
            evidence.append(f"{heavyweight_shocks} heavyweight shock(s) detected in the same snapshot.")
        return evidence[:6]

    @staticmethod
    def _next_confirmation(*, risk_state: str, event_window: str, source_mode: str, market_confirmation: str) -> List[str]:
        checks: List[str] = []
        if market_confirmation == "EVENT_RISK_NOT_YET_MARKET_CONFIRMED":
            checks.append("Check next snapshot for VIX, NIFTY range and heavyweight reaction confirmation.")
        if market_confirmation == "UNSCHEDULED_MARKET_SHOCK":
            checks.append("Verify data freshness and require shock persistence before attributing it to an event.")
        if event_window in {"EVENT_ACTIVE", "PRE_EVENT_45M", "POST_EVENT_REACTION"}:
            checks.append("Reassess after the event window; pre-event and post-event behaviour can differ.")
        if source_mode != "CALENDAR_AND_NEWS_AUTO":
            checks.append("Coverage is incomplete; manual impact label and live market reaction remain important.")
        if not checks:
            checks.append("Continue normal bounded monitoring; no material impact escalation detected.")
        return checks[:3]

    @staticmethod
    def _warnings(*, source_mode: str, risk_state: str, market_confirmation: str, uncertainty_score: int) -> List[str]:
        warnings: List[str] = []
        if source_mode == "MANUAL_FALLBACK_PLUS_MARKET_REACTION":
            warnings.append("Automatic event/news sources unavailable; classification uses manual fallback plus market reaction.")
        elif "FALLBACK" in source_mode:
            warnings.append("Only one automatic source is active; coverage is partial.")
        if risk_state in {"HIGH_IMPACT_EVENT_WINDOW", "HIGH_IMPACT_CONFIRMED", "UNSCHEDULED_HIGH_IMPACT_SHOCK_WATCH"}:
            warnings.append("High-impact conditions require fresh-snapshot verification by CO and Risk Department.")
        if market_confirmation in {"EVENT_RISK_NOT_YET_MARKET_CONFIRMED", "UNSCHEDULED_MARKET_SHOCK"}:
            warnings.append("Source evidence and market reaction are not fully aligned.")
        if uncertainty_score >= 60:
            warnings.append("Impact uncertainty is high; do not treat the label as a confirmed causal explanation.")
        return warnings[:4]

    @staticmethod
    def _confidence(*, source_mode: str, market_confirmation: str, uncertainty_score: int, impact_level: str) -> float:
        coverage = {
            "CALENDAR_AND_NEWS_AUTO": 82.0,
            "CALENDAR_AUTO_NEWS_FALLBACK": 68.0,
            "NEWS_AUTO_CALENDAR_FALLBACK": 64.0,
            "MANUAL_FALLBACK_PLUS_MARKET_REACTION": 50.0,
        }.get(source_mode, 50.0)
        if market_confirmation == "SOURCE_AND_MARKET_CONFIRMED":
            coverage += 10
        elif market_confirmation == "PARTIAL_MARKET_CONFIRMATION":
            coverage += 4
        elif market_confirmation in {"EVENT_RISK_NOT_YET_MARKET_CONFIRMED", "UNSCHEDULED_MARKET_SHOCK"}:
            coverage -= 6
        if impact_level == "LOW" and source_mode == "MANUAL_FALLBACK_PLUS_MARKET_REACTION":
            coverage -= 4
        coverage -= max(0, uncertainty_score - 50) * 0.20
        return _clamp(coverage, 30.0, 95.0)

    @staticmethod
    def _summary(*, impact_level: str, impact_score: int, risk_state: str, event_window: str, market_confirmation: str) -> str:
        return (
            f"News-impact investigation: {impact_level} {impact_score}/100 | "
            f"{risk_state} | {event_window} | {market_confirmation}."
        )[:300]

    @staticmethod
    def _details(report: Any) -> Mapping[str, Any]:
        if report is None:
            return {}
        if isinstance(report, Mapping):
            details = report.get("details")
            return details if isinstance(details, Mapping) else report
        details = getattr(report, "details", None)
        return details if isinstance(details, Mapping) else {}
