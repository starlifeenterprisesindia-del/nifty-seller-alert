"""
Nifty Seller AI — Decision Engine v19.6

Combines:
Snapshot Engine + AI Brain + Risk Engine + Market/Freeze context
into one final execution verdict.

No API calls.
No auto-order execution.
No portfolio mutation.
"""

TRADE_ACTIONS = {"SELL CE", "SELL PE"}


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace("₹", "").replace(",", "").replace("%", "").strip()
            if not cleaned:
                return default
            token = ""
            started = False
            for ch in cleaned:
                if ch.isdigit() or ch in ".-+":
                    token += ch
                    started = True
                elif started:
                    break
            return float(token) if token else default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        return int(round(_safe_float(value, default)))
    except Exception:
        return default


def _clip(value, low=0, high=100):
    return max(low, min(high, _safe_float(value, low)))


def _action(value):
    value = str(value or "WAIT").strip().upper()
    return value if value in TRADE_ACTIONS else "WAIT"


def _plan_validation(action, strategy):
    strategy = strategy if isinstance(strategy, dict) else {}
    action = _action(action)

    if action == "WAIT":
        return {
            "complete": False,
            "valid": False,
            "issues": ["No directional trade action selected."],
            "values": {},
        }

    sell_raw = strategy.get("sell_strike", "")
    hedge_raw = strategy.get("hedge_strike", "")
    sell_strike = _safe_float(sell_raw, 0)
    hedge_strike = _safe_float(hedge_raw, 0)
    entry = _safe_float(strategy.get("entry", 0), 0)
    sl = _safe_float(strategy.get("sl", 0), 0)
    target = _safe_float(strategy.get("target", 0), 0)
    lots = _safe_int(strategy.get("lots", 0), 0)

    issues = []

    if sell_strike <= 0:
        issues.append("Sell strike missing.")
    if hedge_strike <= 0:
        issues.append("Hedge strike missing.")
    if entry <= 0:
        issues.append("Entry premium missing.")
    if sl <= 0:
        issues.append("Stop-loss missing.")
    if target <= 0:
        issues.append("Target missing.")
    if lots <= 0:
        issues.append("Suggested lots missing.")

    # Seller premium logic.
    if entry > 0 and sl > 0 and sl <= entry:
        issues.append("Seller SL must be above entry premium.")
    if entry > 0 and target > 0 and target >= entry:
        issues.append("Seller target must be below entry premium.")

    sell_text = str(sell_raw).upper()
    hedge_text = str(hedge_raw).upper()

    if action == "SELL CE":
        if "PE" in sell_text:
            issues.append("Sell strike side conflicts with SELL CE.")
        if "PE" in hedge_text:
            issues.append("Hedge side conflicts with SELL CE.")
        if sell_strike > 0 and hedge_strike > 0 and hedge_strike <= sell_strike:
            issues.append("CE hedge should be above CE sell strike.")

    if action == "SELL PE":
        if "CE" in sell_text:
            issues.append("Sell strike side conflicts with SELL PE.")
        if "CE" in hedge_text:
            issues.append("Hedge side conflicts with SELL PE.")
        if sell_strike > 0 and hedge_strike > 0 and hedge_strike >= sell_strike:
            issues.append("PE hedge should be below PE sell strike.")

    complete = all(v > 0 for v in (sell_strike, hedge_strike, entry, sl, target)) and lots > 0
    valid = complete and not issues

    return {
        "complete": complete,
        "valid": valid,
        "issues": issues,
        "values": {
            "sell_strike": sell_strike,
            "hedge_strike": hedge_strike,
            "entry": entry,
            "sl": sl,
            "target": target,
            "lots": lots,
        },
    }


