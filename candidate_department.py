"""
candidate_department.py
Version : V50.8.4
Department : Candidate Intelligence
Status : Phase-1 Professional Candidate Architecture

Purpose:
- Shortlist and rank CE/PE candidates
- Validate premium, liquidity, distance and hedge quality
- No BUY/SELL/WAIT decision
- Reports candidates only to AI_MASTER
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Candidate:
    option_type: str
    strike: float
    premium: float
    score: float
    status: str
    reasons: List[str]
    hedge_strike: Optional[float] = None


@dataclass
class CandidateReport:
    summary: str
    confidence: float
    best_ce: Optional[Candidate]
    best_pe: Optional[Candidate]
    details: Dict[str, Any]


class StrikeDistanceSpecialist:
    def score(self, spot: float, strike: float, option_type: str, atr: float) -> Dict[str, Any]:
        distance = abs(strike - spot)
        atr = max(float(atr or 0), 1.0)
        ratio = distance / atr

        if option_type == "CE":
            correct_side = strike >= spot
        else:
            correct_side = strike <= spot

        if not correct_side:
            score = 0.0
            status = "Wrong Side"
        elif 0.45 <= ratio <= 1.30:
            score = 90.0
            status = "Professional Distance"
        elif 0.25 <= ratio < 0.45 or 1.30 < ratio <= 1.80:
            score = 70.0
            status = "Acceptable Distance"
        else:
            score = 45.0
            status = "Weak Distance"

        return {
            "distance_points": round(distance, 2),
            "distance_atr_ratio": round(ratio, 2),
            "score": score,
            "status": status,
        }


class PremiumQualitySpecialist:
    def score(self, premium: float, min_premium: float = 20.0, max_premium: float = 120.0) -> Dict[str, Any]:
        premium = float(premium or 0)

        if premium <= 0:
            score = 0.0
            status = "Invalid Premium"
        elif min_premium <= premium <= max_premium:
            score = 90.0
            status = "Good Premium"
        elif premium < min_premium:
            score = 50.0
            status = "Low Reward"
        else:
            score = 55.0
            status = "High Risk Premium"

        return {"score": score, "status": status}


class LiquiditySpecialist:
    def score(self, volume: float, oi: float, bid_ask_spread: float) -> Dict[str, Any]:
        volume = max(float(volume or 0), 0.0)
        oi = max(float(oi or 0), 0.0)
        spread = max(float(bid_ask_spread or 0), 0.0)

        score = 0.0
        reasons = []

        if volume >= 100000:
            score += 35
            reasons.append("High volume")
        elif volume >= 25000:
            score += 25
            reasons.append("Acceptable volume")
        else:
            score += 10
            reasons.append("Low volume")

        if oi >= 100000:
            score += 35
            reasons.append("High OI")
        elif oi >= 25000:
            score += 25
            reasons.append("Acceptable OI")
        else:
            score += 10
            reasons.append("Low OI")

        if spread <= 1.0:
            score += 30
            reasons.append("Tight spread")
        elif spread <= 2.5:
            score += 20
            reasons.append("Acceptable spread")
        else:
            score += 5
            reasons.append("Wide spread")

        return {
            "score": min(score, 100.0),
            "status": "Liquid" if score >= 70 else "Weak Liquidity",
            "reasons": reasons,
        }


class OIWritingSpecialist:
    """
    Candidate-quality scorer for *verified* option-flow evidence.

    Positive OI by itself is never treated as writing. Writing requires the
    canonical price+OI classifier to explicitly return CE_WRITING/PE_WRITING.
    This keeps Candidate Intelligence subordinate to the Option DSP evidence
    and prevents a second, contradictory flow brain.
    """

    WRITING_CODES = {"CE_WRITING", "PE_WRITING"}
    BUYING_CODES = {"CE_LONG_BUILDUP", "PE_LONG_BUILDUP"}
    COVERING_CODES = {"CE_SHORT_COVERING", "PE_SHORT_COVERING"}
    UNWINDING_CODES = {"CE_LONG_UNWINDING", "PE_LONG_UNWINDING"}

    def score(
        self,
        oi_change: float,
        option_type: str,
        flow_code: str = "",
        flow_signal: str = "",
        evidence_ready: bool = False,
    ) -> Dict[str, Any]:
        option_type = str(option_type or "").upper()
        flow_code = str(flow_code or "").upper()
        flow_signal = str(flow_signal or "").strip()

        if not evidence_ready:
            return {
                "score": 40.0,
                "status": "Flow Confirmation Pending",
                "flow_code": flow_code or "UNCONFIRMED",
                "evidence_ready": False,
            }

        expected_prefix = f"{option_type}_" if option_type in {"CE", "PE"} else ""
        if expected_prefix and flow_code and not flow_code.startswith(expected_prefix):
            return {
                "score": 10.0,
                "status": "Flow Side Mismatch",
                "flow_code": flow_code,
                "evidence_ready": True,
            }

        if flow_code in self.WRITING_CODES:
            score = 90.0
            status = flow_signal or f"Fresh {option_type} Writing"
        elif flow_code in self.BUYING_CODES:
            score = 15.0
            status = flow_signal or f"Fresh {option_type} Buying - Seller Risk"
        elif flow_code in self.COVERING_CODES:
            score = 25.0
            status = flow_signal or f"{option_type} Short Covering - Seller Risk"
        elif flow_code in self.UNWINDING_CODES:
            score = 35.0
            status = flow_signal or f"{option_type} Long Unwinding"
        elif flow_code.endswith("_NEUTRAL") or flow_code in {"NEUTRAL", "NO_MATERIAL_FLOW"}:
            score = 45.0
            status = flow_signal or "Neutral Flow"
        else:
            # Unknown/legacy labels are not converted into writing from OI sign.
            score = 35.0
            status = flow_signal or "Unverified Flow Label"

        return {
            "score": round(score, 1),
            "status": status,
            "flow_code": flow_code or "UNVERIFIED",
            "evidence_ready": True,
        }


class BarrierSafetySpecialist:
    def score(
        self,
        option_type: str,
        strike: float,
        support: Optional[float],
        resistance: Optional[float],
    ) -> Dict[str, Any]:
        if option_type == "CE" and resistance is not None:
            gap = strike - resistance
            if gap >= 0:
                return {"score": 90.0, "status": "Above Resistance", "gap": round(gap, 2)}
            return {"score": 45.0, "status": "Inside Resistance Zone", "gap": round(gap, 2)}

        if option_type == "PE" and support is not None:
            gap = support - strike
            if gap >= 0:
                return {"score": 90.0, "status": "Below Support", "gap": round(gap, 2)}
            return {"score": 45.0, "status": "Inside Support Zone", "gap": round(gap, 2)}

        return {"score": 60.0, "status": "Barrier Data Unavailable", "gap": None}


class HedgeSpecialist:
    def choose(self, sell_strike: float, option_type: str, available_strikes: List[float]) -> Optional[float]:
        strikes = sorted({float(s) for s in available_strikes})

        if option_type == "CE":
            valid = [s for s in strikes if s > sell_strike]
            return valid[0] if valid else None

        valid = [s for s in strikes if s < sell_strike]
        return valid[-1] if valid else None


class CandidateRankingSpecialist:
    WEIGHTS = {
        "distance": 0.20,
        "premium": 0.15,
        "liquidity": 0.25,
        "oi_writing": 0.25,
        "barrier": 0.15,
    }

    def rank(
        self,
        row: Dict[str, Any],
        spot: float,
        atr: float,
        support: Optional[float],
        resistance: Optional[float],
        all_strikes: List[float],
    ) -> Candidate:
        option_type = str(row.get("option_type", "")).upper()
        strike = float(row.get("strike", 0))
        premium = float(row.get("premium", 0))

        distance = StrikeDistanceSpecialist().score(spot, strike, option_type, atr)
        premium_quality = PremiumQualitySpecialist().score(premium)
        liquidity = LiquiditySpecialist().score(
            row.get("volume", 0),
            row.get("oi", 0),
            row.get("bid_ask_spread", 0),
        )
        writing = OIWritingSpecialist().score(
            row.get("oi_change", 0),
            option_type,
            flow_code=row.get("flow_code", ""),
            flow_signal=row.get("flow_signal", ""),
            evidence_ready=bool(row.get("flow_evidence_ready", False)),
        )
        barrier = BarrierSafetySpecialist().score(option_type, strike, support, resistance)

        weighted_score = (
            distance["score"] * self.WEIGHTS["distance"]
            + premium_quality["score"] * self.WEIGHTS["premium"]
            + liquidity["score"] * self.WEIGHTS["liquidity"]
            + writing["score"] * self.WEIGHTS["oi_writing"]
            + barrier["score"] * self.WEIGHTS["barrier"]
        )

        hedge = HedgeSpecialist().choose(strike, option_type, all_strikes)

        reasons = [
            distance["status"],
            premium_quality["status"],
            liquidity["status"],
            writing["status"],
            barrier["status"],
        ]

        if weighted_score >= 80:
            status = "Strong Watchlist"
        elif weighted_score >= 65:
            status = "Watchlist"
        else:
            status = "Rejected"

        return Candidate(
            option_type=option_type,
            strike=strike,
            premium=premium,
            score=round(weighted_score, 1),
            status=status,
            reasons=reasons,
            hedge_strike=hedge,
        )


class CandidateDirector:
    """
    Receives one verified snapshot and produces CE/PE candidate reports.
    It does not approve trades. AI_MASTER remains the only decision authority.
    """

    def __init__(self):
        self.ranker = CandidateRankingSpecialist()

    def build_report(
        self,
        option_rows: List[Dict[str, Any]],
        spot: float,
        atr: float,
        support: Optional[float] = None,
        resistance: Optional[float] = None,
    ) -> CandidateReport:
        rows = [r for r in option_rows if r.get("strike") is not None]
        all_strikes = [float(r["strike"]) for r in rows]

        ranked = [
            self.ranker.rank(
                row=r,
                spot=spot,
                atr=atr,
                support=support,
                resistance=resistance,
                all_strikes=all_strikes,
            )
            for r in rows
            if str(r.get("option_type", "")).upper() in {"CE", "PE"}
        ]

        ce_candidates = sorted(
            [c for c in ranked if c.option_type == "CE"],
            key=lambda c: c.score,
            reverse=True,
        )
        pe_candidates = sorted(
            [c for c in ranked if c.option_type == "PE"],
            key=lambda c: c.score,
            reverse=True,
        )

        best_ce = ce_candidates[0] if ce_candidates else None
        best_pe = pe_candidates[0] if pe_candidates else None

        confidence_values = [c.score for c in (best_ce, best_pe) if c is not None]
        confidence = round(sum(confidence_values) / len(confidence_values), 1) if confidence_values else 0.0

        details = {
            "ce_candidates": ce_candidates[:3],
            "pe_candidates": pe_candidates[:3],
            "candidate_count": len(ranked),
        }

        summary = (
            f'Best CE: {best_ce.strike if best_ce else "None"} | '
            f'Best PE: {best_pe.strike if best_pe else "None"}'
        )

        return CandidateReport(
            summary=summary,
            confidence=confidence,
            best_ce=best_ce,
            best_pe=best_pe,
            details=details,
        )
