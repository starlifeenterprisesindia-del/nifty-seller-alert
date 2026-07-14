"""
Nifty Seller AI — OI Flow Engine v19.14

Purpose:
Track option-chain OI movement across refreshes:
- Call Writing
- Call Unwinding
- Put Writing
- Put Unwinding
- OI migration / strike shift
- Resistance/support strengthening
- OI flow bias and confidence

No API calls.
No broker execution.
No portfolio mutation.
Session-memory based only.
"""
try:
    from option_flow_integrity import classify_option_flow
except Exception:
    classify_option_flow = None

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


def _clip(value, low=0, high=100):
    return max(low, min(high, _safe_float(value, low)))


def _rows_from_option_chain(option_chain):
    if not isinstance(option_chain, dict):
        return []
    rows = option_chain.get("rows", [])
    return rows if isinstance(rows, list) else []


def _row_value(row, *keys):
    for k in keys:
        if k in row:
            return row.get(k)
    return 0


def _normalize_snapshot(option_chain):
    rows = _rows_from_option_chain(option_chain)
    out = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        strike = _safe_int(_row_value(row, "strike", "Strike", "strikePrice"), 0)
        if strike <= 0:
            continue

        ce_oi = _safe_float(_row_value(row, "ce_oi", "CE_OI", "call_oi", "callOI", "CE OI"), 0)
        pe_oi = _safe_float(_row_value(row, "pe_oi", "PE_OI", "put_oi", "putOI", "PE OI"), 0)

        ce_chg = _safe_float(_row_value(row, "ce_oi_chg", "ce_change_oi", "call_oi_change", "CE_CHG_OI", "CE Chg OI"), 0)
        pe_chg = _safe_float(_row_value(row, "pe_oi_chg", "pe_change_oi", "put_oi_change", "PE_CHG_OI", "PE Chg OI"), 0)

        ce_ltp = _safe_float(_row_value(row, "ce_ltp", "CE_LTP", "call_ltp", "CE LTP"), 0)
        pe_ltp = _safe_float(_row_value(row, "pe_ltp", "PE_LTP", "put_ltp", "PE LTP"), 0)
        ce_price_chg = _safe_float(_row_value(row, "ce_price_change", "ce_change", "CE Price Chg"), 0)
        pe_price_chg = _safe_float(_row_value(row, "pe_price_change", "pe_change", "PE Price Chg"), 0)
        ce_price_pct = _safe_float(_row_value(row, "ce_price_change_pct", "ce_change_pct", "CE Price Chg %"), 0)
        pe_price_pct = _safe_float(_row_value(row, "pe_price_change_pct", "pe_change_pct", "PE Price Chg %"), 0)

        ce_vol = _safe_float(_row_value(row, "ce_volume", "ce_vol", "call_volume", "CE Volume"), 0)
        pe_vol = _safe_float(_row_value(row, "pe_volume", "pe_vol", "put_volume", "PE Volume"), 0)

        out[strike] = {
            "strike": strike,
            "ce_oi": ce_oi,
            "pe_oi": pe_oi,
            "ce_chg": ce_chg,
            "pe_chg": pe_chg,
            "ce_ltp": ce_ltp,
            "pe_ltp": pe_ltp,
            "ce_price_chg": ce_price_chg,
            "pe_price_chg": pe_price_chg,
            "ce_price_pct": ce_price_pct,
            "pe_price_pct": pe_price_pct,
            "ce_volume": ce_vol,
            "pe_volume": pe_vol,
        }

    return out


def _top_by(data, key, reverse=True, limit=5):
    rows = list(data.values())
    rows.sort(key=lambda x: _safe_float(x.get(key, 0)), reverse=reverse)
    return rows[:limit]


def _legacy_code(side, flow_code):
    side = str(side).upper()
    code = str(flow_code or "").upper().replace(f"{side}_", "")
    prefix = "CALL" if side == "CE" else "PUT"
    return {
        "LONG_BUILDUP": f"{prefix}_LONG_BUILDUP",
        "WRITING": f"{prefix}_WRITING",
        "SHORT_COVERING": f"{prefix}_SHORT_COVERING",
        "LONG_UNWINDING": f"{prefix}_LONG_UNWINDING",
    }.get(code, f"{prefix}_NEUTRAL")


