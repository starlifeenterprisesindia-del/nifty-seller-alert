"""
Nifty Seller AI — Snapshot Engine v19.3

This module builds and validates the single market snapshot.
It does not fetch data. It only organizes already-calculated app values.
"""


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        return int(round(_safe_float(value, default)))
    except Exception:
        return default


def build_market_snapshot(ctx, fmt_time_func=None):
    option_chain = ctx.get("option_chain", {}) if isinstance(ctx.get("option_chain", {}), dict) else {}
    option_analysis = ctx.get("option_analysis", {}) if isinstance(ctx.get("option_analysis", {}), dict) else {}
    heavyweight_analysis = ctx.get("heavyweight_analysis", {}) if isinstance(ctx.get("heavyweight_analysis", {}), dict) else {}
    news = ctx.get("news", {}) if isinstance(ctx.get("news", {}), dict) else {}
    final_decision_obj = ctx.get("final_decision", {}) if isinstance(ctx.get("final_decision", {}), dict) else {}

    created_at = ""
    try:
        created_at = fmt_time_func() if fmt_time_func else ""
    except Exception:
        created_at = ""

    nifty_price = _safe_float(ctx.get("price", ctx.get("nifty_price", 0)), 0)
    pcr_value = _safe_float(ctx.get("pcr", option_chain.get("pcr", 0)), 0)

    snapshot = {
        "version": "V19.5.1 Snapshot Engine",
        "created_at": created_at,
        "market": {
            "status": ctx.get("status", ctx.get("market_status_text", "")),
            "day": ctx.get("day_name", ""),
            "nifty_price": nifty_price,
            "nifty_change": _safe_float(ctx.get("change", ctx.get("nifty_change", 0)), 0),
            "nifty_change_pct": _safe_float(ctx.get("change_pct", ctx.get("nifty_change_pct", 0)), 0),
            "india_vix": _safe_float(ctx.get("vix", ctx.get("india_vix", 0)), 0),
            "vix_change_pct": _safe_float(ctx.get("vix_change_pct", 0), 0),
        },
        "option_chain": {
            "success": bool(option_chain.get("success", False)),
            "source": option_chain.get("source", ""),
            "expiry": option_chain.get("expiry", ctx.get("selected_expiry", "")),
            "atm_strike": option_chain.get("atm_strike", ctx.get("atm_strike", "")),
            "pcr": pcr_value,
            "total_call_oi": _safe_int(option_chain.get("total_call_oi", 0), 0),
            "total_put_oi": _safe_int(option_chain.get("total_put_oi", 0), 0),
            "call_oi_change": _safe_int(option_chain.get("call_oi_change", 0), 0),
            "put_oi_change": _safe_int(option_chain.get("put_oi_change", 0), 0),
            "rows_count": len(option_chain.get("rows", []) or []),
        },
        "signals": {
            "option_bias": _safe_float(option_analysis.get("bias", ctx.get("option_bias", 0)), 0),
            "price_action_bias": _safe_float(ctx.get("price_action_bias", 0), 0),
            "heavyweight_bias": _safe_float(heavyweight_analysis.get("pressure", ctx.get("heavy_bias", 0)), 0),
            "market_bias": _safe_float(ctx.get("market_bias", 0), 0),
            "conflict_mode": bool(ctx.get("conflict_mode", False)),
        },
        "risk": {
            "data_quality": _safe_int(ctx.get("data_quality", 0), 0),
            "seller_risk": _safe_int(ctx.get("seller_risk", 0), 0),
            "news_risk": _safe_int(news.get("score", ctx.get("news_score", 0)), 0),
            "gamma_risk": _safe_int(ctx.get("gamma_score_v7", 0), 0),
            "shock_risk": _safe_int(ctx.get("shock_score_v7", 0), 0),
            "expiry_mode": ctx.get("expiry_mode", ctx.get("mode", "")),
        },
        "ai": {
            "final_action": final_decision_obj.get("action", ctx.get("final_trade", "WAIT")),
            "confidence": _safe_int(final_decision_obj.get("confidence", ctx.get("confidence", 0)), 0),
            "quality": final_decision_obj.get("quality", ""),
            "regime": (final_decision_obj.get("ai_intelligence", {}) or {}).get("regime", ""),
            "trade_quality": (final_decision_obj.get("ai_intelligence", {}) or {}).get("trade_quality_score", 0),
        },
        "source_health": {
            "dhan_ready": bool(ctx.get("dhan_ready", False)),
            "nifty_source": ctx.get("nifty_source", ""),
            "heavy_source": ctx.get("heavy_source", ""),
            "vix_source": ctx.get("vix_source", ""),
        }
    }

    snapshot["snapshot_id"] = "|".join([
        str(snapshot["market"]["nifty_price"]),
        str(snapshot["option_chain"]["expiry"]),
        str(snapshot["option_chain"]["atm_strike"]),
        str(snapshot["option_chain"]["pcr"]),
        str(snapshot["signals"]["option_bias"]),
        str(snapshot["risk"]["seller_risk"]),
        str(snapshot["ai"]["final_action"]),
    ])
    return snapshot


