"""
Nifty Seller AI — Memory Engine v19.13

Purpose:
Short-term market memory from recent refreshes.

It remembers:
- actions
- execution status
- confidence
- strike
- intelligence score
- fake-move risk
- material change

No API calls.
No broker execution.
No disk write.
Uses Streamlit session_state in app.py.
"""


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace("₹", "").replace(",", "").replace("%", "").strip()
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


def _action(value):
    value = str(value or "WAIT").upper().strip()
    return value if value in {"SELL CE", "SELL PE"} else "WAIT"


def _trim(history, max_items=20):
    history = history if isinstance(history, list) else []
    return history[-max_items:]


def _trend(values):
    vals = [_safe_float(v, 0) for v in values if v is not None]
    if len(vals) < 3:
        return "NEW", 0
    first = sum(vals[:max(1, len(vals)//3)]) / max(1, len(vals[:max(1, len(vals)//3)]))
    last = sum(vals[-max(1, len(vals)//3):]) / max(1, len(vals[-max(1, len(vals)//3):]))
    delta = last - first
    if delta >= 8:
        return "IMPROVING", int(round(delta))
    if delta <= -8:
        return "WEAKENING", int(round(delta))
    return "STABLE", int(round(delta))


def _mode(items):
    if not items:
        return "NA", 0
    counts = {}
    for x in items:
        counts[x] = counts.get(x, 0) + 1
    best = max(counts, key=counts.get)
    return best, counts[best]


def update_memory(
    history,
    snapshot=None,
    decision_report=None,
    intelligence_report=None,
    stability_report=None,
    strategy_report=None,
    max_items=20,
):
    history = _trim(history, max_items=max_items)

    snapshot = snapshot if isinstance(snapshot, dict) else {}
    decision_report = decision_report if isinstance(decision_report, dict) else {}
    intelligence_report = intelligence_report if isinstance(intelligence_report, dict) else {}
    stability_report = stability_report if isinstance(stability_report, dict) else {}
    strategy_report = strategy_report if isinstance(strategy_report, dict) else {}

    plan = decision_report.get("plan_validation", {})
    plan = plan if isinstance(plan, dict) else {}
    values = plan.get("values", {}) if isinstance(plan.get("values", {}), dict) else {}

    row = {
        "snapshot_id": snapshot.get("snapshot_id", ""),
        "created_at": snapshot.get("created_at", ""),
        "analysis_action": decision_report.get("analysis_action", "WAIT"),
        "final_action": decision_report.get("final_action", "WAIT"),
        "execution_status": decision_report.get("execution_status", "WAIT"),
        "confidence": _safe_int(decision_report.get("calibrated_confidence", 0), 0),
        "strike": _safe_float(values.get("sell_strike", 0), 0),
        "approved_lots": _safe_int(decision_report.get("approved_lots", 0), 0),
        "preview_lots": _safe_int(decision_report.get("preview_lots", 0), 0),
        "intelligence_score": _safe_int(intelligence_report.get("intelligence_score", 0), 0),
        "fake_move_risk": _safe_int(intelligence_report.get("fake_move_risk", 0), 0),
        "conflict_score": _safe_int(intelligence_report.get("conflict_score", 0), 0),
        "market_context": intelligence_report.get("market_context", "NA"),
        "stability_status": stability_report.get("status", "NA"),
        "strategy_status": strategy_report.get("status", "NA"),
    }

    # Avoid adding exact same snapshot+decision repeatedly if rerun did not refresh data.
    if history:
        last = history[-1]
        if (
            last.get("snapshot_id") == row.get("snapshot_id")
            and last.get("analysis_action") == row.get("analysis_action")
            and last.get("execution_status") == row.get("execution_status")
            and int(last.get("confidence", 0)) == int(row.get("confidence", 0))
            and int(last.get("intelligence_score", 0)) == int(row.get("intelligence_score", 0))
        ):
            report = build_memory_report(history)
            report["last_update"] = "UNCHANGED_RERUN"
            return history, report

    history.append(row)
    history = _trim(history, max_items=max_items)
    report = build_memory_report(history)
    report["last_update"] = "ADDED"
    return history, report


def build_memory_report(history):
    history = _trim(history, max_items=20)
    n = len(history)

    if n == 0:
        return {
            "version": "V19.13 Memory Engine",
            "history_count": 0,
            "memory_status": "EMPTY",
            "memory_score": 0,
            "summary": "No memory yet.",
            "warnings": [],
            "positives": [],
            "recent_rows": [],
        }

    actions = [_action(x.get("analysis_action", "WAIT")) for x in history]
    statuses = [str(x.get("execution_status", "WAIT")) for x in history]
    confidences = [_safe_int(x.get("confidence", 0), 0) for x in history]
    intel_scores = [_safe_int(x.get("intelligence_score", 0), 0) for x in history]
    fake_scores = [_safe_int(x.get("fake_move_risk", 0), 0) for x in history]
    conflict_scores = [_safe_int(x.get("conflict_score", 0), 0) for x in history]
    strikes = [_safe_float(x.get("strike", 0), 0) for x in history if _safe_float(x.get("strike", 0), 0) > 0]

    last = history[-1]
    mode_action, mode_count = _mode(actions[-min(10, n):])
    mode_status, status_count = _mode(statuses[-min(10, n):])

    action_stability = int(round((mode_count / max(1, min(10, n))) * 100))
    status_stability = int(round((status_count / max(1, min(10, n))) * 100))

    conf_trend, conf_delta = _trend(confidences[-min(10, n):])
    intel_trend, intel_delta = _trend(intel_scores[-min(10, n):])

    if len(strikes) >= 2:
        strike_range = int(round(max(strikes[-min(10, len(strikes)):]) - min(strikes[-min(10, len(strikes)):])))
    else:
        strike_range = 0

    avg_fake = int(round(sum(fake_scores[-min(10, n):]) / max(1, min(10, n))))
    avg_conflict = int(round(sum(conflict_scores[-min(10, n):]) / max(1, min(10, n))))
    avg_conf = int(round(sum(confidences[-min(10, n):]) / max(1, min(10, n))))
    avg_intel = int(round(sum(intel_scores[-min(10, n):]) / max(1, min(10, n))))

    positives = []
    warnings = []

    if action_stability >= 70:
        positives.append(f"Action stable: {mode_action} appeared {mode_count}/{min(10,n)} times.")
    else:
        warnings.append(f"Action unstable: top action only {mode_count}/{min(10,n)} times.")

    if status_stability >= 70:
        positives.append(f"Execution status stable: {mode_status}.")
    else:
        warnings.append("Execution status changing frequently.")

    if conf_trend == "IMPROVING":
        positives.append(f"Decision confidence improving by {conf_delta} points.")
    elif conf_trend == "WEAKENING":
        warnings.append(f"Decision confidence weakening by {abs(conf_delta)} points.")

    if intel_trend == "IMPROVING":
        positives.append(f"Intelligence score improving by {intel_delta} points.")
    elif intel_trend == "WEAKENING":
        warnings.append(f"Intelligence score weakening by {abs(intel_delta)} points.")

    if strike_range > 150:
        warnings.append(f"Strike selection unstable: recent range {strike_range} pts.")
    elif strike_range > 0:
        positives.append(f"Strike range controlled: {strike_range} pts.")

    if avg_fake >= 60:
        warnings.append(f"Average fake-move risk elevated: {avg_fake}/100.")
    else:
        positives.append(f"Fake-move risk controlled on average: {avg_fake}/100.")

    if avg_conflict >= 60:
        warnings.append(f"Average conflict score elevated: {avg_conflict}/100.")

    memory_score = (
        action_stability * 0.26
        + status_stability * 0.18
        + max(0, 100 - min(100, strike_range / 2)) * 0.12
        + max(0, 100 - avg_fake) * 0.14
        + max(0, 100 - avg_conflict) * 0.12
        + avg_conf * 0.10
        + avg_intel * 0.08
    )
    memory_score = int(round(max(0, min(100, memory_score))))

    if n < 3:
        memory_status = "WARMING UP"
    elif memory_score >= 80:
        memory_status = "STABLE"
    elif memory_score >= 65:
        memory_status = "USABLE"
    elif memory_score >= 50:
        memory_status = "UNSTABLE"
    else:
        memory_status = "NOISY"

    summary = (
        f"Memory sees {mode_action} as dominant action with {action_stability}% stability. "
        f"Confidence trend: {conf_trend}. Intelligence trend: {intel_trend}."
    )

    return {
        "version": "V19.13 Memory Engine",
        "history_count": n,
        "memory_status": memory_status,
        "memory_score": memory_score,
        "dominant_action": mode_action,
        "dominant_status": mode_status,
        "action_stability": action_stability,
        "status_stability": status_stability,
        "confidence_trend": conf_trend,
        "confidence_delta": conf_delta,
        "intelligence_trend": intel_trend,
        "intelligence_delta": intel_delta,
        "strike_range": strike_range,
        "avg_confidence": avg_conf,
        "avg_intelligence": avg_intel,
        "avg_fake_move_risk": avg_fake,
        "avg_conflict_score": avg_conflict,
        "summary": summary,
        "positives": positives[:8],
        "warnings": warnings[:8],
        "recent_rows": history[-10:],
        "last_row": last,
    }
