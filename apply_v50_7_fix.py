#!/usr/bin/env python3
"""Apply the V50.7 recovery-confirmation safety fix to Nifty Seller AI.

Run this file from the project root (the folder containing app.py,
price_action.py, strategy_department.py and ai_master.py).

The patch is deliberately narrow:
- no API/data/refresh/position-manager changes
- no new indicator or parallel decision engine
- AI_MASTER remains the only final authority
- backups are created before any write
"""
from __future__ import annotations

import argparse
import py_compile
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

PATCH_VERSION = "V50.7_RECOVERY_CONFIRMATION_FIX"
REQUIRED_FILES = (
    "app.py",
    "price_action.py",
    "strategy_department.py",
    "ai_master.py",
)


class PatchError(RuntimeError):
    pass


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise PatchError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def _regex_replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise PatchError(f"{label}: expected exactly 1 regex match, found {count}")
    return updated


def patch_price_action(text: str) -> str:
    trend_pattern = r'''class TrendSpecialist:\s*\n\s*def analyze\(self, price, ema20, ema50, movement=None\):.*?\n\s*return \{"trend": trend, "structure": structure, "strength": strength\}'''
    trend_replacement = '''class TrendSpecialist:
    def analyze(self, price, ema20, ema50, movement=None, vwap=None):
        movement = movement if isinstance(movement, Mapping) else {}
        phase = str(movement.get("phase", "NORMAL"))

        price = _num(price)
        ema20 = _num(ema20)
        ema50 = _num(ema50)
        vwap_value = _num(vwap) if vwap is not None else 0.0
        above_ema20 = price > ema20
        above_ema50 = price > ema50
        above_vwap = True if vwap_value <= 0 else price > vwap_value
        below_ema20 = price < ema20
        below_ema50 = price < ema50
        below_vwap = False if vwap_value <= 0 else price < vwap_value

        bullish_alignment = above_ema20 and above_ema50 and above_vwap
        bearish_alignment = below_ema20 and below_ema50 and below_vwap

        if bullish_alignment and ema20 > ema50:
            trend, structure, strength = "Bullish Trend", "BULLISH", 85
        elif bearish_alignment and ema20 < ema50:
            trend, structure, strength = "Bearish Trend", "BEARISH", 85
        elif bullish_alignment:
            trend, structure, strength = "Recovery Confirmed / Mixed Bullish", "MIXED_BULLISH", 62
        elif bearish_alignment:
            trend, structure, strength = "Below EMA/VWAP / Mixed Bearish", "MIXED_BEARISH", 58
        elif above_vwap and above_ema50:
            trend, structure, strength = "Recovery Attempt / Mixed", "NEUTRAL", 52
        elif below_vwap and below_ema50:
            trend, structure, strength = "Weakening / Mixed Bearish", "MIXED_BEARISH", 55
        else:
            trend, structure, strength = "Sideways / Unclear", "NEUTRAL", 42

        directional_confirmation = bool(bullish_alignment or bearish_alignment)
        recovery_confirmed = bool(
            phase in {"RECOVERY", "STRONG_RECOVERY"}
            and bullish_alignment
        )
        pullback_confirmed = bool(
            phase in {"PULLBACK_DOWN", "STRONG_PULLBACK_DOWN"}
            and bearish_alignment
        )

        # Current movement is evidence, but it cannot upgrade direction without
        # price holding on the correct side of EMA20, EMA50 and VWAP.
        if phase == "STRONG_RECOVERY" and not recovery_confirmed:
            trend = "Recovery Attempt / Confirmation Pending"
            structure = "NEUTRAL"
            strength = min(strength, 55)
        elif phase == "RECOVERY" and not recovery_confirmed:
            trend = "Recovery Developing / Confirmation Pending"
            structure = "NEUTRAL"
            strength = min(strength, 52)
        elif phase == "STRONG_PULLBACK_DOWN" and not pullback_confirmed:
            trend = "Pullback Attempt / Confirmation Pending"
            structure = "NEUTRAL"
            strength = min(strength, 55)
        elif phase == "PULLBACK_DOWN" and not pullback_confirmed:
            trend = "Pullback Developing / Confirmation Pending"
            structure = "NEUTRAL"
            strength = min(strength, 52)

        return {
            "trend": trend,
            "structure": structure,
            "strength": strength,
            "directional_confirmation": directional_confirmation,
            "recovery_confirmed": recovery_confirmed,
            "pullback_confirmed": pullback_confirmed,
            "above_ema20": above_ema20,
            "above_ema50": above_ema50,
            "above_vwap": above_vwap,
            "alignment_count": int(above_ema20) + int(above_ema50) + int(above_vwap),
        }'''
    text = _regex_replace_once(text, trend_pattern, trend_replacement, "price_action TrendSpecialist")

    old_call = '"trend": self.trend.analyze(k["price"], k["ema20"], k["ema50"], movement),'
    new_call = '"trend": self.trend.analyze(k["price"], k["ema20"], k["ema50"], movement, k.get("vwap")),'
    text = _replace_once(text, old_call, new_call, "price_action director call")
    text = text.replace("Version: V50.5", f"Version: {PATCH_VERSION}", 1)
    return text