def snapshot_delta(current_snapshot, previous_snapshot=None):
    if not previous_snapshot:
        return {"status": "FIRST", "material_change": 0, "changes": ["First snapshot created; no prior snapshot available for comparison."]}

    changes = []
    cur_m = current_snapshot.get("market", {})
    prev_m = previous_snapshot.get("market", {})
    cur_s = current_snapshot.get("signals", {})
    prev_s = previous_snapshot.get("signals", {})
    cur_r = current_snapshot.get("risk", {})
    prev_r = previous_snapshot.get("risk", {})

    price_delta = abs(_safe_float(cur_m.get("nifty_price")) - _safe_float(prev_m.get("nifty_price")))
    option_delta = abs(_safe_float(cur_s.get("option_bias")) - _safe_float(prev_s.get("option_bias")))
    heavy_delta = abs(_safe_float(cur_s.get("heavyweight_bias")) - _safe_float(prev_s.get("heavyweight_bias")))
    risk_delta = abs(_safe_float(cur_r.get("seller_risk")) - _safe_float(prev_r.get("seller_risk")))
    news_delta = abs(_safe_float(cur_r.get("news_risk")) - _safe_float(prev_r.get("news_risk")))

    if price_delta >= 20:
        changes.append(f"Nifty moved {price_delta:.1f} points.")
    if option_delta >= 12:
        changes.append(f"Option bias changed {option_delta:.0f} points.")
    if heavy_delta >= 12:
        changes.append(f"Heavyweight bias changed {heavy_delta:.0f} points.")
    if risk_delta >= 10:
        changes.append(f"Seller risk changed {risk_delta:.0f} points.")
    if news_delta >= 10:
        changes.append(f"News risk changed {news_delta:.0f} points.")

    material = min(100, price_delta * 0.8 + option_delta * 1.5 + heavy_delta * 1.2 + risk_delta + news_delta)
    return {"status": "CHANGED" if changes else "STABLE", "material_change": int(round(material)), "changes": changes or ["No material market change."]}


def snapshot_health(snapshot):
    issues = []
    warnings = []
    points = 100

    m = snapshot.get("market", {}) if isinstance(snapshot.get("market", {}), dict) else {}
    oc = snapshot.get("option_chain", {}) if isinstance(snapshot.get("option_chain", {}), dict) else {}
    sig = snapshot.get("signals", {}) if isinstance(snapshot.get("signals", {}), dict) else {}
    risk = snapshot.get("risk", {}) if isinstance(snapshot.get("risk", {}), dict) else {}
    src = snapshot.get("source_health", {}) if isinstance(snapshot.get("source_health", {}), dict) else {}

    if _safe_float(m.get("nifty_price", 0)) <= 0:
        issues.append("Nifty price missing.")
        points -= 30

    if not oc.get("success", False):
        issues.append("Live option-chain not confirmed.")
        points -= 35

    if _safe_int(oc.get("rows_count", 0), 0) < 5:
        issues.append("Option-chain rows too low.")
        points -= 15

    pcr = _safe_float(oc.get("pcr", 0), 0)
    if pcr <= 0:
        warnings.append("PCR missing/zero.")
        points -= 10
    elif pcr < 0.55 or pcr > 2.20:
        warnings.append(f"PCR extreme/unusual: {pcr:.2f}.")
        points -= 8

    data_quality = _safe_float(risk.get("data_quality", 0), 0)
    if data_quality < 60:
        issues.append(f"Base data quality weak: {data_quality:.0f}/100.")
        points -= 20

    if not src.get("dhan_ready", False):
        warnings.append("Dhan credentials/source not ready.")
        points -= 10

    bias_values = [
        abs(_safe_float(sig.get("option_bias", 0), 0)),
        abs(_safe_float(sig.get("price_action_bias", 0), 0)),
        abs(_safe_float(sig.get("heavyweight_bias", 0), 0)),
    ]
    if sum(1 for v in bias_values if v > 0) < 2:
        warnings.append("Less than two signal engines have meaningful bias.")
        points -= 10

    points = int(max(0, min(100, points)))
    if points >= 80 and not issues:
        label = "HEALTHY"
    elif points >= 65:
        label = "CAUTION"
    elif points >= 50:
        label = "WEAK"
    else:
        label = "UNRELIABLE"

    return {"score": points, "label": label, "issues": issues[:8], "warnings": warnings[:8]}
