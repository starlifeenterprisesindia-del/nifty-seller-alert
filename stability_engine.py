"""
Nifty Seller AI — Stability Engine v19.12

Prevents unstable refresh-to-refresh decision and strike jumps.
Decision Engine remains final authority; this module locks/filters unstable changes.
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


def apply_stability_lock(
    current_decision,
    previous_locked=None,
    material_change=0,
    risk_report=None,
    intelligence_report=None,
    max_strike_jump=100,
    min_change_for_new_strike=45,
    min_change_for_direction_flip=65,
):
    current = dict(current_decision) if isinstance(current_decision, dict) else {}
    previous = dict(previous_locked) if isinstance(previous_locked, dict) else {}
    risk_report = dict(risk_report) if isinstance(risk_report, dict) else {}
    intelligence_report = dict(intelligence_report) if isinstance(intelligence_report, dict) else {}

    if not current:
        return {
            "decision": current,
            "stability": {"status": "NO_DECISION", "locked": False, "reason": "No decision available."},
            "lock_state": {},
        }

    material_change = _safe_int(material_change, 0)
    risk_score = _safe_int(risk_report.get("risk_score", 0), 0)
    risk_guidance = str(risk_report.get("guidance", "") or "").upper()
    hard_blockers = risk_report.get("hard_blockers", []) or []
    fake_risk = _safe_int(intelligence_report.get("fake_move_risk", 0), 0)
    conflict_score = _safe_int(intelligence_report.get("conflict_score", 0), 0)

    current_action = _action(current.get("analysis_action", current.get("final_action", "WAIT")))
    current_final = _action(current.get("final_action", "WAIT"))
    current_status = str(current.get("execution_status", "WAIT") or "WAIT").upper()
    current_conf = _safe_int(current.get("calibrated_confidence", 0), 0)

    plan = current.get("plan_validation", {}) if isinstance(current.get("plan_validation", {}), dict) else {}
    values = plan.get("values", {}) if isinstance(plan.get("values", {}), dict) else {}
    current_strike = _safe_float(values.get("sell_strike", 0), 0)

    immediate_wait = (
        current_status in {"BLOCKED", "WAIT"}
        and (
            hard_blockers
            or risk_guidance in {"BLOCK TRADE", "WAIT / REDUCE SIZE"}
            or risk_score >= 75
            or fake_risk >= 75
            or conflict_score >= 85
        )
    )

    if not previous:
        lock_state = {
            "analysis_action": current_action,
            "final_action": current_final,
            "execution_status": current_status,
            "strike": current_strike,
            "confidence": current_conf,
            "decision": current,
            "same_count": 1,
        }
        return {
            "decision": current,
            "stability": {
                "status": "FIRST_LOCK",
                "locked": False,
                "reason": "First stable decision stored.",
                "material_change": material_change,
                "strike_jump": 0,
                "same_count": 1,
            },
            "lock_state": lock_state,
        }

    prev_action = _action(previous.get("analysis_action", "WAIT"))
    prev_final = _action(previous.get("final_action", "WAIT"))
    prev_status = str(previous.get("execution_status", "WAIT") or "WAIT").upper()
    prev_strike = _safe_float(previous.get("strike", 0), 0)
    prev_conf = _safe_int(previous.get("confidence", 0), 0)
    prev_decision = previous.get("decision", {}) if isinstance(previous.get("decision", {}), dict) else {}

    strike_jump = abs(current_strike - prev_strike) if current_strike and prev_strike else 0
    action_changed = current_action != prev_action
    strike_changed = strike_jump > 0
    same_direction = current_action == prev_action
    same_strike_zone = strike_jump <= max_strike_jump if current_strike and prev_strike else True

    if immediate_wait:
        lock_state = {
            "analysis_action": current_action,
            "final_action": current_final,
            "execution_status": current_status,
            "strike": current_strike,
            "confidence": current_conf,
            "decision": current,
            "same_count": 1,
        }
        return {
            "decision": current,
            "stability": {
                "status": "SAFETY_OVERRIDE",
                "locked": False,
                "reason": "Risk/blocker strong hai, WAIT/BLOCK immediately allowed.",
                "material_change": material_change,
                "strike_jump": strike_jump,
                "same_count": 1,
            },
            "lock_state": lock_state,
        }

    if action_changed and material_change < min_change_for_direction_flip:
        adjusted = dict(prev_decision or current)
        adjusted["stability_override"] = True
        adjusted["stability_reason"] = (
            f"Direction flip blocked: {prev_action} → {current_action}, "
            f"material change {material_change}/100 < {min_change_for_direction_flip}/100."
        )
        lock_state = dict(previous)
        lock_state["same_count"] = _safe_int(previous.get("same_count", 1), 1)
        return {
            "decision": adjusted,
            "stability": {
                "status": "DIRECTION_LOCKED",
                "locked": True,
                "reason": adjusted["stability_reason"],
                "material_change": material_change,
                "strike_jump": strike_jump,
                "same_count": lock_state["same_count"],
            },
            "lock_state": lock_state,
        }

    if (
        same_direction
        and strike_changed
        and strike_jump > max_strike_jump
        and material_change < min_change_for_new_strike
    ):
        adjusted = dict(prev_decision or current)
        adjusted["stability_override"] = True
        adjusted["stability_reason"] = (
            f"Strike jump blocked: {prev_strike:.0f} → {current_strike:.0f}, "
            f"jump {strike_jump:.0f} pts, material change {material_change}/100 "
            f"< {min_change_for_new_strike}/100."
        )
        lock_state = dict(previous)
        lock_state["same_count"] = _safe_int(previous.get("same_count", 1), 1)
        return {
            "decision": adjusted,
            "stability": {
                "status": "STRIKE_LOCKED",
                "locked": True,
                "reason": adjusted["stability_reason"],
                "material_change": material_change,
                "strike_jump": strike_jump,
                "same_count": lock_state["same_count"],
            },
            "lock_state": lock_state,
        }

    same_count = _safe_int(previous.get("same_count", 1), 1)
    same_count = same_count + 1 if same_direction and same_strike_zone else 1

    lock_state = {
        "analysis_action": current_action,
        "final_action": current_final,
        "execution_status": current_status,
        "strike": current_strike,
        "confidence": current_conf,
        "decision": current,
        "same_count": same_count,
    }

    return {
        "decision": current,
        "stability": {
            "status": "ACCEPTED",
            "locked": False,
            "reason": "Decision accepted by stability engine.",
            "material_change": material_change,
            "strike_jump": strike_jump,
            "same_count": same_count,
        },
        "lock_state": lock_state,
    }
