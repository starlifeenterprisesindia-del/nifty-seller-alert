"""Canonical option premium/OI flow interpretation for Nifty Seller AI V50.8.4.

This module is deliberately pure.  Both the live option department and the
legacy OI-flow history engine call the same classifier, so identical evidence
can no longer receive different labels in different parts of the app.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


_LABELS = {
    "CE": {
        "LONG_BUILDUP": "Likely Fresh CE Buying",
        "WRITING": "Likely Fresh CE Writing",
        "SHORT_COVERING": "CE Short Covering",
        "LONG_UNWINDING": "CE Long Unwinding",
        "NEUTRAL": "Neutral",
    },
    "PE": {
        "LONG_BUILDUP": "Likely Fresh PE Buying",
        "WRITING": "Likely Fresh PE Writing",
        "SHORT_COVERING": "PE Short Covering",
        "LONG_UNWINDING": "PE Long Unwinding",
        "NEUTRAL": "Neutral",
    },
}


def classify_option_flow(
    side: str,
    *,
    price_delta: Any,
    price_pct: Any = 0.0,
    oi_delta: Any,
    oi_pct: Any = 0.0,
    basis: str = "SNAPSHOT",
    volume_ratio: Any = 0.0,
    spread_pct: Any = 0.0,
    evidence_allowed: bool = True,
) -> Dict[str, Any]:
    """Classify one CE/PE leg from matching premium and OI deltas.

    The signs are conventional market inference, not proof of the identity of
    the buyer or writer.  Both premium *and* OI must have a material move.  A
    tiny zero/noise delta is returned as neutral rather than being forced into
    a directional label.
    """

    side_u = str(side or "").upper()
    if side_u not in {"CE", "PE"}:
        raise ValueError("side must be CE or PE")

    p_delta = _num(price_delta)
    p_pct = _num(price_pct)
    o_delta = _num(oi_delta)
    o_pct = _num(oi_pct)
    basis_u = str(basis or "UNKNOWN").upper()

    # Dhan option prices are quoted to paise and OI is integer contracts.  The
    # dual absolute/percentage tests suppress numerical noise without hiding a
    # meaningful move in either low-priced or very high-OI strikes.
    price_material = abs(p_delta) >= 0.05 or abs(p_pct) >= 0.05
    oi_material = abs(o_delta) >= 100 or abs(o_pct) >= 0.01
    usable = bool(evidence_allowed and price_material and oi_material)

    code = "NEUTRAL"
    market_bias = 0.0
    if usable:
        if p_delta > 0 and o_delta > 0:
            code = "LONG_BUILDUP"
            market_bias = 1.0 if side_u == "CE" else -1.0
        elif p_delta < 0 and o_delta > 0:
            code = "WRITING"
            market_bias = -1.0 if side_u == "CE" else 1.0
        elif p_delta > 0 and o_delta < 0:
            code = "SHORT_COVERING"
            market_bias = 1.0 if side_u == "CE" else -1.0
        elif p_delta < 0 and o_delta < 0:
            code = "LONG_UNWINDING"
            market_bias = -0.45 if side_u == "CE" else 0.45

    strength = 0.0
    if usable:
        strength = 25.0
        strength += min(abs(p_pct) * 8.0, 25.0)
        strength += min(abs(o_pct) * 2.5, 25.0)
        vr = _num(volume_ratio)
        if vr >= 2.0:
            strength += 15.0
        elif vr >= 1.2:
            strength += 10.0
        elif vr >= 0.7:
            strength += 5.0
        sp = _num(spread_pct)
        if 0 < sp <= 0.5:
            strength += 10.0
        elif sp <= 1.0:
            strength += 6.0
        elif sp > 2.0:
            strength -= 10.0
        if basis_u == "SNAPSHOT":
            strength += 8.0
        elif "PREOPEN" in basis_u:
            strength = min(strength, 35.0)
        elif "DAY" in basis_u:
            strength = min(strength, 65.0)

    strength = int(round(_clip(strength, 0.0, 98.0)))
    label = _LABELS[side_u][code]
    return {
        "side": side_u,
        "flow_code": f"{side_u}_{code}",
        "signal": label,
        "basis": basis_u,
        "evidence_ready": usable,
        "price_material": price_material,
        "oi_material": oi_material,
        "price_delta": round(p_delta, 4),
        "price_pct": round(p_pct, 4),
        "oi_delta": int(round(o_delta)),
        "oi_pct": round(o_pct, 4),
        "strength": strength,
        "market_bias": market_bias,
        "directional_score": round(market_bias * strength, 2),
        "reason": (
            "Matching premium and OI deltas classified by canonical rule."
            if usable
            else "Neutral: matching premium/OI movement is not material or evidence is not live-eligible."
        ),
    }


def validate_flow_row(row: Mapping[str, Any], side: str) -> Dict[str, Any]:
    """Recompute a stored row and verify its code/label against its evidence."""
    prefix = str(side).lower()
    basis = str(row.get(f"{prefix}_signal_basis", row.get(f"{prefix}_flow_basis", "UNKNOWN")))
    result = classify_option_flow(
        side,
        price_delta=row.get(f"{prefix}_flow_price_delta", 0),
        price_pct=row.get(f"{prefix}_flow_price_pct", 0),
        oi_delta=row.get(f"{prefix}_flow_oi_delta", 0),
        oi_pct=row.get(f"{prefix}_flow_oi_pct", 0),
        basis=basis,
        volume_ratio=row.get(f"{prefix}_volume_ratio", 0),
        spread_pct=row.get(f"{prefix}_spread_pct", 0),
        evidence_allowed=bool(row.get(f"{prefix}_flow_evidence_ready", True)),
    )
    stored_code = str(row.get(f"{prefix}_flow_code", ""))
    stored_signal = str(row.get(f"{prefix}_signal", row.get(f"{prefix}_flow", "")))
    ok = (not stored_code or stored_code == result["flow_code"]) and (
        not stored_signal or stored_signal == result["signal"]
    )
    return {
        "ok": bool(ok),
        "expected_code": result["flow_code"],
        "stored_code": stored_code,
        "expected_signal": result["signal"],
        "stored_signal": stored_signal,
    }
