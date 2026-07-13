"""
Nifty Seller AI — Snapshot Engine v20.5

Single Snapshot Authority.
It does not fetch data. It only organizes one explicit app context into one
refresh snapshot used by AI Final, Signal Reliability, Strategy Matrix and
Live Best Candidates.
"""

from datetime import datetime
import hashlib
import json


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




def _get_row_value(row, *keys, default=0):
    for key in keys:
        try:
            if key in row and row.get(key) is not None:
                return _safe_float(row.get(key), default)
        except Exception:
            pass
    return default


def _aggregate_option_rows(option_chain, option_analysis):
    """Build the only authoritative OI aggregate from the current OC rows.

    Dhan/other sources may expose both top-level totals and row-level values.
    V20.6 uses the current row payload as source-of-truth whenever rows exist,
    then compares top-level totals against it. This prevents one table using
    old totals while another table uses fresh rows.
    """
    rows = []
    try:
        rows = option_analysis.get("rows", []) or option_chain.get("rows", []) or []
    except Exception:
        rows = []
    total_call_oi = 0.0
    total_put_oi = 0.0
    call_oi_change = 0.0
    put_oi_change = 0.0
    for r in rows:
        if not isinstance(r, dict):
            continue
        total_call_oi += _get_row_value(r, "ce_oi", "call_oi", "CE_OI")
        total_put_oi += _get_row_value(r, "pe_oi", "put_oi", "PE_OI")
        call_oi_change += _get_row_value(r, "ce_oi_change", "ce_change_oi", "call_oi_change", "CE_CHG_OI")
        put_oi_change += _get_row_value(r, "pe_oi_change", "pe_change_oi", "put_oi_change", "PE_CHG_OI")
    pcr = (total_put_oi / total_call_oi) if total_call_oi else 0.0
    return {
        "rows_count": len(rows),
        "total_call_oi": int(round(total_call_oi)),
        "total_put_oi": int(round(total_put_oi)),
        "call_oi_change": int(round(call_oi_change)),
        "put_oi_change": int(round(put_oi_change)),
        "pcr": float(pcr),
        "has_rows": bool(rows),
    }


def _pct_gap(a, b):
    base = max(abs(_safe_float(a, 0)), abs(_safe_float(b, 0)), 1.0)
    return abs(_safe_float(a, 0) - _safe_float(b, 0)) / base * 100.0


def _option_bias_from_oi(call_oi_change, put_oi_change):
    base = max(abs(_safe_float(call_oi_change, 0)), abs(_safe_float(put_oi_change, 0)), 1.0)
    raw = ((_safe_float(put_oi_change, 0) - _safe_float(call_oi_change, 0)) / base) * 65.0
    return max(-100.0, min(100.0, raw))


def _compact_signature(value, length=12):
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except Exception:
        raw = str(value)
    return hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()[:length]


def _option_chain_signature(option_chain, option_analysis):
    rows = []
    source_rows = []
    try:
        source_rows = option_analysis.get("rows", []) or option_chain.get("rows", []) or []
    except Exception:
        source_rows = []
    for r in list(source_rows)[:80]:
        if not isinstance(r, dict):
            continue
        rows.append({
            "strike": r.get("strike"),
            "ce_ltp": r.get("ce_ltp"),
            "pe_ltp": r.get("pe_ltp"),
            "ce_oi": r.get("ce_oi"),
            "pe_oi": r.get("pe_oi"),
            "ce_chg": r.get("ce_oi_change", r.get("ce_change_oi")),
            "pe_chg": r.get("pe_oi_change", r.get("pe_change_oi")),
        })
    payload = {
        "source_id": option_chain.get("snapshot_id") or option_analysis.get("snapshot_id") or "",
        "fetched_at": option_analysis.get("fetched_at") or option_chain.get("fetched_at") or "",
        "expiry": option_chain.get("expiry") or option_analysis.get("expiry") or "",
        "atm": option_chain.get("atm_strike") or option_analysis.get("atm_strike") or "",
        "pcr": option_chain.get("pcr") or option_analysis.get("pcr") or "",
        "rows": rows,
    }
    return _compact_signature(payload, 14), payload