def patch_strategy(text: str) -> str:
    guard = '''        # V50.7 recovery-confirmation guard.
        # OI/PCR support is evidence, not permission to sell PE while price has
        # not confirmed above EMA20 + EMA50 + VWAP.
        trend_details = price.get("trend", {}) if isinstance(price.get("trend", {}), dict) else {}
        directional_confirmed = bool(trend_details.get("directional_confirmation", False))
        recovery_confirmed = bool(trend_details.get("recovery_confirmed", False))
        pullback_confirmed = bool(trend_details.get("pullback_confirmed", False))
        vwap_status = str(price.get("vwap", {}).get("vwap_status", "Unknown"))
        sample_count = int(movement.get("sample_count", 0) or 0)

        if movement_phase in {"RECOVERY", "STRONG_RECOVERY"} and not recovery_confirmed:
            scores["SELL PE"] = min(scores["SELL PE"], 62.0)
            scores["WAIT"] = max(scores["WAIT"], 82.0)
            reasons["WAIT"].append("Recovery attempt is not confirmed above EMA20/EMA50/VWAP")
            reasons["SELL PE"].append("Future candidate only; execution confirmation incomplete")

        if movement_phase in {"PULLBACK_DOWN", "STRONG_PULLBACK_DOWN"} and not pullback_confirmed:
            scores["SELL CE"] = min(scores["SELL CE"], 62.0)
            scores["WAIT"] = max(scores["WAIT"], 82.0)
            reasons["WAIT"].append("Pullback attempt is not confirmed below EMA20/EMA50/VWAP")
            reasons["SELL CE"].append("Future candidate only; execution confirmation incomplete")

        if structure in {"NEUTRAL", "MIXED_BULLISH", "MIXED_BEARISH", ""} and not directional_confirmed:
            scores["SELL CE"] = min(scores["SELL CE"], 68.0)
            scores["SELL PE"] = min(scores["SELL PE"], 68.0)

        if vwap_status == "Below VWAP" and movement_phase in {"RECOVERY", "STRONG_RECOVERY"}:
            scores["SELL PE"] = min(scores["SELL PE"], 60.0)
            scores["WAIT"] = max(scores["WAIT"], 84.0)
            reasons["WAIT"].append("Price is below VWAP during recovery attempt")

        if "Near Resistance" in barrier_zone and movement_phase in {"RECOVERY", "STRONG_RECOVERY"}:
            scores["SELL PE"] = min(scores["SELL PE"], 60.0)
            reasons["SELL PE"].append("Near resistance; breakout/hold confirmation required")

        if sample_count < 3 and movement_phase in {"RECOVERY", "STRONG_RECOVERY", "PULLBACK_DOWN", "STRONG_PULLBACK_DOWN"}:
            scores["WAIT"] = max(scores["WAIT"], 85.0)
            scores["SELL CE"] = min(scores["SELL CE"], 60.0)
            scores["SELL PE"] = min(scores["SELL PE"], 60.0)
            reasons["WAIT"].append("Fewer than three persisted movement samples")

'''
    marker = "        result: Dict[str, StrategyScore] = {}\n"
    text = _replace_once(text, marker, guard + marker, "strategy confirmation guard")
    text = text.replace("Version : V50.5", f"Version : {PATCH_VERSION}", 1)
    return text


