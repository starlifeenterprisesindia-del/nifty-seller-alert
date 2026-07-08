"""
Nifty Seller AI — Strategy Engine v19.10

Single responsibility:
Build one final option-selling trade plan:
- sell strike
- hedge strike
- entry premium
- stop-loss
- targets
- trailing reference
- lots
- plan validation/status

No API calls.
No broker order execution.
No portfolio mutation.
"""

TRADE_ACTIONS = {"SELL CE", "SELL PE"}


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = (
                value.replace("₹", "")
                .replace(",", "")
                .replace("%", "")
                .strip()
            )
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


def _money(value):
    value = _safe_float(value, 0)
    return f"₹{value:.2f}" if value > 0 else "No Trade"


def _action(value):
    value = str(value or "WAIT").strip().upper()
    return value if value in TRADE_ACTIONS else "WAIT"


def _seller_sl_target(premium, confidence=0, gamma_score=0, shock_score=0):
    premium = _safe_float(premium, 0)
    conf = _safe_float(confidence, 0)
    gamma = _safe_float(gamma_score, 0)
    shock = _safe_float(shock_score, 0)

    if premium <= 0:
        return {
            "sl": 0.0,
            "target1": 0.0,
            "target2": 0.0,
            "trail_after": 0.0,
            "sl_pct": 0.0,
        }

    # Preserve the proven seller premium logic from the prior app.
    sl_pct = 0.28
    if gamma >= 70 or shock >= 65:
        sl_pct = 0.18
    elif conf >= 80:
        sl_pct = 0.32

    target1_pct = 0.30
    target2_pct = 0.50

    return {
        "sl": round(premium * (1 + sl_pct), 2),
        "target1": round(max(0.05, premium * (1 - target1_pct)), 2),
        "target2": round(max(0.05, premium * (1 - target2_pct)), 2),
        "trail_after": round(max(0.05, premium * 0.75), 2),
        "sl_pct": round(sl_pct * 100, 1),
    }


def _row_for_action(action, best_ce=None, best_pe=None):
    if action == "SELL CE":
        return best_ce if isinstance(best_ce, dict) else None, "CE"
    if action == "SELL PE":
        return best_pe if isinstance(best_pe, dict) else None, "PE"
    return None, None


def _extract_row_plan(row, side):
    if not isinstance(row, dict) or side not in {"CE", "PE"}:
        return 0.0, 0.0

    strike = _safe_float(row.get("strike", 0), 0)
    premium_key = "ce_ltp" if side == "CE" else "pe_ltp"
    premium = _safe_float(row.get(premium_key, 0), 0)
    return strike, premium


def build_strategy_plan(
    action,
    best_ce=None,
    best_pe=None,
    hedge_gap=100,
    confidence=0,
    gamma_score=0,
    shock_score=0,
    base_lots=0,
    existing_strategy=None,
    market_open=False,
    market_status="Unknown",
):
    """
    Build one strategy plan for SELL CE / SELL PE.

    `existing_strategy` is a compatibility fallback only when live candidate
    premium/strike is unavailable. It does not override a valid live row.
    """
    action = _action(action)
    existing_strategy = (
        existing_strategy if isinstance(existing_strategy, dict) else {}
    )

    if action == "WAIT":
        return {
            "version": "V19.10 Strategy Engine",
            "action": "WAIT",
            "side": None,
            "status": "WAIT",
            "source": "NO_ACTION",
            "market_open": bool(market_open),
            "market_status": market_status,
            "sell_strike": "No Strike",
            "hedge_strike": "No Hedge",
            "entry": "No Trade",
            "sl": "No Trade",
            "target": "No Trade",
            "target2": "No Trade",
            "trail_after": "No Trade",
            "lots": 0,
            "issues": ["No directional trade action selected."],
            "valid": False,
        }

    row, side = _row_for_action(action, best_ce, best_pe)
    sell_strike, premium = _extract_row_plan(row, side)
    source = "LIVE_CANDIDATE" if sell_strike > 0 and premium > 0 else "EXISTING_FALLBACK"

    # Compatibility fallback from current strategy object.
    if sell_strike <= 0:
        sell_strike = _safe_float(existing_strategy.get("sell_strike", 0), 0)

    if premium <= 0:
        premium = _safe_float(existing_strategy.get("entry", 0), 0)

    hedge_gap = max(50, _safe_int(hedge_gap, 100))
    hedge_strike = 0.0

    if sell_strike > 0:
        hedge_strike = (
            sell_strike + hedge_gap
            if side == "CE"
            else sell_strike - hedge_gap
        )

    if hedge_strike <= 0:
        hedge_strike = _safe_float(
            existing_strategy.get("hedge_strike", 0),
            0,
        )

    premium_plan = _seller_sl_target(
        premium,
        confidence=confidence,
        gamma_score=gamma_score,
        shock_score=shock_score,
    )

    lots = max(0, _safe_int(base_lots, 0))
    if lots <= 0:
        lots = max(0, _safe_int(existing_strategy.get("lots", 0), 0))

    issues = []

    if sell_strike <= 0:
        issues.append("Sell strike missing.")
    if hedge_strike <= 0:
        issues.append("Hedge strike missing.")
    if premium <= 0:
        issues.append("Entry premium missing.")
    if premium_plan.get("sl", 0) <= 0:
        issues.append("Stop-loss missing.")
    if premium_plan.get("target1", 0) <= 0:
        issues.append("Target missing.")
    if lots <= 0:
        issues.append("Lots missing.")

    if side == "CE" and sell_strike > 0 and hedge_strike > 0:
        if hedge_strike <= sell_strike:
            issues.append("CE hedge must be above CE sell strike.")

    if side == "PE" and sell_strike > 0 and hedge_strike > 0:
        if hedge_strike >= sell_strike:
            issues.append("PE hedge must be below PE sell strike.")

    valid = len(issues) == 0

    if not valid:
        status = "INCOMPLETE"
    elif not bool(market_open):
        status = "PREVIEW"
    else:
        status = "READY"

    sell_label = (
        f"{int(round(sell_strike))} {side}"
        if sell_strike > 0
        else "No Strike"
    )
    hedge_label = (
        f"{int(round(hedge_strike))} {side}"
        if hedge_strike > 0
        else "No Hedge"
    )

    return {
        "version": "V19.10 Strategy Engine",
        "action": action,
        "side": side,
        "status": status,
        "source": source,
        "market_open": bool(market_open),
        "market_status": market_status,
        "sell_strike": sell_label,
        "hedge_strike": hedge_label,
        "entry": _money(premium),
        "entry_value": round(premium, 2) if premium > 0 else 0.0,
        "sl": _money(premium_plan.get("sl", 0)),
        "sl_value": premium_plan.get("sl", 0),
        "target": _money(premium_plan.get("target1", 0)),
        "target_value": premium_plan.get("target1", 0),
        "target2": _money(premium_plan.get("target2", 0)),
        "target2_value": premium_plan.get("target2", 0),
        "trail_after": _money(premium_plan.get("trail_after", 0)),
        "trail_after_value": premium_plan.get("trail_after", 0),
        "sl_pct": premium_plan.get("sl_pct", 0),
        "lots": lots,
        "hedge_gap": hedge_gap,
        "issues": issues,
        "valid": valid,
    }