def _classify(prev, cur, market_open=True):
    """Classify with matching snapshot or day deltas; never compare LTP to zero."""
    strike = cur.get("strike")
    prev = prev or {}
    has_prev = bool(prev)
    basis = "SNAPSHOT" if has_prev else ("DAY_CHANGE" if market_open else "PREOPEN_REFERENCE")

    if has_prev:
        ce_oi_delta = _safe_float(cur.get("ce_oi")) - _safe_float(prev.get("ce_oi"))
        pe_oi_delta = _safe_float(cur.get("pe_oi")) - _safe_float(prev.get("pe_oi"))
        ce_price_delta = _safe_float(cur.get("ce_ltp")) - _safe_float(prev.get("ce_ltp"))
        pe_price_delta = _safe_float(cur.get("pe_ltp")) - _safe_float(prev.get("pe_ltp"))
        ce_price_pct = (ce_price_delta / abs(_safe_float(prev.get("ce_ltp"), 0)) * 100.0) if _safe_float(prev.get("ce_ltp"), 0) else 0.0
        pe_price_pct = (pe_price_delta / abs(_safe_float(prev.get("pe_ltp"), 0)) * 100.0) if _safe_float(prev.get("pe_ltp"), 0) else 0.0
        ce_oi_pct = (ce_oi_delta / abs(_safe_float(prev.get("ce_oi"), 0)) * 100.0) if _safe_float(prev.get("ce_oi"), 0) else 0.0
        pe_oi_pct = (pe_oi_delta / abs(_safe_float(prev.get("pe_oi"), 0)) * 100.0) if _safe_float(prev.get("pe_oi"), 0) else 0.0
    else:
        ce_oi_delta, pe_oi_delta = _safe_float(cur.get("ce_chg")), _safe_float(cur.get("pe_chg"))
        ce_price_delta, pe_price_delta = _safe_float(cur.get("ce_price_chg")), _safe_float(cur.get("pe_price_chg"))
        ce_price_pct, pe_price_pct = _safe_float(cur.get("ce_price_pct")), _safe_float(cur.get("pe_price_pct"))
        if abs(ce_price_delta) < 1e-9 and abs(ce_price_pct) > 1e-9 and (100.0 + ce_price_pct) > 1e-6:
            ce_previous = _safe_float(cur.get("ce_ltp")) / (1.0 + ce_price_pct / 100.0)
            ce_price_delta = _safe_float(cur.get("ce_ltp")) - ce_previous
        if abs(pe_price_delta) < 1e-9 and abs(pe_price_pct) > 1e-9 and (100.0 + pe_price_pct) > 1e-6:
            pe_previous = _safe_float(cur.get("pe_ltp")) / (1.0 + pe_price_pct / 100.0)
            pe_price_delta = _safe_float(cur.get("pe_ltp")) - pe_previous
        ce_oi_pct = (ce_oi_delta / max(abs(_safe_float(cur.get("ce_oi")) - ce_oi_delta), 1.0)) * 100.0
        pe_oi_pct = (pe_oi_delta / max(abs(_safe_float(cur.get("pe_oi")) - pe_oi_delta), 1.0)) * 100.0

    if classify_option_flow is None:
        ce_result = {"flow_code": "CE_NEUTRAL", "signal": "Neutral", "evidence_ready": False}
        pe_result = {"flow_code": "PE_NEUTRAL", "signal": "Neutral", "evidence_ready": False}
    else:
        ce_result = classify_option_flow("CE", price_delta=ce_price_delta, price_pct=ce_price_pct, oi_delta=ce_oi_delta, oi_pct=ce_oi_pct, basis=basis, evidence_allowed=bool(market_open))
        pe_result = classify_option_flow("PE", price_delta=pe_price_delta, price_pct=pe_price_pct, oi_delta=pe_oi_delta, oi_pct=pe_oi_pct, basis=basis, evidence_allowed=bool(market_open))

    return {
        "strike": strike,
        "basis": basis,
        "ce_oi_delta": int(round(ce_oi_delta)), "pe_oi_delta": int(round(pe_oi_delta)),
        "ce_price_delta": round(ce_price_delta, 2), "pe_price_delta": round(pe_price_delta, 2),
        "ce_flow": _legacy_code("CE", ce_result.get("flow_code")),
        "pe_flow": _legacy_code("PE", pe_result.get("flow_code")),
        "ce_flow_label": ce_result.get("signal", "Neutral"),
        "pe_flow_label": pe_result.get("signal", "Neutral"),
        "ce_evidence_ready": bool(ce_result.get("evidence_ready", False)),
        "pe_evidence_ready": bool(pe_result.get("evidence_ready", False)),
        "ce_oi": int(round(_safe_float(cur.get("ce_oi")))), "pe_oi": int(round(_safe_float(cur.get("pe_oi")))),
        "ce_ltp": round(_safe_float(cur.get("ce_ltp")), 2), "pe_ltp": round(_safe_float(cur.get("pe_ltp")), 2),
    }


