from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import short_horizon_outlook as forecast

IST = ZoneInfo("Asia/Kolkata")


def _master() -> dict:
    return {
        "snapshot_id": "SNAP-V5087-001",
        "final_action": "WAIT",
        "execution_status": "WAIT",
        "confidence": 87.3,
        "decision_confidence": 87.3,
        "data_flow_status": "FRESH",
        "oi_sync_status": "OK",
        "data_confidence": 97,
        "direction_confidence": 69,
        "projection": {"raw": 38, "bullish": 69, "bearish": 31},
        "department_integrity": {"score": 95.9, "critical_ok": True},
        "evidence_rows": [
            {"Signal": "Price Action", "Bias": 80},
            {"Signal": "Option Chain / OI", "Bias": 68.1},
            {"Signal": "Live Movement", "Bias": 20.8},
        ],
        "strategy": {"type": "WAIT"},
        "strategy_scores": {"WAIT": 88, "SELL PE": 69, "SELL CE": 6},
        "ce_plan": {"strike": "24400 CE"},
        "pe_plan": {"strike": "23850 PE"},
        "candidate_rows": [],
        "strategy_rows": [],
        "warnings": ["DSP integrity: CAUTION (95.9%)"],
        "blockers": [],
    }


def _movement(**overrides) -> dict:
    row = {
        "movement_bias": 20.8,
        "phase": "RECOVERY",
        "recent_sample_count": 4,
        "sample_count": 40,
        "continuity_status": "GAP_RESET",
        "move_1m": 0,
        "move_3m": 0,
        "move_5m": 0,
        "recovery_from_low": 52.95,
        "pullback_from_high": 10,
    }
    row.update(overrides)
    return row


def _pa_context(count: int = 31, age: float = 120.0) -> dict:
    return {
        "success": True,
        "current_session_available": True,
        "current_session_candle_count": count,
        "candle_age_seconds": age,
        "source": "Dhan 5m candles",
    }


def _build(tmp_path, monkeypatch, **overrides):
    monkeypatch.setattr(forecast, "_STORE", tmp_path / "forecast.json")
    monkeypatch.setattr(forecast, "_LOCK", tmp_path / "forecast.lock")
    master = overrides.pop("ai_master", _master())
    movement = overrides.pop("movement", _movement())
    kwargs = {
        "ai_master": master,
        "market_snapshot": {"snapshot_id": master["snapshot_id"], "risk": {}},
        "movement": movement,
        "current_price": 24150,
        "atr_points": 30,
        "observed_at": datetime(2026, 7, 16, 11, 57, tzinfo=IST),
        "market_open": True,
        "state": {},
        "quote_age_seconds": 2.4,
        "option_age_seconds": 1.6,
        "option_evidence_status": "DAY_CHANGE_ONLY",
        "price_action_context": _pa_context(),
        "support_level": 24141.15,
        "resistance_level": 24167.40,
    }
    kwargs.update(overrides)
    return forecast.build_market_path_forecast(**kwargs)


def test_gap_reset_and_day_change_create_limited_forecast_not_blank(tmp_path, monkeypatch):
    master = _master()
    before = deepcopy(master)
    result = _build(tmp_path, monkeypatch, ai_master=master)

    assert master == before
    assert result["status"] == "LIMITED"
    assert result["availability_mode"] == "LIMITED"
    assert result["rows"]
    assert result["horizon_15m"]["reliability"] <= 54
    assert result["horizon_30m"]["reliability"] <= 48
    assert "LIMITED" in result["horizon_15m"]["status"]
    assert any("continuity reset" in x for x in result["degradation_reasons"])
    assert any("day-change-only" in x for x in result["degradation_reasons"])
    assert result["authority_contract"]["feedback_to_ai_master"] is False
    assert result["authority_contract"]["can_change_execution"] is False


def test_limited_forecast_is_barrier_aware(tmp_path, monkeypatch):
    result = _build(tmp_path, monkeypatch)
    h15 = result["horizon_15m"]
    assert h15["up_probability"] > h15["down_probability"]
    assert h15["likely_high"] < 24167.40
    assert "STALL" in h15["path"] or "REVERSAL" in h15["path"]


def test_opening_shock_with_one_candle_remains_unavailable(tmp_path, monkeypatch):
    result = _build(
        tmp_path,
        monkeypatch,
        observed_at=datetime(2026, 7, 16, 9, 18, tzinfo=IST),
        movement=_movement(recent_sample_count=1, sample_count=1, continuity_status="FIRST_SAMPLE"),
        price_action_context=_pa_context(count=1, age=90),
    )
    assert result["status"] == "UNAVAILABLE"
    assert any("opening shock" in x for x in result["hard_block_reasons"])


def test_stale_option_chain_is_hard_unavailable(tmp_path, monkeypatch):
    result = _build(tmp_path, monkeypatch, option_age_seconds=30.0)
    assert result["status"] == "UNAVAILABLE"
    assert "option chain stale" in result["hard_block_reasons"]


def test_full_live_sequence_keeps_full_mode(tmp_path, monkeypatch):
    result = _build(
        tmp_path,
        monkeypatch,
        movement=_movement(
            recent_sample_count=8,
            continuity_status="LIVE_SEQUENCE",
            move_1m=3,
            move_3m=9,
            move_5m=15,
        ),
        option_evidence_status="SNAPSHOT_READY",
    )
    assert result["status"] == "AVAILABLE"
    assert result["availability_mode"] == "FULL"
    assert result["degradation_reasons"] == []


def test_app_passes_fallback_inputs_and_displays_exact_mode():
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "option_evidence_status=_forecast_oi_status_v5087" in source
    assert "price_action_context=deepcopy(_forecast_pa_context_v5087)" in source
    assert "LIMITED forecast" in source
    assert "Exact diagnostic is shown in the table" in source
    assert "V50.8.7 Live Market + DSP Integrity Gate" in source
