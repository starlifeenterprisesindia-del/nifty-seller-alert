"""
Nifty Seller AI — Risk Engine Module v19.5

Purpose:
- Read an already-built market snapshot.
- Calculate one explainable risk report.
- Produce risk grade, safety score, warnings and hard blockers.
- No API calls. No refresh logic. No portfolio mutation.
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


def _risk_grade(risk_score):
    score = _clip(risk_score)
    if score >= 85:
        return "CRITICAL"
    if score >= 70:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    if score >= 30:
        return "LOW"
    return "VERY LOW"


def _safety_label(safety_score):
    score = _clip(safety_score)
    if score >= 85:
        return "EXCELLENT"
    if score >= 72:
        return "GOOD"
    if score >= 60:
        return "CAUTION"
    if score >= 45:
        return "WEAK"
    return "UNSAFE"


def build_risk_report(snapshot, snapshot_health=None, snapshot_delta=None, ai_report=None):
    """
    Build one final risk report from snapshot inputs.

    Output:
    - risk_score: 0..100 (higher = more dangerous)
    - safety_score: 0..100 (higher = safer)
    - grade / label
    - hard_blockers
    - warnings
    - components
    - reasons
    """
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    snapshot_health = snapshot_health if isinstance(snapshot_health, dict) else {}
    snapshot_delta = snapshot_delta if isinstance(snapshot_delta, dict) else {}
    ai_report = ai_report if isinstance(ai_report, dict) else {}

    risk = snapshot.get("risk", {}) if isinstance(snapshot.get("risk", {}), dict) else {}
    market = snapshot.get("market", {}) if isinstance(snapshot.get("market", {}), dict) else {}
    option_chain = snapshot.get("option_chain", {}) if isinstance(snapshot.get("option_chain", {}), dict) else {}
    signals = snapshot.get("signals", {}) if isinstance(snapshot.get("signals", {}), dict) else {}
    source_health = snapshot.get("source_health", {}) if isinstance(snapshot.get("source_health", {}), dict) else {}

    seller_risk = _clip(risk.get("seller_risk", 100))
    news_risk = _clip(risk.get("news_risk", 0))
    gamma_risk = _clip(risk.get("gamma_risk", 0))
    shock_risk = _clip(risk.get("shock_risk", 0))
    data_quality = _clip(risk.get("data_quality", 0))
    expiry_mode = str(risk.get("expiry_mode", "") or "").upper()

    vix_change_pct = _safe_float(market.get("vix_change_pct", 0))
    nifty_change_pct = abs(_safe_float(market.get("nifty_change_pct", 0)))
    pcr = _safe_float(option_chain.get("pcr", 0))
    option_ok = bool(option_chain.get("success", False))
    rows_count = _safe_int(option_chain.get("rows_count", 0))
    dhan_ready = bool(source_health.get("dhan_ready", False))
    conflict_mode = bool(signals.get("conflict_mode", False))

    snapshot_health_score = _clip(snapshot_health.get("score", data_quality))
    material_change = _clip(snapshot_delta.get("material_change", 0))

    regime = str(ai_report.get("regime", "") or "")
    alignment_score = _clip(ai_report.get("alignment_score", 0))
    trade_quality = _clip(ai_report.get("trade_quality_score", 0))

    # Expiry risk
    expiry_risk = 18
    if "EXPIRY" in expiry_mode:
        expiry_risk = 82
    elif "NEAR EXPIRY" in expiry_mode:
        expiry_risk = 58
    if regime == "EXPIRY / GAMMA":
        expiry_risk = max(expiry_risk, 75)

    # Volatility risk
    volatility_risk = 15
    if vix_change_pct >= 8:
        volatility_risk = 90
    elif vix_change_pct >= 5:
        volatility_risk = 75
    elif vix_change_pct >= 2:
        volatility_risk = 55
    elif nifty_change_pct >= 1.2:
        volatility_risk = 65
    elif nifty_change_pct >= 0.8:
        volatility_risk = 48

    # Data/source risk
    data_risk = 100 - data_quality
    if snapshot_health_score < 60:
        data_risk = max(data_risk, 75)
    if not option_ok:
        data_risk = max(data_risk, 88)
    if rows_count < 5:
        data_risk = max(data_risk, 75)
    if not dhan_ready:
        data_risk = max(data_risk, 60)

    # Conflict risk
    conflict_risk = 15
    if conflict_mode:
        conflict_risk = 78
    elif alignment_score and alignment_score < 45:
        conflict_risk = 65
    elif alignment_score and alignment_score < 60:
        conflict_risk = 48

    # PCR sanity risk
    pcr_risk = 15
    if pcr <= 0:
        pcr_risk = 60
    elif pcr < 0.55 or pcr > 2.20:
        pcr_risk = 72
    elif pcr < 0.75 or pcr > 1.65:
        pcr_risk = 45

    # Sudden change risk
    change_risk = 20
    if material_change >= 75:
        change_risk = 78
    elif material_change >= 55:
        change_risk = 62
    elif material_change >= 35:
        change_risk = 45

    components = {
        "seller_risk": int(round(seller_risk)),
        "news_risk": int(round(news_risk)),
        "gamma_risk": int(round(gamma_risk)),
        "shock_risk": int(round(shock_risk)),
        "expiry_risk": int(round(expiry_risk)),
        "volatility_risk": int(round(volatility_risk)),
        "data_risk": int(round(_clip(data_risk))),
        "conflict_risk": int(round(conflict_risk)),
        "pcr_risk": int(round(pcr_risk)),
        "material_change_risk": int(round(change_risk)),
    }

    # Weighted final risk score
    weights = {
        "seller_risk": 0.18,
        "news_risk": 0.12,
        "gamma_risk": 0.14,
        "shock_risk": 0.12,
        "expiry_risk": 0.10,
        "volatility_risk": 0.08,
        "data_risk": 0.12,
        "conflict_risk": 0.08,
        "pcr_risk": 0.03,
        "material_change_risk": 0.03,
    }

    risk_score = sum(components[k] * weights[k] for k in weights)
    risk_score = int(round(_clip(risk_score)))
    safety_score = int(round(_clip(100 - risk_score)))

    hard_blockers = []
    warnings = []
    reasons = []

    # Hard blockers: only strong, explainable conditions
    if data_quality < 55:
        hard_blockers.append(f"Data quality too weak: {data_quality:.0f}/100.")
    if snapshot_health_score < 50:
        hard_blockers.append(f"Snapshot health unreliable: {snapshot_health_score:.0f}/100.")
    if not option_ok:
        hard_blockers.append("Live option-chain not confirmed.")
    if gamma_risk >= 88:
        hard_blockers.append(f"Gamma risk critical: {gamma_risk:.0f}/100.")
    if news_risk >= 90:
        hard_blockers.append(f"News/Event risk critical: {news_risk:.0f}/100.")
    if shock_risk >= 92:
        hard_blockers.append(f"Shock risk extreme: {shock_risk:.0f}/100.")
    if seller_risk >= 90:
        hard_blockers.append(f"Seller risk extreme: {seller_risk:.0f}/100.")
    if risk_score >= 85:
        hard_blockers.append(f"Composite risk critical: {risk_score}/100.")

    # Warnings
    if data_quality < 70:
        warnings.append(f"Data quality caution: {data_quality:.0f}/100.")
    if snapshot_health_score < 70:
        warnings.append(f"Snapshot health caution: {snapshot_health_score:.0f}/100.")
    if gamma_risk >= 70:
        warnings.append(f"Gamma risk elevated: {gamma_risk:.0f}/100.")
    if news_risk >= 70:
        warnings.append(f"News risk elevated: {news_risk:.0f}/100.")
    if shock_risk >= 70:
        warnings.append(f"Shock risk elevated: {shock_risk:.0f}/100.")
    if conflict_risk >= 65:
        warnings.append("Signal conflict risk is high.")
    if pcr_risk >= 65:
        warnings.append(f"PCR is extreme/unreliable for aggressive action: {pcr:.2f}.")
    if material_change >= 70:
        warnings.append(f"Market changed materially: {material_change:.0f}/100.")
    if expiry_risk >= 75:
        warnings.append("Expiry/Gamma environment requires smaller size and faster protection.")
    if volatility_risk >= 70:
        warnings.append("Volatility risk elevated.")

    # Positive reasons
    if data_quality >= 80:
        reasons.append(f"Data quality strong: {data_quality:.0f}/100.")
    if snapshot_health_score >= 80:
        reasons.append(f"Snapshot health strong: {snapshot_health_score:.0f}/100.")
    if news_risk < 40:
        reasons.append(f"News risk controlled: {news_risk:.0f}/100.")
    if gamma_risk < 45:
        reasons.append(f"Gamma risk controlled: {gamma_risk:.0f}/100.")
    if shock_risk < 45:
        reasons.append(f"Shock risk controlled: {shock_risk:.0f}/100.")
    if alignment_score >= 70:
        reasons.append(f"Signal alignment supportive: {alignment_score:.0f}/100.")
    if trade_quality >= 72:
        reasons.append(f"Trade quality supportive: {trade_quality:.0f}/100.")

    # Risk grade
    grade = _risk_grade(risk_score)
    safety_label = _safety_label(safety_score)

    # Decision guidance from risk only; never chooses direction.
    if hard_blockers:
        guidance = "BLOCK TRADE"
    elif risk_score >= 70:
        guidance = "WAIT / REDUCE SIZE"
    elif risk_score >= 50:
        guidance = "CAUTION / SMALL SIZE"
    else:
        guidance = "RISK ACCEPTABLE"

    return {
        "version": "V19.5 Risk Engine Module",
        "risk_score": risk_score,
        "safety_score": safety_score,
        "risk_grade": grade,
        "safety_label": safety_label,
        "guidance": guidance,
        "components": components,
        "weights": weights,
        "hard_blockers": hard_blockers[:10],
        "warnings": warnings[:12],
        "reasons": reasons[:10],
        "context": {
            "snapshot_health": int(round(snapshot_health_score)),
            "material_change": int(round(material_change)),
            "regime": regime,
            "alignment_score": int(round(alignment_score)),
            "trade_quality": int(round(trade_quality)),
            "pcr": round(pcr, 3),
        },
    }