def _dominant_strike(data, side):
    key = "ce_oi" if side == "CE" else "pe_oi"
    rows = _top_by(data, key, True, 1)
    return rows[0]["strike"] if rows else 0


def _flow_score(classified_rows, atm_strike=0):
    """
    Positive = bullish / SELL PE support.
    Negative = bearish / SELL CE support.
    """
    bullish = 0.0
    bearish = 0.0
    reasons = []

    atm = _safe_float(atm_strike, 0)

    for r in classified_rows:
        strike = _safe_float(r.get("strike", 0), 0)
        proximity_weight = 1.0
        if atm > 0:
            dist = abs(strike - atm)
            if dist <= 50:
                proximity_weight = 1.35
            elif dist <= 100:
                proximity_weight = 1.20
            elif dist <= 200:
                proximity_weight = 1.0
            else:
                proximity_weight = 0.65

        ce_delta = max(0, _safe_float(r.get("ce_oi_delta", 0)))
        pe_delta = max(0, _safe_float(r.get("pe_oi_delta", 0)))

        if r.get("ce_flow") == "CALL_WRITING":
            bearish += min(100, ce_delta / 10000) * proximity_weight
            reasons.append(f"{int(strike)} CE call writing.")
        elif r.get("ce_flow") == "CALL_SHORT_COVERING":
            bullish += min(100, abs(_safe_float(r.get("ce_oi_delta", 0))) / 10000) * proximity_weight
            reasons.append(f"{int(strike)} CE short covering.")

        if r.get("pe_flow") == "PUT_WRITING":
            bullish += min(100, pe_delta / 10000) * proximity_weight
            reasons.append(f"{int(strike)} PE put writing.")
        elif r.get("pe_flow") == "PUT_SHORT_COVERING":
            bearish += min(100, abs(_safe_float(r.get("pe_oi_delta", 0))) / 10000) * proximity_weight
            reasons.append(f"{int(strike)} PE short covering.")

    net = bullish - bearish
    if net >= 15:
        bias = "SELL PE"
    elif net <= -15:
        bias = "SELL CE"
    else:
        bias = "WAIT"

    confidence = int(round(_clip(abs(net) * 2.5, 0, 95)))

    return {
        "bias": bias,
        "net_flow": int(round(net)),
        "bullish_flow": int(round(bullish)),
        "bearish_flow": int(round(bearish)),
        "confidence": confidence,
        "reasons": reasons[:8],
    }