def build_market_snapshot(ctx, fmt_time_func=None):
    option_chain = ctx.get("option_chain", {}) if isinstance(ctx.get("option_chain", {}), dict) else {}
    option_analysis = ctx.get("option_analysis", {}) if isinstance(ctx.get("option_analysis", {}), dict) else {}
    heavyweight_analysis = ctx.get("heavyweight_analysis", {}) if isinstance(ctx.get("heavyweight_analysis", {}), dict) else {}
    news = ctx.get("news", {}) if isinstance(ctx.get("news", {}), dict) else {}
    final_decision_obj = ctx.get("final_decision", {}) if isinstance(ctx.get("final_decision", {}), dict) else {}
    movement = ctx.get("movement", {}) if isinstance(ctx.get("movement", {}), dict) else {}
    source_registry = ctx.get("source_registry", {}) if isinstance(ctx.get("source_registry", {}), dict) else {}

    created_at = ""
    try:
        created_at = fmt_time_func() if fmt_time_func else ""
    except Exception:
        created_at = ""

    nifty_price = _safe_float(ctx.get("price", ctx.get("nifty_price", 0)), 0)

    oi_row_aggregate = _aggregate_option_rows(option_chain, option_analysis)
    # V20.6 OI Single Source Lock: row aggregate is authoritative when rows exist.
    oc_total_call = _safe_int(option_chain.get("total_call_oi", 0), 0)
    oc_total_put = _safe_int(option_chain.get("total_put_oi", 0), 0)
    oc_call_chg = _safe_int(option_chain.get("call_oi_change", 0), 0)
    oc_put_chg = _safe_int(option_chain.get("put_oi_change", 0), 0)

    if oi_row_aggregate.get("has_rows"):
        auth_total_call_oi = oi_row_aggregate["total_call_oi"]
        auth_total_put_oi = oi_row_aggregate["total_put_oi"]
        auth_call_oi_change = oi_row_aggregate["call_oi_change"]
        auth_put_oi_change = oi_row_aggregate["put_oi_change"]
        auth_pcr = oi_row_aggregate["pcr"]
        oi_source = "current_option_chain_rows"
    else:
        auth_total_call_oi = oc_total_call
        auth_total_put_oi = oc_total_put
        auth_call_oi_change = oc_call_chg
        auth_put_oi_change = oc_put_chg
        auth_pcr = _safe_float(ctx.get("pcr", option_chain.get("pcr", 0)), 0)
        oi_source = "option_chain_totals"

    pcr_value = auth_pcr if auth_pcr > 0 else _safe_float(ctx.get("pcr", option_chain.get("pcr", 0)), 0)

    oi_mismatches = []
    if oi_row_aggregate.get("has_rows"):
        if oc_call_chg and _pct_gap(oc_call_chg, auth_call_oi_change) > 3:
            oi_mismatches.append(f"Call OI Chg top-level != rows ({oc_call_chg} vs {auth_call_oi_change})")
        if oc_put_chg and _pct_gap(oc_put_chg, auth_put_oi_change) > 3:
            oi_mismatches.append(f"Put OI Chg top-level != rows ({oc_put_chg} vs {auth_put_oi_change})")
        if oc_total_call and _pct_gap(oc_total_call, auth_total_call_oi) > 3:
            oi_mismatches.append("Call OI total top-level != rows")
        if oc_total_put and _pct_gap(oc_total_put, auth_total_put_oi) > 3:
            oi_mismatches.append("Put OI total top-level != rows")

    oc_signature, oc_payload = _option_chain_signature(option_chain, option_analysis)
    refresh_time = created_at or datetime.now().strftime("%H:%M:%S")

    snapshot = {
        "version": "V20.5 Single Snapshot Authority",
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
            "total_call_oi": int(auth_total_call_oi),
            "total_put_oi": int(auth_total_put_oi),
            "call_oi_change": int(auth_call_oi_change),
            "put_oi_change": int(auth_put_oi_change),
            "rows_count": len(option_chain.get("rows", []) or []),
            "analysis_rows_count": len(option_analysis.get("rows", []) or []),
            "fetched_at": option_analysis.get("fetched_at") or option_chain.get("fetched_at", ""),
            "source_snapshot_id": option_chain.get("snapshot_id") or option_analysis.get("snapshot_id") or "",
            "signature": oc_signature,
        },
        "signals": {
            "option_bias": _safe_float(option_analysis.get("bias", _option_bias_from_oi(auth_call_oi_change, auth_put_oi_change)), 0),
            "price_action_bias": _safe_float(ctx.get("price_action_bias", 0), 0),
            "heavyweight_bias": _safe_float(heavyweight_analysis.get("pressure", ctx.get("heavy_bias", 0)), 0),
            "smart_money_bias": _safe_float(ctx.get("smart_money_bias", 0), 0),
            "pcr_bias": _safe_float(ctx.get("pcr_bias", 0), 0),
            "market_bias": _safe_float(ctx.get("market_bias", 0), 0),
            "movement_bias": _safe_float(ctx.get("movement_bias", movement.get("movement_bias", 0)), 0),
            "movement_phase": str(movement.get("phase", "UNAVAILABLE")),
            "conflict_mode": bool(ctx.get("conflict_mode", False)),
        },
        "movement": {
            "ready": bool(movement.get("ready", False)),
            "phase": str(movement.get("phase", "UNAVAILABLE")),
            "label": str(movement.get("label", "")),
            "last_move": movement.get("last_move"),
            "move_1m": movement.get("move_1m"),
            "move_3m": movement.get("move_3m"),
            "move_5m": movement.get("move_5m"),
            "recovery_from_low": _safe_float(movement.get("recovery_from_low", 0), 0),
            "pullback_from_high": _safe_float(movement.get("pullback_from_high", 0), 0),
            "movement_bias": _safe_float(movement.get("movement_bias", 0), 0),
            "sample_count": _safe_int(movement.get("sample_count", 0), 0),
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
            "price_action_source": ctx.get("price_action_source", ""),
            "price_action_auto_ok": bool(ctx.get("price_action_auto_ok", False)),
            "price_action_usable": bool(ctx.get("price_action_direction_usable", False)),
            "vix_live_ok": bool(ctx.get("vix_live_ok", False)),
            "registry": source_registry,
        },
        "candidates": {
            "best_ce_strike": (ctx.get("best_ce") or {}).get("strike") if isinstance(ctx.get("best_ce"), dict) else None,
            "best_pe_strike": (ctx.get("best_pe") or {}).get("strike") if isinstance(ctx.get("best_pe"), dict) else None,
            "candidate_source": "current_option_chain_row",
        },
        "oi_single_source": {
            "source": oi_source,
            "available": bool(oi_row_aggregate.get("has_rows")),
            "sync_ok": bool(oi_row_aggregate.get("has_rows")) and len(oi_mismatches) == 0,
            "status": ("OK" if oi_row_aggregate.get("has_rows") and not oi_mismatches else "MISMATCH" if oi_row_aggregate.get("has_rows") else "UNKNOWN"),
            "mismatches": oi_mismatches[:6],
            "row_aggregate": oi_row_aggregate,
            "authoritative": {
                "total_call_oi": int(auth_total_call_oi),
                "total_put_oi": int(auth_total_put_oi),
                "call_oi_change": int(auth_call_oi_change),
                "put_oi_change": int(auth_put_oi_change),
                "pcr": float(pcr_value),
                "option_bias": _safe_float(option_analysis.get("bias", _option_bias_from_oi(auth_call_oi_change, auth_put_oi_change)), 0),
            },
        },
        "data_flow": {
            "refresh_time": refresh_time,
            "oc_signature": oc_signature,
            "oc_payload_id": _compact_signature(oc_payload, 10),
            "single_snapshot": True,
            "oi_single_source": True,
        },
    }

    id_payload = {
        "refresh_time": refresh_time,
        "price": snapshot["market"]["nifty_price"],
        "expiry": snapshot["option_chain"]["expiry"],
        "atm": snapshot["option_chain"]["atm_strike"],
        "oc_sig": oc_signature,
        "option_bias": snapshot["signals"]["option_bias"],
        "price_action_bias": snapshot["signals"].get("price_action_bias", 0),
        "heavyweight_bias": snapshot["signals"].get("heavyweight_bias", 0),
        "movement_bias": snapshot["signals"].get("movement_bias", 0),
        "movement_phase": snapshot["signals"].get("movement_phase", ""),
        "risk": snapshot["risk"].get("seller_risk", 0),
        "action": snapshot["ai"].get("final_action", "WAIT"),
    }
    snapshot["snapshot_id"] = "SNAP-" + _compact_signature(id_payload, 16)
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
    cur_move = current_snapshot.get("movement", {}) if isinstance(current_snapshot.get("movement", {}), dict) else {}
    prev_move = previous_snapshot.get("movement", {}) if isinstance(previous_snapshot.get("movement", {}), dict) else {}
    movement_delta = abs(_safe_float(cur_move.get("movement_bias")) - _safe_float(prev_move.get("movement_bias")))

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
    if movement_delta >= 18:
        changes.append(f"Live movement bias changed {movement_delta:.0f} points.")
    if str(cur_move.get("phase", "")) != str(prev_move.get("phase", "")):
        changes.append(f"Movement phase: {prev_move.get('phase','NA')} -> {cur_move.get('phase','NA')}.")

    material = min(100, price_delta * 0.8 + option_delta * 1.5 + heavy_delta * 1.2 + risk_delta + news_delta + movement_delta)
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
    if _safe_int(oc.get("analysis_rows_count", 0), 0) < 5:
        warnings.append("Option-analysis rows too low.")
        points -= 8
    if not oc.get("signature"):
        warnings.append("Option-chain signature missing.")
        points -= 8

    oi_lock = snapshot.get("oi_single_source", {}) if isinstance(snapshot.get("oi_single_source", {}), dict) else {}
    if oi_lock and not oi_lock.get("sync_ok", True):
        issues.append("OI single-source mismatch detected.")
        points -= 25
        for msg in (oi_lock.get("mismatches", []) or [])[:3]:
            warnings.append(str(msg))

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
    if not src.get("price_action_auto_ok", False):
        warnings.append("Automatic price action unavailable.")
        points -= 15
    if not src.get("vix_live_ok", False):
        warnings.append("India VIX is manual/fallback, not automatic.")
        points -= 8

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
