"""
smart_money.py
Version : V23.3
Department : Smart Money
Status : Phase-1

Purpose:
Read institutional participation only.
No BUY/SELL decisions.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class SmartMoneyReport:
    summary: str
    confidence: float
    details: Dict[str, Any]


class FIISpecialist:
    def analyze(self, fii_net: float):
        if fii_net > 0:
            return {"fii": "Buying", "score": 80}
        elif fii_net < 0:
            return {"fii": "Selling", "score": 80}
        return {"fii": "Neutral", "score": 50}


class DIISpecialist:
    def analyze(self, dii_net: float):
        if dii_net > 0:
            return {"dii": "Buying"}
        elif dii_net < 0:
            return {"dii": "Selling"}
        return {"dii": "Neutral"}


class HeavyweightSpecialist:
    def analyze(self, advancing: int, declining: int):
        if advancing > declining:
            return {"heavyweights": "Supporting Market"}
        elif declining > advancing:
            return {"heavyweights": "Pressuring Market"}
        return {"heavyweights": "Balanced"}


class BreadthSpecialist:
    def analyze(self, advance: int, decline: int):
        total = max(advance + decline, 1)
        ratio = advance / total
        if ratio > 0.65:
            status = "Strong Breadth"
        elif ratio < 0.35:
            status = "Weak Breadth"
        else:
            status = "Neutral Breadth"
        return {"breadth": status, "ratio": round(ratio,2)}


class SmartMoneyDirector:

    def build_report(self, fii_net, dii_net, advancing, declining, advance, decline):
        fii = FIISpecialist().analyze(fii_net)
        dii = DIISpecialist().analyze(dii_net)
        hw = HeavyweightSpecialist().analyze(advancing, declining)
        br = BreadthSpecialist().analyze(advance, decline)

        details = {
            "fii": fii,
            "dii": dii,
            "heavyweights": hw,
            "breadth": br,
        }

        summary = (
            f'FII: {fii["fii"]} | '
            f'DII: {dii["dii"]} | '
            f'{br["breadth"]}'
        )

        return SmartMoneyReport(
            summary=summary,
            confidence=fii["score"],
            details=details,
        )
