from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import short_horizon_outlook as forecast


def _master(raw: float = 42.0) -> dict:
    bullish = int(round(50 + raw / 2))
    return {
        "snapshot_id": "SNAP-PATH-001",
        "final_action": "WAIT",
        "execution_status": "WAIT",
        "confidence": 81.0,
        "decision_confidence": 81.0,
        "data_flow_status": "FRESH",
        "oi_sync_status": "OK",
        "data_confidence": 96,
        "direction_confidence": max(bullish, 100 - bullish),
        "projection": {"raw": raw, "bullish": bullish, "bearish": 100 - bullish},
        "department_integrity": {"score": 94, "critical_ok": True},
        "evidence_rows": [
            {"Signal": "Price Action", "Bias": raw},
            {"Signal": "Option Chain / OI", "Bias": raw * 0.6},
            {"Signal": "Heavyweights", "Bias": raw * 0.4},
        ],
        "strategy": {"type": "WAIT"},
        "strategy_scores": {"WAIT": 80, "SELL PE": 62, "SELL CE": 20},
        "ce_plan": {"strike": "24100 CE"},
        "pe_plan": {"strike": "24050 PE"},
        "candidate_rows": [],
        "strategy_rows": [],
        "warnings": [],
        "blockers": [],
    }


def _movement(**overrides) -> dict:
    row = {
        "movement_bias": 36,
        "phase": "RECOVERY",
        "recent_sample_count": 8,
        "sample_count": 12,
        "continuity_status": "LIVE_SEQUENCE",
        "move_1m": 4,
        "move_3m": 11,
        "move_5m": 18,
        "recovery_from_low": 44,
        "pullback_from_high": 8,
    }
    row.update(overrides)
    return row


def _run(tmp_path, monkeypatch, *, master=None, movement=None, support=24035, resistance=24120):
    monkeypatch.setattr(forecast, "_STORE", tmp_path / "forecast.json")
    monkeypatch.setattr(forecast, "_LOCK", tmp_path / "forecast.lock")
    master = master or _master()
    return forecast.build_market_path_forecast(
        ai_master=master,
        market_snapshot={"snapshot_id": master["snapshot_id"], "risk": {"news_risk": 10, "shock_risk": 15, "gamma_risk": 20}},
        movement=movement or _movement(),
        current_price=24080,
        atr_points=55,
        observed_at=datetime(2026, 7, 15, 10, 30, tzinfo=timezone.utc),
        market_open=True,
        state={},
        quote_age_seconds=1.0,
        option_age_seconds=1.2,
        support_level=support,
        resistance_level=resistance,
    )


def test_market_path_is_single_brain_read_only(tmp_path, monkeypatch):
    master = _master()
    before = deepcopy(master)
    result = _run(tmp_path, monkeypatch, master=master)
    assert master == before
    contract = result["authority_contract"]
    assert contract["same_snapshot"] is True
    assert contract["authority_intact"] is True
    assert contract["independent_data_fetches"] == 0
    assert contract["can_change_execution"] is False
    assert contract["feedback_to_ai_master"] is False
    assert master["final_action"] == "WAIT"


def test_bullish_path_has_upside_destination_and_barrier_awareness(tmp_path, monkeypatch):
    result = _run(tmp_path, monkeypatch, resistance=24105)
    h15 = result["horizon_15m"]
    assert h15["up_probability"] > h15["down_probability"]
    assert h15["likely_low"] > 24080
    assert h15["likely_high"] <= 24112  # nearby resistance caps normal destination
    assert "UP" in h15["path"]
    assert h15["reversal_risk"] >= 35


def test_bearish_path_has_downside_destination(tmp_path, monkeypatch):
    master = _master(raw=-48)
    movement = _movement(
        movement_bias=-42,
        phase="PULLBACK_DOWN",
        move_1m=-5,
        move_3m=-14,
        move_5m=-23,
        recovery_from_low=5,
        pullback_from_high=52,
    )
    result = _run(tmp_path, monkeypatch, master=master, movement=movement, support=24040, resistance=24130)
    h15 = result["horizon_15m"]
    assert h15["down_probability"] > h15["up_probability"]
    assert h15["likely_high"] < 24080
    assert "DOWN" in h15["path"]


