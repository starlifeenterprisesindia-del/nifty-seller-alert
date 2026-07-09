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
            "ce_volume": ce_vol,
            "pe_volume": pe_vol,
        }

    return out


def _top_by(data, key, reverse=True, limit=5):
    rows = list(data.values())
    rows.sort(key=lambda x: _safe_float(x.get(key, 0)), reverse=reverse)
    return rows[:limit]


def _classify(prev, cur):
    """
    Classify strike-level flow using OI and premium movement.
    """
    strike = cur.get("strike")
    prev = prev or {}

    ce_oi_delta = _safe_float(cur.get("ce_oi", 0)) - _safe_float(prev.get("ce_oi", 0))
    pe_oi_delta = _safe_float(cur.get("pe_oi", 0)) - _safe_float(prev.get("pe_oi", 0))
    ce_price_delta = _safe_float(cur.get("ce_ltp", 0)) - _safe_float(prev.get("ce_ltp", 0))
    pe_price_delta = _safe_float(cur.get("pe_ltp", 0)) - _safe_float(prev.get("pe_ltp", 0))

    # If previous snapshot missing, fall back to exchange-provided OI change.
    if not prev:
        ce_oi_delta = _safe_float(cur.get("ce_chg", 0), 0)
        pe_oi_delta = _safe_float(cur.get("pe_chg", 0), 0)

    ce_label = "CALL_NEUTRAL"
    pe_label = "PUT_NEUTRAL"

    if ce_oi_delta > 0 and ce_price_delta >= 0:
        ce_label = "CALL_LONG_BUILDUP"
    elif ce_oi_delta > 0 and ce_price_delta < 0:
        ce_label = "CALL_WRITING"
    elif ce_oi_delta < 0 and ce_price_delta > 0:
        ce_label = "CALL_SHORT_COVERING"
    elif ce_oi_delta < 0 and ce_price_delta <= 0:
        ce_label = "CALL_LONG_UNWINDING"

    if pe_oi_delta > 0 and pe_price_delta >= 0:
        pe_label = "PUT_LONG_BUILDUP"
    elif pe_oi_delta > 0 and pe_price_delta < 0:
        pe_label = "PUT_WRITING"
    elif pe_oi_delta < 0 and pe_price_delta > 0:
        pe_label = "PUT_SHORT_COVERING"
    elif pe_oi_delta < 0 and pe_price_delta <= 0:
        pe_label = "PUT_LONG_UNWINDING"

    return {
        "strike": strike,
        "ce_oi_delta": int(round(ce_oi_delta)),
        "pe_oi_delta": int(round(pe_oi_delta)),
        "ce_price_delta": round(ce_price_delta, 2),
        "pe_price_delta": round(pe_price_delta, 2),
        "ce_flow": ce_label,
        "pe_flow": pe_label,
        "ce_oi": int(round(_safe_float(cur.get("ce_oi", 0)))),
        "pe_oi": int(round(_safe_float(cur.get("pe_oi", 0)))),
        "ce_ltp": round(_safe_float(cur.get("ce_ltp", 0)), 2),
        "pe_ltp": round(_safe_float(cur.get("pe_ltp", 0)), 2),
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

    classified = []
    for strike, cur in current_map.items():
        prev = prev_map.get(strike, {})
        classified.append(_classify(prev, cur))

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
