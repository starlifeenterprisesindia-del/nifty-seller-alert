from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import institutional_journal as journal
import short_horizon_outlook as outlook


def _configure_journal_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "PRIMARY_CSV", tmp_path / "data" / "fii.csv")
    monkeypatch.setattr(journal, "RUNTIME_CSV", tmp_path / "runtime" / "fii.csv")
    monkeypatch.setattr(journal, "RUNTIME_JSON", tmp_path / "runtime" / "fii.json")
    monkeypatch.setattr(journal, "LOCK_PATH", tmp_path / "runtime" / "fii.lock")


def test_institutional_journal_short_session_cannot_delete_history(tmp_path, monkeypatch):
    _configure_journal_paths(tmp_path, monkeypatch)
    state = {}
    full = pd.DataFrame([
        journal.prepare_upsert_row({"Date": f"2026-07-{day:02d}", "FII Cash Cr": day * 10, "DII Cash Cr": -day * 5})
        for day in range(1, 21)
    ])
    assert journal.save_institutional_journal(full, state, max_rows=60)

    shorter = full.tail(2).copy()
    assert journal.save_institutional_journal(shorter, {}, max_rows=60)
    loaded = journal.load_institutional_journal({}, max_rows=60)
    assert len(loaded) == 20
    assert str(loaded.iloc[0]["Date"]) == "2026-07-01"
    assert str(loaded.iloc[-1]["Date"]) == "2026-07-20"


def test_journal_missing_values_do_not_erase_existing_fields(tmp_path, monkeypatch):
    _configure_journal_paths(tmp_path, monkeypatch)
    old = pd.DataFrame([journal.prepare_upsert_row({
        "Date": "2026-07-14", "FII Cash Cr": -1200, "DII Cash Cr": 900,
        "FII Long %": 38.5, "Notes": "confirmed",
        "Saved At": "2026-07-14T12:00:00+00:00",
    })])
    assert journal.save_institutional_journal(old, {}, max_rows=60)
    partial = pd.DataFrame([journal.prepare_upsert_row({
        "Date": "2026-07-14", "FII Cash Cr": -1250, "DII Cash Cr": 950,
        "Saved At": "2026-07-14T13:00:00+00:00",
    })])
    assert journal.save_institutional_journal(partial, {}, max_rows=60)
    row = journal.load_institutional_journal({}, max_rows=60).iloc[-1]
    assert float(row["FII Cash Cr"]) == -1250
    assert float(row["FII Long %"]) == 38.5
    assert row["Notes"] == "confirmed"


def _master():
    return {
        "snapshot_id": "SNAP-TEST-001",
        "final_action": "WAIT",
        "execution_status": "WAIT",
        "data_flow_status": "FRESH",
        "oi_sync_status": "OK",
        "data_confidence": 94,
        "direction_confidence": 64,
        "projection": {"raw": -28, "bullish": 36, "bearish": 64},
        "department_integrity": {"score": 92, "critical_ok": True},
        "evidence_rows": [
            {"Signal": "Price Action", "Bias": -60},
            {"Signal": "Option Chain / OI", "Bias": 25},
            {"Signal": "Heavyweights", "Bias": -30},
        ],
        "warnings": ["CO conflict: price action vs option flow"],
    }


def test_outlook_is_read_only_and_probabilities_sum_to_100(tmp_path, monkeypatch):
    monkeypatch.setattr(outlook, "_STORE", tmp_path / "outlook.json")
    monkeypatch.setattr(outlook, "_LOCK", tmp_path / "outlook.lock")
    master = _master()
    original_action = master["final_action"]
    state = {}
    result = outlook.build_short_horizon_outlook(
        ai_master=master,
        market_snapshot={},
        movement={"movement_bias": -20, "phase": "PULLBACK_DOWN", "recent_sample_count": 8, "continuity_status": "LIVE_SEQUENCE"},
        current_price=24080,
        atr_points=70,
        observed_at=datetime(2026, 7, 14, 10, 30, tzinfo=timezone.utc),
        market_open=True,
        state=state,
        quote_age_seconds=2,
        option_age_seconds=1,
    )
    assert result["status"] == "AVAILABLE"
    assert master["final_action"] == original_action == "WAIT"
    assert len(result["rows"]) == 2
    for row in result["rows"]:
        assert row["UP %"] + row["DOWN %"] + row["RANGE %"] == 100
        assert "BUY" not in str(row).upper()
        assert "SELL" not in str(row).upper()
    assert result["authority_note"].startswith("Information only")


def test_outlook_fails_closed_on_continuity_gap(tmp_path, monkeypatch):
    monkeypatch.setattr(outlook, "_STORE", tmp_path / "outlook.json")
    monkeypatch.setattr(outlook, "_LOCK", tmp_path / "outlook.lock")
    result = outlook.build_short_horizon_outlook(
        ai_master=_master(), market_snapshot={},
        movement={"movement_bias": 10, "phase": "RECOVERY", "recent_sample_count": 1, "continuity_status": "GAP_RESET"},
        current_price=24080, atr_points=70,
        observed_at=datetime(2026, 7, 14, 10, 30, tzinfo=timezone.utc),
        market_open=True, state={}, quote_age_seconds=2, option_age_seconds=1,
    )
    assert result["status"] == "UNAVAILABLE"
    assert all(row["Most Likely"] == "UNAVAILABLE" for row in result["rows"])