def test_consumed_move_raises_exhaustion_and_reduces_remaining_budget(tmp_path, monkeypatch):
    low_consumed = _run(tmp_path, monkeypatch, movement=_movement(recovery_from_low=18, move_5m=8))
    # Use another store so the comparison is independent.
    monkeypatch.setattr(forecast, "_STORE", tmp_path / "forecast2.json")
    monkeypatch.setattr(forecast, "_LOCK", tmp_path / "forecast2.lock")
    high_consumed = forecast.build_market_path_forecast(
        ai_master=_master(),
        market_snapshot={"snapshot_id": "SNAP-PATH-001", "risk": {}},
        movement=_movement(recovery_from_low=130, move_5m=52, move_3m=38),
        current_price=24080,
        atr_points=55,
        observed_at=datetime(2026, 7, 15, 10, 30, tzinfo=timezone.utc),
        market_open=True,
        state={}, quote_age_seconds=1, option_age_seconds=1,
        support_level=24035, resistance_level=24120,
    )
    a = low_consumed["horizon_15m"]
    b = high_consumed["horizon_15m"]
    assert b["move_consumed"] > a["move_consumed"]
    assert b["remaining_budget_points"] < a["remaining_budget_points"]
    assert b["reversal_risk"] >= a["reversal_risk"]


def test_snapshot_mismatch_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(forecast, "_STORE", tmp_path / "forecast.json")
    monkeypatch.setattr(forecast, "_LOCK", tmp_path / "forecast.lock")
    result = forecast.build_market_path_forecast(
        ai_master=_master(),
        market_snapshot={"snapshot_id": "SNAP-DIFFERENT"},
        movement=_movement(), current_price=24080, atr_points=55,
        observed_at=datetime(2026, 7, 15, 10, 30, tzinfo=timezone.utc),
        market_open=True, state={}, quote_age_seconds=1, option_age_seconds=1,
    )
    assert result["status"] == "UNAVAILABLE"
    assert "snapshot ID mismatch" in result["freshness_reasons"]


def test_app_places_market_path_after_final_authority_and_uses_deepcopy():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    final_pos = app.index('st.markdown("### 🧠 AI FINAL AUTHORITY")')
    path_pos = app.index('st.markdown("### 🧭 MARKET PATH FORECAST')
    signal_pos = app.find('Signal Reliability', path_pos)
    assert final_pos < path_pos
    assert signal_pos == -1 or path_pos < signal_pos
    assert "ai_master=deepcopy(AI_MASTER" in app
    assert 'AI_MASTER["market_path_forecast"]' in app


def test_forecast_module_has_no_market_fetch_or_decision_imports():
    source = (Path(__file__).resolve().parents[1] / "short_horizon_outlook.py").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "import requests" not in lowered
    assert "import yfinance" not in lowered
    assert "from ai_master import" not in lowered
    assert "from strategy" not in lowered
    assert "from decision" not in lowered


def test_provisional_forecast_reliability_is_capped(tmp_path, monkeypatch):
    result = _run(tmp_path, monkeypatch)
    assert result["validation_15m"]["completed"] == 0
    assert result["horizon_15m"]["reliability"] <= 62
    assert result["horizon_30m"]["reliability"] <= 56
    assert "PROVISIONAL" in result["horizon_15m"]["status"] or result["horizon_15m"]["status"] in {"EARLY OUTLOOK", "BUILDING", "LOW RELIABILITY", "EXHAUSTION RISK"}


def test_pdf_accepts_market_path_table():
    from report_pdf import build_ai_report_pdf

    data = build_ai_report_pdf({
        "generated_at": "15-07-2026 16:00:00 IST",
        "summary": {"Version": "V50.8.6", "Snapshot": "SNAP-PATH-001"},
        "market_path_rows": [
            {"Field": "Current Nifty", "Next 15 Minutes": "24080", "Next 30 Minutes": "24080"},
            {"Field": "Likely Zone", "Next 15 Minutes": "24092–24106", "Next 30 Minutes": "24096–24116"},
        ],
        "market_path_summary": "15m UP path; 30m UP/RANGE path.",
        "market_path_authority_note": "One AI_MASTER, zero feedback.",
        "source_rows": [], "evidence_rows": [], "strategy_rows": [], "candidate_rows": [],
        "option_rows": [], "branch_integrity_rows": [], "department_rows": [],
        "reasons": [], "warnings": [],
    })
    assert data.startswith(b"%PDF")
    assert len(data) > 1500