def update_oi_flow(
    previous_state,
    option_chain,
    timestamp="",
    max_history=20,
):
    previous_state = previous_state if isinstance(previous_state, dict) else {}
    current_map = _normalize_snapshot(option_chain)
    prev_map = previous_state.get("last_map", {}) if isinstance(previous_state.get("last_map", {}), dict) else {}
    history = previous_state.get("history", []) if isinstance(previous_state.get("history", []), list) else []

    atm_strike = _safe_int(option_chain.get("atm_strike", 0) if isinstance(option_chain, dict) else 0, 0)
    pcr = _safe_float(option_chain.get("pcr", 0) if isinstance(option_chain, dict) else 0, 0)

    market_open = bool(option_chain.get("_market_open", True)) if isinstance(option_chain, dict) else True
    classified = []
    for strike, cur in current_map.items():
        prev = prev_map.get(strike, {})
        classified.append(_classify(prev, cur, market_open=market_open))

    classified.sort(key=lambda x: abs(_safe_int(x.get("ce_oi_delta", 0))) + abs(_safe_int(x.get("pe_oi_delta", 0))), reverse=True)

    call_writing = [x for x in classified if x.get("ce_flow") == "CALL_WRITING"]
    call_unwinding = [x for x in classified if x.get("ce_flow") in {"CALL_SHORT_COVERING", "CALL_LONG_UNWINDING"}]
    put_writing = [x for x in classified if x.get("pe_flow") == "PUT_WRITING"]
    put_unwinding = [x for x in classified if x.get("pe_flow") in {"PUT_SHORT_COVERING", "PUT_LONG_UNWINDING"}]

    ce_dom = _dominant_strike(current_map, "CE")
    pe_dom = _dominant_strike(current_map, "PE")
    prev_ce_dom = previous_state.get("dominant_ce_strike", 0)
    prev_pe_dom = previous_state.get("dominant_pe_strike", 0)

    ce_shift = _safe_int(ce_dom, 0) - _safe_int(prev_ce_dom, 0) if prev_ce_dom else 0
    pe_shift = _safe_int(pe_dom, 0) - _safe_int(prev_pe_dom, 0) if prev_pe_dom else 0

    flow = _flow_score(classified[:12], atm_strike=atm_strike)

    migration_notes = []
    if ce_shift:
        migration_notes.append(f"Dominant CE OI shifted {prev_ce_dom} → {ce_dom} ({ce_shift:+d}).")
    if pe_shift:
        migration_notes.append(f"Dominant PE OI shifted {prev_pe_dom} → {pe_dom} ({pe_shift:+d}).")

    # Build support/resistance interpretation
    resistance_strength = int(round(_clip(sum(max(0, x.get("ce_oi_delta", 0)) for x in call_writing[:5]) / 20000, 0, 100)))
    support_strength = int(round(_clip(sum(max(0, x.get("pe_oi_delta", 0)) for x in put_writing[:5]) / 20000, 0, 100)))

    warnings = []
    positives = []

    if resistance_strength >= 60:
        positives.append("Call writing resistance strong ho rahi hai.")
    if support_strength >= 60:
        positives.append("Put writing support strong ho rahi hai.")
    if call_unwinding and flow["bias"] == "SELL CE":
        warnings.append("CE sell bias ke against call unwinding bhi aa rahi hai.")
    if put_unwinding and flow["bias"] == "SELL PE":
        warnings.append("PE sell bias ke against put unwinding bhi aa rahi hai.")
    if abs(ce_shift) >= 100:
        warnings.append("Dominant CE strike migration noticeable hai.")
    if abs(pe_shift) >= 100:
        warnings.append("Dominant PE strike migration noticeable hai.")

    summary = (
        f"OI Flow Bias: {flow['bias']} | Net Flow {flow['net_flow']} | "
        f"Support {support_strength}/100 | Resistance {resistance_strength}/100."
    )

    row = {
        "timestamp": timestamp,
        "bias": flow["bias"],
        "net_flow": flow["net_flow"],
        "confidence": flow["confidence"],
        "dominant_ce": ce_dom,
        "dominant_pe": pe_dom,
        "atm": atm_strike,
        "pcr": round(pcr, 3),
        "support_strength": support_strength,
        "resistance_strength": resistance_strength,
    }

    # Avoid duplicate unchanged history rows
    if history:
        last = history[-1]
        if (
            last.get("bias") == row.get("bias")
            and last.get("net_flow") == row.get("net_flow")
            and last.get("dominant_ce") == row.get("dominant_ce")
            and last.get("dominant_pe") == row.get("dominant_pe")
            and last.get("atm") == row.get("atm")
        ):
            history = history[-max_history:]
        else:
            history.append(row)
    else:
        history.append(row)

    history = history[-max_history:]

    report = {
        "version": "V19.14 OI Flow Engine",
        "summary": summary,
        "bias": flow["bias"],
        "net_flow": flow["net_flow"],
        "confidence": flow["confidence"],
        "bullish_flow": flow["bullish_flow"],
        "bearish_flow": flow["bearish_flow"],
        "atm_strike": atm_strike,
        "pcr": round(pcr, 3),
        "dominant_ce_strike": ce_dom,
        "dominant_pe_strike": pe_dom,
        "ce_shift": ce_shift,
        "pe_shift": pe_shift,
        "support_strength": support_strength,
        "resistance_strength": resistance_strength,
        "call_writing": call_writing[:5],
        "call_unwinding": call_unwinding[:5],
        "put_writing": put_writing[:5],
        "put_unwinding": put_unwinding[:5],
        "top_flows": classified[:10],
        "migration_notes": migration_notes,
        "reasons": flow["reasons"],
        "positives": positives[:8],
        "warnings": warnings[:8],
        "history": history,
    }

    new_state = {
        "last_map": current_map,
        "history": history,
        "dominant_ce_strike": ce_dom,
        "dominant_pe_strike": pe_dom,
        "last_report": report,
    }

    return new_state, report