def patch_ai_master(text: str) -> str:
    # Add the confirmation gate immediately after the existing risk gate.
    old = '''        risk_block, risk_warnings = self._risk_gate(
            risk_report=risk_report,
            behaviour_report=behaviour_report,
        )
        warnings.extend(risk_warnings)

        score_gap = self._score_gap(strategy_scores)
'''
    new = '''        risk_block, risk_warnings = self._risk_gate(
            risk_report=risk_report,
            behaviour_report=behaviour_report,
        )
        warnings.extend(risk_warnings)

        execution_confirmation_ok, confirmation_warnings = self._execution_confirmation(
            recommended=recommended,
            price_report=price_report,
            option_report=option_report,
        )
        warnings.extend(confirmation_warnings)

        score_gap = self._score_gap(strategy_scores)
'''
    text = _replace_once(text, old, new, "AI_MASTER confirmation call")

    old_trade = '''        trade_allowed = (
            data_quality_ok
            and co_accepted
            and not risk_block
            and recommended in {"SELL CE", "SELL PE", "IRON CONDOR"}
            and top_score >= 65.0
            and score_gap >= 6.0
        )
'''
    new_trade = '''        trade_allowed = (
            data_quality_ok
            and co_accepted
            and not risk_block
            and execution_confirmation_ok
            and recommended in {"SELL CE", "SELL PE", "IRON CONDOR"}
            and top_score >= 65.0
            and score_gap >= 6.0
        )
'''
    text = _replace_once(text, old_trade, new_trade, "AI_MASTER trade gate")

    # Add trace visibility.
    old_trace = '                "risk_block": risk_block,\n'
    new_trace = '                "risk_block": risk_block,\n                "execution_confirmation_ok": execution_confirmation_ok,\n'
    text = _replace_once(text, old_trace, new_trace, "AI_MASTER trace")

    # Mixed structure and unconfirmed recovery must not be promoted to bullish bias.
    old_bias = '''        if structure in {"BULLISH", "MIXED_BULLISH"} or (
            "Bullish" in trend and "Pullback" not in trend
        ):
            bullish += 2
        if structure in {"BEARISH", "MIXED_BEARISH"} or (
            "Bearish" in trend and "Recovery" not in trend
        ):
            bearish += 2

        # Current impulse is separate from the broader EMA structure. A strong
        # recovery neutralizes a stale bearish continuation reading.
        movement = price.get("movement", {}) if isinstance(price.get("movement", {}), Mapping) else {}
        phase = str(movement.get("phase", ""))
        if phase == "STRONG_RECOVERY":
            bullish += 3
        elif phase == "RECOVERY":
            bullish += 2
        elif phase == "STRONG_PULLBACK_DOWN":
            bearish += 3
        elif phase == "PULLBACK_DOWN":
            bearish += 2
'''
    new_bias = '''        trend_details = price.get("trend", {}) if isinstance(price.get("trend", {}), Mapping) else {}
        directional_confirmed = bool(trend_details.get("directional_confirmation", False))
        recovery_confirmed = bool(trend_details.get("recovery_confirmed", False))
        pullback_confirmed = bool(trend_details.get("pullback_confirmed", False))

        if structure == "BULLISH" and directional_confirmed:
            bullish += 2
        elif structure == "MIXED_BULLISH" and directional_confirmed:
            bullish += 1
        if structure == "BEARISH" and directional_confirmed:
            bearish += 2
        elif structure == "MIXED_BEARISH" and directional_confirmed:
            bearish += 1

        # Recovery/pullback is an attempt until EMA20, EMA50 and VWAP alignment
        # confirms it. Option support alone cannot promote market bias.
        movement = price.get("movement", {}) if isinstance(price.get("movement", {}), Mapping) else {}
        phase = str(movement.get("phase", ""))
        if phase == "STRONG_RECOVERY" and recovery_confirmed:
            bullish += 3
        elif phase == "RECOVERY" and recovery_confirmed:
            bullish += 2
        elif phase == "STRONG_PULLBACK_DOWN" and pullback_confirmed:
            bearish += 3
        elif phase == "PULLBACK_DOWN" and pullback_confirmed:
            bearish += 2
'''
    text = _replace_once(text, old_bias, new_bias, "AI_MASTER market bias")

    helper = '''    def _execution_confirmation(
        self,
        *,
        recommended: str,
        price_report: Any,
        option_report: Any,
    ) -> tuple[bool, List[str]]:
        """Final execution confirmation; evidence-only departments cannot bypass it."""
        recommended = str(recommended or "WAIT").upper()
        if recommended == "WAIT":
            return True, []

        price = _details(price_report)
        option = _details(option_report)
        trend = price.get("trend", {}) if isinstance(price.get("trend", {}), Mapping) else {}
        movement = price.get("movement", {}) if isinstance(price.get("movement", {}), Mapping) else {}
        barrier = price.get("barrier", {}) if isinstance(price.get("barrier", {}), Mapping) else {}
        range_view = price.get("range", {}) if isinstance(price.get("range", {}), Mapping) else {}

        directional = bool(trend.get("directional_confirmation", False))
        recovery_confirmed = bool(trend.get("recovery_confirmed", False))
        pullback_confirmed = bool(trend.get("pullback_confirmed", False))
        sample_count = int(movement.get("sample_count", 0) or 0)
        barrier_zone = str(barrier.get("barrier_zone", ""))
        range_status = str(range_view.get("range_status", ""))
        strike_pressure = str(option.get("strike", {}).get("pressure", ""))

        warnings: List[str] = []
        if recommended == "SELL PE":
            ok = directional and (recovery_confirmed or str(trend.get("structure", "")) == "BULLISH")
            ok = ok and sample_count >= 3 and "Near Resistance" not in barrier_zone
            if not ok:
                warnings.append("Execution confirmation incomplete for SELL PE")
                warnings.append("PE candidate is watchlist-only until price holds above EMA20/EMA50/VWAP")
            return ok, warnings

        if recommended == "SELL CE":
            ok = directional and (pullback_confirmed or str(trend.get("structure", "")) == "BEARISH")
            ok = ok and sample_count >= 3 and "Near Support" not in barrier_zone
            if not ok:
                warnings.append("Execution confirmation incomplete for SELL CE")
                warnings.append("CE candidate is watchlist-only until price holds below EMA20/EMA50/VWAP")
            return ok, warnings

        if recommended == "IRON CONDOR":
            two_sided = strike_pressure == "Two-Sided Writing / Range"
            range_ok = "Tight Range" in range_status or "Normal Range" in range_status
            ok = two_sided and range_ok and sample_count >= 3
            if not ok:
                warnings.append("Execution confirmation incomplete for IRON CONDOR")
            return ok, warnings

        return False, ["Unknown strategy execution confirmation"]

'''
    marker = "    def _risk_gate(\n"
    text = _replace_once(text, marker, helper + marker, "AI_MASTER helper insertion")
    text = text.replace('VERSION = "V50.5_RECOVERY_AND_DATA_INTEGRITY_AUTHORITY"', f'VERSION = "{PATCH_VERSION}"', 1)
    return text


