"""DSP branch evidence-integrity audit for Nifty Seller AI V50.8.4.

The audit is not a decision engine.  It validates that each branch received the
expected authoritative input, that its evidence is internally consistent, and
that unavailable/partial data is labelled before the CO case file is built.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Mapping, MutableMapping

try:
    from option_flow_integrity import validate_flow_row
except Exception:  # fail-closed result is produced by the option audit
    validate_flow_row = None


CRITICAL_BRANCHES = {
    "DATA", "OPTION", "PRICE_ACTION", "MARKET_BEHAVIOUR",
    "SMART_MONEY", "RISK", "STRATEGY", "CANDIDATE",
}
OBSERVATION_ONLY = {
    "MARKET_PSYCHOLOGY", "TIME_INTELLIGENCE", "MARKET_JOURNEY",
    "HEAVYWEIGHT_INTELLIGENCE", "NEWS_INTELLIGENCE", "EXPERIENCE",
    "SELF_REVIEW", "PROMOTION_BOARD", "LEARNING",
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        try:
            return asdict(value)
        except Exception:
            pass
    output: Dict[str, Any] = {}
    for key in ("summary", "confidence", "details", "warnings"):
        try:
            output[key] = getattr(value, key)
        except Exception:
            pass
    return output


def _report_dict(value: Any) -> Dict[str, Any]:
    data = _mapping(value)
    details = data.get("details", {})
    if not isinstance(details, Mapping):
        details = {}
    warnings = data.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = [str(warnings)] if warnings else []
    return {
        "summary": str(data.get("summary", "No report"))[:300],
        "confidence": max(0.0, min(100.0, _num(data.get("confidence", 0)))),
        "details": deepcopy(dict(details)),
        "warnings": [str(item)[:220] for item in warnings[:8]],
    }


def _status(issues: list[str], warnings: list[str]) -> str:
    return "FAIL" if issues else "CAUTION" if warnings else "PASS"


def _source_for(branch: str, context: Mapping[str, Any]) -> str:
    registry = context.get("source_registry", {}) if isinstance(context.get("source_registry", {}), Mapping) else {}
    key_map = {
        "DATA": "nifty", "OPTION": "option_chain", "PRICE_ACTION": "price_action",
        "HEAVYWEIGHT_INTELLIGENCE": "heavyweights", "SMART_MONEY": "fii_dii",
        "NEWS_INTELLIGENCE": "news", "TIME_INTELLIGENCE": "clock",
    }
    key = key_map.get(branch, "")
    entry = registry.get(key, {}) if key and isinstance(registry.get(key, {}), Mapping) else {}
    if entry:
        return str(entry.get("source", entry.get("status", "Authoritative Snapshot")))[:90]
    return "Authoritative Snapshot / Department Evidence"


def audit_department_reports(
    reports: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return sanitized CO reports and a visible branch integrity certificate."""

    reports = reports if isinstance(reports, Mapping) else {}
    canonical_snapshot_id = str(context.get("snapshot_id", ""))
    market_open = bool(context.get("market_open", False))
    option_analysis = context.get("option_analysis", {}) if isinstance(context.get("option_analysis", {}), Mapping) else {}
    option_rows = option_analysis.get("rows", []) if isinstance(option_analysis.get("rows", []), list) else []
    oi_sync_ok = bool(context.get("oi_sync_ok", False))
    pa_usable = bool(context.get("price_action_usable", False))
    pa_reference_ready = bool(context.get("price_action_reference_ready", pa_usable))
    pa_age = _num(context.get("price_action_age_seconds", 0))
    price = _num(context.get("price", 0))
    support = context.get("support")
    resistance = context.get("resistance")
    pivot_integrity = str(context.get("pivot_integrity", "UNKNOWN")).upper()
    heavy_count = int(_num(context.get("heavyweight_count", 0)))
    expected_heavy_count = int(_num(context.get("expected_heavyweight_count", 0)))
    institutional_state = str(context.get("institutional_state", ""))
    candidate_count = int(_num(context.get("candidate_count", 0)))

    sanitized: Dict[str, Dict[str, Any]] = {}
    rows: list[Dict[str, Any]] = []
    critical_failures: list[str] = []

    all_names = list(dict.fromkeys(list(reports.keys()) + sorted(CRITICAL_BRANCHES | OBSERVATION_ONLY)))
    for branch in all_names:
        report = _report_dict(reports.get(branch))
        issues: list[str] = []
        warnings: list[str] = []

        if branch not in reports:
            issues.append("Department report missing")
        if not report["summary"] or report["summary"] == "No report":
            issues.append("Summary missing")
        if not isinstance(report["details"], dict):
            issues.append("Structured details missing")

        if branch == "DATA":
            report_sid = str(report["details"].get("snapshot_id", ""))
            if not canonical_snapshot_id:
                issues.append("Canonical snapshot ID missing")
            elif report_sid and report_sid != canonical_snapshot_id:
                issues.append("Department snapshot ID differs from canonical snapshot")
            quality = _num(report["details"].get("quality_score", report["confidence"]))
            if quality < 60:
                issues.append(f"Data quality below 60% ({quality:.0f}%)")
            elif quality < 70:
                warnings.append(f"Data quality below live floor ({quality:.0f}%)")

        elif branch == "OPTION":
            if not option_analysis.get("success", False) or len(option_rows) < 5:
                issues.append("Live option-chain evidence unavailable/insufficient")
            if not oi_sync_ok:
                issues.append("Authoritative OI row aggregate is not synchronized")
            if market_open and not bool(option_analysis.get("snapshot_ready", False)):
                warnings.append("Only day-change evidence available; fresh second snapshot pending")
            if not market_open:
                warnings.append("Pre-open option evidence is reference-only")
            if validate_flow_row is None:
                issues.append("Canonical option-flow validator unavailable")
            else:
                mismatches = 0
                checked = 0
                for row in option_rows[:40]:
                    if not isinstance(row, Mapping):
                        continue
                    for side in ("CE", "PE"):
                        checked += 1
                        try:
                            if not validate_flow_row(row, side).get("ok", False):
                                mismatches += 1
                        except Exception:
                            mismatches += 1
                if mismatches:
                    issues.append(f"{mismatches}/{checked} option-flow labels disagree with canonical evidence")

        elif branch == "PRICE_ACTION":
            if not pa_usable:
                if (not market_open) and pa_reference_ready:
                    warnings.append("Pre-open price action is previous-session reference only")
                else:
                    issues.append("Price-action source unavailable or excluded")
            if market_open and pa_age > 720:
                issues.append(f"Latest candle stale ({pa_age/60:.1f} min)")
            if pivot_integrity in {"FAIL", "INVALID"}:
                issues.append("Previous-session pivot inputs failed integrity validation")
            elif pivot_integrity not in {"OK", "PASS", "READY"}:
                warnings.append("Pivot provenance is incomplete")
            try:
                if support is not None and _num(support) > price + 0.01:
                    issues.append("Selected support is above current price")
                if resistance is not None and _num(resistance) < price - 0.01:
                    issues.append("Selected resistance is below current price")
            except Exception:
                warnings.append("Barrier ordering could not be verified")

        elif branch == "MARKET_BEHAVIOUR":
            if not pa_usable:
                warnings.append("Behaviour has no usable price-action witness")
            if not option_analysis.get("success", False):
                warnings.append("Behaviour has no option-chain witness")

        elif branch == "TIME_INTELLIGENCE":
            if not str(report["details"].get("time_phase", report["details"].get("phase", ""))):
                warnings.append("Time phase not exposed in structured details")

        elif branch == "MARKET_JOURNEY":
            if "range pts" in report["summary"].lower():
                issues.append("Move summary contains incomplete 'range pts' placeholder")
            if price <= 0:
                issues.append("Current price unavailable for journey calculation")

        elif branch == "HEAVYWEIGHT_INTELLIGENCE":
            if expected_heavy_count > 0 and heavy_count < expected_heavy_count:
                if heavy_count < max(4, int(expected_heavy_count * 0.75)):
                    issues.append(f"Heavyweight coverage only {heavy_count}/{expected_heavy_count}")
                else:
                    warnings.append(f"Heavyweight coverage partial {heavy_count}/{expected_heavy_count}")

        elif branch == "NEWS_INTELLIGENCE":
            state = str(report["details"].get("investigation_state", report["details"].get("impact_level", "")))
            if not state:
                warnings.append("News coverage state not exposed")

        elif branch == "SMART_MONEY":
            if "PARTIAL" in institutional_state.upper() or "UNAVAILABLE" in institutional_state.upper():
                warnings.append("Institutional data partial; branch must remain neutral/capped")

        elif branch == "RISK":
            if report["confidence"] <= 0:
                issues.append("Risk report has no usable confidence")

        elif branch == "STRATEGY":
            if report["confidence"] <= 0:
                issues.append("Strategy routing report unavailable")

        elif branch == "CANDIDATE":
            if candidate_count <= 0:
                issues.append("No option candidates supplied to candidate department")

        elif branch in {"EXPERIENCE", "SELF_REVIEW", "PROMOTION_BOARD", "LEARNING"}:
            # Governance branches are bounded and observation-only.  Negative
            # counters or an execution instruction would indicate corruption.
            text = (report["summary"] + " " + str(report["details"])).upper()
            if any(token in text for token in ("EXECUTE BUY", "EXECUTE SELL", "ENTRY APPROVED")):
                issues.append("Observation-only governance branch contains execution language")

        status = _status(issues, warnings)
        if status == "FAIL" and branch in CRITICAL_BRANCHES:
            critical_failures.append(branch)

        # Preserve the department's evidence but attach the audit certificate.
        # Critical failures are made unavailable before BranchBoss/CO review.
        effective_confidence = report["confidence"]
        if status == "FAIL":
            effective_confidence = 0.0
        elif status == "CAUTION":
            effective_confidence = min(effective_confidence, 65.0)

        integrity = {
            "status": status,
            "canonical_snapshot_id": canonical_snapshot_id,
            "source": _source_for(branch, context),
            "issues": issues[:6],
            "warnings": warnings[:6],
            "critical": branch in CRITICAL_BRANCHES,
            "observation_only": branch in OBSERVATION_ONLY,
        }
        details = deepcopy(report["details"])
        details["integrity"] = integrity
        if status == "FAIL":
            details["availability"] = {
                "status": "INTEGRITY_HOLD",
                "used_for_direction": False,
            }
        sanitized[branch] = {
            "summary": (
                f"INTEGRITY HOLD: {'; '.join(issues[:2])}"
                if status == "FAIL" else report["summary"]
            )[:300],
            "confidence": round(effective_confidence, 1),
            "details": details,
            "warnings": list(dict.fromkeys(report["warnings"] + warnings + issues))[:8],
        }
        rows.append({
            "Branch": branch.replace("_", " ").title(),
            "Integrity": status,
            "Confidence": f"{effective_confidence:.1f}%",
            "Source": integrity["source"],
            "Checks": " | ".join(issues[:2] or warnings[:2] or ["Inputs and output consistent"]),
        })

    score = 0.0
    if rows:
        score = sum(100.0 if row["Integrity"] == "PASS" else 65.0 if row["Integrity"] == "CAUTION" else 0.0 for row in rows) / len(rows)
    overall = "HOLD" if critical_failures else "CAUTION" if any(row["Integrity"] == "CAUTION" for row in rows) else "PASS"
    return {
        "version": "V50.8.4_DSP_EVIDENCE_INTEGRITY",
        "overall_status": overall,
        "score": round(score, 1),
        "critical_ok": not critical_failures,
        "critical_failures": critical_failures,
        "rows": rows,
        "reports": sanitized,
        "snapshot_id": canonical_snapshot_id,
    }
