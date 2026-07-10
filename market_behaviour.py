"""
market_behaviour.py
Version : V23.2
Department : Market Behaviour
Status : Phase-1

Reads reports from:
- Price Action Department
- Option Intelligence Department

Produces behaviour report only.
No BUY/SELL decisions.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class MarketBehaviourReport:
    summary: str
    confidence: float
    details: Dict[str, Any]


class BarrierIntelligenceSpecialist:
    def analyze(self, price_report, option_report):
        zone = price_report.get("barrier", {}).get("barrier_zone", "")
        pressure = option_report.get("strike", {}).get("pressure", "")
        if "Resistance" in zone and pressure == "CE Resistance":
            return {"barrier_view": "Strong Resistance"}
        if "Support" in zone and pressure == "PE Support":
            return {"barrier_view": "Strong Support"}
        return {"barrier_view": "Neutral Barrier"}


class BreakoutSpecialist:
    def analyze(self, barrier_view, volume_status):
        if volume_status in ("High", "Spike") and "Strong" not in barrier_view:
            return {"breakout_probability": "Increasing"}
        return {"breakout_probability": "Normal"}


class ReversalSpecialist:
    def analyze(self, stage):
        if stage in ("Late Move", "Exhaustion Move"):
            return {"reversal_risk": "High"}
        return {"reversal_risk": "Low"}


class FakeBreakoutSpecialist:
    def analyze(self, breakout_probability, volume_status):
        if breakout_probability == "Increasing" and volume_status == "Weak":
            return {"fake_breakout": "Possible"}
        return {"fake_breakout": "Low"}


class RangeBehaviourSpecialist:
    def analyze(self, range_status):
        return {"range_behaviour": range_status}


class TimeBehaviourSpecialist:
    def analyze(self, hour):
        if 9 <= hour < 10:
            return {"time_phase": "Opening"}
        if 11 <= hour < 12:
            return {"time_phase": "Observation Zone"}
        if 14 <= hour < 15:
            return {"time_phase": "Afternoon Move"}
        return {"time_phase": "Normal"}


class MarketEnergySpecialist:
    def analyze(self, stage):
        energy = "High"
        if stage == "Late Move":
            energy = "Medium"
        if stage == "Exhaustion Move":
            energy = "Low"
        return {"market_energy": energy}


class MovePotentialSpecialist:
    def analyze(self, energy, reversal):
        if energy == "High":
            return {"move_potential": "Further Move Possible"}
        if reversal == "High":
            return {"move_potential": "Watch For Reversal"}
        return {"move_potential": "Balanced"}


class MarketBehaviourDirector:

    def build_report(self, price_details, option_details, hour):
        barrier = BarrierIntelligenceSpecialist().analyze(price_details, option_details)
        stage = price_details.get("move_stage", {}).get("stage", "")
        volume = option_details.get("volume", {}).get("status", "")
        breakout = BreakoutSpecialist().analyze(barrier["barrier_view"], volume)
        reversal = ReversalSpecialist().analyze(stage)
        fake = FakeBreakoutSpecialist().analyze(
            breakout["breakout_probability"], volume
        )
        rng = RangeBehaviourSpecialist().analyze(
            price_details.get("range", {}).get("range_status", "")
        )
        tm = TimeBehaviourSpecialist().analyze(hour)
        energy = MarketEnergySpecialist().analyze(stage)
        potential = MovePotentialSpecialist().analyze(
            energy["market_energy"], reversal["reversal_risk"]
        )

        details = {
            "barrier": barrier,
            "breakout": breakout,
            "reversal": reversal,
            "fake_breakout": fake,
            "range": rng,
            "time": tm,
            "energy": energy,
            "potential": potential,
        }

        return MarketBehaviourReport(
            summary="Market Behaviour analysis completed",
            confidence=75.0,
            details=details,
        )
