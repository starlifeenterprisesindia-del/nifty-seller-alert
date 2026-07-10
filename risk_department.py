"""
risk_department.py
Version : V23.4
Department : Risk
Status : Phase-1

Purpose:
Evaluate market risk only.
Never generates BUY/SELL.
"""

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class RiskReport:
    summary:str
    confidence:float
    details:Dict[str,Any]

class VIXSpecialist:
    def analyze(self,vix):
        if vix>=20: return {"vix":"High Volatility","risk":"High"}
        if vix>=15: return {"vix":"Normal Volatility","risk":"Medium"}
        return {"vix":"Low Volatility","risk":"Low"}

class NewsRiskSpecialist:
    def analyze(self,high_impact:bool):
        return {"news":"High Impact" if high_impact else "Normal"}

class ExpirySpecialist:
    def analyze(self,is_expiry:bool):
        return {"expiry":"Expiry Day" if is_expiry else "Normal Day"}

class EventRiskSpecialist:
    def analyze(self,event_name:str):
        return {"event":event_name if event_name else "No Major Event"}

class GapRiskSpecialist:
    def analyze(self,gap_pct:float):
        if abs(gap_pct)>=1:
            level="High Gap"
        elif abs(gap_pct)>=0.4:
            level="Moderate Gap"
        else:
            level="Low Gap"
        return {"gap":level,"gap_pct":gap_pct}

class RiskDirector:
    def build_report(self,vix,high_impact,is_expiry,event_name,gap_pct):
        details={
            "vix":VIXSpecialist().analyze(vix),
            "news":NewsRiskSpecialist().analyze(high_impact),
            "expiry":ExpirySpecialist().analyze(is_expiry),
            "event":EventRiskSpecialist().analyze(event_name),
            "gap":GapRiskSpecialist().analyze(gap_pct)
        }
        score=85
        if details["vix"]["risk"]=="High": score-=20
        if high_impact: score-=15
        if is_expiry: score-=10
        return RiskReport(
            summary="Risk assessment completed",
            confidence=max(score,30),
            details=details
        )
