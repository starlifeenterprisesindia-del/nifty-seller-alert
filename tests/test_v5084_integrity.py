from datetime import datetime
from pathlib import Path

from candidate_department import CandidateDirector, OIWritingSpecialist
from command_hierarchy import BranchBoss
from department_integrity import audit_department_reports
from live_market_state import update_live_market_state
from market_journey import MarketJourneyReport
from oi_flow_engine import _classify
from option_flow_integrity import classify_option_flow, validate_flow_row
from report_pdf import build_ai_report_pdf
from snapshot_engine import build_market_snapshot


def test_canonical_option_flow_sign_matrix():
    cases = [
        ("CE", -10, +100000, "CE_WRITING", "Likely Fresh CE Writing"),
        ("PE", -10, +100000, "PE_WRITING", "Likely Fresh PE Writing"),
        ("PE", +10, +100000, "PE_LONG_BUILDUP", "Likely Fresh PE Buying"),
        ("PE", +10, -100000, "PE_SHORT_COVERING", "PE Short Covering"),
        ("CE", +10, -100000, "CE_SHORT_COVERING", "CE Short Covering"),
    ]
    for side, price_delta, oi_delta, code, label in cases:
        result = classify_option_flow(
            side,
            price_delta=price_delta,
            price_pct=5 if price_delta > 0 else -5,
            oi_delta=oi_delta,
            oi_pct=5 if oi_delta > 0 else -5,
            basis="SNAPSHOT",
        )
        assert result["flow_code"] == code
        assert result["signal"] == label


def test_first_oi_sample_uses_matching_day_changes_and_preopen_is_neutral():
    current = {
        "strike": 24100,
        "ce_oi": 500000,
        "pe_oi": 400000,
        "ce_chg": 100000,
        "pe_chg": 100000,
        "ce_ltp": 20,
        "pe_ltp": 50,
        "ce_price_chg": -60,
        "pe_price_chg": 5,
        "ce_price_pct": -75,
        "pe_price_pct": 11,
    }
    first = _classify({}, current, market_open=True)
    assert first["basis"] == "DAY_CHANGE"
    assert first["ce_flow"] == "CALL_WRITING"
    assert first["pe_flow"] == "PUT_LONG_BUILDUP"

    preopen = _classify({}, current, market_open=False)
    assert preopen["ce_flow"] == "CALL_NEUTRAL"
    assert preopen["pe_flow"] == "PUT_NEUTRAL"


def _valid_option_row(strike=24100):
    return {
        "strike": strike,
        "ce_flow_code": "CE_WRITING",
        "ce_signal": "Likely Fresh CE Writing",
        "ce_flow_basis": "SNAPSHOT",
        "ce_flow_price_delta": -2,
        "ce_flow_price_pct": -3,
        "ce_flow_oi_delta": 10000,
        "ce_flow_oi_pct": 2,
        "ce_flow_evidence_ready": True,
        "pe_flow_code": "PE_SHORT_COVERING",
        "pe_signal": "PE Short Covering",
        "pe_flow_basis": "SNAPSHOT",
        "pe_flow_price_delta": 3,
        "pe_flow_price_pct": 4,
        "pe_flow_oi_delta": -10000,
        "pe_flow_oi_pct": -2,
        "pe_flow_evidence_ready": True,
    }


def test_flow_row_validator():
    row = _valid_option_row()
    assert validate_flow_row(row, "CE")["ok"]
    assert validate_flow_row(row, "PE")["ok"]