def build_final_decision(
    legacy_decision,
    snapshot,
    ai_report,
    risk_report,
    snapshot_health=None,
    snapshot_delta=None,
    market_open=False,
    market_status="Unknown",
    freeze_state=None,
):
    legacy_decision = legacy_decision if isinstance(legacy_decision, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    ai_report = ai_report if isinstance(ai_report, dict) else {}
    risk_report = risk_report if isinstance(risk_report, dict) else {}
    snapshot_health = snapshot_health if isinstance(snapshot_health, dict) else {}
    snapshot_delta = snapshot_delta if isinstance(snapshot_delta, dict) else {}
    freeze_state = freeze_state if isinstance(freeze_state, dict) else {}

    legacy_action = _action(legacy_decision.get("action", "WAIT"))
    legacy_conf = _clip(legacy_decision.get("confidence", 0))
    strategy = legacy_decision.get("strategy", {})
    strategy = strategy if isinstance(strategy, dict) else {}

    snapshot_bias = ai_report.get("snapshot_bias", {})
    snapshot_bias = snapshot_bias if isinstance(snapshot_bias, dict) else {}
    ai_proposed = _action(snapshot_bias.get("proposed_action", "WAIT"))

    analysis_action = legacy_action
    if analysis_action == "WAIT" and ai_proposed in TRADE_ACTIONS:
        analysis_action = ai_proposed

    direction_conflict = (
        legacy_action in TRADE_ACTIONS
        and ai_proposed in TRADE_ACTIONS
        and legacy_action != ai_proposed
    )

    alignment = _clip(ai_report.get("alignment_score", 0))
    trade_quality = _clip(ai_report.get("trade_quality_score", 0))
    smart_conf = _clip(ai_report.get("smart_confidence", legacy_conf))

    risk_context = risk_report.get("context", {})
    risk_context = risk_context if isinstance(risk_context, dict) else {}

    health_score = _clip(
        snapshot_health.get("score", risk_context.get("snapshot_health", 0))
    )
    safety_score = _clip(risk_report.get("safety_score", 0))
    risk_score = _clip(risk_report.get("risk_score", 100))
    risk_guidance = str(risk_report.get("guidance", "") or "").upper()
    risk_grade = str(risk_report.get("risk_grade", "") or "").upper()
    risk_hard_blockers = list(risk_report.get("hard_blockers", []) or [])

    delta_status = str(snapshot_delta.get("status", "") or "").upper()
    material_change = _clip(snapshot_delta.get("material_change", 0))

    freeze_confirmed = bool(freeze_state.get("confirmed", False))
    freeze_count = _safe_int(freeze_state.get("same_count", 0), 0)
    freeze_required = max(1, _safe_int(freeze_state.get("required", 3), 3))

    plan = _plan_validation(analysis_action, strategy)

    calibrated = (
        legacy_conf * 0.30
        + smart_conf * 0.24
        + alignment * 0.18
        + trade_quality * 0.14
        + safety_score * 0.08
        + health_score * 0.06
    )

    warnings = []
    blockers = []
    reasons = []

    if direction_conflict:
        blockers.append(
            f"Direction conflict: legacy {legacy_action} vs Snapshot AI {ai_proposed}."
        )
        calibrated -= 22

    if analysis_action in TRADE_ACTIONS and not freeze_confirmed:
        blockers.append(
            f"Freeze confirmation pending: {freeze_count}/{freeze_required} refresh."
        )
        calibrated -= 8

    if risk_hard_blockers:
        blockers.extend([f"Risk Engine: {x}" for x in risk_hard_blockers[:6]])
        calibrated -= 18

    if risk_guidance == "BLOCK TRADE":
        blockers.append("Risk guidance is BLOCK TRADE.")
        calibrated -= 18
    elif risk_guidance == "WAIT / REDUCE SIZE":
        blockers.append("Risk guidance requires WAIT / REDUCE SIZE.")
        calibrated -= 12
    elif risk_guidance == "CAUTION / SMALL SIZE":
        warnings.append("Risk Engine recommends CAUTION / SMALL SIZE.")
        calibrated -= 5

    if health_score < 55:
        blockers.append(f"Snapshot health too weak: {health_score:.0f}/100.")
        calibrated -= 15
    elif health_score < 70:
        warnings.append(f"Snapshot health caution: {health_score:.0f}/100.")
        calibrated -= 5

    if alignment < 50 and analysis_action in TRADE_ACTIONS:
        blockers.append(f"Signal alignment too weak: {alignment:.0f}/100.")
        calibrated -= 12
    elif alignment < 65 and analysis_action in TRADE_ACTIONS:
        warnings.append(f"Signal alignment only moderate: {alignment:.0f}/100.")
        calibrated -= 4

    if trade_quality < 50 and analysis_action in TRADE_ACTIONS:
        blockers.append(f"Trade quality too weak: {trade_quality:.0f}/100.")
        calibrated -= 12
    elif trade_quality < 65 and analysis_action in TRADE_ACTIONS:
        warnings.append(f"Trade quality caution: {trade_quality:.0f}/100.")
        calibrated -= 4

    if analysis_action in TRADE_ACTIONS and not plan.get("valid", False):
        blockers.extend([f"Trade plan: {x}" for x in plan.get("issues", [])[:8]])
        calibrated -= 15

    if delta_status == "FIRST":
        warnings.append("First snapshot: no prior snapshot comparison yet.")
        calibrated -= 2
    elif material_change >= 75:
        warnings.append(f"Large material market change: {material_change:.0f}/100.")
        calibrated -= 6

    if safety_score <= 55:
        warnings.append(f"Safety score weak: {safety_score:.0f}/100.")
        calibrated -= 5

    calibrated = int(round(_clip(calibrated, 0, 98)))

    if analysis_action in TRADE_ACTIONS and calibrated < 65:
        blockers.append(f"Calibrated confidence below execution floor: {calibrated}%.")

    # Final status
    if analysis_action == "WAIT":
        status = "WAIT"
        final_action = "WAIT"
    elif not bool(market_open):
        status = "PREVIEW_ONLY"
        final_action = "WAIT"
    elif blockers:
        status = "BLOCKED"
        final_action = "WAIT"
    else:
        status = "APPROVED"
        final_action = analysis_action

    base_lots = max(0, _safe_int(strategy.get("lots", 0), 0))

    if safety_score >= 80:
        size_factor = 1.00
    elif safety_score >= 70:
        size_factor = 0.85
    elif safety_score >= 60:
        size_factor = 0.65
    elif safety_score >= 50:
        size_factor = 0.45
    else:
        size_factor = 0.25

    if risk_guidance == "CAUTION / SMALL SIZE":
        size_factor = min(size_factor, 0.50)
    if risk_grade in {"HIGH", "CRITICAL"}:
        size_factor = min(size_factor, 0.35)

    preview_lots = 0
    if base_lots > 0 and analysis_action in TRADE_ACTIONS:
        preview_lots = max(1, min(base_lots, int(round(base_lots * size_factor))))

    approved_lots = preview_lots if status == "APPROVED" else 0

    if analysis_action in TRADE_ACTIONS:
        reasons.append(f"Analysis bias: {analysis_action}.")
    if legacy_action == ai_proposed and legacy_action in TRADE_ACTIONS:
        reasons.append(f"Direction consensus confirmed: {legacy_action}.")
    if alignment >= 70:
        reasons.append(f"Signal alignment strong: {alignment:.0f}/100.")
    if trade_quality >= 72:
        reasons.append(f"Trade quality strong: {trade_quality:.0f}/100.")
    if health_score >= 80:
        reasons.append(f"Snapshot health strong: {health_score:.0f}/100.")
    if safety_score >= 60:
        reasons.append(f"Risk safety score: {safety_score:.0f}/100.")
    if plan.get("valid"):
        reasons.append("Strike + hedge + entry + SL + target plan validated.")
    if freeze_confirmed:
        reasons.append(f"Freeze confirmation complete: {freeze_count}/{freeze_required}.")

    execution_reason = {
        "APPROVED": "All execution gates passed.",
        "BLOCKED": "One or more execution blockers remain active.",
        "PREVIEW_ONLY": f"{market_status}: analytical plan only; no fresh entry.",
        "WAIT": "No approved trade action.",
    }.get(status, "No approved trade action.")

    decision_id = (
        ai_report.get("decision_id")
        or snapshot.get("snapshot_id")
        or "AI-DECISION"
    )

    consensus = "AGREE"
    if direction_conflict:
        consensus = "CONFLICT"
    elif legacy_action == "WAIT" or ai_proposed == "WAIT":
        consensus = "PARTIAL"

    return {
        "version": "V19.6 Decision Engine",
        "decision_id": decision_id,
        "analysis_action": analysis_action,
        "legacy_action": legacy_action,
        "ai_proposed_action": ai_proposed,
        "final_action": final_action,
        "execution_status": status,
        "execution_reason": execution_reason,
        "calibrated_confidence": calibrated,
        "consensus": consensus,
        "direction_conflict": direction_conflict,
        "approved_lots": approved_lots,
        "preview_lots": preview_lots,
        "base_lots": base_lots,
        "size_factor": round(size_factor, 2),
        "market_open": bool(market_open),
        "market_status": market_status,
        "freeze": {
            "confirmed": freeze_confirmed,
            "count": freeze_count,
            "required": freeze_required,
        },
        "plan_validation": plan,
        "risk": {
            "risk_score": int(round(risk_score)),
            "safety_score": int(round(safety_score)),
            "risk_grade": risk_grade,
            "guidance": risk_guidance,
        },
        "scores": {
            "legacy_confidence": int(round(legacy_conf)),
            "smart_confidence": int(round(smart_conf)),
            "alignment": int(round(alignment)),
            "trade_quality": int(round(trade_quality)),
            "snapshot_health": int(round(health_score)),
            "safety_score": int(round(safety_score)),
        },
        "blockers": list(dict.fromkeys(blockers))[:16],
        "warnings": list(dict.fromkeys(warnings))[:12],
        "reasons": list(dict.fromkeys(reasons))[:12],
    }
