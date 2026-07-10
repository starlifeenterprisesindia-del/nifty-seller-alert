"""
option_intelligence.py
Version : V22.9
Department : Option Intelligence
Status : Phase-1 Logic

Sprint Goal:
- Interpret OI + Price relationship
- Interpret Volume strength
- No BUY/SELL decision
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class OptionReport:
    summary: str
    confidence: float
    details: Dict[str, Any]


class OISpecialist:
    """Interprets Price + OI behaviour"""

    def analyze(self, price_change: float, oi_change: float):
        if price_change > 0 and oi_change > 0:
            signal = "Long Build-up"
        elif price_change < 0 and oi_change > 0:
            signal = "Short Build-up"
        elif price_change > 0 and oi_change < 0:
            signal = "Short Covering"
        elif price_change < 0 and oi_change < 0:
            signal = "Long Unwinding"
        else:
            signal = "Neutral"

        strength = min(100, abs(oi_change) * 2)

        return {
            "signal": signal,
            "strength": round(strength, 1)
        }


class VolumeSpecialist:
    """Interprets participation quality"""

    def analyze(self, current_volume: float, average_volume: float):
        if average_volume <= 0:
            status = "Unknown"
        else:
            ratio = current_volume / average_volume

            if ratio >= 2:
                status = "Spike Volume"
            elif ratio >= 1.3:
                status = "High Volume"
            elif ratio >= 0.8:
                status = "Normal Volume"
            else:
                status = "Weak Volume"

        return {
            "status": status
        }


class OptionIntelligenceDirector:

    def __init__(self):
        self.oi = OISpecialist()
        self.volume = VolumeSpecialist()

    def build_report(
        self,
        price_change: float,
        oi_change: float,
        current_volume: float,
        average_volume: float,
    ) -> OptionReport:

        oi_report = self.oi.analyze(price_change, oi_change)
        volume_report = self.volume.analyze(
            current_volume,
            average_volume
        )

        details = {
            "oi": oi_report,
            "volume": volume_report,
        }

        summary = (
            f'OI: {oi_report["signal"]} | '
            f'Volume: {volume_report["status"]}'
        )

        return OptionReport(
            summary=summary,
            confidence=oi_report["strength"],
            details=details,
        )
