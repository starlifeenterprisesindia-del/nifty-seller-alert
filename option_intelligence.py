"""
option_intelligence.py
Version: V50.8
Department: Option Intelligence

Consumes the already-built authoritative option analysis. It distinguishes
support, resistance, fresh buying, writing and two-sided range pressure. It
never issues a final trade instruction.
"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class OptionReport:
    summary: str
    confidence: float
    details: Dict[str, Any]


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class OISpecialist:
    def analyze(self, price_change, oi_change, option_bias=None, flow_state="", snapshot_ready=False):
        if option_bias is not None:
            bias = _num(option_bias)
            if bias >= 35:
                sig = "Bullish OI Support"
            elif bias <= -35:
                sig = "Bearish OI Pressure"
            elif abs(bias) < 15:
                sig = "Balanced / Mixed OI"
            else:
                sig = "Mild Bullish OI" if bias > 0 else "Mild Bearish OI"
            strength = min(95, 35 + abs(bias) * 0.6)
            if not snapshot_ready:
                strength = min(strength, 65)
            return {
                "signal": sig,
                "strength": round(strength, 1),
                "bias": round(bias, 1),
                "flow_state": flow_state or "MIXED",
                "basis": "Snapshot" if snapshot_ready else "Day-change fallback",
            }

        if price_change > 0 and oi_change > 0:
            sig = "Long Build-up"
        elif price_change < 0 and oi_change > 0:
            sig = "Short Build-up"
        elif price_change > 0 and oi_change < 0:
            sig = "Short Covering"
        elif price_change < 0 and oi_change < 0:
            sig = "Long Unwinding"
        else:
            sig = "Neutral"
        return {"signal": sig, "strength": min(100, abs(oi_change) * 2)}


class VolumeSpecialist:
    def analyze(self, current, avg):
        if avg <= 0:
            return {"status": "Unknown", "ratio": 0}
        ratio = current / avg
        status = "Spike" if ratio >= 2 else "High" if ratio >= 1.3 else "Normal" if ratio >= 0.8 else "Weak"
        return {"status": status, "ratio": round(ratio, 2)}


class WritingSpecialist:
    def analyze(self, score, side):
        score = max(0.0, min(100.0, _num(score)))
        level = "Strong" if score >= 60 else "Moderate" if score >= 35 else "Weak"
        return {side.lower(): level, "score": round(score, 1)}


class PCRSpecialist:
    def analyze(self, pcr):
        pcr = _num(pcr, 1.0)
        if 0.95 <= pcr <= 1.30:
            sentiment = "Balanced to Bullish"
        elif 1.30 < pcr <= 1.60:
            sentiment = "Bullish / Crowded"
        elif pcr > 1.60:
            sentiment = "Extreme - Contrarian Caution"
        elif 0.75 <= pcr < 0.95:
            sentiment = "Mild Bearish"
        else:
            sentiment = "Bearish"
        return {"sentiment": sentiment, "pcr": round(pcr, 2)}


class StrikePressureSpecialist:
    def analyze(self, ce_oi, pe_oi, support_score=None, resistance_score=None):
        if support_score is not None or resistance_score is not None:
            support = max(0.0, min(100.0, _num(support_score)))
            resistance = max(0.0, min(100.0, _num(resistance_score)))
            if support >= 55 and resistance >= 55 and abs(support - resistance) <= 22:
                pressure = "Two-Sided Writing / Range"
            elif support >= resistance + 12:
                pressure = "PE Support"
            elif resistance >= support + 12:
                pressure = "CE Resistance"
            else:
                pressure = "Balanced"
            return {"pressure": pressure, "support_score": round(support, 1), "resistance_score": round(resistance, 1)}
        if ce_oi > pe_oi:
            return {"pressure": "CE Resistance"}
        if pe_oi > ce_oi:
            return {"pressure": "PE Support"}
        return {"pressure": "Balanced"}


class BarrierReactionSpecialist:
    def analyze(self, touched, respected):
        if not touched:
            return {"barrier": "Not Tested"}
        return {"barrier": "Rejection" if respected else "Break Attempt"}


class OptionIntelligenceDirector:
    def __init__(self):
        self.oi = OISpecialist()
        self.vol = VolumeSpecialist()
        self.pcr = PCRSpecialist()
        self.strike = StrikePressureSpecialist()
        self.barrier = BarrierReactionSpecialist()
        self.writer = WritingSpecialist()

    def build_report(self, **k):
        option_bias = k.get("option_bias")
        snapshot_ready = bool(k.get("snapshot_ready", False))
        flow_state = str(k.get("flow_state", ""))
        support_score = k.get("support_score")
        resistance_score = k.get("resistance_score")
        ce_writing_score = k.get("ce_writing_score", 100 if _num(k.get("ce_change")) > 0 else 0)
        pe_writing_score = k.get("pe_writing_score", 100 if _num(k.get("pe_change")) > 0 else 0)
        availability = str(k.get("availability", "READY"))

        if availability != "READY":
            details = {
                "availability": {"status": availability, "used_for_direction": False},
                "oi": {"signal": "Unknown", "strength": 0, "basis": "Unavailable"},
                "volume": {"status": "Unknown", "ratio": 0},
                "ce": {"ce": "Unknown", "score": 0},
                "pe": {"pe": "Unknown", "score": 0},
                "pcr": self.pcr.analyze(k.get("pcr", 0)),
                "strike": {"pressure": "Unknown", "support_score": 0, "resistance_score": 0},
                "barrier": self.barrier.analyze(k.get("barrier_touched", False), k.get("barrier_respected", False)),
                "flow": {"state": "UNAVAILABLE", "snapshot_ready": False},
            }
            return OptionReport("Option Intelligence unavailable", 0.0, details)

        details = {
            "availability": {"status": "READY", "used_for_direction": True},
            "oi": self.oi.analyze(k.get("price_change", 0), k.get("oi_change", 0), option_bias, flow_state, snapshot_ready),
            "volume": self.vol.analyze(_num(k.get("current_volume")), _num(k.get("average_volume"))),
            "ce": self.writer.analyze(ce_writing_score, "CE"),
            "pe": self.writer.analyze(pe_writing_score, "PE"),
            "pcr": self.pcr.analyze(k.get("pcr", 0)),
            "strike": self.strike.analyze(k.get("ce_oi", 0), k.get("pe_oi", 0), support_score, resistance_score),
            "barrier": self.barrier.analyze(k.get("barrier_touched", False), k.get("barrier_respected", False)),
            "flow": {
                "state": flow_state or "MIXED",
                "snapshot_ready": snapshot_ready,
                "bullish_score": round(_num(k.get("bullish_score")), 1),
                "bearish_score": round(_num(k.get("bearish_score")), 1),
                "conflict_score": round(_num(k.get("conflict_score")), 1),
            },
        }
        pressure = details["strike"]["pressure"]
        signal = details["oi"]["signal"]
        basis = details["oi"].get("basis", "")
        confidence = details["oi"]["strength"]
        if pressure == "Two-Sided Writing / Range":
            confidence = min(82.0, max(confidence, 68.0))
        summary = f"{signal} | {pressure} | {basis}"
        return OptionReport(summary=summary, confidence=round(confidence, 1), details=details)
