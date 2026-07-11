"""
communication_bus.py
Version: V32.0
Role: One-shot department communication bus, CO inbox, AI timeline, and state machine.

Safety:
- No threads, timers, polling, background loops, API calls, or trade decisions.
- One verified snapshot in, one compact message batch out.
- Messages are immutable and bounded.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional


VALID_STATES = (
    "RECEIVED",
    "ANALYSING",
    "WAITING_VERIFICATION",
    "VERIFIED",
    "SENT_TO_CO",
    "CLOSED",
)


@dataclass(frozen=True)
class DepartmentMessage:
    message_id: str
    snapshot_id: str
    timestamp: str
    department: str
    boss: str
    message_type: str
    priority: str
    confidence: float
    subject: str
    body: str
    state: str
    recommendation: str = "INFORMATION_ONLY"
    requires_verification: bool = True
    verified_by: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TimelineEvent:
    sequence: int
    timestamp: str
    snapshot_id: str
    actor: str
    state: str
    event: str


@dataclass(frozen=True)
class CommunicationBatch:
    snapshot_id: str
    generated_at: str
    messages: List[DepartmentMessage]
    co_inbox: List[DepartmentMessage]
    ai_master_inbox: List[DepartmentMessage]
    timeline: List[TimelineEvent]
    state_by_department: Dict[str, str]
    readiness_score: float
    urgent_count: int
    pending_verification_count: int
    health: str

    def to_compact_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at,
            "messages": [asdict(item) for item in self.messages],
            "co_inbox": [asdict(item) for item in self.co_inbox],
            "ai_master_inbox": [asdict(item) for item in self.ai_master_inbox],
            "timeline": [asdict(item) for item in self.timeline],
            "state_by_department": dict(self.state_by_department),
            "readiness_score": self.readiness_score,
            "urgent_count": self.urgent_count,
            "pending_verification_count": self.pending_verification_count,
            "health": self.health,
        }


class DepartmentCommunicationBus:
    """Builds a bounded communication batch from reviewed branch reports."""

    PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

    def build_batch(
        self,
        *,
        snapshot_id: str,
        branch_reports: Mapping[str, Any],
        co_case_file: Optional[Any] = None,
    ) -> CommunicationBatch:
        now = datetime.now(timezone.utc).isoformat()
        messages: List[DepartmentMessage] = []
        timeline: List[TimelineEvent] = []
        states: Dict[str, str] = {}
        sequence = 1

        for department, report in branch_reports.items():
            boss = str(self._read(report, "boss", f"DSP {department.title()}"))
            confidence = self._number(self._read(report, "confidence", 0.0))
            summary = str(self._read(report, "summary", "No report"))[:320]
            recommendation = str(self._read(report, "recommendation", "INFORMATION_ONLY"))
            status = str(self._read(report, "status", "CAUTION"))
            risk_note = str(self._read(report, "risk_note", ""))[:220]
            warnings = self._read(report, "warnings", [])
            warnings = list(warnings) if isinstance(warnings, (list, tuple)) else []

            for state, event in (
                ("RECEIVED", "Department report received by communication bus"),
                ("ANALYSING", "DSP report compacted and checked"),
                ("WAITING_VERIFICATION", "Awaiting cross-branch verification"),
            ):
                timeline.append(TimelineEvent(sequence, now, snapshot_id, department, state, event))
                sequence += 1

            priority = self._priority(department, confidence, status, risk_note, warnings)
            verified_by = self._verification_witnesses(department, report, branch_reports)
            state = "VERIFIED" if verified_by or department == "DATA" else "WAITING_VERIFICATION"
            if state == "VERIFIED":
                timeline.append(TimelineEvent(sequence, now, snapshot_id, department, state, "Cross-branch verification completed"))
                sequence += 1

            message = DepartmentMessage(
                message_id=f"{snapshot_id}-{department}-{len(messages)+1}",
                snapshot_id=snapshot_id,
                timestamp=now,
                department=department,
                boss=boss,
                message_type="EVIDENCE_REPORT",
                priority=priority,
                confidence=round(max(0.0, min(100.0, confidence)), 1),
                subject=f"{department.replace('_', ' ').title()} report",
                body=summary,
                state=state,
                recommendation=recommendation,
                requires_verification=(department != "DATA"),
                verified_by=verified_by,
                tags=self._tags(summary, risk_note),
            )
            messages.append(message)
            states[department] = state

        messages = sorted(
            messages,
            key=lambda item: (
                self.PRIORITY_ORDER.get(item.priority, 9),
                -item.confidence,
                item.department,
            ),
        )[:24]

        co_inbox: List[DepartmentMessage] = []
        for item in messages:
            co_state = "SENT_TO_CO" if item.state == "VERIFIED" else item.state
            states[item.department] = co_state
            co_item = DepartmentMessage(**{**asdict(item), "state": co_state})
            co_inbox.append(co_item)
            if co_state == "SENT_TO_CO":
                timeline.append(TimelineEvent(sequence, now, snapshot_id, item.department, co_state, "Verified message delivered to CO inbox"))
                sequence += 1

        accepted = bool(self._read(co_case_file, "accepted", False))
        command_status = str(self._read(co_case_file, "command_status", "CASE_FILE_HOLD"))
        ai_master_inbox: List[DepartmentMessage] = []
        if accepted:
            court_brief = str(self._read(co_case_file, "court_brief", "CO case file ready"))[:360]
            case_strength = self._number(self._read(co_case_file, "case_strength", 0.0))
            ai_master_inbox.append(
                DepartmentMessage(
                    message_id=f"{snapshot_id}-CO-FINAL",
                    snapshot_id=snapshot_id,
                    timestamp=now,
                    department="CO",
                    boss="Commanding Officer",
                    message_type="APPROVED_CASE_FILE",
                    priority="CRITICAL",
                    confidence=round(case_strength, 1),
                    subject="CO case file approved for AI_MASTER",
                    body=court_brief,
                    state="SENT_TO_CO",
                    recommendation="FORWARD_TO_AI_MASTER",
                    requires_verification=False,
                    verified_by=["CO"],
                    tags=["CASE_READY", command_status],
                )
            )
            timeline.append(TimelineEvent(sequence, now, snapshot_id, "CO", "SENT_TO_CO", "Approved case file forwarded to AI_MASTER inbox"))
            sequence += 1
        else:
            ai_master_inbox.append(
                DepartmentMessage(
                    message_id=f"{snapshot_id}-CO-HOLD",
                    snapshot_id=snapshot_id,
                    timestamp=now,
                    department="CO",
                    boss="Commanding Officer",
                    message_type="CASE_HOLD",
                    priority="HIGH",
                    confidence=self._number(self._read(co_case_file, "case_strength", 0.0)),
                    subject="CO case file held",
                    body="Case file not cleared. AI_MASTER must remain in WAIT.",
                    state="CLOSED",
                    recommendation="WAIT",
                    requires_verification=False,
                    verified_by=["CO"],
                    tags=["CASE_HOLD", command_status],
                )
            )
            timeline.append(TimelineEvent(sequence, now, snapshot_id, "CO", "CLOSED", "Case held; WAIT instruction delivered to AI_MASTER inbox"))
            sequence += 1

        verified_count = sum(1 for state in states.values() if state in {"VERIFIED", "SENT_TO_CO", "CLOSED"})
        total = max(1, len(states))
        readiness = round(verified_count / total * 100.0, 1)
        urgent = sum(1 for item in messages if item.priority in {"CRITICAL", "HIGH"})
        pending = sum(1 for item in messages if item.state == "WAITING_VERIFICATION")
        health = "HEALTHY" if readiness >= 75 and pending <= 2 else "CAUTION"

        # Close branch lifecycle after handoff. This is state only; no background task exists.
        for department in list(states):
            if states[department] == "SENT_TO_CO":
                states[department] = "CLOSED"
                timeline.append(TimelineEvent(sequence, now, snapshot_id, department, "CLOSED", "Department cycle closed until next snapshot"))
                sequence += 1

        return CommunicationBatch(
            snapshot_id=snapshot_id,
            generated_at=now,
            messages=messages,
            co_inbox=co_inbox,
            ai_master_inbox=ai_master_inbox,
            timeline=timeline[-80:],
            state_by_department=states,
            readiness_score=readiness,
            urgent_count=urgent,
            pending_verification_count=pending,
            health=health,
        )

    def _verification_witnesses(
        self,
        department: str,
        report: Any,
        all_reports: Mapping[str, Any],
    ) -> List[str]:
        source_text = self._report_text(report)
        source_tokens = {token for token in source_text.split() if len(token) >= 5}
        witnesses: List[str] = []
        for other_name, other_report in all_reports.items():
            if other_name == department:
                continue
            other_tokens = {token for token in self._report_text(other_report).split() if len(token) >= 5}
            if len(source_tokens.intersection(other_tokens)) >= 1:
                witnesses.append(other_name)
        return witnesses[:3]

    @staticmethod
    def _priority(department: str, confidence: float, status: str, risk_note: str, warnings: List[str]) -> str:
        text = f"{status} {risk_note} {' '.join(map(str, warnings))}".lower()
        if department in {"DATA", "RISK", "STRATEGY"} and ("high" in text or "missing" in text or "caution" in text):
            return "CRITICAL"
        if confidence >= 80 or warnings:
            return "HIGH"
        if confidence >= 55:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _tags(summary: str, risk_note: str) -> List[str]:
        text = f"{summary} {risk_note}".lower()
        tags: List[str] = []
        for token, label in (
            ("bullish", "BULLISH"),
            ("bearish", "BEARISH"),
            ("wait", "CAUTION"),
            ("resistance", "RESISTANCE"),
            ("support", "SUPPORT"),
            ("volume", "VOLUME"),
            ("oi", "OI"),
            ("risk", "RISK"),
        ):
            if token in text:
                tags.append(label)
        return tags[:6]

    @staticmethod
    def _report_text(report: Any) -> str:
        summary = str(DepartmentCommunicationBus._read(report, "summary", ""))
        facts = str(DepartmentCommunicationBus._read(report, "facts", ""))
        recommendation = str(DepartmentCommunicationBus._read(report, "recommendation", ""))
        return f"{summary} {facts} {recommendation}".lower()

    @staticmethod
    def _read(source: Any, key: str, default: Any) -> Any:
        if source is None:
            return default
        if isinstance(source, Mapping):
            return source.get(key, default)
        return getattr(source, key, default)

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
