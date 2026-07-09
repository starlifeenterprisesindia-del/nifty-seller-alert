"""Single AI Advisor Authority for Nifty Seller AI.

This module does NOT fetch data and does NOT calculate a separate trade signal.
It only converts the already-stabilized Decision Engine output into one common
advisor object for all UI sections.

Rule: Snapshot -> AI/Decision/Stability -> advisor_engine -> UI.
No UI table should create its own advice/verdict.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean_list(values: Any, limit: int = 3) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    for item in values:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def build_advisor_report(
    *,
    snapshot: Dict[str, Any] | None = None,
    final_decision: Dict[str, Any] | None = None,
    decision_report: Dict[str, Any] | None = None,
    strategy_report: Dict[str, Any] | None = None,
    intelligence_report: Dict[str, Any] | None = None,
    risk_report: Dict[str, Any] | None = None,
    stability_report: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build one final advisor object for every visible UI section.

    Decision/Stability Engine remains the only execution authority. Strategy,
    intelligence, risk and OI flow are evidence providers only.
    """

    snap = _safe_dict(snapshot)
    fd = _safe_dict(final_decision)
    de = _safe_dict(decision_report) or _safe_dict(fd.get("decision_engine"))
    sr = _safe_dict(strategy_report) or _safe_dict(fd.get("strategy_engine_report"))
    ir = _safe_dict(intelligence_report) or _safe_dict(fd.get("intelligence_report"))
    rr = _safe_dict(risk_report) or _safe_dict(fd.get("risk_report"))
    st = _safe_dict(stability_report) or _safe_dict(fd.get("stability_report"))

    final_action = str(de.get("final_action", fd.get("action", "WAIT")) or "WAIT").upper()
    execution_status = str(de.get("execution_status", fd.get("execution_status", "WAIT")) or "WAIT").upper()
    confidence = int(float(de.get("calibrated_confidence", fd.get("confidence", 0)) or 0))

    strategy = _safe_dict(fd.get("strategy"))
    if sr:
        # Strategy report may contain fresher validated strike/entry values.
        strategy = {
            **strategy,
            "type": sr.get("action", strategy.get("type", final_action)),
            "sell_side": sr.get("side", strategy.get("sell_side")),
            "sell_strike": sr.get("sell_strike", strategy.get("sell_strike", "No Strike")),
            "hedge_strike": sr.get("hedge_strike", strategy.get("hedge_strike", "No Hedge")),
            "entry": sr.get("entry", strategy.get("entry", "No Trade")),
            "sl": sr.get("sl", strategy.get("sl", "No Trade")),
            "target": sr.get("target", strategy.get("target", "No Trade")),
            "lots": int(sr.get("lots", strategy.get("lots", 0)) or 0),
        }

    blockers = _clean_list(de.get("blockers", []), 4)
    warnings = _clean_list(de.get("warnings", []), 4)
    reasons = _clean_list(de.get("reasons", []), 3)
    if not reasons:
        reason = str(de.get("execution_reason", "") or "").strip()
        if reason:
            reasons = [reason]
    if not reasons and ir:
        rows = ir.get("reliability_rows", [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    factor = str(row.get("Signal", row.get("Factor", "")) or "").strip()
                    verdict = str(row.get("Verdict", row.get("Bias", "")) or "").strip()
                    if factor and verdict:
                        reasons.append(f"{factor}: {verdict}")
                    if len(reasons) >= 3:
                        break
    if not reasons:
        reasons = ["Mixed market evidence — wait for clear confirmation."]

    snapshot_id = str(snap.get("snapshot_id", fd.get("single_snapshot_id", "SNAP-NA")) or "SNAP-NA")
    flow = _safe_dict(snap.get("data_flow_monitor", fd.get("data_flow_monitor", {})))
    oi_lock = _safe_dict(snap.get("oi_single_source", fd.get("oi_single_source_lock", {})))

    data_status = str(flow.get("status", flow.get("data_flow_status", "UNKNOWN")) or "UNKNOWN")
    oi_status = str(oi_lock.get("status", oi_lock.get("sync_status", "UNKNOWN")) or "UNKNOWN")

    risk_score = rr.get("risk_score", rr.get("score", None))
    risk_label = rr.get("label", rr.get("risk_label", "NA"))

    # User-friendly common advice line. This is display advice only; execution
    # still depends on broker/margin/spread confirmation.
    if final_action == "WAIT" or execution_status in ("WAIT", "BLOCKED"):
        advice = "WAIT — no fresh trade. Let confirmation improve."
    elif final_action in ("SELL CE", "SELL PE", "IRON CONDOR"):
        strike = strategy.get("sell_strike", "No Strike")
        hedge = strategy.get("hedge_strike", "No Hedge")
        advice = f"{final_action}: {strike} | Hedge {hedge} | Confirm spread/margin."
    else:
        advice = f"{final_action} — use only after strong confirmation."

    return {
        "advisor_version": "V21.4_SINGLE_ADVISOR_AUTHORITY",
        "created_at": datetime.now().strftime("%H:%M:%S"),
        "snapshot_id": snapshot_id,
        "short_snapshot_id": snapshot_id[-8:] if len(snapshot_id) > 8 else snapshot_id,
        "source_of_truth": "decision_engine_after_stability_lock",
        "final_action": final_action,
        "execution_status": execution_status,
        "confidence": confidence,
        "strategy": strategy,
        "advice": advice,
        "reasons": reasons[:3],
        "blockers": blockers,
        "warnings": warnings,
        "data_flow_status": data_status,
        "oi_sync_status": oi_status,
        "risk_score": risk_score,
        "risk_label": risk_label,
        "stability": st,
        "evidence_sources": {
            "snapshot": bool(snap),
            "decision_engine": bool(de),
            "strategy_engine": bool(sr),
            "intelligence_engine": bool(ir),
            "risk_engine": bool(rr),
            "stability_engine": bool(st),
        },
    }
