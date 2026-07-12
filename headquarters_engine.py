"""
headquarters_engine.py
Version : V50.3
Role    : Final AI Headquarters integrity and live-validation certificate.

This module is not a department and not a second decision engine.
It runs only after AI_MASTER has issued the final judgement. It verifies the
single-authority chain, produces one compact headquarters certificate, and
maintains a bounded session-only live-validation ledger.

Hard locks:
- Cannot change action, confidence, candidate, execution permission, rules,
  weights, thresholds, SOPs, ranks, training, code, or department votes.
- No API call, timer, thread, loop, polling, or automatic trading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence


ALLOWED_ACTIONS = {"WAIT", "SELL CE", "SELL PE", "IRON CONDOR"}
CRITICAL_STAGES = (
    "VERIFIED_SNAPSHOT",
    "DEPARTMENT_INVESTIGATION",
    "CO_CASE_FILE",
    "MASTER_DOSSIER",
    "AI_MASTER_JUDGEMENT",
    "REASONING_CERTIFICATE",
)


@dataclass(frozen=True)
class HeadquartersCheckpoint:
    stage: str
    status: str
    statement: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "stage": self.stage,
            "status": self.status,
            "statement": self.statement,
        }


@dataclass(frozen=True)
class HeadquartersCertificate:
    snapshot_id: str
    version: str
    headquarters_state: str
    statement: str
    authority_integrity_score: float
    pipeline_complete: bool
    single_brain_lock: str
    final_authority: str
    final_action: str
    final_confidence: float
    trade_allowed: bool
    co_case_id: str
    co_status: str
    co_case_strength: float
    master_state: str
    reasoning_fingerprint: str
    reporting_departments: int
    ready_departments: int
    observation_only_departments: int
    missing_stages: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    checkpoints: List[HeadquartersCheckpoint] = field(default_factory=list)
    live_testing_state: str = "ARCHITECTURE_VALIDATION"
    live_testing_metrics: Dict[str, Any] = field(default_factory=dict)
    testing_protocol: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "version": self.version,
            "headquarters_state": self.headquarters_state,
            "statement": self.statement,
            "authority_integrity_score": self.authority_integrity_score,
            "pipeline_complete": self.pipeline_complete,
            "single_brain_lock": self.single_brain_lock,
            "final_authority": self.final_authority,
            "final_action": self.final_action,
            "final_confidence": self.final_confidence,
            "trade_allowed": self.trade_allowed,
            "co_case_id": self.co_case_id,
            "co_status": self.co_status,
            "co_case_strength": self.co_case_strength,
            "master_state": self.master_state,
            "reasoning_fingerprint": self.reasoning_fingerprint,
            "reporting_departments": self.reporting_departments,
            "ready_departments": self.ready_departments,
            "observation_only_departments": self.observation_only_departments,
            "missing_stages": list(self.missing_stages),
            "conflicts": list(self.conflicts),
            "checkpoints": [item.to_dict() for item in self.checkpoints],
            "live_testing_state": self.live_testing_state,
            "live_testing_metrics": dict(self.live_testing_metrics),
            "testing_protocol": list(self.testing_protocol),
            "warnings": list(self.warnings),
            "authority_chain": [
                "VERIFIED_SNAPSHOT",
                "DSP_DEPARTMENTS",
                "CO_CROSS_EXAMINATION",
                "AI_MASTER_MASTER_DOSSIER",
                "AI_MASTER_FINAL_JUDGEMENT",
                "AI_MASTER_REASONING_CERTIFICATE",
                "V50_HEADQUARTERS_INTEGRITY_CERTIFICATE",
            ],
            "authority": "AI_MASTER_ONLY",
            "execution_instruction": "NONE",
            "automatic_decision_change": False,
            "automatic_confidence_change": False,
            "automatic_candidate_change": False,
            "automatic_execution_change": False,
            "automatic_rule_change": False,
            "automatic_weight_change": False,
            "automatic_threshold_change": False,
            "automatic_training_change": False,
            "automatic_rank_change": False,
            "certificate_only": True,
        }


class FinalAIHeadquarters:
    """Post-judgement integrity certificate for the one-brain architecture."""

    VERSION = "V50.3_FINAL_AI_HEADQUARTERS_CERTIFICATE"
    LEDGER_KEY = "v50_live_validation_ledger"

    def __init__(self, *, history_limit: int = 300) -> None:
        self.history_limit = max(30, min(int(history_limit), 600))

    def certify(
        self,
        *,
        state: MutableMapping[str, Any],
        snapshot_id: str,
        observed_at: Optional[str],
        co_case_file: Any,
        master_intelligence: Any,
        ai_master_decision: Any,
        branch_reports: Mapping[str, Any],
        experience: Optional[Mapping[str, Any]] = None,
        replay: Optional[Mapping[str, Any]] = None,
        self_review: Optional[Mapping[str, Any]] = None,
        promotion_board: Optional[Mapping[str, Any]] = None,
        learning: Optional[Mapping[str, Any]] = None,
    ) -> HeadquartersCertificate:
        snapshot = str(snapshot_id or "UNKNOWN")
        action = str(self._read(ai_master_decision, "action", "WAIT") or "WAIT").upper()
        confidence = self._number(self._read(ai_master_decision, "confidence", 0.0))
        trade_allowed = bool(self._read(ai_master_decision, "trade_allowed", False))
        decision_trace = self._mapping(self._read(ai_master_decision, "trace", {}))
        reasoning = self._mapping(self._read(ai_master_decision, "reasoning_report", {}))
        co_case_id = str(self._read(co_case_file, "case_id", "") or "")
        co_status = str(self._read(co_case_file, "command_status", "CASE_FILE_HOLD") or "CASE_FILE_HOLD")
        co_accepted = bool(self._read(co_case_file, "accepted", False))
        co_strength = self._number(self._read(co_case_file, "case_strength", 0.0))
        master = self._compact_report(master_intelligence)
        master_state = str(master.get("master_state", "COLLECTING_CONTEXT"))
        reports = dict(branch_reports or {})

        checkpoints: List[HeadquartersCheckpoint] = []
        missing: List[str] = []
        conflicts: List[str] = []
        warnings: List[str] = []

        snapshot_ok = snapshot not in {"", "UNKNOWN", "NONE"}
        self._checkpoint(checkpoints, missing, "VERIFIED_SNAPSHOT", snapshot_ok, f"Snapshot {snapshot}")

        department_count = len(reports)
        ready_count = sum(1 for report in reports.values() if str(self._read(report, "status", "")).upper() == "READY")
        observation_only = sum(
            1 for report in reports.values()
            if str(self._read(report, "recommendation", "")).upper() == "INFORMATION_ONLY"
            and str(self._read(report, "branch_vote", "NEUTRAL")).upper() == "NEUTRAL"
        )
        departments_ok = department_count >= 12 and ready_count >= max(8, int(department_count * 0.60))
        self._checkpoint(
            checkpoints,
            missing,
            "DEPARTMENT_INVESTIGATION",
            departments_ok,
            f"{department_count} departments reported; {ready_count} ready; {observation_only} observation-only.",
        )

        co_ok = bool(co_case_id) and decision_trace.get("co_case_id", co_case_id) == co_case_id
        self._checkpoint(
            checkpoints,
            missing,
            "CO_CASE_FILE",
            co_ok,
            f"CO {co_status}; case {co_case_id or 'missing'}; strength {co_strength:.1f}%.",
        )
        if not co_accepted:
            warnings.append("CO case file is on HOLD; AI_MASTER must remain WAIT.")
            if action != "WAIT" or trade_allowed:
                conflicts.append("CO HOLD conflicts with executable AI_MASTER judgement.")

        master_ok = bool(master) and bool(master.get("version")) and master.get("execution_instruction", "NONE") == "NONE"
        self._checkpoint(
            checkpoints,
            missing,
            "MASTER_DOSSIER",
            master_ok,
            f"Master dossier {master_state}; shadow/control disabled.",
        )

        action_ok = action in ALLOWED_ACTIONS
        final_authority_ok = action_ok and str(decision_trace.get("version", "")).startswith(("V49", "V50"))
        self._checkpoint(
            checkpoints,
            missing,
            "AI_MASTER_JUDGEMENT",
            final_authority_ok,
            f"AI_MASTER final action {action}; confidence {confidence:.1f}%; trade_allowed={trade_allowed}.",
        )

        reasoning_fingerprint = str(reasoning.get("decision_fingerprint", reasoning.get("certificate_fingerprint", reasoning.get("fingerprint", ""))) or "")
        if not reasoning_fingerprint:
            reasoning_fingerprint = self._fingerprint(snapshot, co_case_id, action, confidence, reasoning.get("primary_reason", ""))
        reasoning_ok = bool(reasoning) and bool(reasoning.get("primary_reason"))
        self._checkpoint(
            checkpoints,
            missing,
            "REASONING_CERTIFICATE",
            reasoning_ok,
            f"Post-judgement WHY certificate {reasoning_fingerprint[:12]}.",
        )

        experience_view = dict(experience or {})
        replay_view = dict(replay or {})
        self_review_view = dict(self_review or {})
        promotion_view = dict(promotion_board or {})
        learning_view = dict(learning or {})
        institutional_layers_ok = all(
            bool(view)
            for view in (experience_view, replay_view, self_review_view, promotion_view, learning_view)
        )
        checkpoints.append(HeadquartersCheckpoint(
            stage="EXPERIENCE_LEARNING_GOVERNANCE",
            status="PASS" if institutional_layers_ok else "COLLECTING",
            statement=(
                "Experience, Replay, Self Review, Promotion Board and True Learning connected."
                if institutional_layers_ok
                else "One or more long-term learning/governance layers are still collecting evidence."
            ),
        ))

        single_brain_lock = "LOCKED"
        if action not in ALLOWED_ACTIONS or conflicts or not final_authority_ok:
            single_brain_lock = "CAUTION"
        if not co_ok or not snapshot_ok:
            single_brain_lock = "HOLD"

        passed_critical = sum(1 for item in checkpoints if item.stage in CRITICAL_STAGES and item.status == "PASS")
        integrity = passed_critical / len(CRITICAL_STAGES) * 100.0
        if conflicts:
            integrity = max(0.0, integrity - len(conflicts) * 12.0)
        if action == "WAIT" and trade_allowed:
            conflicts.append("WAIT cannot carry executable trade permission.")
            integrity = max(0.0, integrity - 15.0)
        if action != "WAIT" and not trade_allowed:
            warnings.append("Directional action exists in preview/non-executable mode.")

        pipeline_complete = not missing and not conflicts and passed_critical == len(CRITICAL_STAGES)
        if pipeline_complete and single_brain_lock == "LOCKED":
            headquarters_state = "FINAL_HEADQUARTERS_READY"
        elif snapshot_ok and co_ok and final_authority_ok:
            headquarters_state = "FINAL_HEADQUARTERS_CAUTION"
        else:
            headquarters_state = "FINAL_HEADQUARTERS_HOLD"

        ledger = self._record_validation(
            state=state,
            snapshot_id=snapshot,
            observed_at=observed_at,
            action=action,
            confidence=confidence,
            trade_allowed=trade_allowed,
            co_accepted=co_accepted,
            headquarters_state=headquarters_state,
        )
        metrics = self._validation_metrics(
            ledger,
            experience=experience_view,
            self_review=self_review_view,
        )
        live_state = self._live_testing_state(headquarters_state, metrics)
        protocol = [
            "Run 2–3 weeks of live observation before V51 development.",
            "Measure department-wise accuracy using completed cases only.",
            "Review false directional signals, false WAIT cases and late confirmations.",
            "Compare stated confidence with realised accuracy and adverse movement.",
            "Do not auto-change rules; submit validated improvements to AI_MASTER review.",
        ]
        if metrics.get("storage_scope") == "SESSION_ONLY":
            warnings.append("V50 testing ledger is session-bound and may reset after restart/redeploy.")

        statement = (
            f"{headquarters_state}: one verified snapshot, one CO case and one AI_MASTER judgement; "
            f"authority integrity {integrity:.0f}%, single-brain lock {single_brain_lock}."
        )
        return HeadquartersCertificate(
            snapshot_id=snapshot,
            version=self.VERSION,
            headquarters_state=headquarters_state,
            statement=statement,
            authority_integrity_score=round(max(0.0, min(100.0, integrity)), 1),
            pipeline_complete=pipeline_complete,
            single_brain_lock=single_brain_lock,
            final_authority="AI_MASTER",
            final_action=action,
            final_confidence=round(max(0.0, min(100.0, confidence)), 1),
            trade_allowed=trade_allowed,
            co_case_id=co_case_id,
            co_status=co_status,
            co_case_strength=round(max(0.0, min(100.0, co_strength)), 1),
            master_state=master_state,
            reasoning_fingerprint=reasoning_fingerprint,
            reporting_departments=department_count,
            ready_departments=ready_count,
            observation_only_departments=observation_only,
            missing_stages=missing[:8],
            conflicts=conflicts[:8],
            checkpoints=checkpoints[:10],
            live_testing_state=live_state,
            live_testing_metrics=metrics,
            testing_protocol=protocol,
            warnings=warnings[:8],
        )

    @staticmethod
    def _checkpoint(
        checkpoints: List[HeadquartersCheckpoint],
        missing: List[str],
        stage: str,
        ok: bool,
        statement: str,
    ) -> None:
        checkpoints.append(HeadquartersCheckpoint(stage, "PASS" if ok else "HOLD", statement))
        if not ok:
            missing.append(stage)

    def _record_validation(
        self,
        *,
        state: MutableMapping[str, Any],
        snapshot_id: str,
        observed_at: Optional[str],
        action: str,
        confidence: float,
        trade_allowed: bool,
        co_accepted: bool,
        headquarters_state: str,
    ) -> List[Dict[str, Any]]:
        raw = state.get(self.LEDGER_KEY, [])
        ledger = [dict(item) for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []
        if not ledger or str(ledger[-1].get("snapshot_id", "")) != snapshot_id:
            stamp = str(observed_at or datetime.now(timezone.utc).isoformat())
            ledger.append({
                "snapshot_id": snapshot_id,
                "observed_at": stamp,
                "date": stamp[:10],
                "action": action,
                "confidence": round(confidence, 1),
                "trade_allowed": bool(trade_allowed),
                "co_accepted": bool(co_accepted),
                "headquarters_state": headquarters_state,
            })
        ledger = ledger[-self.history_limit :]
        state[self.LEDGER_KEY] = ledger
        return ledger

    def _validation_metrics(
        self,
        ledger: Sequence[Mapping[str, Any]],
        *,
        experience: Mapping[str, Any],
        self_review: Mapping[str, Any],
    ) -> Dict[str, Any]:
        actions = [str(item.get("action", "WAIT")).upper() for item in ledger]
        confidences = [self._number(item.get("confidence", 0)) for item in ledger]
        days = {str(item.get("date", "")) for item in ledger if item.get("date")}
        flip_count = sum(1 for left, right in zip(actions, actions[1:]) if left != right)
        completed_cases = int(self._number(
            experience.get("completed_cases", experience.get("total_completed_cases", 0))
        ))
        reviewed_cases = int(self._number(
            self_review.get("reviewed_cases", self_review.get("completed_cases_reviewed", 0))
        ))
        return {
            "unique_snapshots": len(ledger),
            "observed_days": len(days),
            "wait_judgements": actions.count("WAIT"),
            "trade_judgements": sum(action in {"SELL CE", "SELL PE", "IRON CONDOR"} for action in actions),
            "sell_ce_count": actions.count("SELL CE"),
            "sell_pe_count": actions.count("SELL PE"),
            "iron_condor_count": actions.count("IRON CONDOR"),
            "decision_flip_count": flip_count,
            "average_confidence": round(sum(confidences) / len(confidences), 1) if confidences else 0.0,
            "co_accepted_snapshots": sum(bool(item.get("co_accepted", False)) for item in ledger),
            "headquarters_ready_snapshots": sum(
                str(item.get("headquarters_state", "")) == "FINAL_HEADQUARTERS_READY" for item in ledger
            ),
            "completed_experience_cases": completed_cases,
            "self_reviewed_cases": reviewed_cases,
            "target_live_testing_days": "14–21",
            "storage_scope": "SESSION_ONLY",
        }

    @staticmethod
    def _live_testing_state(headquarters_state: str, metrics: Mapping[str, Any]) -> str:
        if headquarters_state == "FINAL_HEADQUARTERS_HOLD":
            return "LIVE_TEST_BLOCKED_BY_ARCHITECTURE"
        snapshots = int(metrics.get("unique_snapshots", 0) or 0)
        days = int(metrics.get("observed_days", 0) or 0)
        completed = int(metrics.get("completed_experience_cases", 0) or 0)
        if snapshots < 5:
            return "READY_TO_BEGIN_2_3_WEEK_LIVE_TEST"
        if days < 3 or completed < 3:
            return "LIVE_TEST_COLLECTING_BASELINE"
        if days < 14:
            return "LIVE_TEST_IN_PROGRESS"
        return "LIVE_TEST_REVIEW_READY"

    @staticmethod
    def _fingerprint(*parts: Any) -> str:
        payload = "|".join(str(part) for part in parts)
        return sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:20].upper()

    @staticmethod
    def _mapping(value: Any) -> Dict[str, Any]:
        return dict(value) if isinstance(value, Mapping) else {}

    @staticmethod
    def _compact_report(value: Any) -> Dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "to_compact_dict"):
            try:
                result = value.to_compact_dict()
                return dict(result) if isinstance(result, Mapping) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _read(value: Any, key: str, default: Any) -> Any:
        if isinstance(value, Mapping):
            return value.get(key, default)
        return getattr(value, key, default)

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