def patch_app(text: str) -> str:
    old_phase = '''    if phase == "STRONG_RECOVERY":
        bullish = max(bullish, 56)
    elif phase == "RECOVERY":
        bullish = max(bullish, 53)
    elif phase == "STRONG_PULLBACK_DOWN":
        bullish = min(bullish, 44)
    elif phase == "PULLBACK_DOWN":
        bullish = min(bullish, 47)

    # Incomplete core evidence must not produce an exaggerated 70-80% outlook.
    if not pa_usable:
        bullish = max(35, min(65, bullish))

    bearish = int(max(0, min(100, 100 - bullish)))
    if phase in {"STRONG_RECOVERY", "RECOVERY"}:
        direction = "RECOVERY"
        probability = bullish
'''
    new_phase = '''    sample_count = int(movement.get("sample_count", 0) or 0)
    recovery_confirmed = bool(
        pa >= 45 and ob >= 25 and hw >= 0 and sample_count >= 3
    )
    pullback_confirmed = bool(
        pa <= -45 and ob <= -25 and hw <= 0 and sample_count >= 3
    )

    if phase == "STRONG_RECOVERY":
        bullish = max(bullish, 56) if recovery_confirmed else min(bullish, 58)
    elif phase == "RECOVERY":
        bullish = max(bullish, 53) if recovery_confirmed else min(bullish, 55)
    elif phase == "STRONG_PULLBACK_DOWN":
        bullish = min(bullish, 44) if pullback_confirmed else max(bullish, 42)
    elif phase == "PULLBACK_DOWN":
        bullish = min(bullish, 47) if pullback_confirmed else max(bullish, 45)

    # Incomplete or conflicting evidence must not produce an exaggerated outlook.
    if not pa_usable:
        bullish = max(35, min(65, bullish))

    bearish = int(max(0, min(100, 100 - bullish)))
    if phase in {"STRONG_RECOVERY", "RECOVERY"}:
        direction = "RECOVERY" if recovery_confirmed else "RECOVERY ATTEMPT"
        probability = bullish
'''
    text = _replace_once(text, old_phase, new_phase, "app projection confirmation")

    text = text.replace(
        '"AI Status": "APPROVED" if _approved else "WATCHLIST / WAITING CONFIRMATION",',
        '"AI Status": "APPROVED" if _approved else "WATCHLIST / FUTURE CANDIDATE — EXECUTION BLOCKED",',
        1,
    )
    if "WATCHLIST / FUTURE CANDIDATE — EXECUTION BLOCKED" not in text:
        raise PatchError("app candidate wording was not patched")

    # Update all V50.6 app labels, including fail-closed branches.
    text = text.replace("V50.6_DHAN_AUTO_FEEDS_PDF", "V50.7_RECOVERY_CONFIRMATION_FIX")
    text = text.replace("Nifty Seller AI V50.6 Dhan Auto Feeds", "Nifty Seller AI V50.7 Recovery Confirmation Fix")
    return text


