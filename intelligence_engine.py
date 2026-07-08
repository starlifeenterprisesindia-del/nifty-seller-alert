"""
Nifty Seller AI — Intelligence Engine v19.11

Purpose:
- Read outputs from Snapshot Engine, AI Brain, Risk Engine, Strategy Engine and Decision Engine.
- Produce explainable market intelligence:
  - Market context
  - Signal reliability
  - Conflict detection
  - Fake-move risk
  - Trade quality
  - Human-readable explanation

No API calls.
No broker execution.
No portfolio mutation.
Decision Engine remains final execution authority.
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


def _label(score):
    score = _clip(score)
    if score >= 85:
        return "EXCELLENT"
    if score >= 72:
        return "STRONG"
    if score >= 60:
        return "GOOD"
    if score >= 45:
        return "WEAK"
    return "POOR"


def _bias_direction(value):
    value = _safe_float(value, 0)
    if value >= 20:
        return "BULLISH"
    if value <= -20:
        return "BEARISH"
    return "NEUTRAL"


def _direction_for_action(action):
    action = str(action or "WAIT").upper()
    if action == "SELL PE":
        return "BULLISH"
    if action == "SELL CE":
        return "BEARISH"
    return "NEUTRAL"


def _support_score(signal_direction, desired_direction, strength):
    strength = _clip(abs(strength))
    if desired_direction == "NEUTRAL":
        return 45
    if signal_direction == desired_direction:
        return min(100, 50 + strength * 0.5)
    if signal_direction == "NEUTRAL":
        return 45
    return max(0, 45 - strength * 0.35)


def _market_context(snapshot, ai_report, risk_report):
    ai_report = ai_report if isinstance(ai_report, dict) else {}
    risk_report = risk_report if isinstance(risk_report, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}

    regime = str(ai_report.get("regime", "") or "").upper()
    risk_grade = str(risk_report.get("risk_grade", "") or "").upper()
    signals = snapshot.get("signals", {}) if isinstance(snapshot.get("signals", {}), dict) else {}
    risk = snapshot.get("risk", {}) if isinstance(snapshot.get("risk", {}), dict) else {}

    option_bias = _safe_float(signals.get("option_bias", 0))
    price_bias = _safe_float(signals.get("price_action_bias", 0))
    heavy_bias = _safe_float(signals.get("heavyweight_bias", 0))
    news_risk = _safe_float(risk.get("news_risk", 0))
    gamma_risk = _safe_float(risk.get("gamma_risk", 0))
    shock_risk = _safe_float(risk.get("shock_risk", 0))

    aligned_bear = option_bias <= -35 and price_bias <= -25 and heavy_bias <= -25
    aligned_bull = option_bias >= 35 and price_bias >= 25 and heavy_bias >= 25

    if news_risk >= 75:
        return "NEWS DRIVEN", "News/event risk is dominating normal signals."
    if gamma_risk >= 75:
        return "EXPIRY / GAMMA", "Gamma pressure is high; seller risk can change quickly."
    if shock_risk >= 75 or risk_grade in {"HIGH", "CRITICAL"}:
        return "HIGH RISK", "Shock or composite risk is elevated."
    if aligned_bear:
        return "TRENDING BEAR", "Option chain, price action and heavyweights support bearish pressure."
    if aligned_bull:
        return "TRENDING BULL", "Option chain, price action and heavyweights support bullish pressure."
    if regime:
        return regime, ai_report.get("regime_reason", "AI Brain regime classification.")
    return "MIXED", "Market signals are not fully aligned."


def build_intelligence_report(
    snapshot,
    ai_report=None,
    risk_report=None,
    strategy_report=None,
    decision_report=None,
):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    ai_report = ai_report if isinstance(ai_report, dict) else {}
    risk_report = risk_report if isinstance(risk_report, dict) else {}
    strategy_report = strategy_report if isinstance(strategy_report, dict) else {}
    decision_report = decision_report if isinstance(decision_report, dict) else {}

    signals = snapshot.get("signals", {}) if isinstance(snapshot.get("signals", {}), dict) else {}
    risk = snapshot.get("risk", {}) if isinstance(snapshot.get("risk", {}), dict) else {}
    oc = snapshot.get("option_chain", {}) if isinstance(snapshot.get("option_chain", {}), dict) else {}

    analysis_action = str(decision_report.get("analysis_action", "WAIT") or "WAIT").upper()
    final_action = str(decision_report.get("final_action", "WAIT") or "WAIT").upper()
    execution_status = str(decision_report.get("execution_status", "WAIT") or "WAIT").upper()
    desired_direction = _direction_for_action(analysis_action)

    signal_items = [
        ("Option Chain", _safe_float(signals.get("option_bias", 0)), 0.28),
        ("Price Action", _safe_float(signals.get("price_action_bias", 0)), 0.24),
        ("Heavyweights", _safe_float(signals.get("heavyweight_bias", 0)), 0.22),
        ("Market Bias", _safe_float(signals.get("market_bias", 0)), 0.10),
    ]

    pcr = _safe_float(oc.get("pcr", 0))
    pcr_bias = 0
    if pcr >= 1.20:
        pcr_bias = 25
    elif 0 < pcr <= 0.85:
        pcr_bias = -25
    signal_items.append(("PCR", pcr_bias, 0.08))

    # Risk cleanliness acts as a signal.
    risk_score = _safe_float(risk_report.get("risk_score", 100))
    safety_score = _safe_float(risk_report.get("safety_score", 0))
    signal_items.append(("Risk Cleanliness", safety_score - 50, 0.08))

    reliability_rows = []
    weighted_total = 0.0
    weight_sum = 0.0
    bullish_votes = 0
    bearish_votes = 0
    neutral_votes = 0

    for name, raw_bias, weight in signal_items:
        direction = _bias_direction(raw_bias)
        if direction == "BULLISH":
            bullish_votes += 1
        elif direction == "BEARISH":
            bearish_votes += 1
        else:
            neutral_votes += 1

        support = _support_score(direction, desired_direction, raw_bias)
        weighted_total += support * weight
        weight_sum += weight

        reliability_rows.append({
            "signal": name,
            "bias": int(round(raw_bias)),
            "direction": direction,
            "support_score": int(round(support)),
            "weight": weight,
            "label": _label(support),
        })

    signal_reliability = int(round(_clip(weighted_total / max(weight_sum, 0.01))))

    # Conflict detection
    conflicts = []
    option_dir = _bias_direction(signals.get("option_bias", 0))
    price_dir = _bias_direction(signals.get("price_action_bias", 0))
    heavy_dir = _bias_direction(signals.get("heavyweight_bias", 0))

    if option_dir != "NEUTRAL" and price_dir != "NEUTRAL" and option_dir != price_dir:
        conflicts.append("Option chain and price action are opposite.")
    if heavy_dir != "NEUTRAL" and desired_direction != "NEUTRAL" and heavy_dir != desired_direction:
        conflicts.append("Heavyweights do not support the analysis direction.")
    if pcr > 1.65 and desired_direction == "BULLISH":
        conflicts.append("PCR looks overheated for fresh bullish premium selling.")
    if 0 < pcr < 0.75 and desired_direction == "BEARISH":
        conflicts.append("PCR already bearish; CE sell may be late if move is extended.")
    if risk_score >= 70:
        conflicts.append("Composite risk is high.")
    if risk.get("news_risk", 0) and _safe_float(risk.get("news_risk", 0)) >= 70:
        conflicts.append("News/event risk is elevated.")
    if decision_report.get("direction_conflict"):
        conflicts.append("Decision Engine detected direction conflict.")

    conflict_score = int(round(_clip(len(conflicts) * 22)))

    # Fake move / trap risk
    fake_move_risk = 0
    fake_reasons = []

    if option_dir != "NEUTRAL" and price_dir != "NEUTRAL" and option_dir != price_dir:
        fake_move_risk += 32
        fake_reasons.append("OI/Option bias and price action disagree.")
    if heavy_dir != "NEUTRAL" and desired_direction != "NEUTRAL" and heavy_dir != desired_direction:
        fake_move_risk += 24
        fake_reasons.append("Heavyweights are not confirming the direction.")
    if risk_score >= 60:
        fake_move_risk += 15
        fake_reasons.append("Risk environment is not fully clean.")
    if execution_status in {"BLOCKED", "PREVIEW_ONLY"} and analysis_action != "WAIT":
        fake_move_risk += 12
        fake_reasons.append("Execution gates are not fully open.")
    if pcr > 1.8 or (0 < pcr < 0.65):
        fake_move_risk += 12
        fake_reasons.append("PCR is extreme; trap probability increases.")

    fake_move_risk = int(round(_clip(fake_move_risk)))

    # Trade quality: combine intelligence evidence + decision + risk + plan.
    decision_conf = _safe_float(decision_report.get("calibrated_confidence", 0))
    trade_quality = _safe_float(ai_report.get("trade_quality_score", 0))
    plan_valid = bool(strategy_report.get("valid", False))
    plan_bonus = 8 if plan_valid else -18
    execution_bonus = {
        "APPROVED": 8,
        "PREVIEW_ONLY": -5,
        "BLOCKED": -18,
        "WAIT": -10,
    }.get(execution_status, -10)

    intelligence_score = (
        signal_reliability * 0.30
        + decision_conf * 0.22
        + trade_quality * 0.18
        + safety_score * 0.16
        + (100 - conflict_score) * 0.08
        + (100 - fake_move_risk) * 0.06
        + plan_bonus
        + execution_bonus
    )
    intelligence_score = int(round(_clip(intelligence_score)))

    if intelligence_score >= 85:
        quality_label = "INSTITUTIONAL GRADE"
    elif intelligence_score >= 72:
        quality_label = "HIGH QUALITY"
    elif intelligence_score >= 60:
        quality_label = "MODERATE"
    elif intelligence_score >= 45:
        quality_label = "WEAK / WAIT PREFERRED"
    else:
        quality_label = "AVOID"

    market_context, context_reason = _market_context(snapshot, ai_report, risk_report)

    positives = []
    negatives = []

    if signal_reliability >= 70:
        positives.append(f"Signal reliability is strong: {signal_reliability}/100.")
    else:
        negatives.append(f"Signal reliability is not strong: {signal_reliability}/100.")

    if decision_conf >= 70:
        positives.append(f"Decision confidence is supportive: {int(round(decision_conf))}%.")
    else:
        negatives.append(f"Decision confidence is weak/moderate: {int(round(decision_conf))}%.")

    if safety_score >= 60:
        positives.append(f"Risk safety score is acceptable: {int(round(safety_score))}/100.")
    else:
        negatives.append(f"Risk safety score is weak: {int(round(safety_score))}/100.")

    if plan_valid:
        positives.append("Strategy plan has valid strike, hedge, entry, SL and target.")
    else:
        negatives.append("Strategy plan is incomplete or not execution-ready.")

    if conflicts:
        negatives.extend(conflicts[:4])
    if fake_move_risk >= 50:
        negatives.append(f"Fake-move/trap risk is elevated: {fake_move_risk}/100.")
    else:
        positives.append(f"Fake-move/trap risk is controlled: {fake_move_risk}/100.")

    if execution_status == "APPROVED":
        verdict_summary = (
            f"{analysis_action} is approved by Decision Engine, with {quality_label.lower()} intelligence quality."
        )
    elif execution_status == "PREVIEW_ONLY":
        verdict_summary = (
            f"{analysis_action} is an analytical preview only; market is not open for fresh entry."
        )
    elif execution_status == "BLOCKED":
        verdict_summary = (
            f"{analysis_action} bias exists, but execution is blocked by Decision Engine."
        )
    else:
        verdict_summary = "WAIT is preferred because no clean execution setup is approved."

    return {
        "version": "V19.11 Intelligence Engine",
        "market_context": market_context,
        "context_reason": context_reason,
        "analysis_action": analysis_action,
        "final_action": final_action,
        "execution_status": execution_status,
        "signal_reliability": signal_reliability,
        "conflict_score": conflict_score,
        "fake_move_risk": fake_move_risk,
        "intelligence_score": intelligence_score,
        "quality_label": quality_label,
        "reliability_rows": reliability_rows,
        "vote_summary": {
            "bullish": bullish_votes,
            "bearish": bearish_votes,
            "neutral": neutral_votes,
        },
        "conflicts": conflicts[:8],
        "fake_move_reasons": fake_reasons[:8],
        "positives": positives[:8],
        "negatives": negatives[:8],
        "verdict_summary": verdict_summary,
    }
