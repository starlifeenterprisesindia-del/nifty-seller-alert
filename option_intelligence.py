"""
option_intelligence.py
Version: V23.0
Department: Option Intelligence
Status: Phase-2 Professional Architecture

Adds:
- CE/PE Writing Specialists
- PCR Specialist
- Unwinding Specialist
- Strike Pressure Specialist
- Barrier Reaction Evaluator
- Unified Director Report
"""

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class OptionReport:
    summary:str
    confidence:float
    details:Dict[str,Any]

class OISpecialist:
    def analyze(self, price_change, oi_change):
        if price_change>0 and oi_change>0:
            sig="Long Build-up"
        elif price_change<0 and oi_change>0:
            sig="Short Build-up"
        elif price_change>0 and oi_change<0:
            sig="Short Covering"
        elif price_change<0 and oi_change<0:
            sig="Long Unwinding"
        else:
            sig="Neutral"
        return {"signal":sig,"strength":min(100,abs(oi_change)*2)}

class VolumeSpecialist:
    def analyze(self,current,avg):
        if avg<=0:return {"status":"Unknown"}
        r=current/avg
        if r>=2:return {"status":"Spike"}
        if r>=1.3:return {"status":"High"}
        if r>=0.8:return {"status":"Normal"}
        return {"status":"Weak"}

class CEWritingSpecialist:
    def analyze(self,ce_change):
        return {"ce":"Strong" if ce_change>0 else "Weak"}

class PEWritingSpecialist:
    def analyze(self,pe_change):
        return {"pe":"Strong" if pe_change>0 else "Weak"}

class PCRSpecialist:
    def analyze(self,pcr):
        if pcr>1.2:return {"sentiment":"Bullish"}
        if pcr<0.8:return {"sentiment":"Bearish"}
        return {"sentiment":"Balanced"}

class UnwindingSpecialist:
    def analyze(self,oi_change):
        return {"unwinding":oi_change<0}

class StrikePressureSpecialist:
    def analyze(self,ce_oi,pe_oi):
        if ce_oi>pe_oi:
            return {"pressure":"CE Resistance"}
        if pe_oi>ce_oi:
            return {"pressure":"PE Support"}
        return {"pressure":"Balanced"}

class BarrierReactionSpecialist:
    def analyze(self,touched,respected):
        if not touched:
            return {"barrier":"Not Tested"}
        return {"barrier":"Rejection" if respected else "Break Attempt"}

class OptionIntelligenceDirector:
    def __init__(self):
        self.oi=OISpecialist()
        self.vol=VolumeSpecialist()
        self.ce=CEWritingSpecialist()
        self.pe=PEWritingSpecialist()
        self.pcr=PCRSpecialist()
        self.unwind=UnwindingSpecialist()
        self.strike=StrikePressureSpecialist()
        self.barrier=BarrierReactionSpecialist()

    def build_report(self,**k):
        details={
            "oi":self.oi.analyze(k["price_change"],k["oi_change"]),
            "volume":self.vol.analyze(k["current_volume"],k["average_volume"]),
            "ce":self.ce.analyze(k["ce_change"]),
            "pe":self.pe.analyze(k["pe_change"]),
            "pcr":self.pcr.analyze(k["pcr"]),
            "unwinding":self.unwind.analyze(k["oi_change"]),
            "strike":self.strike.analyze(k["ce_oi"],k["pe_oi"]),
            "barrier":self.barrier.analyze(k["barrier_touched"],k["barrier_respected"])
        }
        return OptionReport(
            summary="Professional Option Intelligence report ready",
            confidence=details["oi"]["strength"],
            details=details
        )