PATCHERS: dict[str, Callable[[str], str]] = {
    "app.py": patch_app,
    "price_action.py": patch_price_action,
    "strategy_department.py": patch_strategy,
    "ai_master.py": patch_ai_master,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Nifty Seller AI V50.7 safety fix")
    parser.add_argument("project", nargs="?", default=".", help="Project folder containing app.py")
    parser.add_argument("--dry-run", action="store_true", help="Validate patch without writing files")
    args = parser.parse_args()

    root = Path(args.project).expanduser().resolve()
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        print("ERROR: project folder is missing: " + ", ".join(missing), file=sys.stderr)
        return 2

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / f"backup_before_v50_7_{timestamp}"
    originals: dict[str, str] = {}
    patched: dict[str, str] = {}

    try:
        for name in REQUIRED_FILES:
            originals[name] = (root / name).read_text(encoding="utf-8")
            if PATCH_VERSION in originals[name] or "V50.7_RECOVERY_CONFIRMATION_FIX" in originals[name]:
                raise PatchError(f"{name}: V50.7 patch appears to be already applied")
            patched[name] = PATCHERS[name](originals[name])

        if args.dry_run:
            print("DRY RUN PASS: all four files match the expected V50.6/V50.5 structure.")
            return 0

        backup_dir.mkdir(parents=False, exist_ok=False)
        for name in REQUIRED_FILES:
            shutil.copy2(root / name, backup_dir / name)

        try:
            for name in REQUIRED_FILES:
                (root / name).write_text(patched[name], encoding="utf-8")
            for name in REQUIRED_FILES:
                py_compile.compile(str(root / name), doraise=True)
        except Exception:
            for name in REQUIRED_FILES:
                shutil.copy2(backup_dir / name, root / name)
            raise

        report = root / "V50_7_PATCH_APPLIED.txt"
        report.write_text(
            "\n".join(
                [
                    "Nifty Seller AI V50.7 Recovery Confirmation Fix",
                    f"Applied: {datetime.now().isoformat(timespec='seconds')}",
                    f"Backup: {backup_dir.name}",
                    "Changed files: app.py, price_action.py, strategy_department.py, ai_master.py",
                    "Syntax compilation: PASS",
                    "No API/data/refresh/position-manager change.",
                ]
            ) + "\n",
            encoding="utf-8",
        )
        print("PASS: V50.7 fix applied and all changed Python files compiled successfully.")
        print(f"Backup created: {backup_dir}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