def test_candidate_department_uses_canonical_flow_not_positive_oi_alone():
    specialist = OIWritingSpecialist()
    writing = specialist.score(
        100000,
        "CE",
        flow_code="CE_WRITING",
        flow_signal="Likely Fresh CE Writing",
        evidence_ready=True,
    )
    buying = specialist.score(
        100000,
        "CE",
        flow_code="CE_LONG_BUILDUP",
        flow_signal="Likely Fresh CE Buying",
        evidence_ready=True,
    )
    unconfirmed = specialist.score(100000, "CE", evidence_ready=False)
    assert writing["score"] > buying["score"]
    assert unconfirmed["status"] == "Flow Confirmation Pending"
    assert unconfirmed["score"] == 40.0

    report = CandidateDirector().build_report(
        [
            {
                "option_type": "CE", "strike": 24100, "premium": 20,
                "volume": 200000, "oi": 500000, "oi_change": 100000,
                "bid_ask_spread": 0.5, "flow_code": "CE_LONG_BUILDUP",
                "flow_signal": "Likely Fresh CE Buying", "flow_evidence_ready": True,
            },
            {
                "option_type": "CE", "strike": 24150, "premium": 10,
                "volume": 200000, "oi": 500000, "oi_change": 100000,
                "bid_ask_spread": 0.5, "flow_code": "CE_WRITING",
                "flow_signal": "Likely Fresh CE Writing", "flow_evidence_ready": True,
            },
            {
                "option_type": "PE", "strike": 24000, "premium": 20,
                "volume": 200000, "oi": 500000, "oi_change": 100000,
                "bid_ask_spread": 0.5, "flow_code": "PE_WRITING",
                "flow_signal": "Likely Fresh PE Writing", "flow_evidence_ready": True,
            },
        ],
        24050,
        50,
        24000,
        24100,
    )
    assert report.best_ce is not None
    assert any("Writing" in reason for reason in report.best_ce.reasons)


def test_preopen_movement_is_not_carried_into_live_sequence():
    state = {}
    preopen = update_live_market_state(
        state, price=24000, observed_at=datetime(2026, 7, 14, 9, 12), market_open=False
    )
    assert preopen["phase"] == "PREOPEN_REFERENCE"
    assert preopen["sample_count"] == 0

    update_live_market_state(
        state, price=24010, observed_at=datetime(2026, 7, 14, 9, 15, 5), market_open=True
    )
    live = update_live_market_state(
        state, price=24020, observed_at=datetime(2026, 7, 14, 9, 15, 20), market_open=True
    )
    assert live["sample_count"] == 2
    assert live["continuity_status"] == "LIVE_SEQUENCE"


def test_snapshot_exposes_distinct_recent_and_persisted_counts():
    context = {
        "status": "Market Open", "day_name": "Tuesday", "price": 24020,
        "change_pct": -0.2, "vix": 13,
        "option_chain": {"success": True, "rows": [], "snapshot_id": "OC1"},
        "option_analysis": {"success": True, "rows": [], "snapshot_id": "OC1", "bias": 0},
        "movement": {
            "ready": True, "phase": "RECOVERY", "sample_count": 18,
            "recent_sample_count": 5, "continuity_status": "GAP_RESET",
        },
        "source_registry": {},
    }
    snapshot = build_market_snapshot(context, lambda: "12:50:15")
    assert snapshot["movement"]["sample_count"] == 18
    assert snapshot["movement"]["recent_sample_count"] == 5
    assert snapshot["movement"]["continuity_status"] == "GAP_RESET"


def _audit_fixture():
    branches = [
        "DATA", "OPTION", "PRICE_ACTION", "MARKET_BEHAVIOUR",
        "MARKET_PSYCHOLOGY", "TIME_INTELLIGENCE", "MARKET_JOURNEY",
        "HEAVYWEIGHT_INTELLIGENCE", "NEWS_INTELLIGENCE", "SMART_MONEY",
        "EXPERIENCE", "SELF_REVIEW", "PROMOTION_BOARD", "LEARNING",
        "RISK", "CANDIDATE", "STRATEGY",
    ]
    reports = {
        branch: {"summary": f"{branch} healthy", "confidence": 75, "details": {}}
        for branch in branches
    }
    reports["DATA"]["details"] = {"snapshot_id": "SNAP-X", "quality_score": 90}
    reports["TIME_INTELLIGENCE"]["details"] = {"phase": "Lunch"}
    reports["NEWS_INTELLIGENCE"]["details"] = {"impact_level": "LOW"}
    option_rows = [_valid_option_row(strike) for strike in range(23900, 24200, 50)]
    context = {
        "snapshot_id": "SNAP-X", "market_open": True,
        "option_analysis": {"success": True, "rows": option_rows, "snapshot_ready": True},
        "oi_sync_ok": True, "price_action_usable": True,
        "price_action_reference_ready": True, "price_action_age_seconds": 30,
        "pivot_integrity": "OK", "price": 24050, "support": 24000,
        "resistance": 24100, "heavyweight_count": 8,
        "expected_heavyweight_count": 8, "institutional_state": "COMPLETE",
        "candidate_count": 10, "source_registry": {},
    }
    return reports, context


