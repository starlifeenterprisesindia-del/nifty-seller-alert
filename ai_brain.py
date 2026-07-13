"""
Nifty Seller AI — AI Brain Module v19.4 / V50.8 integrity fix

This module reads a market snapshot and produces explainable AI scoring.
It does not fetch data and does not modify portfolio/refresh/DhanHQ logic.
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


def detect_market_regime(snapshot):
    signals = snapshot.get("signals", {}) if isinstance(snapshot.get("signals", {}), dict) else {}
    risk = snapshot.get("risk", {}) if isinstance(snapshot.get("risk", {}), dict) else {}

    news_risk = _safe_float(risk.get("news_risk", 0))
    gamma_risk = _safe_float(risk.get("gamma_risk", 0))
    shock_risk = _safe_float(risk.get("shock_risk", 0))
    seller_risk = _safe_float(risk.get("seller_risk", 0))
    option_bias = _safe_float(signals.get("option_bias", 0))
    price_bias = _safe_float(signals.get("price_action_bias", 0))
    heavy_bias = _safe_float(signals.get("heavyweight_bias", 0))
    expiry_mode = str(risk.get("expiry_mode", "")).upper()

    if news_risk >= 75:
        return "NEWS DRIVEN", "High news/event risk is dominating normal signals."
    if gamma_risk >= 75 or "EXPIRY" in expiry_mode:
        return "EXPIRY / GAMMA", "Expiry/gamma risk requires extra safety."
    if shock_risk >= 70 or seller_risk >= 72:
        return "VOLATILE", "Shock/seller risk is elevated."
    if abs(option_bias) >= 45 and abs(price_bias) >= 35 and (option_bias * price_bias) > 0:
        return "TRENDING", "Option chain and price action are aligned."
    if abs(price_bias) <= 25 and abs(option_bias) <= 35 and abs(heavy_bias) <= 30:
        return "RANGE / NO EDGE", "Major signals are mixed or flat."
    return "MIXED", "Market is not clean enough for aggressive confidence."


def direction_alignment(snapshot, action):
    action = str(action or "WAIT").upper()
    if action == "SELL PE" or "BUY CALL" in action:
        direction = 1
    elif action == "SELL CE" or "BUY PUT" in action:
        direction = -1
    else:
        return 0, [{"engine": "Decision", "score": 0, "note": "WAIT has no directional alignment requirement."}]

    signals = snapshot.get("signals", {}) if isinstance(snapshot.get("signals", {}), dict) else {}
    components = [
        ("Option Chain", _safe_float(signals.get("option_bias", 0)), 0.36),
        ("Price Action", _safe_float(signals.get("price_action_bias", 0)), 0.28),
        ("Heavyweights", _safe_float(signals.get("heavyweight_bias", 0)), 0.24),
        ("Market Bias", _safe_float(signals.get("market_bias", 0)), 0.12),
    ]

    support = 0.0
    weight_sum = 0.0
    notes = []
    for name, bias, weight in components:
        weight_sum += weight
        signed = bias * direction
        if signed >= 45:
            score = 100
            note = f"{name} strongly supports action."
        elif signed >= 20:
            score = 75
            note = f"{name} supports action."
        elif signed >= -15:
            score = 45
            note = f"{name} is neutral/mixed."
        else:
            score = 10
            note = f"{name} opposes action."
        support += score * weight
        notes.append({"engine": name, "raw_bias": int(round(bias)), "score": score, "weight": weight, "note": note})

    return int(round(_clip(support / max(weight_sum, 0.01)))), notes


def snapshot_bias(snapshot):
    signals = snapshot.get("signals", {}) if isinstance(snapshot.get("signals", {}), dict) else {}
    parts = [
        ("Option", _safe_float(signals.get("option_bias", 0)), 0.36),
        ("Price", _safe_float(signals.get("price_action_bias", 0)), 0.28),
        ("Heavy", _safe_float(signals.get("heavyweight_bias", 0)), 0.24),
        ("Market", _safe_float(signals.get("market_bias", 0)), 0.12),
    ]
    bullish = 0.0
    bearish = 0.0
    notes = []
    for name, value, weight in parts:
        if value > 0:
            bullish += min(abs(value), 100) * weight
            notes.append(f"{name} bullish {value:.0f}")
        elif value < 0:
            bearish += min(abs(value), 100) * weight
            notes.append(f"{name} bearish {abs(value):.0f}")
        else:
            notes.append(f"{name} neutral")
    net = bullish - bearish
    if net >= 22:
        proposed = "SELL PE"
    elif net <= -22:
        proposed = "SELL CE"
    else:
        proposed = "WAIT"
    return {
        "proposed_action": proposed,
        "net_bias": int(round(net)),
        "bullish_power": int(round(bullish)),
        "bearish_power": int(round(bearish)),
        "notes": notes[:6],
    }


def trade_quality(snapshot, action, alignment_score, regime):
    if str(action).upper() == "WAIT":
        return 0, "NO TRADE"

    risk = snapshot.get("risk", {}) if isinstance(snapshot.get("risk", {}), dict) else {}
    data_quality = _safe_float(risk.get("data_quality", 0))
    seller_risk = _safe_float(risk.get("seller_risk", 100))
    news_risk = _safe_float(risk.get("news_risk", 100))
    gamma_risk = _safe_float(risk.get("gamma_risk", 100))
    shock_risk = _safe_float(risk.get("shock_risk", 100))

    risk_clean = max(0, 100 - (seller_risk * 0.36 + news_risk * 0.20 + gamma_risk * 0.24 + shock_risk * 0.20))
    regime_bonus = {
        "TRENDING": 10,
        "RANGE / NO EDGE": -12,
        "VOLATILE": -15,
        "NEWS DRIVEN": -25,
        "EXPIRY / GAMMA": -10,
        "MIXED": -7,
    }.get(regime, 0)

    quality = data_quality * 0.25 + alignment_score * 0.38 + risk_clean * 0.37 + regime_bonus
    quality = int(round(_clip(quality)))

    if quality >= 85:
        label = "EXCELLENT"
    elif quality >= 72:
        label = "GOOD"
    elif quality >= 60:
        label = "CAUTION"
    else:
        label = "WEAK"
    return quality, label


def build_ai_explanation(snapshot, final_decision=None):
    fd = final_decision if isinstance(final_decision, dict) else {}
    action = str(fd.get("action", snapshot.get("ai", {}).get("final_action", "WAIT"))).upper()

    regime, regime_reason = detect_market_regime(snapshot)
    bias = snapshot_bias(snapshot)
    alignment_action = action if action != "WAIT" else str(bias.get("proposed_action", "WAIT")).upper()
    alignment_score, alignment_notes = direction_alignment(snapshot, alignment_action)
    quality_score, quality_label = trade_quality(snapshot, alignment_action, alignment_score, regime)

    risk = snapshot.get("risk", {}) if isinstance(snapshot.get("risk", {}), dict) else {}
    data_quality = _safe_float(risk.get("data_quality", 0))
    seller_risk = _safe_float(risk.get("seller_risk", 100))
    news_risk = _safe_float(risk.get("news_risk", 100))
    gamma_risk = _safe_float(risk.get("gamma_risk", 100))
    shock_risk = _safe_float(risk.get("shock_risk", 100))

    risk_penalty = seller_risk * 0.20 + news_risk * 0.14 + gamma_risk * 0.16 + shock_risk * 0.12
    old_conf = _safe_float(fd.get("confidence", snapshot.get("ai", {}).get("confidence", 0)))

    if action == "WAIT":
        smart_conf = max(45, min(88, 55 + risk_penalty * 0.35 + (100 - data_quality) * 0.25))
    else:
        smart_conf = old_conf * 0.25 + data_quality * 0.20 + alignment_score * 0.32 + quality_score * 0.23 - risk_penalty * 0.10
    smart_conf = int(round(_clip(smart_conf, 0, 98)))

    scorecard = [
        {"engine": "Data Quality", "score": int(round(data_quality)), "impact": "Positive if above 70"},
        {"engine": "Alignment", "score": alignment_score, "impact": "Shows signal agreement with action"},
        {"engine": "Trade Quality", "score": quality_score, "impact": quality_label},
        {"engine": "Risk Cleanliness", "score": int(round(_clip(100 - risk_penalty))), "impact": "Higher means safer for seller"},
        {"engine": "Snapshot Bias", "score": int(round(_clip(abs(bias.get("net_bias", 0))))), "impact": bias.get("proposed_action", "WAIT")},
    ]

    reasons = [
        f"Market regime: {regime} — {regime_reason}",
        f"Snapshot AI proposes {bias.get('proposed_action')} with net bias {bias.get('net_bias')}.",
        f"Signal alignment: {alignment_score}/100.",
        f"Trade quality: {quality_score}/100 ({quality_label}).",
        f"Smart confidence estimate: {smart_conf}%.",
    ]

    decision_id = "AI-" + str(snapshot.get("created_at", "")).replace(" ", "-").replace(":", "").replace("/", "-")
    if not decision_id.strip("AI-"):
        decision_id = "AI-SNAPSHOT"

    return {
        "version": "V19.4 AI Brain Module",
        "decision_id": decision_id,
        "action": action,
        "alignment_action": alignment_action,
        "regime": regime,
        "regime_reason": regime_reason,
        "alignment_score": alignment_score,
        "alignment_notes": alignment_notes[:5],
        "snapshot_bias": bias,
        "trade_quality_score": quality_score,
        "trade_quality_label": quality_label,
        "smart_confidence": smart_conf,
        "scorecard": scorecard,
        "reasons": reasons,
    }