def test_all_dsp_reports_receive_integrity_certificate_and_critical_failures_hold():
    reports, context = _audit_fixture()
    audit = audit_department_reports(reports, context=context)
    assert len(audit["rows"]) == 17
    assert audit["critical_ok"]

    bad_context = dict(context)
    bad_context["oi_sync_ok"] = False
    bad = audit_department_reports(reports, context=bad_context)
    assert not bad["critical_ok"]
    assert "OPTION" in bad["critical_failures"]
    assert bad["reports"]["OPTION"]["details"]["availability"]["status"] == "INTEGRITY_HOLD"

    branch_result = BranchBoss("OPTION", "DSP Option", 40).review(bad["reports"]["OPTION"])
    assert branch_result.status == "CAUTION"
    assert branch_result.confidence == 0
    assert branch_result.branch_vote == "NEUTRAL"
    assert branch_result.recommendation == "INFORMATION_ONLY"


def test_market_journey_range_summary_is_complete():
    report = MarketJourneyReport(
        version="x", status="READY", direction="RANGE", move_stage="Range",
        market_energy="Low", expected_zone_low=0, expected_zone_high=0,
        remaining_points_low=0, remaining_points_high=0, upside_remaining_points=6,
        downside_remaining_points=7, primary_direction="RANGE", primary_signed_points=0,
        before_reversal_points=0, estimate_confidence=60, breakout_probability=50,
        reversal_probability=50, reversal_risk="MODERATE", barrier_type="NONE",
        barrier_level=None, barrier_distance_points=None, barrier_adjustment_points=0,
        barrier_touch_count=0, barrier_strength="BALANCED", barrier_statistics={},
        tracked_barriers=[], time_phase="Lunch", time_phase_code="LUNCH",
        time_observed_behaviour="RANGE", time_continuation_factor=1,
        time_reversal_adjustment=0, time_confidence_cap=60,
        psychology_case_state="BALANCED", authority="EVIDENCE_ONLY_TO_CO",
        execution_instruction="NONE", reasons=[], warnings=[],
    )
    summary = report.to_department_report()["summary"]
    assert "range pts" not in summary.lower()
    assert "two-sided +6/-7 pts" in summary


def test_pdf_contains_integrity_section_and_is_valid_pdf():
    reports, context = _audit_fixture()
    audit = audit_department_reports(reports, context=context)
    pdf = build_ai_report_pdf({
        "generated_at": "14-07-2026 12:50:15 IST",
        "summary": {"Version": "V50.8.4", "Snapshot": "SNAP-X"},
        "source_rows": [{"Feed": "Nifty", "Ready": "YES"}],
        "evidence_rows": [], "strategy_rows": [], "candidate_rows": [],
        "option_rows": [{
            "Strike": 24100, "CE Basis": "SNAPSHOT", "CE dPx": -2,
            "CE dOI": 10000, "CE Flow": "Likely Fresh CE Writing",
        }],
        "branch_integrity_rows": audit["rows"],
        "department_rows": [{
            "Department": "Option", "Confidence": 75,
            "Integrity": "PASS", "Summary": "healthy",
        }],
        "reasons": ["WAIT"], "warnings": [],
    })
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 3000


def test_static_single_authority_and_v5084_wiring():
    app = Path(__file__).parents[1].joinpath("app.py").read_text()
    assert "V50.8.4_DSP_EVIDENCE_INTEGRITY" in app
    assert "audit_department_reports(" in app
    assert "evidence_allowed=bool(market_open)" in app
    assert "previous_was_market_open" in app
    assert "_payload_snapshot_id_v24" in app
    assert '"flow_code": _r.get(f"{_prefix}_flow_code"' in app
