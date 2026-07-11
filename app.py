import os
import gc
from io import StringIO
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf


# V19.5.1 Full Audit Fix module import.
try:
    from snapshot_engine import (
        build_market_snapshot as v19_build_market_snapshot,
        snapshot_delta as v19_snapshot_delta,
        snapshot_health as v19_snapshot_health,
    )
    V19_SNAPSHOT_ENGINE_READY = True
except Exception:
    V19_SNAPSHOT_ENGINE_READY = False

# V19.4 AI Brain module import.
try:
    from ai_brain import build_ai_explanation as v19_build_ai_explanation
    V19_AI_BRAIN_READY = True
except Exception:
    V19_AI_BRAIN_READY = False

# V19.5 Risk Engine module import.
try:
    from risk_engine import build_risk_report as v19_build_risk_report
    V19_RISK_ENGINE_READY = True
except Exception:
    V19_RISK_ENGINE_READY = False

# V19.6 Decision Engine module import.
try:
    from decision_engine import build_final_decision as v19_build_final_decision
    V19_DECISION_ENGINE_READY = True
except Exception:
    V19_DECISION_ENGINE_READY = False

# V19.10 Strategy Engine module import.
try:
    from strategy_engine import build_strategy_plan as v19_build_strategy_plan
    V19_STRATEGY_ENGINE_READY = True
except Exception:
    V19_STRATEGY_ENGINE_READY = False

# V19.11 Intelligence Engine module import.
try:
    from intelligence_engine import build_intelligence_report as v19_build_intelligence_report
    V19_INTELLIGENCE_ENGINE_READY = True
except Exception:
    V19_INTELLIGENCE_ENGINE_READY = False

# V19.12 Stability Engine module import.
try:
    from stability_engine import apply_stability_lock as v19_apply_stability_lock
    V19_STABILITY_ENGINE_READY = True
except Exception:
    V19_STABILITY_ENGINE_READY = False

# V19.13 Memory Engine module import.
try:
    from memory_engine import update_memory as v19_update_memory
    V19_MEMORY_ENGINE_READY = True
except Exception:
    V19_MEMORY_ENGINE_READY = False

# V19.14 OI Flow Engine module import.
try:
    from oi_flow_engine import update_oi_flow as v19_update_oi_flow
    V19_OI_FLOW_ENGINE_READY = True
except Exception:
    V19_OI_FLOW_ENGINE_READY = False

# V21.4 Single Advisor Authority module import.
try:
    from advisor_engine import build_advisor_report as v214_build_advisor_report
    V21_ADVISOR_ENGINE_READY = True
except Exception:
    V21_ADVISOR_ENGINE_READY = False

# V24 Department Architecture imports.
try:
    from option_intelligence import OptionIntelligenceDirector
    from price_action import PriceActionDirector
    from market_behaviour import MarketBehaviourDirector
    from smart_money import SmartMoneyDirector
    from risk_department import RiskDirector
    from candidate_department import CandidateDirector
    from strategy_department import StrategyDirector
    from ai_master import AIMaster
    from market_memory import MarketMemory
    from learning_department import LearningDepartment
    from command_hierarchy import AIOrganizationController
    from department_academy import DepartmentAcademy
    from communication_bus import DepartmentCommunicationBus
    from case_history import CaseHistoryEngine
    from core.data_intelligence import SnapshotManager, DataDistributor
    V24_DEPARTMENT_ARCHITECTURE_READY = True
except Exception as _v24_import_error:
    V24_DEPARTMENT_ARCHITECTURE_READY = False
    V24_DEPARTMENT_IMPORT_ERROR = str(_v24_import_error)


def _safe_display_df(data):
    """Return a compact, mixed-type-safe DataFrame for HTML rendering.

    V25 deliberately avoids Streamlit's Arrow dataframe transport because the
    deployed Python 3.14 + PyArrow process was segfaulting on browser reconnect.
    """
    df = data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    df = df.head(250).copy()
    for col in df.columns:
        df[col] = df[col].map(
            lambda v: "-" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
        )
    return df


def _render_safe_table(data, *, max_rows=250):
    """Render mixed-type tables without Arrow and without showing raw HTML tags."""
    df = _safe_display_df(data).head(max_rows)
    if df.empty:
        st.caption("No rows available.")
        return

    table_html = df.to_html(
        index=False,
        escape=True,
        border=0,
        classes="v27-safe-table",
    )
    full_html = (
        "<style>"
        ".v27-table-wrap{width:100%;overflow-x:auto;margin:.35rem 0 1rem 0;}"
        ".v27-safe-table{width:100%;border-collapse:collapse;font-size:.84rem;white-space:nowrap;}"
        ".v27-safe-table th,.v27-safe-table td{padding:7px 9px;border:1px solid rgba(128,128,128,.28);text-align:left;}"
        ".v27-safe-table th{font-weight:800;background:rgba(128,128,128,.14);position:sticky;top:0;}"
        ".v27-safe-table tr:nth-child(even){background:rgba(128,128,128,.045);}"
        "</style>"
        "<div class='v27-table-wrap'>" + table_html + "</div>"
    )
    try:
        st.html(full_html)
    except Exception:
        # No indentation before HTML: prevents Markdown from treating it as code.
        st.markdown(full_html, unsafe_allow_html=True)


def _render_v27_command_hierarchy(case_data):
    """Compact visual organization: branches -> CO -> AI_MASTER."""
    if not isinstance(case_data, dict):
        st.info("CO command hierarchy report abhi available nahi hai.")
        return

    status = str(case_data.get("co_status", "CASE_FILE_HOLD"))
    accepted = bool(case_data.get("accepted", False))
    agreement = float(case_data.get("agreement_score", 0) or 0)
    quality = float(case_data.get("data_quality_score", 0) or 0)
    conflicts = list(case_data.get("conflicts", []) or [])
    warnings = list(case_data.get("warnings", []) or [])
    branches = case_data.get("branches", {}) or {}
    case_id = str(case_data.get("case_id", "UNKNOWN"))
    case_strength = float(case_data.get("case_strength", 0) or 0)
    readiness = float(case_data.get("department_readiness", 0) or 0)
    witness_score = float(case_data.get("witness_score", 0) or 0)
    cross_exam_score = float(case_data.get("cross_exam_score", 0) or 0)
    consensus_direction = str(case_data.get("consensus_direction", "NEUTRAL"))
    cross_examinations = list(case_data.get("cross_examinations", []) or [])
    branch_votes = dict(case_data.get("branch_votes", {}) or {})
    court_brief = str(case_data.get("court_brief", ""))
    accepted_evidence = list(case_data.get("accepted_evidence", []) or [])
    rejected_evidence = list(case_data.get("rejected_evidence", []) or [])
    missing_evidence = list(case_data.get("missing_evidence", []) or [])

    co_icon = "✅" if accepted else "⛔"
    st.markdown(
        f"**🎖️ CO Case File:** {co_icon} `{status}` &nbsp; | &nbsp; "
        f"**Branch Agreement:** {agreement:.0f}% &nbsp; | &nbsp; "
        f"**Data Quality:** {quality:.0f}%"
    )
    st.caption(
        f"Case ID: {case_id} | Case Strength: {case_strength:.0f}% | "
        f"Readiness: {readiness:.0f}% | Witness: {witness_score:.0f}% | "
        f"Cross Exam: {cross_exam_score:.0f}% | Consensus: {consensus_direction}"
    )

    rows = []
    branch_order = [
        "DATA", "OPTION", "PRICE_ACTION", "MARKET_BEHAVIOUR",
        "SMART_MONEY", "RISK", "STRATEGY", "CANDIDATE",
    ]
    for branch_name in branch_order:
        branch = branches.get(branch_name, {}) if isinstance(branches, dict) else {}
        if not isinstance(branch, dict):
            branch = {}
        branch_status = str(branch.get("status", "MISSING"))
        rows.append({
            "Branch": branch_name.replace("_", " ").title(),
            "Boss": branch.get("boss", "DSP Not Assigned"),
            "Status": ("✅ " if branch_status == "READY" else "⚠️ ") + branch_status,
            "Confidence": f"{float(branch.get('confidence', 0) or 0):.0f}%",
            "SOP": str(branch.get("sop_status", "NOT_TRAINED")),
            "Learning": str(branch.get("learning_state", "NO_MEMORY")),
            "Memory": str(branch.get("memory_count", 0)),
            "Experience": str(branch.get("experience_count", 0)),
            "Reliability": f"{float(branch.get('reliability_score', 0) or 0):.0f}%",
            "Training": str(branch.get("training_status", "RECRUIT")),
            "Evidence": str(branch.get("evidence_count", 0)),
            "Vote": str(branch.get("branch_vote", branch_votes.get(branch_name, "NEUTRAL"))),
            "Recommendation": str(branch.get("recommendation", "INFORMATION_ONLY")),
            "Report": str(branch.get("summary", "No report"))[:140],
        })
    _render_safe_table(rows, max_rows=12)

    if court_brief:
        st.info("AI Court Brief: " + court_brief)
    if cross_examinations:
        with st.expander("🗣️ CO Cross Examination", expanded=False):
            _cross_rows = []
            for _item in cross_examinations[:12]:
                if not isinstance(_item, dict):
                    continue
                _cross_rows.append({
                    "From": _item.get("question_from", "-"),
                    "To": _item.get("question_to", "-"),
                    "Question": _item.get("question", "-"),
                    "Verdict": _item.get("verdict", "-"),
                    "Score": f"{float(_item.get('score', 0) or 0):.0f}%",
                    "Answer": str(_item.get("answer", "-"))[:180],
                })
            _render_safe_table(_cross_rows, max_rows=12)
    if accepted_evidence:
        st.markdown("**Accepted Evidence**")
        for item in accepted_evidence[:6]: st.write("✅ " + str(item))
    if rejected_evidence:
        with st.expander("Rejected / Weak Evidence"):
            for item in rejected_evidence[:6]: st.write("❌ " + str(item))
    if missing_evidence:
        st.caption("Missing evidence: " + " | ".join(str(x) for x in missing_evidence[:4]))
    if conflicts:
        st.warning("CO conflicts: " + " | ".join(str(x) for x in conflicts[:4]))
    if warnings:
        st.caption("CO warnings: " + " | ".join(str(x) for x in warnings[:4]))

    bus = case_data.get("communication_bus", {}) if isinstance(case_data, dict) else {}
    if isinstance(bus, dict) and bus:
        with st.expander("📡 V32 Department Communication Bus", expanded=False):
            st.markdown(
                f"**Bus Health:** `{bus.get('health','NA')}` &nbsp; | &nbsp; "
                f"**Readiness:** {float(bus.get('readiness_score',0) or 0):.0f}% &nbsp; | &nbsp; "
                f"**Urgent:** {int(bus.get('urgent_count',0) or 0)} &nbsp; | &nbsp; "
                f"**Pending Verification:** {int(bus.get('pending_verification_count',0) or 0)}"
            )
            inbox_rows = []
            for msg in list(bus.get("co_inbox", []) or [])[:16]:
                if not isinstance(msg, dict):
                    continue
                inbox_rows.append({
                    "Priority": msg.get("priority", "-"),
                    "Department": msg.get("department", "-"),
                    "Boss": msg.get("boss", "-"),
                    "State": msg.get("state", "-"),
                    "Confidence": f"{float(msg.get('confidence',0) or 0):.0f}%",
                    "Verified By": ", ".join(msg.get("verified_by", []) or []) or "Pending",
                    "Subject": msg.get("subject", "-"),
                    "Recommendation": msg.get("recommendation", "-"),
                })
            if inbox_rows:
                st.markdown("**CO Inbox**")
                _render_safe_table(inbox_rows, max_rows=16)

            ai_rows = []
            for msg in list(bus.get("ai_master_inbox", []) or [])[:4]:
                if isinstance(msg, dict):
                    ai_rows.append({
                        "Type": msg.get("message_type", "-"),
                        "Priority": msg.get("priority", "-"),
                        "State": msg.get("state", "-"),
                        "Confidence": f"{float(msg.get('confidence',0) or 0):.0f}%",
                        "Recommendation": msg.get("recommendation", "-"),
                        "Message": str(msg.get("body", "-"))[:220],
                    })
            if ai_rows:
                st.markdown("**AI_MASTER Inbox**")
                _render_safe_table(ai_rows, max_rows=4)

            timeline_rows = []
            for event in list(bus.get("timeline", []) or [])[-24:]:
                if isinstance(event, dict):
                    timeline_rows.append({
                        "Seq": event.get("sequence", "-"),
                        "Actor": event.get("actor", "-"),
                        "State": event.get("state", "-"),
                        "Event": event.get("event", "-"),
                    })
            if timeline_rows:
                st.markdown("**Snapshot Timeline**")
                _render_safe_table(timeline_rows, max_rows=24)

    history = case_data.get("case_history", {}) if isinstance(case_data, dict) else {}
    if isinstance(history, dict) and history:
        with st.expander("📚 V33 Case History & Pattern Match", expanded=False):
            st.markdown(
                f"**Status:** `{history.get('status','NA')}` &nbsp; | &nbsp; "
                f"**Stored Cases:** {int(history.get('stored_cases',0) or 0)} &nbsp; | &nbsp; "
                f"**Best Match:** {float(history.get('best_similarity',0) or 0):.0f}%"
            )
            _accuracy = history.get("historical_accuracy")
            if _accuracy is not None:
                st.caption(
                    f"Completed matched cases: {int(history.get('matched_completed_cases',0) or 0)} | "
                    f"Historical accuracy: {float(_accuracy):.1f}%"
                )
            else:
                st.caption("Outcome learning pending: pattern similarity is descriptive, not a guarantee.")
            _similar_rows = []
            for _case in list(history.get("similar_cases", []) or [])[:5]:
                if not isinstance(_case, dict):
                    continue
                _similar_rows.append({
                    "Case ID": _case.get("case_id", "-"),
                    "Similarity": f"{float(_case.get('similarity',0) or 0):.0f}%",
                    "Action": _case.get("action", "-"),
                    "Bias": _case.get("market_bias", "-"),
                    "Case Strength": f"{float(_case.get('case_strength',0) or 0):.0f}%",
                    "Outcome": _case.get("outcome", "PENDING"),
                    "Shared Evidence": ", ".join(_case.get("shared_features", []) or [])[:240],
                })
            if _similar_rows:
                _render_safe_table(_similar_rows, max_rows=5)
            else:
                st.info("Abhi enough similar cases collect nahi hue.")

    st.caption("Command flow: Verified Snapshot → Branch Message Bus → CO Inbox → CO Case File → AI_MASTER Inbox → Case History → Final Authority")


# =========================================================
# NIFTY SELLER AI DASHBOARD V33.0 - CASE HISTORY
# DhanHQ-ready | OI+Price | Heavyweights | News Risk | FII/DII
# =========================================================

IST = ZoneInfo("Asia/Kolkata")
DHAN_BASE = "https://api.dhan.co/v2"
DHAN_INSTRUMENT_MASTER = "https://images.dhan.co/api-data/api-scrip-master.csv"
DEFAULT_NIFTY_SECURITY_ID = 13
DEFAULT_NIFTY_SEGMENT = "IDX_I"

# Official Nifty 50 factsheet dated 30-Jun-2026.
# Keep editable in the sidebar because weights change over time.
TOP5_DEFAULT = {
    "HDFCBANK": {"name": "HDFC Bank", "weight": 11.18, "yahoo": "HDFCBANK.NS"},
    "ICICIBANK": {"name": "ICICI Bank", "weight": 9.01, "yahoo": "ICICIBANK.NS"},
    "RELIANCE": {"name": "Reliance", "weight": 8.00, "yahoo": "RELIANCE.NS"},
    "BHARTIARTL": {"name": "Bharti Airtel", "weight": 5.15, "yahoo": "BHARTIARTL.NS"},
    "LT": {"name": "Larsen & Toubro", "weight": 4.44, "yahoo": "LT.NS"},
}

st.set_page_config(
    page_title="Nifty Seller AI V33 Case History",
    page_icon="🧠",
    layout="wide",
)


# =========================================================
# V19.1 PERSISTENT UI STATE + REFRESH CONTROL FIX
# =========================================================
# Keeps Developer Mode / Trading Mode / Auto Refresh stable across reruns.
if "developer_mode" not in st.session_state:
    st.session_state["developer_mode"] = False
if "trading_mode_clean" not in st.session_state:
    st.session_state["trading_mode_clean"] = True
if "auto_refresh_enabled" not in st.session_state:
    st.session_state["auto_refresh_enabled"] = False
if "auto_refresh_interval" not in st.session_state:
    st.session_state["auto_refresh_interval"] = "20 sec"
if "last_manual_refresh" not in st.session_state:
    st.session_state["last_manual_refresh"] = ""

# V24.1 migration cleanup: older builds stored custom department objects in
# session_state. Remove them once; compact plain-dict history is used now.
for _legacy_v24_key in ("v24_market_memory", "v24_learning_department"):
    st.session_state.pop(_legacy_v24_key, None)

# V21.6: ONE SAFE REFRESH CONTROLLER
# Manual button, floating button and auto-refresh all come through this same function.
def v215_unified_refresh(source="manual", do_rerun=True):
    st.session_state["refresh_master_tick"] = st.session_state.get("refresh_master_tick", 0) + 1
    st.session_state["manual_refresh_tick"] = st.session_state.get("manual_refresh_tick", 0) + 1
    st.session_state["last_manual_refresh"] = datetime.now(IST).strftime("%H:%M:%S")
    st.session_state["last_refresh_source"] = str(source)
    # V24.1 stability: do NOT clear the complete Streamlit cache on every refresh.
    # Global cache clearing creates a large temporary memory spike because all
    # Yahoo/Dhan/DataFrame objects are rebuilt together. Short TTL caches will
    # refresh naturally; the refresh tick still forces the app rerun.
    try:
        # Remove only transient V24 objects; keep bounded history and UI state.
        for _key in (
            "v24_last_department_reports",
            "v24_last_candidate_payload",
            "v24_last_strategy_payload",
        ):
            st.session_state.pop(_key, None)
        gc.collect()
    except Exception:
        pass
    if do_rerun:
        st.rerun()

# Query-param refresh trigger used only by fixed/floating HTML button and auto-refresh JS.
try:
    _manual_qp = str(st.query_params.get("manual_refresh", "")).lower() in ("1", "true", "yes")
    _auto_qp = bool(st.query_params.get("auto_refresh_tick", ""))
    if _manual_qp or _auto_qp:
        _src = "floating" if _manual_qp else "auto"
        for _k in ("manual_refresh", "auto_refresh_tick"):
            try:
                if _k in st.query_params:
                    del st.query_params[_k]
            except Exception:
                pass
        v215_unified_refresh(_src, do_rerun=True)
except Exception:
    pass


st.markdown(
    """
<style>
.main-title {font-size: 2.05rem; font-weight: 850; margin-bottom: 0.15rem;}
.sub-title {font-size: 0.94rem; opacity: 0.75; margin-bottom: 0.95rem;}
.advisor-card {padding: 22px; border-radius: 20px; margin-bottom: 16px; border: 1px solid rgba(255,255,255,0.12); box-shadow: 0 8px 26px rgba(0,0,0,0.18);}
.card-green {background: linear-gradient(135deg, rgba(0,135,75,0.96), rgba(0,82,58,0.96));}
.card-red {background: linear-gradient(135deg, rgba(160,38,38,0.96), rgba(92,24,24,0.96));}
.card-yellow {background: linear-gradient(135deg, rgba(170,126,22,0.96), rgba(105,76,18,0.96));}
.card-wait {background: linear-gradient(135deg, rgba(82,88,99,0.96), rgba(43,48,58,0.96));}
.advisor-card h1 {color: white; font-size: 2.9rem; margin: 4px 0 8px 0;}
.advisor-card h3 {color: white; margin: 0; opacity: 0.96;}
.advisor-card p {color: white; font-size: 1rem; margin: 7px 0;}
.ribbon {padding: 10px 12px; border-radius: 14px; background: rgba(255,255,255,0.075); border: 1px solid rgba(255,255,255,0.10); text-align: center; font-weight: 750; margin-bottom: 8px;}
.small-note {opacity: 0.74; font-size: 0.86rem;}
.source-pill {padding: 5px 9px; border-radius: 10px; background: rgba(255,255,255,0.07); display: inline-block; margin-right: 6px; font-size: 0.84rem;}
.v13-card {padding: 16px; border-radius: 16px; border: 1px solid rgba(128,128,128,0.25); background: rgba(128,128,128,0.06); margin: 8px 0 14px 0;}
.v13-green {color:#16a34a; font-weight:800;}
.v13-red {color:#dc2626; font-weight:800;}
.v13-flat {color:#6b7280; font-weight:800;}
.v13-badge {display:inline-block; padding:4px 8px; border-radius:10px; background:rgba(128,128,128,0.12); margin:2px; font-weight:700;}

.super-card {padding:18px; border-radius:18px; border:1px solid rgba(128,128,128,.25); background:rgba(128,128,128,.07); margin:10px 0;}
.super-good {background:rgba(22,163,74,.16); border-left:5px solid #16a34a; padding:12px; border-radius:12px;}
.super-warn {background:rgba(234,179,8,.16); border-left:5px solid #eab308; padding:12px; border-radius:12px;}
.super-bad {background:rgba(220,38,38,.16); border-left:5px solid #dc2626; padding:12px; border-radius:12px;}
.super-muted {opacity:.76; font-size:.88rem;}
.sidebar-refresh-note {padding:10px;border-radius:12px;background:rgba(34,197,94,.10);border:1px solid rgba(34,197,94,.25);margin:8px 0;}
.v201-top-status{padding:9px 12px;border-radius:12px;background:rgba(128,128,128,.09);border:1px solid rgba(128,128,128,.20);font-weight:750;margin:6px 0 10px 0;}
.v201-ai-card{padding:18px 20px;border-radius:18px;margin:10px 0 14px 0;border-left:8px solid #f59e0b;background:rgba(170,126,22,.20);}
.v201-ai-card.green{border-left-color:#22c55e;background:rgba(22,135,75,.23);}
.v201-ai-card.red{border-left-color:#ef4444;background:rgba(170,38,38,.23);}
.v201-ai-card h2{margin:0 0 8px 0;font-size:1.6rem;}
.v201-reason{margin-top:8px;line-height:1.42;}
.floating-refresh{position:fixed;right:18px;bottom:22px;z-index:999999;background:#2563eb;color:white!important;padding:12px 16px;border-radius:999px;text-decoration:none!important;font-weight:850;box-shadow:0 8px 24px rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.25);cursor:pointer;}
.floating-refresh:hover{background:#1d4ed8;color:white!important;}
@media(max-width:700px){.floating-refresh{right:12px;bottom:16px;padding:11px 14px;font-size:.92rem}.main-title{font-size:1.35rem}.v201-ai-card h2{font-size:1.25rem}}
</style>
<style>
.v17-strip {padding:14px 18px;border-radius:14px;margin:10px 0 12px 0;font-weight:800;border-left:7px solid rgba(255,255,255,.3);}
.v17-red {background:rgba(170,38,38,.25); border-left-color:#ef4444; color:#fecaca;}
.v17-green {background:rgba(22,135,75,.23); border-left-color:#22c55e; color:#bbf7d0;}
.v17-yellow {background:rgba(170,126,22,.22); border-left-color:#f59e0b; color:#fde68a;}
.v17-grey {background:rgba(82,88,99,.22); border-left-color:#94a3b8; color:#e5e7eb;}
.v17-final {padding:24px;border-radius:18px;margin:12px 0 16px 0;border-left:8px solid #f59e0b;background:rgba(170,126,22,.22);}
.v17-final.green {border-left-color:#22c55e;background:rgba(22,135,75,.24);}
.v17-final.red {border-left-color:#ef4444;background:rgba(170,38,38,.24);}
.v17-kpi {padding:16px;border-radius:14px;background:rgba(128,128,128,.08);border:1px solid rgba(128,128,128,.25);}
</style>

<script>
(function() {
  const key = "nifty_ai_scroll_y";
  window.addEventListener("beforeunload", function() {
    try { localStorage.setItem(key, String(window.scrollY || 0)); } catch(e) {}
  });
  setTimeout(function() {
    try {
      const y = parseInt(localStorage.getItem(key) || "0");
      if (y > 200) window.scrollTo(0, y);
    } catch(e) {}
  }, 250);
})();
</script>

""",
    unsafe_allow_html=True,
)


# =========================================================
# GENERIC HELPERS
# =========================================================
def clamp(value, low=0, high=100):
    try:
        value = float(value)
    except Exception:
        value = 0.0
    return max(low, min(high, value))


def signed_clamp(value, low=-100, high=100):
    try:
        value = float(value)
    except Exception:
        value = 0.0
    return max(low, min(high, value))


def safe_divide(a, b, default=0.0):
    try:
        b = float(b)
        if b == 0:
            return default
        return float(a) / b
    except Exception:
        return default


def pct_change(current, previous, default=0.0):
    try:
        previous = float(previous)
        if previous == 0:
            return default
        return ((float(current) - previous) / abs(previous)) * 100.0
    except Exception:
        return default


def get_secret(name, default=""):
    try:
        return str(st.secrets[name]).strip()
    except Exception:
        return str(os.getenv(name, default)).strip()


def now_ist():
    return datetime.now(IST)


def fmt_time(dt=None):
    dt = dt or now_ist()
    return dt.strftime("%d-%m-%Y %I:%M:%S %p")


def market_status():
    now = now_ist()
    open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_open = now.weekday() < 5 and open_time <= now <= close_time
    return "Market Open" if is_open else "Market Closed", now.strftime("%A")


def risk_label(score):
    score = clamp(score)
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


def bias_label(score):
    score = signed_clamp(score)
    if score >= 55:
        return "STRONG BULLISH"
    if score >= 20:
        return "BULLISH"
    if score <= -55:
        return "STRONG BEARISH"
    if score <= -20:
        return "BEARISH"
    return "MIXED"


def manual_risk_score(label):
    return {"Low": 15, "Medium": 45, "High": 70, "Critical": 92}.get(label, 15)


def dhan_credentials():
    return get_secret("DHAN_CLIENT_ID"), get_secret("DHAN_ACCESS_TOKEN")


def dhan_headers(client_id, access_token):
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "client-id": str(client_id),
        "access-token": str(access_token),
    }



# V19.1 Refresh compatibility variables
try:
    auto_refresh = bool(st.session_state.get("auto_refresh_enabled", False))
    auto_refresh_enabled = auto_refresh
    auto_interval_label = st.session_state.get("auto_refresh_interval", "20 sec")
    auto_interval_seconds = int(str(auto_interval_label).split()[0])
except Exception:
    auto_refresh = False
    auto_refresh_enabled = False
    auto_interval_label = "20 sec"
    auto_interval_seconds = 20


# =========================================================
# DHANHQ DATA LAYER
# =========================================================
@st.cache_data(ttl=86400, show_spinner=False)
def get_dhan_instrument_master():
    """Fetch Dhan compact instrument master and return a DataFrame."""
    try:
        response = requests.get(DHAN_INSTRUMENT_MASTER, timeout=25)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text), low_memory=False)
        return {"success": True, "df": df, "message": "Dhan instrument master loaded."}
    except Exception as exc:
        return {"success": False, "df": pd.DataFrame(), "message": f"Instrument master error: {exc}"}


def resolve_top5_security_ids(master_df):
    """Resolve NSE equity security IDs from Dhan instrument master."""
    if master_df is None or master_df.empty:
        return {}

    required = {
        "exchange": "SEM_EXM_EXCH_ID",
        "segment": "SEM_SEGMENT",
        "security": "SEM_SMST_SECURITY_ID",
        "symbol": "SEM_TRADING_SYMBOL",
    }
    if not all(column in master_df.columns for column in required.values()):
        return {}

    work = master_df.copy()
    work[required["exchange"]] = work[required["exchange"]].astype(str).str.upper().str.strip()
    work[required["segment"]] = work[required["segment"]].astype(str).str.upper().str.strip()
    work[required["symbol"]] = work[required["symbol"]].astype(str).str.upper().str.strip()

    eq = work[(work[required["exchange"]] == "NSE") & (work[required["segment"]] == "E")]
    result = {}
    for symbol in TOP5_DEFAULT:
        rows = eq[eq[required["symbol"]] == symbol]
        if not rows.empty:
            try:
                result[symbol] = int(float(rows.iloc[0][required["security"]]))
            except Exception:
                pass
    return result


@st.cache_data(ttl=4, show_spinner=False)
def get_dhan_market_bundle(client_id, access_token, top5_ids, nifty_security_id=DEFAULT_NIFTY_SECURITY_ID):
    """One Dhan Market Quote request for Nifty + top-5 equities."""
    if not client_id or not access_token:
        return {"success": False, "message": "Dhan credentials missing."}
    try:
        body = {"IDX_I": [int(nifty_security_id)]}
        if top5_ids:
            body["NSE_EQ"] = [int(v) for v in top5_ids.values()]

        response = requests.post(
            f"{DHAN_BASE}/marketfeed/quote",
            headers=dhan_headers(client_id, access_token),
            json=body,
            timeout=12,
        )
        if response.status_code != 200:
            return {"success": False, "message": f"Dhan Market Quote HTTP {response.status_code}: {response.text[:180]}"}
        payload = response.json()
        if payload.get("status") != "success":
            return {"success": False, "message": f"Dhan Market Quote failed: {payload}"}
        return {"success": True, "data": payload.get("data", {}), "fetched_at": fmt_time(), "message": "OK"}
    except Exception as exc:
        return {"success": False, "message": f"Dhan Market Quote error: {exc}"}


@st.cache_data(ttl=600, show_spinner=False)
def get_dhan_expiries(client_id, access_token, underlying_scrip=DEFAULT_NIFTY_SECURITY_ID, underlying_seg=DEFAULT_NIFTY_SEGMENT):
    if not client_id or not access_token:
        return {"success": False, "expiries": [], "message": "Dhan credentials missing."}
    try:
        response = requests.post(
            f"{DHAN_BASE}/optionchain/expirylist",
            headers=dhan_headers(client_id, access_token),
            json={"UnderlyingScrip": int(underlying_scrip), "UnderlyingSeg": underlying_seg},
            timeout=12,
        )
        if response.status_code != 200:
            return {"success": False, "expiries": [], "message": f"Dhan expiry HTTP {response.status_code}: {response.text[:180]}"}
        payload = response.json()
        expiries = payload.get("data", []) if payload.get("status") == "success" else []
        return {"success": bool(expiries), "expiries": expiries, "message": "OK" if expiries else f"No expiries: {payload}"}
    except Exception as exc:
        return {"success": False, "expiries": [], "message": f"Dhan expiry error: {exc}"}


def parse_dhan_leg(leg):
    leg = leg or {}
    greeks = leg.get("greeks", {}) or {}
    ltp = float(leg.get("last_price", 0) or 0)
    prev_close = float(leg.get("previous_close_price", 0) or 0)
    oi = int(leg.get("oi", 0) or 0)
    prev_oi = int(leg.get("previous_oi", 0) or 0)
    volume = int(leg.get("volume", 0) or 0)
    prev_volume = int(leg.get("previous_volume", 0) or 0)
    bid = float(leg.get("top_bid_price", 0) or 0)
    ask = float(leg.get("top_ask_price", 0) or 0)
    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else max(ltp, 0)
    spread = max(ask - bid, 0) if ask > 0 and bid > 0 else 0

    return {
        "ltp": ltp,
        "previous_close": prev_close,
        "price_change": ltp - prev_close if prev_close else 0.0,
        "price_change_pct": pct_change(ltp, prev_close),
        "oi": oi,
        "previous_oi": prev_oi,
        "oi_change": oi - prev_oi,
        "oi_change_pct": pct_change(oi, prev_oi),
        "volume": volume,
        "previous_volume": prev_volume,
        "volume_ratio": safe_divide(volume, prev_volume, 0.0),
        "iv": float(leg.get("implied_volatility", 0) or 0),
        "delta": float(greeks.get("delta", 0) or 0),
        "theta": float(greeks.get("theta", 0) or 0),
        "gamma": float(greeks.get("gamma", 0) or 0),
        "vega": float(greeks.get("vega", 0) or 0),
        "bid": bid,
        "ask": ask,
        "bid_qty": int(leg.get("top_bid_quantity", 0) or 0),
        "ask_qty": int(leg.get("top_ask_quantity", 0) or 0),
        "spread": spread,
        "spread_pct": safe_divide(spread, mid, 0.0) * 100 if mid else 0.0,
        "security_id": int(leg.get("security_id", 0) or 0),
        "average_price": float(leg.get("average_price", 0) or 0),
    }


@st.cache_data(ttl=4, show_spinner=False)
def get_dhan_option_chain(client_id, access_token, expiry, underlying_scrip=DEFAULT_NIFTY_SECURITY_ID, underlying_seg=DEFAULT_NIFTY_SEGMENT, strikes_each_side=6, strike_gap=50):
    """Fetch and normalize Dhan option chain. Official API minimum unique request window is 3 seconds."""
    if not client_id or not access_token or not expiry:
        return {"success": False, "message": "Dhan credentials/expiry missing."}
    try:
        response = requests.post(
            f"{DHAN_BASE}/optionchain",
            headers=dhan_headers(client_id, access_token),
            json={
                "UnderlyingScrip": int(underlying_scrip),
                "UnderlyingSeg": underlying_seg,
                "Expiry": str(expiry),
            },
            timeout=15,
        )
        if response.status_code != 200:
            return {"success": False, "message": f"Dhan Option Chain HTTP {response.status_code}: {response.text[:220]}"}
        payload = response.json()
        if payload.get("status") != "success":
            return {"success": False, "message": f"Dhan Option Chain failed: {payload}"}

        data = payload.get("data", {}) or {}
        spot = float(data.get("last_price", 0) or 0)
        raw_oc = data.get("oc", {}) or {}
        if not raw_oc:
            return {"success": False, "message": "Dhan option chain returned no strikes."}

        atm = int(round(spot / strike_gap) * strike_gap) if spot else 0
        lower = atm - strikes_each_side * strike_gap
        upper = atm + strikes_each_side * strike_gap
        rows = []

        for strike_key, strike_data in raw_oc.items():
            try:
                strike = int(round(float(strike_key)))
            except Exception:
                continue
            if atm and not (lower <= strike <= upper):
                continue

            ce = parse_dhan_leg((strike_data or {}).get("ce", {}))
            pe = parse_dhan_leg((strike_data or {}).get("pe", {}))
            row = {"strike": strike}
            for prefix, leg in (("ce", ce), ("pe", pe)):
                for key, value in leg.items():
                    row[f"{prefix}_{key}"] = value
            rows.append(row)

        rows.sort(key=lambda x: x["strike"])
        if not rows:
            return {"success": False, "message": "No Dhan strikes found near ATM."}

        total_call_oi = sum(r["ce_oi"] for r in rows)
        total_put_oi = sum(r["pe_oi"] for r in rows)
        call_oi_change = sum(r["ce_oi_change"] for r in rows)
        put_oi_change = sum(r["pe_oi_change"] for r in rows)

        return {
            "success": True,
            "source": "DhanHQ",
            "underlying": spot,
            "expiry": str(expiry),
            "atm_strike": atm,
            "rows": rows,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "call_oi_change": call_oi_change,
            "put_oi_change": put_oi_change,
            "pcr": safe_divide(total_put_oi, total_call_oi, 0.0),
            "fetched_at": fmt_time(),
            "snapshot_id": f"{expiry}|{fmt_time()}|{sum(r['ce_oi'] + r['pe_oi'] for r in rows)}",
            "message": "OK",
        }
    except Exception as exc:
        return {"success": False, "message": f"Dhan Option Chain error: {exc}"}


# =========================================================
# YAHOO FALLBACKS (NO NSE OPTION-CHAIN SCRAPING)
# =========================================================
@st.cache_data(ttl=30, show_spinner=False)
def get_yahoo_nifty():
    try:
        ticker = yf.Ticker("^NSEI")
        intraday = ticker.history(period="2d", interval="1m").dropna()
        if intraday.empty:
            intraday = ticker.history(period="5d", interval="5m").dropna()
        if intraday.empty:
            return {"success": False, "message": "Yahoo Nifty unavailable."}
        ltp = float(intraday["Close"].iloc[-1])
        daily = ticker.history(period="7d", interval="1d").dropna()
        prev = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else ltp
        return {
            "success": True,
            "price": ltp,
            "change": ltp - prev,
            "change_pct": pct_change(ltp, prev),
            "source": "Yahoo fallback",
            "fetched_at": fmt_time(),
        }
    except Exception as exc:
        return {"success": False, "message": f"Yahoo Nifty error: {exc}"}


@st.cache_data(ttl=60, show_spinner=False)
def get_yahoo_vix():
    try:
        ticker = yf.Ticker("^INDIAVIX")
        intraday = ticker.history(period="2d", interval="1m").dropna()
        if intraday.empty:
            intraday = ticker.history(period="5d", interval="5m").dropna()
        if intraday.empty:
            return {"success": False, "message": "Yahoo VIX unavailable."}
        ltp = float(intraday["Close"].iloc[-1])
        daily = ticker.history(period="7d", interval="1d").dropna()
        prev = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else ltp
        return {
            "success": True,
            "vix": ltp,
            "change": ltp - prev,
            "change_pct": pct_change(ltp, prev),
            "source": "Yahoo fallback",
            "fetched_at": fmt_time(),
        }
    except Exception as exc:
        return {"success": False, "message": f"Yahoo VIX error: {exc}"}



@st.cache_data(ttl=10, show_spinner=False)
def get_yahoo_price_action():
    """Automatic Price Action from Nifty intraday candles.
    Dhan option-chain remains primary; this gives live auto EMA/VWAP/ATR/High-Low fallback
    instead of stale manual sidebar values.
    """
    try:
        ticker = yf.Ticker("^NSEI")
        df = ticker.history(period="5d", interval="5m").dropna()
        if df.empty or len(df) < 60:
            return {"success": False, "message": "Not enough Nifty candles for Price Action."}
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(IST)
        else:
            df.index = df.index.tz_convert(IST)
        close = df["Close"].astype(float)
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series([0]*len(df), index=df.index)
        ema20_v = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50_v = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        # VWAP for current trading date. If volume is unavailable/zero, fall back to typical price mean.
        today_date = df.index[-1].date()
        today_df = df[df.index.date == today_date].copy()
        if today_df.empty:
            today_df = df.tail(75).copy()
        typical = (today_df["High"] + today_df["Low"] + today_df["Close"]) / 3.0
        vol = today_df["Volume"] if "Volume" in today_df.columns else pd.Series([0]*len(today_df), index=today_df.index)
        if float(vol.sum() or 0) > 0:
            vwap_v = float((typical * vol).sum() / vol.sum())
        else:
            vwap_v = float(typical.mean())
        prev_dates = sorted(set(df.index.date))
        prev_day_high_v = float(high.max())
        prev_day_low_v = float(low.min())
        if len(prev_dates) >= 2:
            prev_df = df[df.index.date == prev_dates[-2]]
            if not prev_df.empty:
                prev_day_high_v = float(prev_df["High"].max())
                prev_day_low_v = float(prev_df["Low"].min())
        today_high_v = float(today_df["High"].max())
        today_low_v = float(today_df["Low"].min())
        # Opening range 09:15 to 09:30/09:45 if available
        or_df = today_df.between_time("09:15", "09:45")
        if or_df.empty:
            or_df = today_df.head(6)
        or_high_v = float(or_df["High"].max()) if not or_df.empty else today_high_v
        or_low_v = float(or_df["Low"].min()) if not or_df.empty else today_low_v
        prev_close = close.shift(1)
        tr = pd.concat([(high-low).abs(), (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
        atr5_v = float(tr.rolling(14).mean().dropna().iloc[-1]) if not tr.rolling(14).mean().dropna().empty else 0.0
        return {
            "success": True,
            "ema20": ema20_v,
            "ema50": ema50_v,
            "vwap": vwap_v,
            "atr5": atr5_v,
            "previous_day_high": prev_day_high_v,
            "previous_day_low": prev_day_low_v,
            "today_high": today_high_v,
            "today_low": today_low_v,
            "opening_range_high": or_high_v,
            "opening_range_low": or_low_v,
            "fetched_at": fmt_time(),
            "source": "Yahoo candles auto",
            "message": "OK",
        }
    except Exception as exc:
        return {"success": False, "message": f"Price Action auto error: {exc}", "source": "Manual"}

@st.cache_data(ttl=60, show_spinner=False)
def get_yahoo_heavyweights():
    """Batch fallback for top-5 stock moves; 5-minute bars to keep it lighter."""
    try:
        symbols = [cfg["yahoo"] for cfg in TOP5_DEFAULT.values()]
        intraday = yf.download(
            tickers=symbols,
            period="2d",
            interval="5m",
            group_by="column",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        daily = yf.download(
            tickers=symbols,
            period="7d",
            interval="1d",
            group_by="column",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        rows = []
        for symbol, cfg in TOP5_DEFAULT.items():
            ysym = cfg["yahoo"]
            try:
                if isinstance(intraday.columns, pd.MultiIndex):
                    close_series = intraday["Close"][ysym].dropna()
                    vol_series = intraday["Volume"][ysym].dropna() if "Volume" in intraday.columns.get_level_values(0) else pd.Series(dtype=float)
                else:
                    close_series = intraday["Close"].dropna()
                    vol_series = intraday.get("Volume", pd.Series(dtype=float)).dropna()
                if isinstance(daily.columns, pd.MultiIndex):
                    day_close = daily["Close"][ysym].dropna()
                else:
                    day_close = daily["Close"].dropna()
                if close_series.empty:
                    continue
                ltp = float(close_series.iloc[-1])
                prev = float(day_close.iloc[-2]) if len(day_close) >= 2 else ltp
                momentum_5m = pct_change(ltp, float(close_series.iloc[-2])) if len(close_series) >= 2 else 0.0
                rows.append({
                    "symbol": symbol,
                    "name": cfg["name"],
                    "weight": cfg["weight"],
                    "ltp": ltp,
                    "previous_close": prev,
                    "change_pct": pct_change(ltp, prev),
                    "momentum_pct": momentum_5m,
                    "volume": int(vol_series.iloc[-1]) if not vol_series.empty else 0,
                })
            except Exception:
                continue
        return {"success": bool(rows), "rows": rows, "source": "Yahoo fallback", "fetched_at": fmt_time(), "message": "OK" if rows else "No heavyweight rows."}
    except Exception as exc:
        return {"success": False, "rows": [], "message": f"Yahoo heavyweight error: {exc}"}


# =========================================================
# SNAPSHOT DELTAS + OPTION INTELLIGENCE
# =========================================================
def attach_option_snapshot_deltas(rows, snapshot_id):
    """Add snapshot-to-snapshot deltas for OI acceleration. First snapshot is day-change only."""
    current_map = {}
    for row in rows:
        for side in ("ce", "pe"):
            current_map[(row["strike"], side)] = {
                "ltp": row.get(f"{side}_ltp", 0),
                "oi": row.get(f"{side}_oi", 0),
                "volume": row.get(f"{side}_volume", 0),
            }

    last_id = st.session_state.get("oc_snapshot_id")
    previous_map = st.session_state.get("oc_snapshot_map", {})
    stored_deltas = st.session_state.get("oc_snapshot_deltas", {})

    if snapshot_id != last_id:
        deltas = {}
        for key, current in current_map.items():
            previous = previous_map.get(key)
            if previous:
                deltas[key] = {
                    "price": current["ltp"] - previous["ltp"],
                    "price_pct": pct_change(current["ltp"], previous["ltp"]),
                    "oi": current["oi"] - previous["oi"],
                    "oi_pct": pct_change(current["oi"], previous["oi"]),
                    "volume": current["volume"] - previous["volume"],
                    "ready": True,
                }
            else:
                deltas[key] = {"price": 0.0, "price_pct": 0.0, "oi": 0, "oi_pct": 0.0, "volume": 0, "ready": False}
        st.session_state["oc_snapshot_map"] = current_map
        st.session_state["oc_snapshot_id"] = snapshot_id
        st.session_state["oc_snapshot_deltas"] = deltas
        stored_deltas = deltas

    output = []
    for row in rows:
        row = row.copy()
        for side in ("ce", "pe"):
            delta = stored_deltas.get((row["strike"], side), {})
            row[f"{side}_snap_price_change"] = delta.get("price", 0.0)
            row[f"{side}_snap_price_change_pct"] = delta.get("price_pct", 0.0)
            row[f"{side}_snap_oi_change"] = delta.get("oi", 0)
            row[f"{side}_snap_oi_change_pct"] = delta.get("oi_pct", 0.0)
            row[f"{side}_snap_volume_change"] = delta.get("volume", 0)
            row[f"{side}_snapshot_ready"] = bool(delta.get("ready", False))
        output.append(row)
    return output


def classify_oi_price_signal(side, row):
    """Conventional OI/price inference; not proof of buyer/seller identity."""
    prefix = side.lower()
    use_snapshot = bool(row.get(f"{prefix}_snapshot_ready", False)) and (
        abs(row.get(f"{prefix}_snap_price_change_pct", 0)) >= 0.02
        or abs(row.get(f"{prefix}_snap_oi_change_pct", 0)) >= 0.02
    )

    if use_snapshot:
        price_delta = row.get(f"{prefix}_snap_price_change", 0.0)
        price_pct = row.get(f"{prefix}_snap_price_change_pct", 0.0)
        oi_delta = row.get(f"{prefix}_snap_oi_change", 0)
        oi_pct = row.get(f"{prefix}_snap_oi_change_pct", 0.0)
        basis = "Snapshot"
    else:
        price_delta = row.get(f"{prefix}_price_change", 0.0)
        price_pct = row.get(f"{prefix}_price_change_pct", 0.0)
        oi_delta = row.get(f"{prefix}_oi_change", 0)
        oi_pct = row.get(f"{prefix}_oi_change_pct", 0.0)
        basis = "Day"

    if price_delta > 0 and oi_delta > 0:
        signal = f"Likely Fresh {side} Buying"
        market_bias = 1 if side == "CE" else -1
    elif price_delta < 0 and oi_delta > 0:
        signal = f"Likely Fresh {side} Writing"
        market_bias = -1 if side == "CE" else 1
    elif price_delta > 0 and oi_delta < 0:
        signal = f"{side} Short Covering"
        market_bias = 1 if side == "CE" else -1
    elif price_delta < 0 and oi_delta < 0:
        signal = f"{side} Long Unwinding"
        market_bias = -0.45 if side == "CE" else 0.45
    else:
        signal = "Neutral"
        market_bias = 0

    strength = 25
    strength += min(abs(price_pct) * 8, 25)
    strength += min(abs(oi_pct) * 2.5, 25)

    volume_ratio = row.get(f"{prefix}_volume_ratio", 0.0)
    if volume_ratio >= 2:
        strength += 15
    elif volume_ratio >= 1.2:
        strength += 10
    elif volume_ratio >= 0.7:
        strength += 5

    spread_pct = row.get(f"{prefix}_spread_pct", 0.0)
    if 0 < spread_pct <= 0.5:
        strength += 10
    elif spread_pct <= 1.0:
        strength += 6
    elif spread_pct > 2.0:
        strength -= 10

    if use_snapshot:
        strength += 8

    strength = int(round(clamp(strength, 0, 98)))
    directional_score = market_bias * strength
    return {
        "signal": signal,
        "basis": basis,
        "strength": strength,
        "directional_score": directional_score,
        "price_pct": price_pct,
        "oi_pct": oi_pct,
        "oi_delta": oi_delta,
    }


def score_sell_candidate(side, row, signal_info, spot):
    prefix = side.lower()
    score = 35.0
    reasons = []
    strike = row["strike"]

    is_otm = strike >= spot if side == "CE" else strike <= spot
    if is_otm:
        score += 10
        reasons.append("OTM/ATM side")
    else:
        score -= 18
        reasons.append("ITM risk")

    signal = signal_info["signal"]
    if "Writing" in signal:
        score += 24
        reasons.append("writing inference")
    elif "Short Covering" in signal:
        score -= 30
        reasons.append("short-covering risk")
    elif "Buying" in signal:
        score -= 24
        reasons.append("buyer pressure")
    elif "Long Unwinding" in signal:
        score += 2

    delta_abs = abs(row.get(f"{prefix}_delta", 0.0))
    if 0.15 <= delta_abs <= 0.32:
        score += 18
        reasons.append("seller-friendly delta")
    elif 0.10 <= delta_abs <= 0.40:
        score += 10
    elif delta_abs >= 0.48:
        score -= 20
        reasons.append("high delta")

    spread_pct = row.get(f"{prefix}_spread_pct", 0.0)
    if 0 < spread_pct <= 0.5:
        score += 12
        reasons.append("tight spread")
    elif spread_pct <= 1.0:
        score += 7
    elif spread_pct > 2.0:
        score -= 15
        reasons.append("wide spread")

    volume_ratio = row.get(f"{prefix}_volume_ratio", 0.0)
    if volume_ratio >= 1.5:
        score += 8
    elif volume_ratio >= 0.75:
        score += 4

    oi_change_pct = row.get(f"{prefix}_oi_change_pct", 0.0)
    if oi_change_pct > 0:
        score += min(oi_change_pct * 0.4, 8)

    iv = row.get(f"{prefix}_iv", 0.0)
    if 8 <= iv <= 25:
        score += 6
    elif iv > 35:
        score -= 6
        reasons.append("very high IV risk")

    theta = row.get(f"{prefix}_theta", 0.0)
    if theta < -3:
        score += 4

    return int(round(clamp(score, 0, 98))), ", ".join(reasons[:4])


def analyze_option_chain(option_chain):
    if not option_chain.get("success"):
        return {"success": False, "rows": [], "bias": 0, "message": option_chain.get("message", "No option chain")}

    rows = attach_option_snapshot_deltas(option_chain["rows"], option_chain["snapshot_id"])
    spot = option_chain["underlying"]
    atm = option_chain["atm_strike"]
    analyzed = []
    directional_total = 0.0
    directional_weight = 0.0

    for row in rows:
        ce_info = classify_oi_price_signal("CE", row)
        pe_info = classify_oi_price_signal("PE", row)
        ce_sell_score, ce_reason = score_sell_candidate("CE", row, ce_info, spot)
        pe_sell_score, pe_reason = score_sell_candidate("PE", row, pe_info, spot)

        distance = abs(row["strike"] - atm)
        near_weight = max(0.35, 1.0 - (distance / 500.0))
        directional_total += (ce_info["directional_score"] + pe_info["directional_score"]) * near_weight
        directional_weight += 2 * 98 * near_weight

        analyzed.append({
            **row,
            "ce_signal": ce_info["signal"],
            "ce_signal_basis": ce_info["basis"],
            "ce_signal_strength": ce_info["strength"],
            "ce_sell_score": ce_sell_score,
            "ce_sell_reason": ce_reason,
            "pe_signal": pe_info["signal"],
            "pe_signal_basis": pe_info["basis"],
            "pe_signal_strength": pe_info["strength"],
            "pe_sell_score": pe_sell_score,
            "pe_sell_reason": pe_reason,
        })

    bias = signed_clamp(safe_divide(directional_total, directional_weight, 0.0) * 100, -100, 100)
    ce_candidates = [r for r in analyzed if r["strike"] >= spot]
    pe_candidates = [r for r in analyzed if r["strike"] <= spot]
    best_ce = max(ce_candidates, key=lambda r: r["ce_sell_score"], default=None)
    best_pe = max(pe_candidates, key=lambda r: r["pe_sell_score"], default=None)

    return {
        "success": True,
        "rows": analyzed,
        "bias": bias,
        "best_ce": best_ce,
        "best_pe": best_pe,
        "snapshot_id": option_chain.get("snapshot_id", ""),
        "fetched_at": option_chain.get("fetched_at", ""),
        "underlying": option_chain.get("underlying", spot),
        "message": "OK",
    }


# =========================================================
# HEAVYWEIGHT DRIVER ENGINE
# =========================================================
def parse_dhan_heavyweights(bundle, top5_ids, weights):
    if not bundle.get("success") or not top5_ids:
        return {"success": False, "rows": [], "message": bundle.get("message", "No Dhan bundle")}
    try:
        eq = (bundle.get("data", {}) or {}).get("NSE_EQ", {}) or {}
        rows = []
        for symbol, sec_id in top5_ids.items():
            item = eq.get(str(sec_id), {}) or eq.get(int(sec_id), {}) or {}
            if not item:
                continue
            cfg = TOP5_DEFAULT[symbol]
            ltp = float(item.get("last_price", 0) or 0)
            ohlc = item.get("ohlc", {}) or {}
            prev = float(ohlc.get("close", 0) or 0)
            rows.append({
                "symbol": symbol,
                "name": cfg["name"],
                "weight": float(weights.get(symbol, cfg["weight"])),
                "ltp": ltp,
                "previous_close": prev,
                "change_pct": pct_change(ltp, prev),
                "momentum_pct": 0.0,
                "volume": int(item.get("volume", 0) or 0),
            })
        return {"success": bool(rows), "rows": rows, "source": "DhanHQ", "fetched_at": bundle.get("fetched_at", fmt_time()), "message": "OK" if rows else "No Dhan heavyweight rows."}
    except Exception as exc:
        return {"success": False, "rows": [], "message": f"Dhan heavyweight parse error: {exc}"}


def attach_heavyweight_shocks(rows, snapshot_id):
    current = {r["symbol"]: r["change_pct"] for r in rows}
    last_id = st.session_state.get("hw_snapshot_id")
    previous = st.session_state.get("hw_snapshot_map", {})
    shocks = st.session_state.get("hw_snapshot_shocks", {})

    if snapshot_id != last_id:
        new_shocks = {}
        for symbol, change_pct_value in current.items():
            if symbol in previous:
                new_shocks[symbol] = change_pct_value - previous[symbol]
            else:
                new_shocks[symbol] = 0.0
        st.session_state["hw_snapshot_id"] = snapshot_id
        st.session_state["hw_snapshot_map"] = current
        st.session_state["hw_snapshot_shocks"] = new_shocks
        shocks = new_shocks

    output = []
    for row in rows:
        row = row.copy()
        row["shock_delta_pct"] = float(shocks.get(row["symbol"], 0.0))
        output.append(row)
    return output


def analyze_heavyweights(hw_data, nifty_level, nifty_change_pct):
    if not hw_data.get("success") or not hw_data.get("rows"):
        return {"success": False, "rows": [], "pressure": 0, "estimated_points": 0, "message": hw_data.get("message", "No heavyweight data")}

    snapshot_id = f"{hw_data.get('fetched_at','')}|{sum(round(r['change_pct'],4) for r in hw_data['rows'])}"
    rows = attach_heavyweight_shocks(hw_data["rows"], snapshot_id)
    combined_weight = sum(r["weight"] for r in rows) or 1.0
    weighted_return = sum(r["weight"] * r["change_pct"] for r in rows) / combined_weight
    pressure = signed_clamp(weighted_return * 75, -100, 100)
    estimated_points = sum(nifty_level * (r["weight"] / 100.0) * (r["change_pct"] / 100.0) for r in rows)

    hdfc = next((r for r in rows if r["symbol"] == "HDFCBANK"), None)
    icici = next((r for r in rows if r["symbol"] == "ICICIBANK"), None)
    banking_pair = "MIXED"
    if hdfc and icici:
        if hdfc["change_pct"] > 0.15 and icici["change_pct"] > 0.15:
            banking_pair = "BULLISH"
        elif hdfc["change_pct"] < -0.15 and icici["change_pct"] < -0.15:
            banking_pair = "BEARISH"

    divergence = "NONE"
    if nifty_change_pct >= 0.20 and pressure <= -20:
        divergence = "NIFTY UP / HEAVYWEIGHTS WEAK"
    elif nifty_change_pct <= -0.20 and pressure >= 20:
        divergence = "NIFTY DOWN / HEAVYWEIGHTS STRONG"
    elif abs(nifty_change_pct) <= 0.10 and abs(pressure) >= 45:
        divergence = "HIDDEN HEAVYWEIGHT PRESSURE"

    shock_rows = [r for r in rows if abs(r.get("shock_delta_pct", 0.0)) >= 0.30]
    max_shock = max((abs(r.get("shock_delta_pct", 0.0)) for r in rows), default=0.0)
    shock_score = clamp(max_shock * 120, 0, 100)

    return {
        "success": True,
        "rows": rows,
        "pressure": pressure,
        "estimated_points": estimated_points,
        "banking_pair": banking_pair,
        "divergence": divergence,
        "shock_rows": shock_rows,
        "shock_score": shock_score,
        "source": hw_data.get("source", "Unknown"),
        "message": "OK",
    }


# =========================================================
# AUTOMATIC NEWS RISK ENGINE (OPTIONAL KEYS + MARKET REACTION)
# =========================================================
@st.cache_data(ttl=900, show_spinner=False)
def get_te_calendar_risk(api_key):
    """Optional Trading Economics calendar risk for India + United States."""
    if not api_key:
        return {"success": False, "score": 0, "events": 0, "message": "TE key missing."}
    try:
        all_events = []
        for country in ("india", "united states"):
            url = f"https://api.tradingeconomics.com/calendar/country/{quote(country)}?c={quote(api_key)}"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, list):
                    all_events.extend(payload)

        now = now_ist()
        max_score = 0.0
        relevant = 0
        nearest_minutes = None
        for event in all_events:
            importance = int(event.get("Importance", 0) or 0)
            if importance < 2:
                continue
            raw_date = event.get("Date") or event.get("date")
            if not raw_date:
                continue
            try:
                dt = pd.to_datetime(raw_date, utc=True).to_pydatetime().astimezone(IST)
            except Exception:
                continue
            minutes = (dt - now).total_seconds() / 60.0
            if -30 <= minutes <= 24 * 60:
                relevant += 1
                nearest_minutes = minutes if nearest_minutes is None else min(nearest_minutes, minutes, key=abs)
                if importance >= 3:
                    score = 92 if abs(minutes) <= 30 else 82 if minutes <= 90 else 68 if minutes <= 240 else 52
                else:
                    score = 65 if abs(minutes) <= 30 else 52 if minutes <= 120 else 35
                max_score = max(max_score, score)

        return {
            "success": True,
            "score": clamp(max_score),
            "events": relevant,
            "nearest_minutes": nearest_minutes,
            "message": "OK",
        }
    except Exception as exc:
        return {"success": False, "score": 0, "events": 0, "message": f"TE calendar error: {exc}"}


@st.cache_data(ttl=900, show_spinner=False)
def get_alpha_news_risk(api_key):
    """Optional Alpha Vantage news sentiment risk. Headlines are not displayed."""
    if not api_key:
        return {"success": False, "score": 0, "items": 0, "message": "Alpha Vantage key missing."}
    try:
        params = {
            "function": "NEWS_SENTIMENT",
            "topics": "financial_markets,economy_macro",
            "sort": "LATEST",
            "limit": 50,
            "apikey": api_key,
        }
        response = requests.get("https://www.alphavantage.co/query", params=params, timeout=18)
        if response.status_code != 200:
            return {"success": False, "score": 0, "items": 0, "message": f"Alpha HTTP {response.status_code}"}
        payload = response.json()
        feed = payload.get("feed", []) if isinstance(payload, dict) else []
        if not feed:
            return {"success": False, "score": 0, "items": 0, "message": payload.get("Information", "No news feed") if isinstance(payload, dict) else "No news feed"}

        now = datetime.utcnow()
        keywords = {
            "war", "attack", "tariff", "sanction", "default", "emergency", "recession",
            "inflation", "rate hike", "rate cut", "fed", "rbi", "crude", "oil shock",
            "budget", "election", "missile", "conflict", "bank failure", "downgrade",
        }
        max_score = 0.0
        counted = 0
        for item in feed:
            raw_time = str(item.get("time_published", ""))
            try:
                dt = datetime.strptime(raw_time[:15], "%Y%m%dT%H%M%S")
                age_hours = max((now - dt).total_seconds() / 3600.0, 0)
            except Exception:
                age_hours = 24
            if age_hours > 24:
                continue
            counted += 1
            sentiment = abs(float(item.get("overall_sentiment_score", 0) or 0))
            text = f"{item.get('title','')} {item.get('summary','')}".lower()
            keyword_hits = sum(1 for key in keywords if key in text)
            recency = max(0, 1 - age_hours / 24)
            score = sentiment * 45 + min(keyword_hits * 10, 35) + recency * 20
            max_score = max(max_score, score)

        return {"success": True, "score": clamp(max_score), "items": counted, "message": "OK"}
    except Exception as exc:
        return {"success": False, "score": 0, "items": 0, "message": f"Alpha news error: {exc}"}


def market_reaction_risk(nifty_change_pct, vix_change_pct, heavyweight_analysis):
    score = 0.0
    score += min(abs(nifty_change_pct) * 32, 35)
    score += min(max(vix_change_pct, 0) * 4.5, 30)
    score += min(abs(heavyweight_analysis.get("pressure", 0)) * 0.20, 20)
    score += min(heavyweight_analysis.get("shock_score", 0) * 0.25, 25)
    if heavyweight_analysis.get("divergence") != "NONE":
        score += 10
    return clamp(score)


def build_news_risk(manual_label, te_result, alpha_result, reaction_score, vix_change_pct, heavyweight_shock_score):
    scheduled = te_result.get("score", 0) if te_result.get("success") else manual_risk_score(manual_label)
    breaking = alpha_result.get("score", 0) if alpha_result.get("success") else manual_risk_score(manual_label) * 0.70
    shock = clamp(max(vix_change_pct, 0) * 8 + heavyweight_shock_score * 0.5)
    score = scheduled * 0.35 + breaking * 0.25 + reaction_score * 0.25 + shock * 0.15
    return {
        "score": int(round(clamp(score))),
        "label": risk_label(score),
        "scheduled": int(round(clamp(scheduled))),
        "breaking": int(round(clamp(breaking))),
        "reaction": int(round(clamp(reaction_score))),
        "shock": int(round(clamp(shock))),
        "auto_calendar": bool(te_result.get("success")),
        "auto_news": bool(alpha_result.get("success")),
    }


# =========================================================
# V7 UPGRADE: POSITION MANAGER + EXPIRY/SHOCK/DISCIPLINE
# =========================================================
def detect_expiry_mode(expiry_text, news_score):
    """Auto mode: Normal / Near Expiry / Expiry / Event Risk."""
    if news_score >= 80:
        return "EVENT RISK MODE", 99
    try:
        today = now_ist().date()
        exp_date = pd.to_datetime(str(expiry_text)).date()
        dte = (exp_date - today).days
    except Exception:
        dte = 99
    if dte == 0:
        return "EXPIRY MODE", dte
    if dte in (1, 2):
        return "NEAR EXPIRY MODE", dte
    return "NORMAL DAY MODE", dte


def historical_time_zone_risk(is_expiry):
    """Historical caution zones: prediction nahi, sirf precaution."""
    t = now_ist().time()
    score = 18
    label = "Normal Zone"
    if datetime.strptime("09:15", "%H:%M").time() <= t <= datetime.strptime("09:45", "%H:%M").time():
        score, label = 65, "Opening Volatility Zone"
    elif datetime.strptime("10:00", "%H:%M").time() <= t <= datetime.strptime("10:20", "%H:%M").time():
        score, label = 45, "First Trend Test Zone"
    elif datetime.strptime("11:30", "%H:%M").time() <= t <= datetime.strptime("12:00", "%H:%M").time():
        score, label = 35, "Midday False Move Zone"
    elif datetime.strptime("13:45", "%H:%M").time() <= t <= datetime.strptime("14:15", "%H:%M").time():
        score, label = 42, "Post-Lunch Setup Zone"
    elif datetime.strptime("14:30", "%H:%M").time() <= t <= datetime.strptime("15:15", "%H:%M").time():
        score, label = 58, "Last Hour Move Zone"
    if is_expiry and datetime.strptime("14:15", "%H:%M").time() <= t <= datetime.strptime("15:25", "%H:%M").time():
        score, label = max(score, 78), "Expiry Gamma Danger Zone"
    return int(clamp(score)), label


def theta_decay_score(is_expiry, entry_price, current_price):
    decay_pct = 0.0
    if entry_price and entry_price > 0 and current_price >= 0:
        decay_pct = ((entry_price - current_price) / entry_price) * 100.0
    score = 20 + (35 if is_expiry else 0)
    if decay_pct >= 35:
        score += 35
    elif decay_pct >= 20:
        score += 25
    elif decay_pct >= 10:
        score += 12
    return int(clamp(score)), decay_pct


def gamma_risk_score(is_expiry, vix_change_pct, shock_score, option_bias, heavy_bias):
    score = 18 + (35 if is_expiry else 0)
    if vix_change_pct > 5:
        score += 25
    elif vix_change_pct > 2:
        score += 12
    score += min(abs(option_bias) * 0.15, 12)
    score += min(abs(heavy_bias) * 0.12, 10)
    score += shock_score * 0.22
    return int(clamp(score))


def shock_probability_score(time_risk, vix_risk, option_bias, heavy_bias, news_score):
    oi_shift_risk = clamp(abs(option_bias))
    hw_risk = clamp(abs(heavy_bias))
    score = time_risk * 0.20 + vix_risk * 0.20 + oi_shift_risk * 0.20 + hw_risk * 0.20 + news_score * 0.20
    return int(round(clamp(score)))


def active_position_manager(side, strike, entry_price, current_price, lots, theta_score, gamma_score, shock_score, final_trade, confidence):
    if side == "None" or lots <= 0 or entry_price <= 0:
        return {"action": "NO ACTIVE POSITION", "confidence": 0, "risk": 0, "trail_sl": 0.0, "profit_pct": 0.0, "reasons": ["Active trade details not entered."]}
    profit_pct = ((entry_price - current_price) / entry_price) * 100.0
    reasons = [f"Premium move from ₹{entry_price:.2f} to ₹{current_price:.2f}: approx {profit_pct:.1f}% in seller favour."]
    opposite = (side == "CE" and final_trade == "SELL PE") or (side == "PE" and final_trade == "SELL CE")
    if shock_score >= 78 or gamma_score >= 78:
        reasons += ["Shock/Gamma risk high.", "Capital protection priority."]
        return {"action": "EXIT NOW", "confidence": 88, "risk": max(shock_score, gamma_score), "trail_sl": 0.0, "profit_pct": profit_pct, "reasons": reasons}
    if opposite and confidence >= 60:
        reasons += ["Fresh AI direction is opposite to current sold side.", "Hold risk has increased."]
        return {"action": "EXIT / BOOK PROFIT", "confidence": 82, "risk": max(shock_score, gamma_score), "trail_sl": 0.0, "profit_pct": profit_pct, "reasons": reasons}
    if profit_pct >= 30 and (shock_score >= 55 or gamma_score >= 60):
        reasons += ["Good profit available but risk is rising.", "Book full/partial profit is safer."]
        return {"action": "BOOK PROFIT", "confidence": 84, "risk": max(shock_score, gamma_score), "trail_sl": 0.0, "profit_pct": profit_pct, "reasons": reasons}
    if profit_pct >= 22 and theta_score >= 60 and shock_score < 55:
        trail = round(max(current_price * 1.15, current_price + 3), 2)
        reasons += ["Theta decay still supportive.", f"Trail SL around ₹{trail:.2f} premium."]
        return {"action": "HOLD + TRAIL SL", "confidence": 78, "risk": shock_score, "trail_sl": trail, "profit_pct": profit_pct, "reasons": reasons}
    if theta_score >= 65 and shock_score < 50 and gamma_score < 55:
        reasons += ["Theta favourable and live danger controlled."]
        return {"action": "HOLD", "confidence": 70, "risk": shock_score, "trail_sl": 0.0, "profit_pct": profit_pct, "reasons": reasons}
    reasons += ["No strong edge for aggressive hold.", "Tight SL recommended."]
    return {"action": "TIGHTEN SL", "confidence": 62, "risk": max(shock_score, gamma_score), "trail_sl": round(current_price * 1.10, 2), "profit_pct": profit_pct, "reasons": reasons}


def discipline_status(trades_taken, daily_loss_hit, confidence, seller_risk):
    if daily_loss_hit:
        return "STOP TRADING TODAY", 15, "Daily loss hit: recovery/revenge trade avoid karo."
    if trades_taken >= 3:
        return "OVERTRADING WARNING", 35, "3 or more trades: discipline mode active."
    if confidence < 58:
        return "NO TRADE - LOW CONFIDENCE", 45, "AI confidence low hai. Wait is better."
    if seller_risk >= 70:
        return "RISK HIGH - REDUCE SIZE", 55, "Seller risk high hai; quantity reduce/avoid."
    return "DISCIPLINE OK", 85, "Rules ke andar trade allowed only if setup clear."


def trade_quality_score(confidence, seller_risk, shock_score):
    return int(round(clamp(confidence * 0.55 + (100 - seller_risk) * 0.25 + (100 - shock_score) * 0.20)))



# =========================================================
# V9 DECISION QUALITY LAYER
# =========================================================
def v9_conflict_detector(price_action_bias, option_bias, heavy_bias, pcr, gamma_score=0):
    """
    Detects when market parts disagree. In conflict mode, WAIT is preferred.
    """
    reasons = []
    if option_bias >= 55 and price_action_bias <= -45:
        reasons.append("Option Chain bullish hai, lekin Price Action strong bearish hai.")
    if option_bias <= -55 and price_action_bias >= 45:
        reasons.append("Option Chain bearish hai, lekin Price Action strong bullish hai.")
    if heavy_bias >= 35 and price_action_bias <= -45:
        reasons.append("Heavyweights bullish hain, lekin chart bearish hai.")
    if heavy_bias <= -35 and price_action_bias >= 45:
        reasons.append("Heavyweights bearish hain, lekin chart bullish hai.")
    if pcr < 0.80 and option_bias >= 45:
        reasons.append("PCR bearish zone mein hai, par Option Chain bullish signal de rahi hai.")
    if pcr > 1.55 and option_bias <= -45:
        reasons.append("PCR overheated bullish zone mein hai, par Option Chain bearish signal de rahi hai.")
    if gamma_score >= 70:
        reasons.append("Gamma risk high hai; option seller ko aggressive trade avoid karna chahiye.")
    return bool(reasons), reasons


# V18.4 cleanup: removed unused old helper v9_action_plan


# V18.4 cleanup: removed unused old helper v9_data_quality_score



# =========================================================
# V9.1 DECISION QUALITY LAYER - STABLE
# =========================================================
def v91_safe_num(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def v91_conflict_detector(price_action_bias, option_bias, heavy_bias, pcr, gamma_score=0):
    """
    Market ke major signals opposite hon to fresh trade avoid.
    """
    reasons = []
    price_action_bias = v91_safe_num(price_action_bias)
    option_bias = v91_safe_num(option_bias)
    heavy_bias = v91_safe_num(heavy_bias)
    pcr = v91_safe_num(pcr)
    gamma_score = v91_safe_num(gamma_score)

    if option_bias >= 55 and price_action_bias <= -45:
        reasons.append("Option Chain bullish hai, lekin Price Action strong bearish hai.")
    if option_bias <= -55 and price_action_bias >= 45:
        reasons.append("Option Chain bearish hai, lekin Price Action strong bullish hai.")
    if heavy_bias >= 35 and price_action_bias <= -45:
        reasons.append("Heavyweights bullish hain, lekin chart bearish hai.")
    if heavy_bias <= -35 and price_action_bias >= 45:
        reasons.append("Heavyweights bearish hain, lekin chart bullish hai.")
    if pcr < 0.80 and option_bias >= 45:
        reasons.append("PCR bearish zone mein hai, par Option Chain bullish signal de rahi hai.")
    if pcr > 1.55 and option_bias <= -45:
        reasons.append("PCR overheated bullish zone mein hai, par Option Chain bearish signal de rahi hai.")
    if gamma_score >= 70:
        reasons.append("Gamma risk high hai; option seller ko aggressive trade avoid karna chahiye.")
    return bool(reasons), reasons

def v91_data_quality_score(dhan_ready=False, option_ok=False, nifty_source="Fallback", heavy_source="Fallback", vix_source="Fallback"):
    score = 0
    reasons = []
    if dhan_ready:
        score += 20
        reasons.append("Dhan credentials detected")
    else:
        reasons.append("Dhan credentials missing")

    if option_ok:
        score += 35
        reasons.append("Dhan live option-chain active")
    else:
        reasons.append("Option-chain fallback/not live")

    if str(nifty_source).lower().startswith("dhan"):
        score += 20
        reasons.append("Nifty from DhanHQ")
    else:
        score += 8
        reasons.append(f"Nifty source: {nifty_source}")

    if str(heavy_source).lower().startswith("dhan"):
        score += 15
        reasons.append("Heavyweights from DhanHQ")
    elif str(heavy_source).lower().startswith("yahoo"):
        score += 10
        reasons.append("Heavyweights from Yahoo fallback")
    else:
        reasons.append(f"Heavyweights source: {heavy_source}")

    if str(vix_source).lower().startswith("dhan"):
        score += 10
        reasons.append("VIX from DhanHQ")
    elif str(vix_source):
        score += 6
        reasons.append(f"VIX source: {vix_source}")
    else:
        reasons.append("VIX source unavailable")

    return int(max(0, min(100, score))), reasons

def v91_action_plan(final_trade, selected_strike, hedge, confidence, seller_risk, shock_score, gamma_score, conflict_reasons, source_text, data_quality=0):
    plan = []
    if data_quality < 70:
        plan.append("Data quality 70 se kam hai: real trade avoid karo, pehle data source verify karo.")
    if "Fallback" in str(source_text):
        plan.append("Fallback data active hai: real trade avoid karo ya sirf observation mode rakho.")
    if conflict_reasons:
        plan.append("Market conflict mode: fresh trade avoid karo jab tak 2-3 signals same direction mein na aayen.")
        for r in conflict_reasons[:3]:
            plan.append(r)
    if final_trade == "WAIT":
        plan.append("Final action: WAIT. No trade bhi valid seller decision hai.")
    else:
        plan.append(f"Final action: {final_trade} at {selected_strike} with hedge {hedge}.")
        plan.append(f"Confidence {v91_safe_num(confidence):.0f}% | Seller Risk {v91_safe_num(seller_risk):.0f}% | Shock {v91_safe_num(shock_score):.0f}/100 | Gamma {v91_safe_num(gamma_score):.0f}/100")
        if v91_safe_num(confidence) < 70:
            plan.append("Confidence medium/low hai: sirf 1 lot test ya avoid.")
        if v91_safe_num(seller_risk) > 55 or v91_safe_num(shock_score) > 55:
            plan.append("Risk elevated hai: SL tight rakho aur profit fast protect karo.")
    return plan



# =========================================================
# V10.2 UI + FII/DII JOURNAL HELPERS
# =========================================================
from pathlib import Path as _Path

FII_DII_STORE = _Path("data/fii_dii_journal.csv")

ACTIVE_POSITION_STORE = _Path("data/active_position.csv")

def v16_load_active_position():
    defaults = {
        "Active Sold Side": "None", "Active Strike": 0, "Entry Premium ₹": 0.0,
        "Current Premium ₹": 0.0, "Active Lots": 0, "Trades Taken Today": 0,
        "Daily Loss Hit / Stop Trading": False, "Saved At": ""
    }
    try:
        if ACTIVE_POSITION_STORE.exists():
            df = pd.read_csv(ACTIVE_POSITION_STORE)
            if not df.empty:
                row = df.iloc[-1].to_dict()
                defaults.update(row)
                defaults["Active Strike"] = int(float(defaults.get("Active Strike", 0) or 0))
                defaults["Active Lots"] = int(float(defaults.get("Active Lots", 0) or 0))
                defaults["Trades Taken Today"] = int(float(defaults.get("Trades Taken Today", 0) or 0))
                defaults["Entry Premium ₹"] = float(defaults.get("Entry Premium ₹", 0) or 0)
                defaults["Current Premium ₹"] = float(defaults.get("Current Premium ₹", 0) or 0)
                defaults["Daily Loss Hit / Stop Trading"] = str(defaults.get("Daily Loss Hit / Stop Trading", False)).lower() in ("true", "1", "yes")
    except Exception:
        pass
    return defaults

def v16_save_active_position(side, strike, entry_price, current_price, lots, trades_taken, daily_loss_hit):
    try:
        ACTIVE_POSITION_STORE.parent.mkdir(parents=True, exist_ok=True)
        row = pd.DataFrame([{
            "Active Sold Side": side,
            "Active Strike": int(strike or 0),
            "Entry Premium ₹": float(entry_price or 0),
            "Current Premium ₹": float(current_price or 0),
            "Active Lots": int(lots or 0),
            "Trades Taken Today": int(trades_taken or 0),
            "Daily Loss Hit / Stop Trading": bool(daily_loss_hit),
            "Saved At": fmt_time(),
        }])
        row.to_csv(ACTIVE_POSITION_STORE, index=False)
        return True
    except Exception:
        return False

def v16_clear_active_position():
    try:
        if ACTIVE_POSITION_STORE.exists():
            ACTIVE_POSITION_STORE.unlink()
        return True
    except Exception:
        return False



# =========================================================
# V16.2 SUPER APP: MULTI-POSITION PORTFOLIO MANAGER
# =========================================================
PORTFOLIO_POSITION_STORE = _Path("data/portfolio_positions.csv")

PORTFOLIO_COLUMNS = [
    "Position ID", "Status", "Strategy", "Lots", "Lot Size",
    "Sell1 Side", "Sell1 Strike", "Sell1 Entry", "Hedge1 Strike", "Hedge1 Entry",
    "Sell2 Side", "Sell2 Strike", "Sell2 Entry", "Hedge2 Strike", "Hedge2 Entry",
    "SL %", "Target %", "Created At", "Updated At", "Notes",
]

def v162_portfolio_load():
    try:
        if PORTFOLIO_POSITION_STORE.exists():
            df = pd.read_csv(PORTFOLIO_POSITION_STORE)
            for col in PORTFOLIO_COLUMNS:
                if col not in df.columns:
                    df[col] = "" if col in ["Position ID", "Status", "Strategy", "Created At", "Updated At", "Notes", "Sell1 Side", "Sell2 Side"] else 0
            return df[PORTFOLIO_COLUMNS]
    except Exception:
        pass
    return pd.DataFrame(columns=PORTFOLIO_COLUMNS)

def v162_portfolio_save(df):
    try:
        PORTFOLIO_POSITION_STORE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(PORTFOLIO_POSITION_STORE, index=False)
        return True
    except Exception:
        return False

def v162_new_position_id():
    return "P" + now_ist().strftime("%H%M%S")

def v162_add_position(strategy, lots, lot_size, sell1_side, sell1_strike, sell1_entry, hedge1_strike, hedge1_entry,
                      sell2_side="", sell2_strike=0, sell2_entry=0.0, hedge2_strike=0, hedge2_entry=0.0,
                      sl_pct=25.0, target_pct=35.0, notes=""):
    df = v162_portfolio_load()
    row = {
        "Position ID": v162_new_position_id(),
        "Status": "ACTIVE",
        "Strategy": strategy,
        "Lots": int(lots or 0),
        "Lot Size": int(lot_size or 65),
        "Sell1 Side": sell1_side,
        "Sell1 Strike": int(sell1_strike or 0),
        "Sell1 Entry": float(sell1_entry or 0),
        "Hedge1 Strike": int(hedge1_strike or 0),
        "Hedge1 Entry": float(hedge1_entry or 0),
        "Sell2 Side": sell2_side,
        "Sell2 Strike": int(sell2_strike or 0),
        "Sell2 Entry": float(sell2_entry or 0),
        "Hedge2 Strike": int(hedge2_strike or 0),
        "Hedge2 Entry": float(hedge2_entry or 0),
        "SL %": float(sl_pct or 25),
        "Target %": float(target_pct or 35),
        "Created At": fmt_time(),
        "Updated At": fmt_time(),
        "Notes": notes,
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return v162_portfolio_save(df)

def v162_update_position_status(position_id, status):
    df = v162_portfolio_load()
    if df.empty:
        return False
    mask = df["Position ID"].astype(str) == str(position_id)
    if not mask.any():
        return False
    df.loc[mask, "Status"] = status
    df.loc[mask, "Updated At"] = fmt_time()
    return v162_portfolio_save(df)

def v162_find_leg(row_dict, side, strike):
    """Find live premium for CE/PE strike from analyzed option rows."""
    try:
        rows = (option_analysis or {}).get("rows", []) if isinstance(option_analysis, dict) else []
        strike = int(float(strike or 0))
        side = str(side or "").lower()
        if not side or strike <= 0:
            return 0.0
        for r in rows:
            if int(r.get("strike", 0) or 0) == strike:
                return float(r.get(f"{side}_ltp", 0) or 0)
    except Exception:
        pass
    return 0.0

def v162_leg_pnl(side, sell_strike, sell_entry, hedge_strike, hedge_entry, lots, lot_sz):
    sell_cur = v162_find_leg({}, side, sell_strike)
    hedge_cur = v162_find_leg({}, side, hedge_strike)
    sell_entry = float(sell_entry or 0)
    hedge_entry = float(hedge_entry or 0)
    lots = int(lots or 0)
    lot_sz = int(lot_sz or 65)
    sell_pts = sell_entry - sell_cur if sell_entry > 0 and sell_cur > 0 else 0.0
    hedge_pts = hedge_cur - hedge_entry if hedge_entry > 0 and hedge_cur > 0 else 0.0
    net_pts = sell_pts + hedge_pts
    return {
        "sell_current": sell_cur,
        "hedge_current": hedge_cur,
        "net_points": net_pts,
        "pnl": net_pts * lots * lot_sz,
        "profit_pct": safe_divide(sell_entry - sell_cur, sell_entry, 0.0) * 100 if sell_entry else 0.0,
    }

def v162_analyze_position(pos):
    lots = int(float(pos.get("Lots", 0) or 0))
    lot_sz = int(float(pos.get("Lot Size", 65) or 65))
    leg1 = v162_leg_pnl(pos.get("Sell1 Side", ""), pos.get("Sell1 Strike", 0), pos.get("Sell1 Entry", 0), pos.get("Hedge1 Strike", 0), pos.get("Hedge1 Entry", 0), lots, lot_sz)
    leg2 = {"sell_current":0.0,"hedge_current":0.0,"net_points":0.0,"pnl":0.0,"profit_pct":0.0}
    if str(pos.get("Strategy", "")).upper() == "IRON CONDOR" or str(pos.get("Sell2 Side", "")):
        leg2 = v162_leg_pnl(pos.get("Sell2 Side", ""), pos.get("Sell2 Strike", 0), pos.get("Sell2 Entry", 0), pos.get("Hedge2 Strike", 0), pos.get("Hedge2 Entry", 0), lots, lot_sz)
    total_pnl = leg1["pnl"] + leg2["pnl"]
    avg_profit_pct = (leg1["profit_pct"] + (leg2["profit_pct"] if str(pos.get("Sell2 Side", "")) else leg1["profit_pct"])) / (2 if str(pos.get("Sell2 Side", "")) else 1)
    risk = max(int(locals().get("gamma_score_v7", 0) or 0), int(locals().get("shock_score_v7", 0) or 0))
    action = "HOLD"
    reason = "Premium decay normal hai. SL discipline rakho."
    if risk >= 75:
        action, reason = "EXIT / REDUCE", "Gamma/Shock risk high hai. Capital protection priority."
    elif avg_profit_pct >= 35:
        action, reason = "BOOK 50% / TRAIL", "Achha decay mil gaya. Partial profit secure karo."
    elif avg_profit_pct >= 20:
        action, reason = "HOLD + TRAIL SL", "Profit in favour hai. Trail SL use karo."
    elif avg_profit_pct <= -25:
        action, reason = "EXIT IF SL HIT", "Premium seller ke against gaya. SL check karo."
    elif str(locals().get("final_trade", "WAIT")) == "WAIT":
        action, reason = "MANAGE ONLY", "Fresh trade WAIT hai; existing position ko tight manage karo."
    return {
        "Action": action,
        "Reason": reason,
        "P/L ₹": round(total_pnl, 0),
        "Net Points": round(leg1["net_points"] + leg2["net_points"], 2),
        "Profit %": round(avg_profit_pct, 1),
        "Sell1 Cur": round(leg1["sell_current"], 2),
        "Hedge1 Cur": round(leg1["hedge_current"], 2),
        "Sell2 Cur": round(leg2["sell_current"], 2),
        "Hedge2 Cur": round(leg2["hedge_current"], 2),
    }

# V19.7 CLEANUP: removed obsolete v162_signal_gate().
# Decision Engine report is the single execution-gate authority.


def v102_metric_card(label, value, delta=None):
    """Compact metric card for long labels like NEAR EXPIRY MODE."""
    safe_delta = f"<div class='metric-delta'>{delta}</div>" if delta not in (None, "") else ""
    st.markdown(
        f"""
        <div class="mini-metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value-small">{value}</div>
            {safe_delta}
        </div>
        """,
        unsafe_allow_html=True,
    )

def v102_load_fii_dii_journal():
    """Load FII/DII journal and keep schema backward-compatible."""
    cols = [
        "Date", "FII Cash Cr", "DII Cash Cr",
        "FII Index Futures Contracts", "FII Long %", "FII Short %",
        "FII Index Futures Bias", "FII Options Bias", "Notes"
    ]
    try:
        if FII_DII_STORE.exists():
            df = pd.read_csv(FII_DII_STORE)
            for col in cols:
                if col not in df.columns:
                    df[col] = 0.0 if col in ["FII Index Futures Contracts", "FII Long %", "FII Short %"] else ""
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
            return df[cols]
    except Exception:
        pass
    return pd.DataFrame(columns=cols)

def v102_save_fii_dii_journal(df):
    try:
        FII_DII_STORE.parent.mkdir(parents=True, exist_ok=True)
        df2 = df.copy()
        if "Date" in df2.columns:
            df2["Date"] = pd.to_datetime(df2["Date"], errors="coerce").dt.date.astype(str)
        df2.to_csv(FII_DII_STORE, index=False)
        return True
    except Exception:
        return False

def v102_journal_stats(df, lookback=30):
    if df is None or df.empty:
        return {"rows": 0, "fii_5": 0.0, "dii_5": 0.0, "fii_10": 0.0, "dii_10": 0.0, "bias": 0.0, "label": "No data"}
    d = df.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d = d.dropna(subset=["Date"]).sort_values("Date").tail(int(lookback))
    for col in ["FII Cash Cr", "DII Cash Cr"]:
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0.0)
    last5 = d.tail(5)
    last10 = d.tail(10)
    fii5 = float(last5["FII Cash Cr"].sum()) if not last5.empty else 0.0
    dii5 = float(last5["DII Cash Cr"].sum()) if not last5.empty else 0.0
    fii10 = float(last10["FII Cash Cr"].sum()) if not last10.empty else 0.0
    dii10 = float(last10["DII Cash Cr"].sum()) if not last10.empty else 0.0
    bias = 0.0
    bias += 35 if fii5 > 1000 else -35 if fii5 < -1000 else fii5 / 30.0
    bias += 15 if dii5 > 1000 else -15 if dii5 < -1000 else dii5 / 70.0
    bias += 20 if fii10 > 2000 else -20 if fii10 < -2000 else fii10 / 100.0
    bias = signed_clamp(bias)
    label = bias_label(bias)
    return {"rows": len(d), "fii_5": fii5, "dii_5": dii5, "fii_10": fii10, "dii_10": dii10, "bias": bias, "label": label}




# =========================================================
# V13 STABILITY + LIVE UX HELPERS
# =========================================================
def v13_is_auth_error(*messages):
    text = " ".join(str(m) for m in messages).lower()
    return any(x in text for x in ["401", "authentication failed", "token invalid", "client id or token invalid"])


def v13_source_text(dhan_ready, option_chain, nifty_source, dhan_bundle, expiry_result):
    messages = [
        (dhan_bundle or {}).get("message", ""),
        (expiry_result or {}).get("message", ""),
        (option_chain or {}).get("message", ""),
    ]
    if not dhan_ready:
        return "Fallback (Dhan token missing)"
    if v13_is_auth_error(*messages):
        return "Fallback (Dhan token INVALID/EXPIRED)"
    if (option_chain or {}).get("success"):
        return "DhanHQ Live OC"
    if str(nifty_source).lower().startswith("dhan"):
        return "DhanHQ Quote (OC unavailable)"
    return "Fallback (Dhan connected, live OC not active)"


def v13_trend(key, value, decimals=2):
    """Compare value against previous refresh and return arrow, css class, delta text."""
    try:
        val = float(value)
    except Exception:
        return "→", "v13-flat", "flat"
    prev_key = f"v13_prev_{key}"
    prev = st.session_state.get(prev_key)
    st.session_state[prev_key] = val
    if prev is None:
        return "→", "v13-flat", "first refresh"
    diff = val - float(prev)
    if abs(diff) < (10 ** (-decimals)):
        return "→", "v13-flat", "flat"
    if diff > 0:
        return "↑", "v13-green", f"+{diff:.{decimals}f} from last refresh"
    return "↓", "v13-red", f"{diff:.{decimals}f} from last refresh"






def v134_journal_row_by_date(df, target_date):
    try:
        if df is None or df.empty or target_date is None:
            return None
        d = df.copy()
        d["Date"] = pd.to_datetime(d["Date"], errors="coerce").dt.date
        rows = d[d["Date"] == pd.to_datetime(target_date).date()]
        if rows.empty:
            return None
        return rows.iloc[-1].to_dict()
    except Exception:
        return None

def v134_latest_journal_date(df):
    try:
        if df is None or df.empty:
            return now_ist().date()
        d = df.copy()
        d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
        d = d.dropna(subset=["Date"]).sort_values("Date")
        if d.empty:
            return now_ist().date()
        return d["Date"].iloc[-1].date()
    except Exception:
        return now_ist().date()

def v135_auto_fut_bias(long_pct, short_pct):
    """Auto-bias from FII Index Futures long/short percentage."""
    try:
        long_pct = float(long_pct or 0)
        short_pct = float(short_pct or 0)
    except Exception:
        return "Neutral"
    if short_pct >= 65 and short_pct - long_pct >= 25:
        return "Bearish"
    if long_pct >= 65 and long_pct - short_pct >= 25:
        return "Bullish"
    return "Neutral"

def v135_fut_bias_score(long_pct, short_pct, manual_bias="Neutral"):
    try:
        long_pct = float(long_pct or 0)
        short_pct = float(short_pct or 0)
    except Exception:
        long_pct, short_pct = 0.0, 0.0
    spread = long_pct - short_pct
    # Convert long-short spread into -30 to +30 score.
    score = signed_clamp(spread * 0.45, -30, 30)
    if abs(score) < 3:
        score = 22 if manual_bias == "Bullish" else -22 if manual_bias == "Bearish" else 0
    return score

def v135_safe_float_from_row(row, key, default=0.0):
    try:
        return float((row or {}).get(key, default) or default)
    except Exception:
        return default


def v132_vix_range_engine(nifty_price, india_vix):
    """India VIX expected daily range for option sellers.
    Shortcut used by traders: VIX / 16 ≈ expected 1-day move percentage.
    This is an estimate, not a guarantee.
    """
    try:
        spot = float(nifty_price)
        vixv = float(india_vix)
    except Exception:
        spot, vixv = 0.0, 0.0
    if spot <= 0 or vixv <= 0:
        return {
            "ok": False, "move_pct": 0.0, "move_points": 0.0, "upper": 0.0, "lower": 0.0,
            "position": "Unavailable", "risk": "UNKNOWN", "message": "VIX range unavailable."
        }
    move_pct = vixv / 16.0
    move_points = spot * move_pct / 100.0
    upper = spot + move_points
    lower = spot - move_points
    # Position inside the estimated band using current spot as centre. Kept for UI symmetry.
    width = max(upper - lower, 1.0)
    pct_from_lower = clamp(((spot - lower) / width) * 100.0)
    if move_pct >= 1.35:
        risk = "HIGH RANGE"
    elif move_pct >= 0.90:
        risk = "MEDIUM RANGE"
    else:
        risk = "LOW RANGE"
    return {
        "ok": True,
        "move_pct": move_pct,
        "move_points": move_points,
        "upper": upper,
        "lower": lower,
        "pct_from_lower": pct_from_lower,
        "position": "Middle of expected range",
        "risk": risk,
        "message": f"Expected 1-day move approx ±{move_points:.0f} pts ({move_pct:.2f}%)."
    }




def v133_fake_move_engine(price_action_bias, option_bias, heavy_bias, pcr, vix, gamma_score, shock_score, news_score, conflict_mode, final_trade, vix_range=None):
    """Fake move probability meter for the WAIT / no-trade zone.
    This is a decision-support filter, not a guarantee.
    Higher score means confirmation is weak or signals are fighting each other.
    """
    pa = v91_safe_num(price_action_bias)
    ob = v91_safe_num(option_bias)
    hw = v91_safe_num(heavy_bias)
    pcrv = v91_safe_num(pcr, 1.0)
    vixv = v91_safe_num(vix)
    gamma = v91_safe_num(gamma_score)
    shock = v91_safe_num(shock_score)
    news = v91_safe_num(news_score)

    score = 15.0
    reasons = []
    confirmations = []

    if conflict_mode:
        score += 20
        reasons.append('Major signal conflict active hai.')

    if pa >= 45 and ob <= 15:
        score += 18
        reasons.append('Price upar hai, par option-chain support weak/negative hai.')
    elif pa <= -45 and ob >= -15:
        score += 18
        reasons.append('Price neeche hai, par option-chain breakdown support weak/positive hai.')
    else:
        confirmations.append('Price action aur option-chain me severe mismatch nahi hai.')

    if abs(pa - ob) >= 85:
        score += 18
        reasons.append('Price action aur OI/option bias me strong mismatch hai.')
    elif abs(pa - ob) >= 55:
        score += 10
        reasons.append('Price action aur OI/option bias partially disagree kar rahe hain.')

    if hw >= 35 and pa <= -25:
        score += 12
        reasons.append('Heavyweights support de rahe hain, lekin chart weak dikh raha hai.')
    elif hw <= -35 and pa >= 25:
        score += 12
        reasons.append('Chart upar hai, lekin heavyweights pressure de rahe hain.')
    else:
        confirmations.append('Heavyweights me major opposite pressure nahi dikh raha.')

    if pcrv < 0.80 and ob >= 35:
        score += 10
        reasons.append('PCR bearish zone me hai, par option bias bullish hai.')
    elif pcrv > 1.55 and ob <= -35:
        score += 10
        reasons.append('PCR overheated bullish zone me hai, par option bias bearish hai.')

    if gamma >= 70:
        score += 14
        reasons.append('Gamma risk high hai; spike/fake move ka chance badh sakta hai.')
    if shock >= 65:
        score += 12
        reasons.append('Shock probability elevated hai.')
    if news >= 70:
        score += 12
        reasons.append('News/event risk high hai.')

    if vix_range and vix_range.get('ok') and vix_range.get('risk') == 'HIGH RANGE':
        score += 8
        reasons.append('VIX expected range wide hai; seller ko confirmation chahiye.')
    elif vixv <= 14 and abs(pa - ob) < 45 and not conflict_mode:
        confirmations.append('VIX low/normal hai aur conflict limited hai.')

    if final_trade == 'WAIT':
        score += 6
        reasons.append('Final AI already WAIT mode me hai.')

    score = int(round(clamp(score, 0, 100)))
    if score >= 75:
        label = 'HIGH FAKE MOVE RISK'
        action = 'WAIT / no fresh entry. Confirmation candle + OI support ka wait karo.'
        tone = 'error'
    elif score >= 50:
        label = 'MEDIUM FAKE MOVE RISK'
        action = 'Small size ya avoid. Entry tabhi jab next refresh me same direction confirm ho.'
        tone = 'warning'
    else:
        label = 'LOW FAKE MOVE RISK'
        action = 'Fake move risk controlled, but hedge + SL mandatory.'
        tone = 'success'

    if not reasons:
        reasons.append('Koi major fake-move warning active nahi hai.')
    return {
        'score': score,
        'label': label,
        'action': action,
        'tone': tone,
        'reasons': reasons[:5],
        'confirmations': confirmations[:3],
    }


# =========================================================
# V14 AI BRAIN UPGRADE: MEMORY + FREEZE + REGIME + CANDLE
# =========================================================
def v14_snapshot_engine(snapshot, max_len=20):
    """Rolling memory: sirf last 20 snapshots session_state me rakhe. App slow nahi hogi."""
    hist = st.session_state.get("v14_memory", [])
    sid = str(snapshot.get("snapshot_id", ""))
    if not hist or str(hist[-1].get("snapshot_id", "")) != sid:
        hist.append(snapshot)
        hist = hist[-int(max_len):]
        st.session_state["v14_memory"] = hist
    return hist


def v14_decision_freeze(proposed_trade, confidence, history, required=3):
    """Trade signal tabhi confirm jab same non-WAIT signal required refreshes tak rahe."""
    proposed = str(proposed_trade or "WAIT")
    recent = [str(x.get("proposed_trade", "WAIT")) for x in history[-int(required):]]
    same_count = 0
    for sig in reversed(recent):
        if sig == proposed:
            same_count += 1
        else:
            break
    if proposed == "WAIT":
        return {
            "final_trade": "WAIT",
            "confirmed": False,
            "same_count": same_count,
            "required": required,
            "status": "WAIT MODE",
            "reason": "AI currently WAIT mode me hai.",
            "confidence": confidence,
        }
    if same_count >= required:
        return {
            "final_trade": proposed,
            "confirmed": True,
            "same_count": same_count,
            "required": required,
            "status": "SIGNAL CONFIRMED",
            "reason": f"{proposed} signal {same_count} refresh se stable hai.",
            "confidence": confidence,
        }
    return {
        "final_trade": "WAIT",
        "confirmed": False,
        "same_count": same_count,
        "required": required,
        "status": "FREEZE ACTIVE",
        "reason": f"{proposed} signal abhi {same_count}/{required} refresh confirm hua hai. Jaldbazi avoid.",
        "confidence": min(float(confidence or 0), 60),
    }


def v14_confidence_stability(history, current_trade, confidence):
    if not history:
        return {"score": 0, "label": "NO MEMORY", "note": "First refresh."}
    recent = history[-5:]
    decisions = [str(x.get("proposed_trade", "WAIT")) for x in recent]
    same = sum(1 for d in decisions if d == str(current_trade))
    decision_score = same / max(len(decisions), 1) * 100
    confs = [float(x.get("confidence", 0) or 0) for x in recent]
    conf_range = max(confs) - min(confs) if confs else 0
    penalty = min(conf_range * 1.2, 35)
    score = int(round(clamp(decision_score - penalty, 0, 100)))
    if score >= 80:
        label = "STABLE"
    elif score >= 55:
        label = "MEDIUM"
    else:
        label = "UNSTABLE"
    return {"score": score, "label": label, "note": f"Last {len(recent)} refresh decisions: " + " → ".join(decisions)}


def v14_market_regime(price_action_bias, option_bias, heavy_bias, vix, shock_score, gamma_score, is_expiry=False, time_risk=0):
    pa = v91_safe_num(price_action_bias)
    ob = v91_safe_num(option_bias)
    hw = v91_safe_num(heavy_bias)
    vixv = v91_safe_num(vix)
    shock = v91_safe_num(shock_score)
    gamma = v91_safe_num(gamma_score)
    tr = v91_safe_num(time_risk)
    aligned_bull = pa >= 25 and ob >= 25 and hw >= 10
    aligned_bear = pa <= -25 and ob <= -25 and hw <= -10
    if is_expiry and (gamma >= 65 or tr >= 70):
        return {"label": "⚡ EXPIRY GAMMA DAY", "score": 90, "note": "Expiry + gamma/time risk high. Fresh entry only after confirmation."}
    if shock >= 70 or vixv >= 18:
        return {"label": "🔴 VOLATILE DAY", "score": 75, "note": "Shock/VIX elevated. Quantity reduce, SL strict."}
    if aligned_bull or aligned_bear:
        return {"label": "🟢 TRENDING DAY", "score": 82, "note": "Price action, option-chain aur heavyweights same direction me hain."}
    if abs(pa) <= 30 and abs(ob) <= 35 and vixv <= 15:
        return {"label": "🟡 RANGE DAY", "score": 68, "note": "Directional edge limited. Premium decay strategies better."}
    return {"label": "⚪ MIXED DAY", "score": 50, "note": "Signals mixed hain. Decision Freeze follow karo."}


def v14_candle_confirmation(open_, high_, low_, close_, final_direction):
    o = v91_safe_num(open_)
    h = v91_safe_num(high_)
    l = v91_safe_num(low_)
    c = v91_safe_num(close_)
    rng = max(h - l, 0.01)
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    pattern = "Neutral Candle"
    score = 0
    note = "15m candle neutral hai."
    if body <= rng * 0.18:
        pattern, score, note = "Doji / Indecision", 0, "Decision weak: next 15m close ka wait better."
    elif c > o and body >= rng * 0.55:
        pattern, score, note = "Strong Bullish 15m", 12, "Bullish close PE-sell setup ko confirm kar sakta hai."
    elif c < o and body >= rng * 0.55:
        pattern, score, note = "Strong Bearish 15m", -12, "Bearish close CE-sell setup ko confirm kar sakta hai."
    if upper_wick >= rng * 0.45 and c < h - rng * 0.30:
        pattern, score, note = "Upper Wick Rejection", min(score, -8), "Upar rejection: bullish move fake ho sakta hai."
    if lower_wick >= rng * 0.45 and c > l + rng * 0.30:
        pattern, score, note = "Lower Wick Rejection", max(score, 8), "Neeche rejection: bearish move fake ho sakta hai."
    fd = v91_safe_num(final_direction)
    aligned = (score > 0 and fd > 0) or (score < 0 and fd < 0) or abs(score) < 3
    return {"pattern": pattern, "score": int(score), "aligned": aligned, "note": note}


def v14_seller_strength(best_ce, best_pe, option_bias):
    ce = int(best_ce.get("ce_sell_score", 0)) if best_ce else 0
    pe = int(best_pe.get("pe_sell_score", 0)) if best_pe else 0
    ob = v91_safe_num(option_bias)
    ce_strength = int(clamp(ce + max(-ob, 0) * 0.20, 0, 100))
    pe_strength = int(clamp(pe + max(ob, 0) * 0.20, 0, 100))
    if ce_strength > pe_strength + 10:
        winner = "CE Sellers Strong"
    elif pe_strength > ce_strength + 10:
        winner = "PE Sellers Strong"
    else:
        winner = "Balanced"
    return {"ce": ce_strength, "pe": pe_strength, "winner": winner}


def v14_entry_window(market_mode, time_risk, confidence, stability_score, freeze_confirmed, seller_risk):
    t = now_ist().time()
    if "EXPIRY" in str(market_mode) and datetime.strptime("14:30", "%H:%M").time() <= t:
        return {"label": "NO FRESH ENTRY", "note": "Expiry last hour: gamma spike risk. Sirf manage/exit focus."}
    if seller_risk >= 70 or time_risk >= 75:
        return {"label": "WAIT", "note": "Risk zone high hai. Confirmation ke bina entry avoid."}
    if freeze_confirmed and confidence >= 70 and stability_score >= 70:
        return {"label": "ENTRY WINDOW OPEN", "note": "Signal stable + confidence acceptable. Hedge/SL mandatory."}
    if confidence >= 60:
        return {"label": "WAIT FOR CONFIRMATION", "note": "Setup ban raha hai, par Freeze/Stability abhi complete nahi."}
    return {"label": "NO EDGE", "note": "Confidence low hai. No trade bhi valid trade hai."}


def v14_reason_breakdown(price_action_bias, option_bias, heavy_bias, smart_money_bias, pcr_bias, fake_move_score, vix_risk, seller_risk):
    items = [
        ("Price Action", v91_safe_num(price_action_bias) * 0.12),
        ("Option Chain / OI", v91_safe_num(option_bias) * 0.14),
        ("Heavyweights", v91_safe_num(heavy_bias) * 0.10),
        ("FII/DII", v91_safe_num(smart_money_bias) * 0.08),
        ("PCR", v91_safe_num(pcr_bias) * 0.08),
        ("Fake Move Risk", -v91_safe_num(fake_move_score) * 0.10),
        ("VIX Risk", -v91_safe_num(vix_risk) * 0.06),
        ("Seller Risk", -v91_safe_num(seller_risk) * 0.05),
    ]
    return [(name, int(round(val))) for name, val in items]


# =========================================================
# V15 SAFE EXPIRY SCORE: ZERO PREMIUM / PREMIUM EXPLOSION RISK
# =========================================================
def v15_minutes_to_expiry_close(expiry_text=None):
    """Minutes left till 15:30 IST expiry close. Lightweight, no API call."""
    try:
        now = now_ist()
        if expiry_text:
            exp_date = pd.to_datetime(str(expiry_text)).date()
        else:
            exp_date = now.date()
        close_dt = datetime.combine(exp_date, datetime.strptime("15:30", "%H:%M").time()).replace(tzinfo=IST)
        return int(max((close_dt - now).total_seconds() / 60.0, 0))
    except Exception:
        return 999


def v15_remaining_expected_move(price, vix, minutes_left):
    """Expiry remaining expected move estimate using VIX/16 daily shortcut scaled by sqrt(time)."""
    price = v91_safe_num(price)
    vix = max(v91_safe_num(vix), 0.0)
    minutes_left = max(v91_safe_num(minutes_left), 1.0)
    full_day_minutes = 375.0
    daily_pct = vix / 16.0 / 100.0
    move = price * daily_pct * (minutes_left / full_day_minutes) ** 0.5
    return max(move, 1.0)


def v15_safe_expiry_for_leg(side, row, spot, vix, minutes_left, gamma_score, shock_score, fake_move_score, regime_label):
    """Return Safe Expiry score for one CE/PE leg. Higher = higher chance premium dies safely."""
    if not row:
        return None
    side = str(side).upper()
    prefix = side.lower()
    strike = int(row.get("strike", 0) or 0)
    spot = v91_safe_num(spot)
    premium = v91_safe_num(row.get(f"{prefix}_ltp", 0))
    delta_abs = abs(v91_safe_num(row.get(f"{prefix}_delta", 0)))
    iv = v91_safe_num(row.get(f"{prefix}_iv", 0))
    sell_score = v91_safe_num(row.get(f"{prefix}_sell_score", 0))
    signal = str(row.get(f"{prefix}_signal", ""))
    oi_chg = v91_safe_num(row.get(f"{prefix}_oi_change", 0))
    vol = v91_safe_num(row.get(f"{prefix}_volume", 0))

    distance = (strike - spot) if side == "CE" else (spot - strike)
    otm = distance > 0
    rem_move = v15_remaining_expected_move(spot, vix, minutes_left)
    distance_ratio = distance / rem_move if rem_move else 0

    score = 35.0
    reasons = []
    warnings = []

    if not otm:
        score -= 40
        warnings.append("ITM/ATM risk high")
    elif distance_ratio >= 1.8:
        score += 32; reasons.append("Strike expected range se kaafi door")
    elif distance_ratio >= 1.2:
        score += 24; reasons.append("Strike expected range se bahar")
    elif distance_ratio >= 0.8:
        score += 12; warnings.append("Strike range ke edge par")
    else:
        score -= 18; warnings.append("Strike expected range ke andar/near")

    if delta_abs <= 0.08:
        score += 18; reasons.append("Delta very low")
    elif delta_abs <= 0.16:
        score += 12; reasons.append("Delta seller-friendly")
    elif delta_abs >= 0.35:
        score -= 18; warnings.append("Delta high")
    elif delta_abs >= 0.25:
        score -= 8; warnings.append("Delta moderate/high")

    if "Writing" in signal:
        score += 10; reasons.append("OI writing support")
    elif "Buying" in signal or "Short Covering" in signal:
        score -= 12; warnings.append("Premium buying/covering risk")

    if sell_score >= 85:
        score += 10
    elif sell_score <= 55:
        score -= 8

    if minutes_left <= 45:
        score += 18; reasons.append("Expiry close: theta strong")
    elif minutes_left <= 120:
        score += 10; reasons.append("Time decay supportive")
    elif minutes_left >= 300:
        score -= 6; warnings.append("Time left high")

    # Risk penalties: premium explosion risk ka core.
    gamma = v91_safe_num(gamma_score)
    shock = v91_safe_num(shock_score)
    fake = v91_safe_num(fake_move_score)
    risk_penalty = gamma * 0.12 + shock * 0.12 + fake * 0.18
    score -= risk_penalty
    if gamma >= 70: warnings.append("Gamma risk high")
    if shock >= 65: warnings.append("Shock risk elevated")
    if fake >= 50: warnings.append("Fake move risk active")
    if "VOLATILE" in str(regime_label) or "GAMMA" in str(regime_label):
        score -= 8; warnings.append("Volatile/expiry gamma regime")

    if iv >= 25:
        score -= 6; warnings.append("IV high")
    if premium <= 1.0 and otm:
        score += 8; reasons.append("Premium already near zero")
    elif premium >= 30 and minutes_left <= 90:
        score -= 6; warnings.append("Premium still heavy")

    safe_score = int(round(clamp(score, 0, 100)))
    explosion_risk = int(round(clamp(100 - safe_score + gamma * 0.08 + fake * 0.10, 0, 100)))
    worthless_prob = int(round(clamp(safe_score * 0.82 + max(distance_ratio, 0) * 8, 0, 98)))

    if safe_score >= 85:
        label = "🟢 STRONG"
    elif safe_score >= 70:
        label = "🟡 CAUTION"
    else:
        label = "🔴 AVOID"

    return {
        "side": side,
        "strike": strike,
        "premium": premium,
        "safe_score": safe_score,
        "worthless_probability": worthless_prob,
        "premium_explosion_risk": explosion_risk,
        "distance": distance,
        "distance_ratio": distance_ratio,
        "delta": delta_abs,
        "iv": iv,
        "label": label,
        "reasons": reasons[:3] or ["Distance/delta/time based score"],
        "warnings": warnings[:3],
        "oi_change": oi_chg,
        "volume": vol,
    }




# =========================================================
# V16.1 PERSISTENT AUTO REFRESH ENGINE
# =========================================================
def v161_qp_get(name, default=""):
    try:
        val = st.query_params.get(name, default)
        if isinstance(val, list):
            return val[0] if val else default
        return val
    except Exception:
        return default




def v161_init_refresh_state():
    """Keep auto-refresh ON across browser/meta refresh for up to 30 minutes."""
    try:
        qp_auto = str(v161_qp_get("auto_refresh", "0")).lower() in ("1", "true", "yes", "on")
        qp_interval = int(float(v161_qp_get("refresh_interval", "20") or 20))
    except Exception:
        qp_auto, qp_interval = False, 20
    qp_interval = int(max(20, min(300, qp_interval)))

    if "v161_auto_refresh" not in st.session_state:
        st.session_state["v161_auto_refresh"] = qp_auto
    if "v161_refresh_interval" not in st.session_state:
        st.session_state["v161_refresh_interval"] = qp_interval
    if "v161_auto_until" not in st.session_state:
        st.session_state["v161_auto_until"] = v161_qp_get("auto_until", "")





v161_init_refresh_state()

# =========================================================
# SIDEBAR + SOURCE CONFIG
# =========================================================
client_id, access_token = dhan_credentials()
dhan_ready = bool(client_id and access_token)

st.sidebar.title("🏛️ V27 AI COMMAND")
st.sidebar.caption("ONE BRAIN • CO CONTROL • DATA OWNERSHIP")
st.sidebar.markdown("**👑 AI_MASTER — Final Authority**")
st.sidebar.caption("🎖️ CO — Consolidates verified branch case file")
st.sidebar.caption("📡 DSP Data Intelligence")
st.sidebar.caption("📊 DSP Option Intelligence")
st.sidebar.caption("📈 DSP Price Action")
st.sidebar.caption("🧭 DSP Market Behaviour")
st.sidebar.caption("💰 DSP Smart Money")
st.sidebar.caption("🛡️ DSP Risk")
st.sidebar.caption("🎯 DSP Strategy")
st.sidebar.caption("📋 DSP Candidate")

# Legacy engines remain available for compatibility, but do not clutter command view.
with st.sidebar.expander("Legacy Engine Health", expanded=False):
    try:
        st.caption("snapshot_engine: " + ("READY / AUTHORITY" if V19_SNAPSHOT_ENGINE_READY else "MISSING"))
        st.caption("ai_brain: " + ("READY" if V19_AI_BRAIN_READY else "FALLBACK"))
        st.caption("risk_engine: " + ("READY" if V19_RISK_ENGINE_READY else "FALLBACK"))
        st.caption("decision_engine: " + ("READY" if V19_DECISION_ENGINE_READY else "FALLBACK"))
        st.caption("strategy_engine: " + ("READY / PLAN AUTHORITY" if V19_STRATEGY_ENGINE_READY else "MISSING"))
        st.caption("intelligence_engine: " + ("READY / EXPLAINER" if V19_INTELLIGENCE_ENGINE_READY else "MISSING"))
        st.caption("stability_engine: " + ("READY / LOCK" if V19_STABILITY_ENGINE_READY else "MISSING"))
        st.caption("memory_engine: " + ("READY / MEMORY" if V19_MEMORY_ENGINE_READY else "MISSING"))
        st.caption("oi_flow_engine: " + ("READY / OI FLOW" if V19_OI_FLOW_ENGINE_READY else "MISSING"))
    except Exception:
        st.caption("Legacy health unavailable")

# V19.1 Sidebar Refresh Control Center
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔄 Refresh Control")
st.sidebar.markdown("<div class='sidebar-refresh-note'>Primary refresh control. Use this when scrolled down.</div>", unsafe_allow_html=True)
if st.sidebar.button("🔄 Refresh Live Data", key="v191_sidebar_refresh_btn", width="stretch"):
    v215_unified_refresh("sidebar_control", do_rerun=True)

_interval_options_v191 = ["10 sec", "20 sec", "30 sec", "60 sec"]
if st.session_state.get("auto_refresh_interval") not in _interval_options_v191:
    st.session_state["auto_refresh_interval"] = "20 sec"
st.sidebar.selectbox(
    "Auto interval",
    _interval_options_v191,
    key="auto_refresh_interval",
)

st.sidebar.toggle(
    "Auto ON for 30 min",
    key="auto_refresh_enabled",
)

st.sidebar.caption(
    "Last refresh: " + (
        st.session_state.get("last_manual_refresh")
        or st.session_state.get("v163_last_manual_refresh")
        or st.session_state.get("last_refresh")
        or "First app run"
    )
)
st.sidebar.caption("State lock: Developer/Trading mode preserved")
st.sidebar.caption("Top duplicate removed: YES | Snapshot module: " + ("READY" if V19_SNAPSHOT_ENGINE_READY else "FALLBACK") + "")

# V21.5: Auto-refresh uses the same master refresh controller via query param.
try:
    if st.session_state.get("auto_refresh_enabled", False):
        if not st.session_state.get("auto_refresh_until"):
            st.session_state["auto_refresh_until"] = (datetime.now(IST) + timedelta(minutes=30)).isoformat()
        _until = datetime.fromisoformat(st.session_state.get("auto_refresh_until"))
        if datetime.now(IST) <= _until:
            _sec = int(str(st.session_state.get("auto_refresh_interval", "20 sec")).split()[0])
            _sec = max(10, min(300, _sec))
            components.html(
                f"""
                <script>
                setTimeout(function() {{
                    const base = window.parent.location.pathname;
                    window.parent.location.replace(base + '?auto_refresh_tick=' + Date.now());
                }}, {_sec * 1000});
                </script>
                """,
                height=0,
            )
            st.sidebar.caption(f"Auto refresh active: every {_sec}s until {_until.strftime('%H:%M:%S')}")
        else:
            st.session_state["auto_refresh_enabled"] = False
            st.session_state["auto_refresh_until"] = ""
            st.sidebar.warning("Auto refresh 30 min complete. Manual refresh still active.")
    else:
        st.session_state["auto_refresh_until"] = ""
except Exception as _auto_exc:
    st.sidebar.warning(f"Auto refresh controller issue: {_auto_exc}")


# V17: one main refresh button remains in the top header. Sidebar is only for settings.
if dhan_ready:
    st.sidebar.success("DhanHQ credentials detected")
else:
    st.sidebar.info("DhanHQ credentials not added yet — safe fallbacks active")

# Persist UI mode settings across auto/manual refresh.
if "developer_mode" not in st.session_state:
    st.session_state["developer_mode"] = False
if "trading_mode_clean" not in st.session_state:
    st.session_state["trading_mode_clean"] = True

developer_mode = st.sidebar.checkbox(
    "🛠️ Developer Mode",
    key="developer_mode",
    help="OFF rakho to app clean rahegi. ON karoge to diagnostics/internal calculations dikhenge.",
)
trading_mode_clean = st.sidebar.checkbox(
    "🎯 Trading Mode Clean UI",
    key="trading_mode_clean",
    help="Duplicate/internal sections hide karta hai.",
)

with st.sidebar.expander("1️⃣ Data Source", expanded=True):
    prefer_dhan = st.checkbox("Prefer DhanHQ Live Data", value=dhan_ready, disabled=not dhan_ready)
    nifty_security_id = int(st.number_input("Nifty Dhan Security ID", value=DEFAULT_NIFTY_SECURITY_ID, step=1))
    strikes_each_side = st.slider("Option strikes each side", 3, 10, 6)
    st.caption("NSE direct option-chain scraping removed. DhanHQ is the intended live source.")

with st.sidebar.expander("2️⃣ Manual Market Fallback", expanded=False):
    manual_nifty = st.number_input("Manual Nifty", value=25000.0, step=1.0)
    manual_nifty_change_pct = st.number_input("Manual Nifty Change %", value=0.0, step=0.05)
    manual_vix = st.number_input("Manual India VIX", value=13.5, step=0.1)
    manual_vix_change_pct = st.number_input("Manual VIX Change %", value=0.0, step=0.1)

with st.sidebar.expander("3️⃣ Price Action", expanded=False):
    auto_price_action = st.checkbox("Auto Price Action (EMA/VWAP/ATR/High-Low)", value=True)
    st.caption("Auto ON: app candles se values update karegi. Manual values fallback rahengi.")
    manual_ema20 = st.number_input("Manual EMA 20", value=24950.0, step=1.0)
    manual_ema50 = st.number_input("Manual EMA 50", value=24900.0, step=1.0)
    manual_vwap = st.number_input("Manual VWAP", value=24940.0, step=1.0)
    manual_atr5 = st.number_input("Manual ATR 5 Min", value=45.0, step=1.0)
    manual_previous_day_high = st.number_input("Manual Previous Day High", value=25150.0, step=1.0)
    manual_previous_day_low = st.number_input("Manual Previous Day Low", value=24850.0, step=1.0)
    manual_today_high = st.number_input("Manual Today High", value=25080.0, step=1.0)
    manual_today_low = st.number_input("Manual Today Low", value=24920.0, step=1.0)
    manual_opening_range_high = st.number_input("Manual Opening Range High", value=25060.0, step=1.0)
    manual_opening_range_low = st.number_input("Manual Opening Range Low", value=24940.0, step=1.0)
    # Start with manual fallback. After live fetch, V16 overrides these when auto_price_action is ON.
    ema20 = manual_ema20
    ema50 = manual_ema50
    vwap = manual_vwap
    atr5 = manual_atr5
    previous_day_high = manual_previous_day_high
    previous_day_low = manual_previous_day_low
    today_high = manual_today_high
    today_low = manual_today_low
    opening_range_high = manual_opening_range_high
    opening_range_low = manual_opening_range_low
    price_action_source = "Manual fallback"
    price_action_result = {"success": False, "message": "Manual fallback active", "source": "Manual fallback"}

with st.sidebar.expander("3B 🕯️ 15m Candle Confirmation", expanded=False):
    st.caption("Optional: 15-min candle values chart se daalo. Empty/default rahe to app price-action proxy use karegi.")
    candle15_open = st.number_input("15m Open", value=manual_nifty, step=1.0)
    candle15_high = st.number_input("15m High", value=manual_nifty + 40.0, step=1.0)
    candle15_low = st.number_input("15m Low", value=manual_nifty - 40.0, step=1.0)
    candle15_close = st.number_input("15m Close", value=manual_nifty, step=1.0)

with st.sidebar.expander("4️⃣ Manual Option Fallback", expanded=False):
    manual_call_oi_change = st.number_input("Call OI Change", value=150000, step=1000)
    manual_put_oi_change = st.number_input("Put OI Change", value=180000, step=1000)
    manual_total_call_oi = st.number_input("Total Call OI", value=1500000, step=10000)
    manual_total_put_oi = st.number_input("Total Put OI", value=1800000, step=10000)
    manual_ce_strike = int(st.number_input("Manual CE Sell Strike", value=25100, step=50))
    manual_pe_strike = int(st.number_input("Manual PE Sell Strike", value=24900, step=50))
    hedge_gap = int(st.number_input("Hedge Gap", value=100, step=50))

with st.sidebar.expander("5️⃣ FII / DII — Date-wise Manual", expanded=True):
    _quick_journal_df = v102_load_fii_dii_journal()
    _default_data_date = v134_latest_journal_date(_quick_journal_df)
    fii_data_date = st.date_input("FII/DII Data Date", value=_default_data_date, key="v134_fii_data_date")
    _saved_row_for_date = v134_journal_row_by_date(_quick_journal_df, fii_data_date)
    _default_fii_today = v135_safe_float_from_row(_saved_row_for_date, "FII Cash Cr", 0.0)
    _default_dii_today = v135_safe_float_from_row(_saved_row_for_date, "DII Cash Cr", 0.0)
    _default_fut_contracts = v135_safe_float_from_row(_saved_row_for_date, "FII Index Futures Contracts", 0.0)
    _default_long_pct = v135_safe_float_from_row(_saved_row_for_date, "FII Long %", 0.0)
    _default_short_pct = v135_safe_float_from_row(_saved_row_for_date, "FII Short %", 0.0)
    _quick_stats = v102_journal_stats(_quick_journal_df)
    _date_key = pd.to_datetime(fii_data_date).strftime("%Y%m%d")
    fii_today = st.number_input("FII Cash ₹ Cr", value=_default_fii_today, step=100.0, key=f"v134_fii_today_{_date_key}")
    dii_today = st.number_input("DII Cash ₹ Cr", value=_default_dii_today, step=100.0, key=f"v134_dii_today_{_date_key}")
    fii_5day = st.number_input("FII 5 Day Net ₹ Cr", value=float(_quick_stats.get("fii_5", 0.0)), step=100.0, key="v134_fii_5day")
    dii_5day = st.number_input("DII 5 Day Net ₹ Cr", value=float(_quick_stats.get("dii_5", 0.0)), step=100.0, key="v134_dii_5day")
    fii_index_futures_contracts = st.number_input("FII Index Futures Contracts", value=_default_fut_contracts, step=1000.0, key=f"v135_fut_contracts_{_date_key}")
    fii_long_pct = st.number_input("FII Index Futures Long %", value=_default_long_pct, min_value=0.0, max_value=100.0, step=0.01, key=f"v135_long_pct_{_date_key}")
    fii_short_pct = st.number_input("FII Index Futures Short %", value=_default_short_pct, min_value=0.0, max_value=100.0, step=0.01, key=f"v135_short_pct_{_date_key}")
    _auto_bias = v135_auto_fut_bias(fii_long_pct, fii_short_pct)
    _bias_default = str((_saved_row_for_date or {}).get("FII Index Futures Bias", _auto_bias) or _auto_bias)
    _bias_options = ["Auto", "Neutral", "Bullish", "Bearish"]
    _bias_index = 0 if _bias_default not in ["Neutral", "Bullish", "Bearish"] else _bias_options.index(_bias_default)
    _bias_choice = st.selectbox("FII Futures Bias", _bias_options, index=_bias_index, key=f"v135_fut_bias_{_date_key}")
    fii_index_futures_bias = _auto_bias if _bias_choice == "Auto" else _bias_choice
    st.caption(f"Auto Derived Bias: {_auto_bias} | Selected Bias: {fii_index_futures_bias} | Long {fii_long_pct:.2f}% / Short {fii_short_pct:.2f}%")
    if _saved_row_for_date:
        st.success(f"{pd.to_datetime(fii_data_date).strftime('%d-%m-%Y')} ka saved data loaded.")
    else:
        st.info("Is date ka data abhi save nahi hai.")
    if st.button("💾 Save Selected Date FII/DII", width="stretch"):
        _new_row = pd.DataFrame([{
            "Date": fii_data_date,
            "FII Cash Cr": fii_today,
            "DII Cash Cr": dii_today,
            "FII Index Futures Contracts": fii_index_futures_contracts,
            "FII Long %": fii_long_pct,
            "FII Short %": fii_short_pct,
            "FII Index Futures Bias": fii_index_futures_bias,
            "FII Options Bias": "Neutral",
            "Notes": "Saved from date-wise manual fields",
        }])
        _save_df = pd.concat([_quick_journal_df, _new_row], ignore_index=True)
        _save_df["Date"] = pd.to_datetime(_save_df["Date"], errors="coerce")
        _save_df = _save_df.dropna(subset=["Date"]).drop_duplicates(subset=["Date"], keep="last").sort_values("Date").tail(30)
        if v102_save_fii_dii_journal(_save_df):
            st.success("Saved. Ab date change karoge to usi date ka data load hoga.")
        else:
            st.error("Save failed.")
    st.caption("Bug fix: har date ka data alag save/load hoga; 02-07 aur 03-07 mix nahi honge.")

with st.sidebar.expander("5B 📒 FII/DII Journal — 30 Day Storage", expanded=False):
    fii_journal_df = v102_load_fii_dii_journal()
    journal_date = st.date_input("Date", value=v134_latest_journal_date(fii_journal_df), key="v134_journal_date")
    _journal_existing = v134_journal_row_by_date(fii_journal_df, journal_date)
    _jkey = pd.to_datetime(journal_date).strftime("%Y%m%d")
    journal_fii = st.number_input("Journal FII Cash ₹ Cr", value=float((_journal_existing or {}).get("FII Cash Cr", 0.0) or 0.0), step=100.0, key=f"journal_fii_{_jkey}")
    journal_dii = st.number_input("Journal DII Cash ₹ Cr", value=float((_journal_existing or {}).get("DII Cash Cr", 0.0) or 0.0), step=100.0, key=f"journal_dii_{_jkey}")
    journal_fut_contracts = st.number_input("Journal FII Index Futures Contracts", value=v135_safe_float_from_row(_journal_existing, "FII Index Futures Contracts", 0.0), step=1000.0, key=f"journal_fut_contracts_{_jkey}")
    journal_long_pct = st.number_input("Journal FII Long %", value=v135_safe_float_from_row(_journal_existing, "FII Long %", 0.0), min_value=0.0, max_value=100.0, step=0.01, key=f"journal_long_pct_{_jkey}")
    journal_short_pct = st.number_input("Journal FII Short %", value=v135_safe_float_from_row(_journal_existing, "FII Short %", 0.0), min_value=0.0, max_value=100.0, step=0.01, key=f"journal_short_pct_{_jkey}")
    _jfut_auto = v135_auto_fut_bias(journal_long_pct, journal_short_pct)
    _jfut = str((_journal_existing or {}).get("FII Index Futures Bias", _jfut_auto) or _jfut_auto)
    _jopt = str((_journal_existing or {}).get("FII Options Bias", "Neutral") or "Neutral")
    _journal_bias_options = ["Auto", "Neutral", "Bullish", "Bearish"]
    _journal_bias_index = 0 if _jfut not in ["Neutral", "Bullish", "Bearish"] else _journal_bias_options.index(_jfut)
    _journal_bias_choice = st.selectbox("Journal FII Futures Bias", _journal_bias_options, index=_journal_bias_index, key=f"journal_fut_bias_{_jkey}")
    journal_fut_bias = _jfut_auto if _journal_bias_choice == "Auto" else _journal_bias_choice
    journal_opt_bias = st.selectbox("Journal FII Options Bias", ["Neutral", "Bullish", "Bearish"], index=["Neutral", "Bullish", "Bearish"].index(_jopt) if _jopt in ["Neutral", "Bullish", "Bearish"] else 0, key=f"journal_opt_bias_{_jkey}")
    journal_notes = st.text_input("Notes", value=str((_journal_existing or {}).get("Notes", "") or ""), key=f"journal_notes_{_jkey}")
    if _journal_existing:
        st.success("Selected date ka saved row loaded.")
    col_j1, col_j2 = st.columns(2)
    if col_j1.button("Save FII/DII Day"):
        new_row = pd.DataFrame([{
            "Date": journal_date,
            "FII Cash Cr": journal_fii,
            "DII Cash Cr": journal_dii,
            "FII Index Futures Contracts": journal_fut_contracts,
            "FII Long %": journal_long_pct,
            "FII Short %": journal_short_pct,
            "FII Index Futures Bias": journal_fut_bias,
            "FII Options Bias": journal_opt_bias,
            "Notes": journal_notes,
        }])
        fii_journal_df = pd.concat([fii_journal_df, new_row], ignore_index=True)
        fii_journal_df["Date"] = pd.to_datetime(fii_journal_df["Date"], errors="coerce")
        fii_journal_df = fii_journal_df.dropna(subset=["Date"]).drop_duplicates(subset=["Date"], keep="last").sort_values("Date").tail(30)
        if v102_save_fii_dii_journal(fii_journal_df):
            st.success("Saved. Last 30 trading days retained.")
        else:
            st.error("Save failed. Use download backup.")
    if col_j2.button("Clear Journal"):
        fii_journal_df = fii_journal_df.iloc[0:0]
        v102_save_fii_dii_journal(fii_journal_df)
        st.warning("Journal cleared.")
    journal_stats = v102_journal_stats(fii_journal_df)
    st.caption(f"Rows: {journal_stats['rows']} | 5D FII: ₹{journal_stats['fii_5']:,.0f} Cr | 5D DII: ₹{journal_stats['dii_5']:,.0f} Cr")
    if not fii_journal_df.empty:
        st.download_button(
            "Download Journal CSV",
            data=fii_journal_df.to_csv(index=False),
            file_name="fii_dii_journal_backup.csv",
            mime="text/csv",
        )

with st.sidebar.expander("6️⃣ News Risk", expanded=True):
    manual_news_risk = st.selectbox("Manual fallback", ["Low", "Medium", "High", "Critical"])
    use_auto_news = st.checkbox("Use automatic news APIs when keys exist", value=True)
    st.caption("Optional secrets: TRADING_ECONOMICS_API_KEY, ALPHAVANTAGE_API_KEY")

with st.sidebar.expander("7️⃣ Top-5 Weights", expanded=False):
    st.caption("Defaults: official Nifty 50 factsheet, 30-Jun-2026")
    weights = {}
    for symbol, cfg in TOP5_DEFAULT.items():
        weights[symbol] = st.number_input(f"{cfg['name']} weight %", value=float(cfg["weight"]), step=0.01)

with st.sidebar.expander("8️⃣ Risk / Position", expanded=True):
    capital = st.number_input("Capital ₹", value=500000, step=10000)
    margin_per_lot = st.number_input("Margin Per Lot ₹", value=50000, step=5000)
    current_lots = int(st.number_input("Current Lots", value=0, step=1))
    lot_size = int(st.number_input("Lot Size", value=65, step=5))


with st.sidebar.expander("9️⃣ V16 Active Trade / Discipline", expanded=True):
    _pos_saved = v16_load_active_position()
    _side_options = ["None", "CE", "PE"]
    _saved_side = str(_pos_saved.get("Active Sold Side", "None"))
    _side_index = _side_options.index(_saved_side) if _saved_side in _side_options else 0
    active_side = st.selectbox("Active Sold Side", _side_options, index=_side_index, key="v16_active_side")
    active_strike = int(st.number_input("Active Strike", value=int(_pos_saved.get("Active Strike", 0) or 0), step=50, key="v16_active_strike"))
    active_entry_price = st.number_input("Entry Premium ₹", value=float(_pos_saved.get("Entry Premium ₹", 0.0) or 0.0), step=0.05, key="v16_entry_premium")
    active_current_price = st.number_input("Current Premium ₹", value=float(_pos_saved.get("Current Premium ₹", 0.0) or 0.0), step=0.05, key="v16_current_premium")
    active_lots = int(st.number_input("Active Lots", value=int(_pos_saved.get("Active Lots", 0) or 0), step=1, key="v16_active_lots"))
    trades_taken_today = int(st.number_input("Trades Taken Today", value=int(_pos_saved.get("Trades Taken Today", 0) or 0), step=1, key="v16_trades_taken"))
    daily_loss_hit = st.checkbox("Daily Loss Hit / Stop Trading", value=bool(_pos_saved.get("Daily Loss Hit / Stop Trading", False)), key="v16_daily_loss_hit")
    pcol1, pcol2 = st.columns(2)
    if pcol1.button("💾 Save Position", width="stretch"):
        if v16_save_active_position(active_side, active_strike, active_entry_price, active_current_price, active_lots, trades_taken_today, daily_loss_hit):
            st.success("Position saved. Refresh/restart ke baad bhi load hogi.")
        else:
            st.error("Position save failed.")
    if pcol2.button("🧹 Clear Position", width="stretch"):
        if v16_clear_active_position():
            st.success("Saved position cleared.")
            st.rerun()
    if _pos_saved.get("Saved At"):
        st.caption(f"Last saved: {_pos_saved.get('Saved At')}")


# =========================================================
# FETCH LIVE SOURCES
# =========================================================
master_result = get_dhan_instrument_master() if (prefer_dhan and dhan_ready) else {"success": False, "df": pd.DataFrame()}
top5_ids = resolve_top5_security_ids(master_result.get("df", pd.DataFrame())) if master_result.get("success") else {}
dhan_bundle = get_dhan_market_bundle(client_id, access_token, top5_ids, nifty_security_id) if (prefer_dhan and dhan_ready) else {"success": False, "message": "Dhan disabled."}

# Nifty
nifty_source = "Manual"
if dhan_bundle.get("success"):
    idx_data = (dhan_bundle.get("data", {}) or {}).get("IDX_I", {}) or {}
    idx_item = idx_data.get(str(nifty_security_id), {}) or idx_data.get(int(nifty_security_id), {}) or {}
    if idx_item:
        price = float(idx_item.get("last_price", 0) or manual_nifty)
        idx_ohlc = idx_item.get("ohlc", {}) or {}
        idx_prev = float(idx_ohlc.get("close", 0) or 0)
        nifty_change = price - idx_prev if idx_prev else 0.0
        nifty_change_pct = pct_change(price, idx_prev) if idx_prev else manual_nifty_change_pct
        nifty_source = "DhanHQ"
    else:
        yahoo_nifty = get_yahoo_nifty()
        price = yahoo_nifty.get("price", manual_nifty) if yahoo_nifty.get("success") else manual_nifty
        nifty_change = yahoo_nifty.get("change", 0.0) if yahoo_nifty.get("success") else 0.0
        nifty_change_pct = yahoo_nifty.get("change_pct", manual_nifty_change_pct) if yahoo_nifty.get("success") else manual_nifty_change_pct
        nifty_source = yahoo_nifty.get("source", "Manual") if yahoo_nifty.get("success") else "Manual"
else:
    yahoo_nifty = get_yahoo_nifty()
    price = yahoo_nifty.get("price", manual_nifty) if yahoo_nifty.get("success") else manual_nifty
    nifty_change = yahoo_nifty.get("change", 0.0) if yahoo_nifty.get("success") else 0.0
    nifty_change_pct = yahoo_nifty.get("change_pct", manual_nifty_change_pct) if yahoo_nifty.get("success") else manual_nifty_change_pct
    nifty_source = yahoo_nifty.get("source", "Manual") if yahoo_nifty.get("success") else "Manual"

# VIX
yahoo_vix = get_yahoo_vix()
if yahoo_vix.get("success"):
    vix = float(yahoo_vix["vix"])
    vix_change_pct = float(yahoo_vix["change_pct"])
    vix_source = yahoo_vix.get("source", "Yahoo fallback")
else:
    vix = manual_vix
    vix_change_pct = manual_vix_change_pct
    vix_source = "Manual"


# V16 Automatic Price Action - overrides stale manual values when enabled.
if auto_price_action:
    price_action_result = get_yahoo_price_action()
    if price_action_result.get("success"):
        ema20 = float(price_action_result.get("ema20", ema20))
        ema50 = float(price_action_result.get("ema50", ema50))
        vwap = float(price_action_result.get("vwap", vwap))
        atr5 = float(price_action_result.get("atr5", atr5))
        previous_day_high = float(price_action_result.get("previous_day_high", previous_day_high))
        previous_day_low = float(price_action_result.get("previous_day_low", previous_day_low))
        today_high = float(price_action_result.get("today_high", today_high))
        today_low = float(price_action_result.get("today_low", today_low))
        opening_range_high = float(price_action_result.get("opening_range_high", opening_range_high))
        opening_range_low = float(price_action_result.get("opening_range_low", opening_range_low))
        price_action_source = price_action_result.get("source", "Auto candles")
    else:
        price_action_source = "Manual fallback (auto failed)"
else:
    price_action_source = "Manual fallback"

# Heavyweights
if dhan_bundle.get("success") and top5_ids:
    heavy_raw = parse_dhan_heavyweights(dhan_bundle, top5_ids, weights)
    # V9 accuracy improvement: if Dhan quote gives symbols but no usable daily move, fallback to Yahoo for movement.
    if heavy_raw.get("success") and heavy_raw.get("rows") and all(abs(float(r.get("change_pct", 0) or 0)) < 0.001 for r in heavy_raw["rows"]):
        yahoo_hw = get_yahoo_heavyweights()
        if yahoo_hw.get("success"):
            for row in yahoo_hw["rows"]:
                row["weight"] = float(weights.get(row["symbol"], row["weight"]))
            yahoo_hw["source"] = "Yahoo fallback (Dhan stock move unavailable)"
            heavy_raw = yahoo_hw
else:
    heavy_raw = get_yahoo_heavyweights()
    if heavy_raw.get("success"):
        for row in heavy_raw["rows"]:
            row["weight"] = float(weights.get(row["symbol"], row["weight"]))
heavy_analysis = analyze_heavyweights(heavy_raw, price, nifty_change_pct)

# Option chain - Dhan only; manual aggregate fallback otherwise
option_chain = {"success": False, "message": "Waiting for Dhan expiry/option-chain response. Check Data API subscription, expiry list and token."}
selected_expiry = None
expiry_result = {"success": False, "expiries": [], "message": "Dhan not attempted."}
if prefer_dhan and dhan_ready:
    expiry_result = get_dhan_expiries(client_id, access_token, nifty_security_id, DEFAULT_NIFTY_SEGMENT)
    if expiry_result.get("success"):
        selected_expiry = st.sidebar.selectbox("📅 Dhan Nifty Expiry", expiry_result["expiries"], index=0)
        option_chain = get_dhan_option_chain(
            client_id,
            access_token,
            selected_expiry,
            nifty_security_id,
            DEFAULT_NIFTY_SEGMENT,
            strikes_each_side,
            50,
        )
    else:
        option_chain = {"success": False, "message": "Expiry list unavailable: " + str(expiry_result.get("message", "Unknown Dhan expiry error"))}

option_analysis = analyze_option_chain(option_chain) if option_chain.get("success") else {"success": False, "rows": [], "bias": 0}

# Aggregates
if option_chain.get("success"):
    total_call_oi = option_chain["total_call_oi"]
    total_put_oi = option_chain["total_put_oi"]
    call_oi_change = option_chain["call_oi_change"]
    put_oi_change = option_chain["put_oi_change"]
    pcr = option_chain["pcr"]
else:
    total_call_oi = manual_total_call_oi
    total_put_oi = manual_total_put_oi
    call_oi_change = manual_call_oi_change
    put_oi_change = manual_put_oi_change
    pcr = safe_divide(total_put_oi, total_call_oi, 0.0)

# News risk
te_key = get_secret("TRADING_ECONOMICS_API_KEY")
alpha_key = get_secret("ALPHAVANTAGE_API_KEY")
te_result = get_te_calendar_risk(te_key) if use_auto_news and te_key else {"success": False, "score": 0}
alpha_result = get_alpha_news_risk(alpha_key) if use_auto_news and alpha_key else {"success": False, "score": 0}
reaction_score = market_reaction_risk(nifty_change_pct, vix_change_pct, heavy_analysis)
news = build_news_risk(manual_news_risk, te_result, alpha_result, reaction_score, vix_change_pct, heavy_analysis.get("shock_score", 0))


# =========================================================
# SELLER INTELLIGENCE ENGINE
# =========================================================
support_levels = [previous_day_low, today_low, opening_range_low]
resistance_levels = [previous_day_high, today_high, opening_range_high]
nearest_support = max([x for x in support_levels if x <= price], default=min(support_levels))
nearest_resistance = min([x for x in resistance_levels if x >= price], default=max(resistance_levels))
support_distance = max(price - nearest_support, 0)
resistance_distance = max(nearest_resistance - price, 0)

price_action_bias = 0.0
price_action_bias += 22 if price > ema20 else -22
price_action_bias += 18 if price > ema50 else -18
price_action_bias += 25 if price > vwap else -25
price_action_bias += 15 if ema20 > ema50 else -15
if price > opening_range_high:
    price_action_bias += 18
elif price < opening_range_low:
    price_action_bias -= 18
price_action_bias = signed_clamp(price_action_bias)

sr_bias = 0.0
if support_distance <= 30:
    sr_bias += 55
elif support_distance <= 60:
    sr_bias += 25
if resistance_distance <= 30:
    sr_bias -= 55
elif resistance_distance <= 60:
    sr_bias -= 25
sr_bias = signed_clamp(sr_bias)

# Option-chain directional bias. When Dhan is absent, use aggregate OI + PCR only.
if option_analysis.get("success"):
    option_bias = float(option_analysis.get("bias", 0))
else:
    oi_delta_base = max(abs(call_oi_change), abs(put_oi_change), 1)
    option_bias = signed_clamp(((put_oi_change - call_oi_change) / oi_delta_base) * 65)

pcr_bias = 0.0
if 0.95 <= pcr <= 1.25:
    pcr_bias = 35
elif 1.25 < pcr <= 1.55:
    pcr_bias = 18
elif pcr > 1.55:
    pcr_bias = -5
elif 0.75 <= pcr < 0.95:
    pcr_bias = -22
else:
    pcr_bias = -45

# Use FII/DII journal rolling data if available; manual fields remain fallback.
try:
    _journal_stats_live = v102_journal_stats(locals().get("fii_journal_df", pd.DataFrame()))
    if _journal_stats_live.get("rows", 0) > 0:
        if abs(float(fii_5day)) < 0.001:
            fii_5day = _journal_stats_live["fii_5"]
        if abs(float(dii_5day)) < 0.001:
            dii_5day = _journal_stats_live["dii_5"]
except Exception:
    _journal_stats_live = {"rows": 0, "fii_5": fii_5day, "dii_5": dii_5day, "bias": 0}

smart_money_bias = 0.0
smart_money_bias += 22 if fii_today > 0 else -22 if fii_today < 0 else 0
smart_money_bias += 10 if dii_today > 0 else -10 if dii_today < 0 else 0
smart_money_bias += 18 if fii_5day > 0 else -18 if fii_5day < 0 else 0
smart_money_bias += 8 if dii_5day > 0 else -8 if dii_5day < 0 else 0
_fut_score = v135_fut_bias_score(locals().get("fii_long_pct", 0), locals().get("fii_short_pct", 0), fii_index_futures_bias)
smart_money_bias += _fut_score
smart_money_bias = signed_clamp(smart_money_bias)

heavy_bias = float(heavy_analysis.get("pressure", 0)) if heavy_analysis.get("success") else 0.0

# Weighted directional model
final_direction = (
    price_action_bias * 0.24
    + option_bias * 0.24
    + heavy_bias * 0.19
    + smart_money_bias * 0.12
    + pcr_bias * 0.09
    + sr_bias * 0.12
)
final_direction = signed_clamp(final_direction)

# Risk model for an option seller
vix_risk = 15 if vix <= 14 else 30 if vix <= 18 else 65 if vix <= 24 else 90
liquidity_risk = 0
if option_analysis.get("success"):
    selected_rows = [r for r in option_analysis["rows"] if abs(r["strike"] - price) <= 200]
    wide = [r for r in selected_rows if max(r.get("ce_spread_pct", 0), r.get("pe_spread_pct", 0)) > 2.0]
    liquidity_risk = safe_divide(len(wide), len(selected_rows), 0) * 100 if selected_rows else 0

divergence_risk = 35 if heavy_analysis.get("divergence") != "NONE" else 0
seller_risk = (
    news["score"] * 0.42
    + vix_risk * 0.25
    + heavy_analysis.get("shock_score", 0) * 0.18
    + divergence_risk * 0.08
    + liquidity_risk * 0.07
)
seller_risk = clamp(seller_risk)

component_signs = [price_action_bias, option_bias, heavy_bias, smart_money_bias, pcr_bias, sr_bias]
positive_components = sum(1 for x in component_signs if x >= 15)
negative_components = sum(1 for x in component_signs if x <= -15)
agreement = max(positive_components, negative_components) / len(component_signs)
confidence = clamp(abs(final_direction) * 0.72 + agreement * 35 + (100 - seller_risk) * 0.18, 0, 98)

# V9 improved decision model:
# 1) Hard risk blocks first
# 2) Conflict mode = WAIT
# 3) Dhan option-chain can strengthen strike-specific decision, but price action must not be strongly opposite.
hard_block = news["score"] >= 80 or seller_risk >= 82
conflict_mode_pre, conflict_reasons_pre = v9_conflict_detector(price_action_bias, option_bias, heavy_bias, pcr, 0)

if hard_block:
    final_trade = "WAIT"
elif conflict_mode_pre:
    final_trade = "WAIT"
    confidence = min(confidence, 55)
elif option_analysis.get("success") and option_bias >= 55 and price_action_bias > -45 and pcr >= 0.80:
    final_trade = "SELL PE"
    confidence = max(confidence, 66)
elif option_analysis.get("success") and option_bias <= -55 and price_action_bias < 45 and pcr <= 1.30:
    final_trade = "SELL CE"
    confidence = max(confidence, 66)
elif final_direction >= 24 and confidence >= 58:
    final_trade = "SELL PE"
elif final_direction <= -24 and confidence >= 58:
    final_trade = "SELL CE"
else:
    final_trade = "WAIT"

# Strike selection from Dhan ranking when available; manual fallback otherwise.
best_ce = option_analysis.get("best_ce") if option_analysis.get("success") else None
best_pe = option_analysis.get("best_pe") if option_analysis.get("success") else None
ce_strike = int(best_ce["strike"]) if best_ce else manual_ce_strike
pe_strike = int(best_pe["strike"]) if best_pe else manual_pe_strike

if final_trade == "SELL PE":
    selected_strike = f"{pe_strike} PE"
    hedge = f"{pe_strike - hedge_gap} PE"
    selected_strike_score = best_pe.get("pe_sell_score", 0) if best_pe else 0
elif final_trade == "SELL CE":
    selected_strike = f"{ce_strike} CE"
    hedge = f"{ce_strike + hedge_gap} CE"
    selected_strike_score = best_ce.get("ce_sell_score", 0) if best_ce else 0
else:
    selected_strike = "No Strike"
    hedge = "No Hedge"
    selected_strike_score = 0

max_lots = int(capital / margin_per_lot) if margin_per_lot > 0 else 0
if final_trade == "WAIT":
    suggested_lots = 0
else:
    risk_multiplier = max(0.0, (100 - seller_risk) / 100)
    confidence_multiplier = confidence / 100
    raw_lots = int(max_lots * risk_multiplier * confidence_multiplier)
    suggested_lots = max(1, min(max_lots, raw_lots)) if max_lots > 0 else 0

sl_points = round(max(atr5 * (1.25 if seller_risk < 50 else 1.6), 20), 2)
target_points = round(max(atr5 * 0.85, 15), 2)
if final_trade == "WAIT":
    sl_display = "No Trade"
    target_display = "No Trade"
else:
    sl_display = f"{sl_points} pts"
    target_display = f"{target_points} pts"


# V7 advanced management layer
market_mode, dte = detect_expiry_mode(selected_expiry, news["score"])
is_expiry_mode = market_mode in ("EXPIRY MODE", "NEAR EXPIRY MODE")
time_risk, time_zone_label = historical_time_zone_risk(is_expiry_mode)
theta_score_v7, active_profit_pct = theta_decay_score(is_expiry_mode, active_entry_price, active_current_price)
gamma_score_v7 = gamma_risk_score(is_expiry_mode, vix_change_pct, time_risk, option_bias, heavy_bias)
shock_score_v7 = shock_probability_score(time_risk, vix_risk, option_bias, heavy_bias, news["score"])
position_ai = active_position_manager(active_side, active_strike, active_entry_price, active_current_price, active_lots, theta_score_v7, gamma_score_v7, shock_score_v7, final_trade, confidence)
discipline_text, discipline_score, discipline_reason = discipline_status(trades_taken_today, daily_loss_hit, confidence, seller_risk)
trade_quality = trade_quality_score(confidence, seller_risk, shock_score_v7)

# Final V9 conflict check now includes Gamma.
conflict_mode, conflict_reasons = v9_conflict_detector(price_action_bias, option_bias, heavy_bias, pcr, gamma_score_v7)
if conflict_mode and final_trade != "WAIT":
    final_trade = "WAIT"
    confidence = min(confidence, 55)
    selected_strike = "No Strike"
    hedge = "No Hedge"
    selected_strike_score = 0
    suggested_lots = 0
    trade_quality = trade_quality_score(confidence, seller_risk, shock_score_v7)


# AI Brain: rolling memory + decision freeze + stability.
proposed_trade_v14 = final_trade
try:
    vix_range = v132_vix_range_engine(price, vix)
except Exception:
    vix_range = {"ok": False}

candle15 = v14_candle_confirmation(
    locals().get("candle15_open", price),
    locals().get("candle15_high", price),
    locals().get("candle15_low", price),
    locals().get("candle15_close", price),
    final_direction,
)
# Candle is confirmation only: low weight, no overreaction.
if candle15.get("aligned") and proposed_trade_v14 != "WAIT":
    confidence = clamp(confidence + min(abs(candle15.get("score", 0)), 6), 0, 98)
elif not candle15.get("aligned") and proposed_trade_v14 != "WAIT":
    confidence = min(confidence, 68)

v14_snapshot = {
    "snapshot_id": f"{fmt_time()}|{price:.2f}|{vix:.2f}|{proposed_trade_v14}|{round(option_bias,2)}|{round(heavy_bias,2)}",
    "time": fmt_time(),
    "price": float(price),
    "vix": float(vix),
    "pcr": float(pcr),
    "option_bias": float(option_bias),
    "heavy_bias": float(heavy_bias),
    "price_action_bias": float(price_action_bias),
    "proposed_trade": proposed_trade_v14,
    "confidence": float(confidence),
}
v14_memory = v14_snapshot_engine(v14_snapshot, max_len=20)
v14_freeze = v14_decision_freeze(proposed_trade_v14, confidence, v14_memory, required=3)
v14_stability = v14_confidence_stability(v14_memory, proposed_trade_v14, confidence)
v14_regime = v14_market_regime(price_action_bias, option_bias, heavy_bias, vix, shock_score_v7, gamma_score_v7, is_expiry_mode, time_risk)
v14_seller_strength = v14_seller_strength(best_ce, best_pe, option_bias)

# V22.4 ZERO MALIK: legacy V14 freeze is evidence only.
# The active stability decision is handled later by stability_engine + advisor_engine.
legacy_v14_freeze_evidence = {
    "proposed_trade": proposed_trade_v14,
    "confirmed": bool(v14_freeze.get("confirmed", False)) if isinstance(v14_freeze, dict) else False,
    "confidence": v14_freeze.get("confidence", confidence) if isinstance(v14_freeze, dict) else confidence,
    "status": "EVIDENCE_ONLY_NOT_AUTHORITY",
}

trade_quality = trade_quality_score(confidence, seller_risk, shock_score_v7)
v14_entry = v14_entry_window(market_mode, time_risk, confidence, v14_stability.get("score", 0), v14_freeze.get("confirmed", False), seller_risk)
v14_reason_items = v14_reason_breakdown(price_action_bias, option_bias, heavy_bias, smart_money_bias, pcr_bias, 0, vix_risk, seller_risk)


# V9.1 stable defaults: prevent NameError if any earlier block skipped.
try:
    _ = conflict_mode
except NameError:
    conflict_mode, conflict_reasons = v91_conflict_detector(price_action_bias, option_bias, heavy_bias, pcr, locals().get("gamma_score_v7", 0))

try:
    _ = data_quality
except NameError:
    data_quality, data_quality_reasons = v91_data_quality_score(
        dhan_ready=locals().get("dhan_ready", False),
        option_ok=bool(locals().get("option_chain", {}).get("success", False)) if isinstance(locals().get("option_chain", {}), dict) else False,
        nifty_source=locals().get("nifty_source", "Fallback"),
        heavy_source=(locals().get("heavy_analysis", {}) or {}).get("source", "Fallback") if isinstance(locals().get("heavy_analysis", {}), dict) else "Fallback",
        vix_source=locals().get("vix_source", "Fallback"),
    )

source_text = v13_source_text(locals().get("dhan_ready", False), locals().get("option_chain", {}), locals().get("nifty_source", "Fallback"), locals().get("dhan_bundle", {}), locals().get("expiry_result", {}))
action_plan = v91_action_plan(
    locals().get("final_trade", "WAIT"),
    locals().get("selected_strike", "No Strike"),
    locals().get("hedge", "No Hedge"),
    locals().get("confidence", 0),
    locals().get("seller_risk", 0),
    locals().get("shock_score_v7", 0),
    locals().get("gamma_score_v7", 0),
    locals().get("conflict_reasons", []),
    source_text,
    data_quality,
)



# =========================================================
# V10 OPTION SELLER AI BRAIN
# =========================================================
def v10_probability_engine(price_action_bias, option_bias, heavy_bias, pcr, vix, gamma_score, shock_score, news_score):
    """
    Converts multiple live signals into directional/range probabilities.
    This is decision-support, not prediction guarantee.
    """
    pa = v91_safe_num(price_action_bias)
    ob = v91_safe_num(option_bias)
    hw = v91_safe_num(heavy_bias)
    pcrv = v91_safe_num(pcr, 1.0)
    vixv = v91_safe_num(vix)
    gamma = v91_safe_num(gamma_score)
    shock = v91_safe_num(shock_score)
    news = v91_safe_num(news_score)

    raw_bull = 50 + (pa * 0.20) + (ob * 0.30) + (hw * 0.20)
    if 1.0 <= pcrv <= 1.35:
        raw_bull += 6
    elif pcrv < 0.85:
        raw_bull -= 8
    elif pcrv > 1.55:
        raw_bull -= 4

    bull = int(max(5, min(95, raw_bull)))
    bear = int(max(5, min(95, 100 - bull)))

    conflict_strength = abs(ob - pa)
    range_prob = 45
    if conflict_strength >= 80:
        range_prob += 22
    if vixv <= 14:
        range_prob += 12
    if gamma >= 70:
        range_prob -= 15
    if shock >= 60:
        range_prob -= 10
    range_prob = int(max(5, min(95, range_prob)))

    breakout_prob = int(max(5, min(95, 100 - range_prob + (gamma * 0.20) + (news * 0.10))))
    fake_breakout = "HIGH" if conflict_strength >= 110 and vixv <= 15 else "MEDIUM" if conflict_strength >= 70 else "LOW"

    return {
        "bullish": bull,
        "bearish": bear,
        "range": range_prob,
        "breakout": breakout_prob,
        "fake_breakout": fake_breakout,
        "conflict_strength": int(conflict_strength),
    }

def v10_interpret_conflict(price_action_bias, option_bias, heavy_bias, pcr):
    pa = v91_safe_num(price_action_bias)
    ob = v91_safe_num(option_bias)
    hw = v91_safe_num(heavy_bias)
    pcrv = v91_safe_num(pcr, 1.0)
    notes = []

    if pa <= -45 and ob >= 55:
        notes.append("Bearish chart + bullish option-chain = possible short-covering / PE writing support, but entry risky until price confirms.")
    elif pa >= 45 and ob <= -55:
        notes.append("Bullish chart + bearish option-chain = possible call writing pressure / resistance, wait for confirmation.")
    elif abs(pa) < 25 and abs(ob) >= 55:
        notes.append("Price action neutral hai, option-chain strong signal de rahi hai. Breakout confirmation ka wait karo.")
    elif abs(ob) < 25 and abs(pa) >= 55:
        notes.append("Chart strong hai, option-chain support weak hai. Seller ke liye low-confidence zone.")
    else:
        notes.append("Major conflict limited hai; signal alignment improve ho raha hai.")

    if hw >= 35 and pa < 0:
        notes.append("Heavyweights hidden support de rahe hain; downside follow-through weak ho sakta hai.")
    if hw <= -35 and pa > 0:
        notes.append("Heavyweights hidden pressure de rahe hain; upside follow-through weak ho sakta hai.")
    if pcrv < 0.85:
        notes.append("PCR low hai: call-side pressure ya bearish sentiment possible.")
    elif pcrv > 1.45:
        notes.append("PCR high hai: bullish sentiment strong but overcrowding risk.")
    return notes


def v10_sl_target(entry_premium, gamma_score, shock_score, confidence):
    """
    Premium based SL/target suggestion for manual active trade.
    """
    entry = v91_safe_num(entry_premium)
    gamma = v91_safe_num(gamma_score)
    shock = v91_safe_num(shock_score)
    conf = v91_safe_num(confidence)
    if entry <= 0:
        return {"sl": 0, "target": 0, "trail_after": 0}
    sl_pct = 0.22
    if gamma >= 65 or shock >= 60:
        sl_pct = 0.16
    elif conf >= 75:
        sl_pct = 0.25
    target_pct = 0.35 if conf >= 70 else 0.25
    return {
        "sl": round(entry * (1 + sl_pct), 2),
        "target": round(entry * (1 - target_pct), 2),
        "trail_after": round(entry * 0.75, 2),
    }



# V10 analytics calculated after all major signals are available.
try:
    _ = v10_probs
except NameError:
    v10_probs = v10_probability_engine(
        price_action_bias,
        option_bias,
        heavy_bias,
        pcr,
        locals().get("vix", locals().get("india_vix", 0)),
        locals().get("gamma_score_v7", 0),
        locals().get("shock_score_v7", 0),
        locals().get("news", {}).get("score", 0) if isinstance(locals().get("news", {}), dict) else 0,
    )

try:
    _ = v10_conflict_notes
except NameError:
    v10_conflict_notes = v10_interpret_conflict(price_action_bias, option_bias, heavy_bias, pcr)



# =========================================================
# V11 SUPER SIGNAL + STRATEGY ENGINE
# =========================================================
def v11_super_signal_engine(
    final_trade="WAIT",
    confidence=0,
    data_quality=0,
    seller_risk=100,
    shock_score=100,
    gamma_score=100,
    conflict_mode=True,
    price_action_bias=0,
    option_bias=0,
    heavy_bias=0,
    smart_money_bias=0,
    news_score=100,
    pcr=1.0,
    vix=99,
):
    """
    High-confidence signal engine.
    Goal: fewer signals, higher quality. No guarantee, only evidence-based grading.
    """
    conf = v91_safe_num(confidence)
    dq = v91_safe_num(data_quality)
    sr = v91_safe_num(seller_risk)
    shock = v91_safe_num(shock_score)
    gamma = v91_safe_num(gamma_score)
    pa = v91_safe_num(price_action_bias)
    ob = v91_safe_num(option_bias)
    hw = v91_safe_num(heavy_bias)
    sm = v91_safe_num(smart_money_bias)
    news = v91_safe_num(news_score)
    pcrv = v91_safe_num(pcr, 1.0)
    vixv = v91_safe_num(vix)

    bullish_votes = 0
    bearish_votes = 0
    range_votes = 0
    notes = []

    if pa >= 35: bullish_votes += 1
    if pa <= -35: bearish_votes += 1
    if ob >= 45: bullish_votes += 1
    if ob <= -45: bearish_votes += 1
    if hw >= 25: bullish_votes += 1
    if hw <= -25: bearish_votes += 1
    if sm >= 20: bullish_votes += 1
    if sm <= -20: bearish_votes += 1
    if 0.95 <= pcrv <= 1.35: bullish_votes += 1
    if pcrv < 0.85: bearish_votes += 1
    if vixv <= 15 and shock <= 45: range_votes += 1
    if gamma <= 55: range_votes += 1
    if news <= 35: range_votes += 1

    safe_core = dq >= 75 and sr <= 55 and shock <= 55 and gamma <= 65 and news <= 55 and not conflict_mode

    if not safe_core:
        notes.append("Super signal blocked: data/risk/conflict conditions not fully safe.")

    level = "NO SUPER SIGNAL"
    signal = "WAIT"
    score = int(max(0, min(100, (conf * 0.35) + (dq * 0.20) + ((100 - sr) * 0.15) + ((100 - shock) * 0.15) + ((100 - gamma) * 0.10) + ((100 - news) * 0.05))))

    if safe_core and conf >= 82:
        if final_trade == "SELL CE" and bearish_votes >= 3:
            signal = "SUPER SELL CE"
            level = "SUPER"
            notes.append("Bearish confirmations aligned for CE selling.")
        elif final_trade == "SELL PE" and bullish_votes >= 3:
            signal = "SUPER SELL PE"
            level = "SUPER"
            notes.append("Bullish confirmations aligned for PE selling.")
        elif range_votes >= 3 and abs(pa) < 45 and abs(ob) < 70:
            signal = "SUPER IRON CONDOR"
            level = "SUPER"
            notes.append("Range + low shock + theta-friendly environment.")
    elif safe_core and conf >= 72:
        level = "HIGH CONFIDENCE"
        signal = final_trade if final_trade != "WAIT" else "WAIT"
        notes.append("High-confidence but not super-grade setup.")
    elif safe_core and conf >= 62:
        level = "STRONG WATCH"
        signal = final_trade
        notes.append("Good setup, but wait for stronger confirmation.")
    else:
        notes.append("No high-confidence signal. WAIT/observe preferred.")

    return {
        "signal": signal,
        "level": level,
        "score": score,
        "bullish_votes": bullish_votes,
        "bearish_votes": bearish_votes,
        "range_votes": range_votes,
        "notes": notes,
    }

def v11_strategy_ranker(
    price_action_bias=0,
    option_bias=0,
    heavy_bias=0,
    smart_money_bias=0,
    pcr=1.0,
    vix=99,
    shock_score=100,
    gamma_score=100,
    news_score=100,
    conflict_mode=True,
    data_quality=0,
):
    """
    Strategy ranking: seller-first, buy-with-hedge only on strong trend/catalyst.
    """
    pa = v91_safe_num(price_action_bias)
    ob = v91_safe_num(option_bias)
    hw = v91_safe_num(heavy_bias)
    sm = v91_safe_num(smart_money_bias)
    pcrv = v91_safe_num(pcr, 1.0)
    vixv = v91_safe_num(vix)
    shock = v91_safe_num(shock_score)
    gamma = v91_safe_num(gamma_score)
    news = v91_safe_num(news_score)
    dq = v91_safe_num(data_quality)

    risk_penalty = max(0, shock - 45) * 0.25 + max(0, gamma - 60) * 0.20 + max(0, news - 55) * 0.25
    data_bonus = max(0, dq - 60) * 0.20
    conflict_penalty = 18 if conflict_mode else 0

    sell_pe = 50 + pa*0.18 + ob*0.25 + hw*0.18 + sm*0.10 + data_bonus - risk_penalty - conflict_penalty
    sell_ce = 50 - pa*0.18 - ob*0.25 - hw*0.18 - sm*0.10 + data_bonus - risk_penalty - conflict_penalty
    range_base = 55 + (15 if vixv <= 15 else 0) + (12 if shock <= 45 else -10) + (10 if gamma <= 55 else -12) - abs(pa)*0.10 - abs(hw)*0.06 - conflict_penalty*0.5
    iron_condor = range_base + data_bonus
    buy_call_hedged = 35 + pa*0.22 + hw*0.20 + sm*0.10 + max(0, news-40)*0.08 - max(0, vixv-18)*0.6 - (8 if ob < 0 else 0)
    buy_put_hedged = 35 - pa*0.22 - hw*0.20 - sm*0.10 + max(0, news-40)*0.08 - max(0, vixv-18)*0.6 + (8 if ob < 0 else 0)

    # Buy strategy should be rare and catalyst/trend based.
    if abs(pa) < 60 or abs(hw) < 25 or dq < 75:
        buy_call_hedged -= 18
        buy_put_hedged -= 18
    if news < 35 and shock < 45:
        buy_call_hedged -= 8
        buy_put_hedged -= 8

    strategies = [
        {"strategy": "SELL PE", "confidence": int(max(0, min(95, sell_pe))), "type": "Seller"},
        {"strategy": "SELL CE", "confidence": int(max(0, min(95, sell_ce))), "type": "Seller"},
        {"strategy": "IRON CONDOR", "confidence": int(max(0, min(95, iron_condor))), "type": "Seller Range"},
        {"strategy": "BUY CALL (Hedged)", "confidence": int(max(0, min(95, buy_call_hedged))), "type": "Defined Risk Buy"},
        {"strategy": "BUY PUT (Hedged)", "confidence": int(max(0, min(95, buy_put_hedged))), "type": "Defined Risk Buy"},
        {"strategy": "WAIT", "confidence": int(max(25, min(95, 100 - max(sell_pe, sell_ce, iron_condor, buy_call_hedged, buy_put_hedged)))), "type": "Safety"},
    ]
    strategies = sorted(strategies, key=lambda x: x["confidence"], reverse=True)
    return strategies




# =========================================================
# V16.4 AI AUDIT + SINGLE DECISION + BEST STRIKE ENGINE
# =========================================================
def v164_live_move_detector(price, nifty_change_pct, atr5=40):
    """Detect fast Nifty movement between app refreshes and daily move shock."""
    try:
        price = float(price or 0)
        atr5 = max(float(atr5 or 40), 1.0)
        prev = st.session_state.get("v164_prev_nifty_price")
        st.session_state["v164_prev_nifty_price"] = price
        move_points = 0.0 if prev in (None, 0) else price - float(prev)
        move_abs = abs(move_points)
        daily_abs_pct = abs(float(nifty_change_pct or 0))
        # Intraday shock if move from last app snapshot is meaningful versus ATR.
        fast_shock = move_abs >= max(35.0, atr5 * 0.70)
        daily_shock = daily_abs_pct >= 0.45
        direction = "DOWN" if move_points < 0 or float(nifty_change_pct or 0) < -0.45 else "UP" if move_points > 0 or float(nifty_change_pct or 0) > 0.45 else "FLAT"
        score = 0
        score += min(move_abs / max(atr5, 1) * 45, 60)
        score += min(daily_abs_pct * 75, 40)
        score = int(clamp(score, 0, 100))
        return {
            "fast_shock": bool(fast_shock),
            "daily_shock": bool(daily_shock),
            "direction": direction,
            "move_points": round(move_points, 2),
            "daily_pct": round(float(nifty_change_pct or 0), 2),
            "score": score,
            "label": "FAST FALL" if direction == "DOWN" and (fast_shock or daily_shock) else "FAST RISE" if direction == "UP" and (fast_shock or daily_shock) else "NORMAL",
        }
    except Exception:
        return {"fast_shock": False, "daily_shock": False, "direction": "FLAT", "move_points": 0.0, "daily_pct": 0.0, "score": 0, "label": "NA"}


def v164_score_candidate(row, side, spot, preferred_min=30, preferred_max=150):
    """Robust best strike scoring: live OTM, premium zone, OI, volume, delta, spread."""
    try:
        side = side.upper()
        prefix = side.lower()
        strike = int(row.get("strike", 0) or 0)
        spot = float(spot or 0)
        premium = float(row.get(f"{prefix}_ltp", 0) or 0)
        delta_abs = abs(float(row.get(f"{prefix}_delta", 0) or 0))
        spread_pct = float(row.get(f"{prefix}_spread_pct", 0) or 0)
        oi_chg_pct = float(row.get(f"{prefix}_oi_change_pct", 0) or 0)
        vol_ratio = float(row.get(f"{prefix}_volume_ratio", 0) or 0)
        base_sell_score = float(row.get(f"{prefix}_sell_score", 0) or 0)
        # SELL CE should be above/at spot; SELL PE should be below/at spot.
        otm_ok = (strike >= int(round(spot / 50) * 50)) if side == "CE" else (strike <= int(round(spot / 50) * 50))
        if not otm_ok or premium <= 0:
            return -9999
        distance = abs(strike - spot)
        score = base_sell_score
        # Premium zone: seller-friendly but not too cheap or too dangerous.
        if preferred_min <= premium <= preferred_max:
            score += 28
        elif 20 <= premium < preferred_min:
            score += 8
        elif preferred_max < premium <= 220:
            score -= 10
        else:
            score -= 35
        # Delta: avoid very high delta and very far useless options.
        if 0.12 <= delta_abs <= 0.34:
            score += 18
        elif 0.08 <= delta_abs <= 0.42:
            score += 8
        else:
            score -= 18
        # Distance: enough distance but not too far.
        if 80 <= distance <= 350:
            score += 14
        elif distance < 50:
            score -= 22
        elif distance > 500:
            score -= 16
        # OI/volume/spread.
        if oi_chg_pct > 0:
            score += min(oi_chg_pct * 0.25, 12)
        if vol_ratio >= 1.0:
            score += min(vol_ratio * 4, 12)
        if 0 < spread_pct <= 1.0:
            score += 10
        elif spread_pct > 2.0:
            score -= 20
        return score
    except Exception:
        return -9999


def v164_select_best_strikes(option_analysis, spot, premium_min=30, premium_max=150):
    rows = option_analysis.get("rows", []) if isinstance(option_analysis, dict) else []
    best = {"CE": None, "PE": None}
    for side in ("CE", "PE"):
        scored = []
        for row in rows:
            sc = v164_score_candidate(row, side, spot, premium_min, premium_max)
            if sc > -1000:
                rr = row.copy()
                rr[f"{side.lower()}_v164_score"] = round(sc, 2)
                scored.append((sc, rr))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored:
            best[side] = scored[0][1]
    return best



# V20.3 Candidate Freshness Guard
# Best CE/PE must always come from the latest option-chain snapshot. The lock stores
# only strike/side state; price/SL/target are always recalculated from current rows.
def _v203_current_option_row(option_analysis, strike):
    try:
        strike = int(float(strike or 0))
        for rr in (option_analysis.get("rows", []) if isinstance(option_analysis, dict) else []):
            if int(rr.get("strike", 0) or 0) == strike:
                return dict(rr)
    except Exception:
        pass
    return None


def _v203_candidate_score(row, side, spot=0):
    if not row:
        return -9999.0
    prefix = str(side).lower()
    try:
        base = float(row.get(f"{prefix}_v164_score", row.get(f"{prefix}_sell_score", -9999)) or -9999)
    except Exception:
        base = -9999.0
    # If v164 score is missing on a refreshed current row, recalculate from current row.
    if base <= -999:
        try:
            base = float(v164_score_candidate(row, str(side).upper(), float(spot or price or 0), 30, 150))
        except Exception:
            base = float(row.get(f"{prefix}_sell_score", -9999) or -9999)
    return base


def _v203_candidate_freshness_guard(side, new_row, option_analysis, spot=0):
    """Keep candidate stable without using stale price.
    - New and previous strikes are both resolved from current option_analysis rows.
    - If best strike flips by a tiny score gap, keep old strike for one confirmation.
    - LTP/Entry/SL/Target always use the current row, never stored old row.
    """
    if not new_row or not isinstance(option_analysis, dict) or not option_analysis.get("success"):
        return new_row
    side = str(side).upper()
    key = f"v203_best_{side}_candidate_lock"
    snapshot_id = str(option_analysis.get("snapshot_id", ""))
    new_strike = int(new_row.get("strike", 0) or 0)
    current_new = _v203_current_option_row(option_analysis, new_strike) or dict(new_row)
    new_score = _v203_candidate_score(current_new, side, spot)
    prev = st.session_state.get(key, {}) if hasattr(st, "session_state") else {}
    prev_strike = int(prev.get("strike", 0) or 0) if isinstance(prev, dict) else 0

    # First run or same strike: update lock and return fresh current row.
    if not prev_strike or prev_strike == new_strike:
        st.session_state[key] = {"strike": new_strike, "pending": 0, "pending_strike": 0, "snapshot_id": snapshot_id, "score": round(new_score, 2), "time": fmt_time()}
        current_new["candidate_freshness"] = "fresh"
        return current_new

    prev_current = _v203_current_option_row(option_analysis, prev_strike)
    if not prev_current:
        # Previous strike is not in latest chain window, so accept new strike.
        st.session_state[key] = {"strike": new_strike, "pending": 0, "pending_strike": 0, "snapshot_id": snapshot_id, "score": round(new_score, 2), "time": fmt_time()}
        current_new["candidate_freshness"] = "fresh-prev-out-of-window"
        return current_new

    prev_score = _v203_candidate_score(prev_current, side, spot)
    score_gap = new_score - prev_score
    try:
        material = int((snapshot_delta or {}).get("material_change", 0) or 0)
    except Exception:
        material = 0
    pending_strike = int(prev.get("pending_strike", 0) or 0) if isinstance(prev, dict) else 0
    pending = int(prev.get("pending", 0) or 0) if isinstance(prev, dict) else 0
    pending = pending + 1 if pending_strike == new_strike else 1

    # Tiny score changes should not make CE/PE jump every refresh.
    if score_gap < 8 and material < 60 and pending < 2:
        st.session_state[key] = {"strike": prev_strike, "pending": pending, "pending_strike": new_strike, "snapshot_id": snapshot_id, "score": round(prev_score, 2), "time": fmt_time()}
        prev_current["candidate_freshness"] = f"stable-lock; new {new_strike} pending"
        return prev_current

    st.session_state[key] = {"strike": new_strike, "pending": 0, "pending_strike": 0, "snapshot_id": snapshot_id, "score": round(new_score, 2), "time": fmt_time()}
    current_new["candidate_freshness"] = "fresh-confirmed"
    return current_new


def v164_unified_decision_engine(ranked, price_action_bias, option_bias, heavy_bias, smart_money_bias, pcr_bias, seller_risk, shock_score, gamma_score, news_score, data_quality, conflict_mode, move_guard):
    """One engine for final decision. Strategy Matrix and final card must not contradict."""
    ranked = ranked or [{"strategy": "WAIT", "confidence": 25}]
    top = dict(ranked[0])
    top_strategy = str(top.get("strategy", "WAIT")).upper()
    top_conf = int(top.get("confidence", 0) or 0)
    reasons = []
    blockers = []
    # Hard blocks.
    if data_quality < 70:
        blockers.append(f"Data quality {data_quality}/100 hai; minimum 70 chahiye.")
    if news_score >= 75:
        blockers.append(f"News risk high {news_score}/100.")
    if seller_risk >= 72:
        blockers.append(f"Seller risk high {seller_risk:.0f}/100.")
    if gamma_score >= 78:
        blockers.append(f"Gamma risk high {gamma_score:.0f}/100.")
    # Conflict is blocker only when real disagreement, but trend shock can override to directional seller/buyer view.
    if conflict_mode and not (move_guard.get("score", 0) >= 55):
        blockers.append("AI modules conflict mein hain.")
    # Market move override: if Nifty falls sharply, don't allow bullish PE sell.
    if move_guard.get("label") == "FAST FALL":
        reasons.append(f"Fast fall detected: {move_guard.get('move_points',0)} pts from last refresh / daily {move_guard.get('daily_pct',0)}%")
        if top_strategy == "SELL PE":
            top_strategy, top_conf = "SELL CE", max(70, min(92, top_conf - 5))
            reasons.append("SELL PE blocked due to fast fall; CE side preferred.")
    elif move_guard.get("label") == "FAST RISE":
        reasons.append(f"Fast rise detected: {move_guard.get('move_points',0)} pts from last refresh / daily {move_guard.get('daily_pct',0)}%")
        if top_strategy == "SELL CE":
            top_strategy, top_conf = "SELL PE", max(70, min(92, top_conf - 5))
            reasons.append("SELL CE blocked due to fast rise; PE side preferred.")
    # Contributor confidence.
    directional_alignment = abs(float(price_action_bias or 0)) * 0.18 + abs(float(option_bias or 0)) * 0.22 + abs(float(heavy_bias or 0)) * 0.16 + abs(float(smart_money_bias or 0)) * 0.10 + abs(float(pcr_bias or 0)) * 0.08
    risk_penalty = float(seller_risk or 0) * 0.20 + float(shock_score or 0) * 0.13 + float(gamma_score or 0) * 0.10 + float(news_score or 0) * 0.12
    final_conf = clamp(top_conf * 0.55 + directional_alignment + (data_quality * 0.12) - risk_penalty * 0.20, 0, 98)
    if top_strategy == "WAIT":
        blockers.append("Top strategy WAIT hai.")
    if top_conf < 65:
        blockers.append(f"Top setup confidence {top_conf}% hai; minimum 65 chahiye.")
    # If top setup is very strong, use it as final unless hard blockers remain.
    if blockers:
        final = "WAIT"
        final_conf = min(final_conf, 64)
    else:
        final = top_strategy
        final_conf = max(final_conf, min(top_conf, 95))
    return {
        "final_trade": final,
        "confidence": int(round(clamp(final_conf, 0, 98))),
        "top_strategy": top_strategy,
        "top_confidence": top_conf,
        "blockers": blockers,
        "reasons": reasons,
    }



# V11 Super Signal + Strategy Ranking
try:
    _ = v11_super
except NameError:
    v11_super = v11_super_signal_engine(
        final_trade=locals().get("final_trade", "WAIT"),
        confidence=locals().get("confidence", 0),
        data_quality=locals().get("data_quality", 0),
        seller_risk=locals().get("seller_risk", 100),
        shock_score=locals().get("shock_score_v7", 100),
        gamma_score=locals().get("gamma_score_v7", 100),
        conflict_mode=locals().get("conflict_mode", True),
        price_action_bias=locals().get("price_action_bias", 0),
        option_bias=locals().get("option_bias", 0),
        heavy_bias=locals().get("heavy_bias", 0),
        smart_money_bias=locals().get("smart_money_bias", 0),
        news_score=(locals().get("news", {}) or {}).get("score", 100) if isinstance(locals().get("news", {}), dict) else 100,
        pcr=locals().get("pcr", 1.0),
        vix=locals().get("vix", 99),
    )

try:
    _ = v11_ranked_strategies
except NameError:
    v11_ranked_strategies = v11_strategy_ranker(
        price_action_bias=locals().get("price_action_bias", 0),
        option_bias=locals().get("option_bias", 0),
        heavy_bias=locals().get("heavy_bias", 0),
        smart_money_bias=locals().get("smart_money_bias", 0),
        pcr=locals().get("pcr", 1.0),
        vix=locals().get("vix", 99),
        shock_score=locals().get("shock_score_v7", 100),
        gamma_score=locals().get("gamma_score_v7", 100),
        news_score=(locals().get("news", {}) or {}).get("score", 100) if isinstance(locals().get("news", {}), dict) else 100,
        conflict_mode=locals().get("conflict_mode", True),
        data_quality=locals().get("data_quality", 0),
    )


# V16.4 AI Audit: current market move + best strike + single final decision.
try:
    v164_move_guard = v164_live_move_detector(price, nifty_change_pct, atr5)
except Exception:
    v164_move_guard = {"fast_shock": False, "daily_shock": False, "direction": "FLAT", "move_points": 0.0, "daily_pct": 0.0, "score": 0, "label": "NA"}

# V22.4 ZERO MALIK: old V16.4/V20.3 candidate selectors are now evidence-only.
# They must never overwrite best_ce/best_pe, strikes, AI_MASTER candidates, or UI advice.
try:
    legacy_v164_candidate_evidence = v164_select_best_strikes(option_analysis, price, 30, 150) if option_analysis.get("success") else {"CE": best_ce, "PE": best_pe}
except Exception:
    legacy_v164_candidate_evidence = {"CE": None, "PE": None, "error": "legacy candidate evidence failed"}

try:
    legacy_v203_candidate_evidence = {
        "CE": _v203_candidate_freshness_guard("CE", best_ce, option_analysis, price) if option_analysis.get("success") and best_ce else None,
        "PE": _v203_candidate_freshness_guard("PE", best_pe, option_analysis, price) if option_analysis.get("success") and best_pe else None,
    }
except Exception:
    legacy_v203_candidate_evidence = {"CE": None, "PE": None, "error": "legacy freshness evidence failed"}

try:
    legacy_v164_decision_evidence = v164_unified_decision_engine(
        ranked=v11_ranked_strategies,
        price_action_bias=price_action_bias,
        option_bias=option_bias,
        heavy_bias=heavy_bias,
        smart_money_bias=smart_money_bias,
        pcr_bias=pcr_bias,
        seller_risk=seller_risk,
        shock_score=shock_score_v7,
        gamma_score=gamma_score_v7,
        news_score=news.get("score", 0),
        data_quality=data_quality,
        conflict_mode=conflict_mode,
        move_guard=v164_move_guard,
    )
    # V22.4 ZERO MALIK: legacy ranker/unified engine is evidence-only.
    # It is not allowed to overwrite final_trade, confidence, or strategy rows.
    v164_unified = dict(legacy_v164_decision_evidence)
    v164_unified["zero_malik_status"] = "EVIDENCE_ONLY_NOT_AUTHORITY"
except Exception as _v164_exc:
    v164_unified = {"final_trade": final_trade, "confidence": confidence, "blockers": [str(_v164_exc)], "reasons": [], "zero_malik_status": "ERROR_EVIDENCE_ONLY"}

# Re-select strike after unified decision.
if final_trade == "SELL PE":
    selected_strike = f"{pe_strike} PE"
    hedge = f"{pe_strike - hedge_gap} PE"
    selected_strike_score = best_pe.get("pe_sell_score", best_pe.get("pe_v164_score", 0)) if best_pe else 0
elif final_trade == "SELL CE":
    selected_strike = f"{ce_strike} CE"
    hedge = f"{ce_strike + hedge_gap} CE"
    selected_strike_score = best_ce.get("ce_sell_score", best_ce.get("ce_v164_score", 0)) if best_ce else 0
elif final_trade == "IRON CONDOR":
    selected_strike = f"CE {ce_strike} + PE {pe_strike}"
    hedge = f"CE {ce_strike + hedge_gap} + PE {pe_strike - hedge_gap}"
    selected_strike_score = int(min((best_ce.get("ce_sell_score", 0) if best_ce else 0), (best_pe.get("pe_sell_score", 0) if best_pe else 0)))
else:
    selected_strike = "No Strike"
    hedge = "No Hedge"
    selected_strike_score = 0

if final_trade == "WAIT":
    suggested_lots = 0
    sl_display = "No Trade"
    target_display = "No Trade"
else:
    risk_multiplier = max(0.0, (100 - seller_risk) / 100)
    confidence_multiplier = confidence / 100
    raw_lots = int(max_lots * risk_multiplier * confidence_multiplier)
    suggested_lots = max(1, min(max_lots, raw_lots)) if max_lots > 0 else 0




# =========================================================
# V12 AI TRADE TICKET ENGINE
# =========================================================



def v12_select_hedge_strike(sell_strike, side, hedge_gap=100):
    try:
        sell_strike = int(sell_strike)
        hedge_gap = int(hedge_gap)
        if side == "CE":
            return sell_strike + hedge_gap
        if side == "PE":
            return sell_strike - hedge_gap
    except Exception:
        pass
    return 0

def v12_sl_target_for_seller(premium, confidence=0, gamma_score=0, shock_score=0):
    premium = v91_safe_num(premium)
    conf = v91_safe_num(confidence)
    gamma = v91_safe_num(gamma_score)
    shock = v91_safe_num(shock_score)
    if premium <= 0:
        return {"sl": 0.0, "target1": 0.0, "target2": 0.0, "trail_after": 0.0}
    # seller SL: premium rises against us
    sl_pct = 0.28
    if gamma >= 70 or shock >= 65:
        sl_pct = 0.18
    elif conf >= 80:
        sl_pct = 0.32
    target1_pct = 0.30
    target2_pct = 0.50
    return {
        "sl": round(premium * (1 + sl_pct), 2),
        "target1": round(max(0.05, premium * (1 - target1_pct)), 2),
        "target2": round(max(0.05, premium * (1 - target2_pct)), 2),
        "trail_after": round(max(0.05, premium * 0.75), 2),
    }


# V19.8 CLEANUP: removed old v12_build_trade_ticket().
# Decision Engine Ticket below is built from final authority output.



# V19.8 CLEANUP:
# Old pre-authority V12 ticket setup removed.
# Ticket UI now reads Decision Engine verdict + validated final strategy.


# =========================================================
# V18.2 AI BRAIN FOUNDATION: ONE FINAL DECISION OBJECT
# =========================================================
# Goal:
# - Stable V17.1 base remains intact.
# - Old layers are treated as signal providers.
# - UI gets one final decision object.
# - No DhanHQ / refresh / option-chain / portfolio change in this version.

def v182_num(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def v182_int(value, default=0):
    try:
        return int(round(v182_num(value, default)))
    except Exception:
        return default


def v182_text(value, default=""):
    try:
        if value is None:
            return default
        value = str(value).strip()
        return value if value else default
    except Exception:
        return default


def v182_clip(value, low=0, high=100):
    return max(low, min(high, v182_num(value, low)))


def v182_build_scores(ctx):
    """Collect existing V17 signals into one score dictionary."""
    option_analysis = ctx.get("option_analysis", {}) if isinstance(ctx.get("option_analysis", {}), dict) else {}
    heavyweight_analysis = ctx.get("heavyweight_analysis", {}) if isinstance(ctx.get("heavyweight_analysis", {}), dict) else {}
    news = ctx.get("news", {}) if isinstance(ctx.get("news", {}), dict) else {}
    data_quality = v182_clip(ctx.get("data_quality", 0), 0, 100)

    scores = {
        "data_quality": int(data_quality),
        "market_bias": int(v182_clip(ctx.get("market_bias", 0), -100, 100)),
        "option_bias": int(v182_clip(option_analysis.get("bias", ctx.get("option_bias", 0)), -100, 100)),
        "price_action_bias": int(v182_clip(ctx.get("price_action_bias", 0), -100, 100)),
        "heavyweight_bias": int(v182_clip(heavyweight_analysis.get("pressure", ctx.get("heavy_bias", 0)), -100, 100)),
        "news_risk": int(v182_clip(news.get("score", ctx.get("news_score", 0)), 0, 100)),
        "seller_risk": int(v182_clip(ctx.get("seller_risk", 100), 0, 100)),
        "gamma_risk": int(v182_clip(ctx.get("gamma_score_v7", 100), 0, 100)),
        "shock_risk": int(v182_clip(ctx.get("shock_score_v7", 100), 0, 100)),
        "confidence_raw": int(v182_clip(ctx.get("confidence", 0), 0, 98)),
    }
    return scores


def v182_material_change_score(ctx, proposed_action):
    """
    Lightweight stability gate.
    It does not block first decision. It only records whether action changed without enough market movement.
    """
    try:
        previous = st.session_state.get("v182_last_final_decision", {})
        if not previous:
            return {"decision_changed": False, "previous_action": "", "material_change_score": 100, "change_reason": "First V18.2 decision."}

        prev_action = previous.get("action", "")
        if prev_action == proposed_action:
            return {"decision_changed": False, "previous_action": prev_action, "material_change_score": 100, "change_reason": "Action unchanged."}

        current_price = v182_num(ctx.get("price", 0), 0)
        previous_price = v182_num(previous.get("nifty_price", current_price), current_price)
        price_move_points = abs(current_price - previous_price)

        scores = v182_build_scores(ctx)
        prev_scores = previous.get("scores", {}) if isinstance(previous.get("scores", {}), dict) else {}
        option_move = abs(scores.get("option_bias", 0) - v182_num(prev_scores.get("option_bias", scores.get("option_bias", 0))))
        heavy_move = abs(scores.get("heavyweight_bias", 0) - v182_num(prev_scores.get("heavyweight_bias", scores.get("heavyweight_bias", 0))))
        news_move = abs(scores.get("news_risk", 0) - v182_num(prev_scores.get("news_risk", scores.get("news_risk", 0))))
        risk_move = abs(scores.get("seller_risk", 0) - v182_num(prev_scores.get("seller_risk", scores.get("seller_risk", 0))))

        material = min(100, price_move_points * 0.8 + option_move * 0.7 + heavy_move * 0.5 + news_move * 0.6 + risk_move * 0.4)
        reason = f"Action changed {prev_action} → {proposed_action}. Material score {material:.0f}/100."
        return {"decision_changed": True, "previous_action": prev_action, "material_change_score": int(round(material)), "change_reason": reason}
    except Exception as exc:
        return {"decision_changed": False, "previous_action": "", "material_change_score": 0, "change_reason": f"Stability check error: {exc}"}


def build_v18_final_decision(ctx):
    """
    V18.2 One Final Decision Object.
    This function does not invent new data. It consolidates current V17 calculations safely.
    """
    scores = v182_build_scores(ctx)

    current_action = v182_text(ctx.get("final_trade"), "WAIT").upper()
    allowed_actions = {"WAIT", "SELL CE", "SELL PE", "IRON CONDOR", "BUY CALL", "BUY PUT", "BUY CALL (HEDGED)", "BUY PUT (HEDGED)", "BUY CALL HEDGED", "BUY PUT HEDGED"}
    if current_action not in allowed_actions:
        current_action = "WAIT"

    selected_strike = ctx.get("selected_strike", "No Strike")
    hedge = ctx.get("hedge", "No Hedge")
    confidence = int(v182_clip(ctx.get("confidence", scores.get("confidence_raw", 0)), 0, 98))
    lots = max(0, v182_int(ctx.get("suggested_lots", 0), 0))
    sl = ctx.get("sl_display", "No Trade")
    target = ctx.get("target_display", "No Trade")

    reasons = []
    warnings = []
    blockers = []

    v164 = ctx.get("v164_unified", {}) if isinstance(ctx.get("v164_unified", {}), dict) else {}
    for item in (v164.get("reasons", []) or []):
        if item and str(item) not in reasons:
            reasons.append(str(item))
    for item in (v164.get("blockers", []) or []):
        if item and str(item) not in blockers:
            blockers.append(str(item))

    conflict_mode = bool(ctx.get("conflict_mode", False))
    if conflict_mode:
        warnings.append("Conflict mode active: major signals not fully aligned.")

    # Hard blockers from Project Bible reliability-first rule.
    if scores["data_quality"] < 60:
        blockers.append(f"Data quality weak: {scores['data_quality']}/100.")
    if scores["seller_risk"] >= 80:
        blockers.append(f"Seller risk high: {scores['seller_risk']}/100.")
    if scores["news_risk"] >= 85:
        blockers.append(f"News/Event risk high: {scores['news_risk']}/100.")
    if scores["gamma_risk"] >= 85:
        blockers.append(f"Gamma risk high: {scores['gamma_risk']}/100.")
    if scores["shock_risk"] >= 90:
        blockers.append(f"Shock risk extreme: {scores['shock_risk']}/100.")
    if conflict_mode and confidence < 82:
        blockers.append("Signal conflict active and confidence below 82%.")

    if current_action != "WAIT":
        if str(selected_strike).strip() in ("", "None", "No Strike", "0"):
            blockers.append("Trade blocked: valid strike missing.")
        if current_action in ("SELL CE", "SELL PE", "IRON CONDOR") and str(hedge).strip() in ("", "None", "No Hedge", "0"):
            blockers.append("Trade blocked: hedge missing for seller strategy.")
        if confidence < 65:
            blockers.append(f"Trade blocked: confidence {confidence}% below 65%.")
        if lots <= 0:
            blockers.append("Trade blocked: suggested lots are zero.")

    # Stability check: if action flips without enough material change, block aggressive flip.
    stability = v182_material_change_score(ctx, current_action)
    if stability.get("decision_changed") and stability.get("material_change_score", 0) < 35 and current_action != "WAIT":
        blockers.append("Decision flip blocked: market change not material enough.")

    if blockers:
        final_action = "WAIT"
        quality = "BLOCKED"
        confidence = min(confidence, 64)
        strategy_type = "WAIT"
        selected_strike = "No Strike"
        hedge = "No Hedge"
        lots = 0
        sl = "No Trade"
        target = "No Trade"
    else:
        final_action = current_action
        quality = "OK" if confidence >= 70 else "CAUTION"
        strategy_type = current_action

    if not reasons:
        if final_action == "WAIT":
            reasons.append("No fresh trade: capital protection and signal clarity priority.")
        else:
            reasons.append("Final action passed V18.2 AI Brain foundation checks.")

    decision = {
        "version": "V19.5.1 Full Audit Fix",
        "timestamp": fmt_time() if "fmt_time" in globals() else "",
        "snapshot_id": str(ctx.get("snapshot_id", ctx.get("oc_snapshot_id", ""))),
        "action": final_action,
        "confidence": int(confidence),
        "quality": quality,
        "strategy": {
            "type": strategy_type,
            "sell_side": "CE" if final_action == "SELL CE" else ("PE" if final_action == "SELL PE" else None),
            "sell_strike": selected_strike,
            "hedge_strike": hedge,
            "entry": ctx.get("entry_display", "As per live premium"),
            "sl": sl,
            "target": target,
            "lots": int(lots),
        },
        "scores": scores,
        "reasons": reasons[:8],
        "blockers": blockers[:10],
        "warnings": warnings[:8],
        "stability": stability,
        "nifty_price": v182_num(ctx.get("price", 0), 0),
    }

    # Store for next refresh stability check.
    try:
        st.session_state["v182_last_final_decision"] = decision
    except Exception:
        pass

    return decision


try:
    final_decision = build_v18_final_decision(locals())
except Exception as _v182_error:
    final_decision = {
        "version": "V19.5.1 Full Audit Fix",
        "timestamp": fmt_time() if "fmt_time" in globals() else "",
        "snapshot_id": "",
        "action": "WAIT",
        "confidence": 0,
        "quality": "ERROR",
        "strategy": {"type": "WAIT", "sell_side": None, "sell_strike": "No Strike", "hedge_strike": "No Hedge", "entry": "No Trade", "sl": "No Trade", "target": "No Trade", "lots": 0},
        "scores": {},
        "reasons": ["V18.2 AI Brain error. WAIT selected for safety."],
        "blockers": [str(_v182_error)],
        "warnings": [],
        "stability": {"decision_changed": False, "change_reason": "AI Brain error.", "previous_action": "", "material_change_score": 0},
        "nifty_price": v182_num(locals().get("price", 0), 0),
    }

# Lock legacy variables after final decision object.
# This prevents lower UI sections from contradicting V18.2.
final_trade = final_decision.get("action", "WAIT")
confidence = float(final_decision.get("confidence", 0))
selected_strike = final_decision.get("strategy", {}).get("sell_strike", "No Strike")
hedge = final_decision.get("strategy", {}).get("hedge_strike", "No Hedge")
suggested_lots = int(final_decision.get("strategy", {}).get("lots", 0) or 0)
sl_display = final_decision.get("strategy", {}).get("sl", "No Trade")
target_display = final_decision.get("strategy", {}).get("target", "No Trade")

try:
    action_plan = []
    if final_decision.get("blockers"):
        action_plan.append("Final action: WAIT. Blockers active.")
        action_plan.extend(final_decision.get("blockers", [])[:4])
    else:
        action_plan.append(f"Final action: {final_trade}.")
        action_plan.extend(final_decision.get("reasons", [])[:4])
except Exception:
    pass




# =========================================================
# V19.8 CLEANUP — OLD V18.3 INTERNAL CONFIDENCE REWRITER REMOVED
# =========================================================
# ai_brain.py is now the only AI evidence/confidence layer.
# decision_engine.py is the only final Decision Confidence authority.

# =========================================================
# V19.7 CLEANUP — OLD V18.5 CONSISTENCY GUARD REMOVED
# =========================================================
# Decision Engine report is now the consistency source of truth.

# =========================================================
# V19.9 CLEANUP — OLD V18.6 INTERNAL SNAPSHOT ENGINE REMOVED
# =========================================================
# snapshot_engine.py is now the only snapshot builder, delta engine,
# and snapshot-health authority.

# =========================================================
# V19.7 CLEANUP — OLD V18.7 MUTATING SNAPSHOT AI REMOVED
# =========================================================
# ai_brain.py now provides snapshot bias/explanation.
# It does not overwrite final action; Decision Engine owns execution verdict.


# =========================================================
# V20.5 SINGLE SNAPSHOT CONTEXT + DATA FLOW MONITOR
# =========================================================
def _v205_build_snapshot_context():
    """Build one explicit context for Snapshot Engine.

    Important: do not pass locals() here. Every top table must use values that
    came from this one context/snapshot chain.
    """
    g = globals()
    return {
        "price": g.get("price", 0),
        "nifty_price": g.get("price", 0),
        "change": g.get("change", 0),
        "change_pct": g.get("change_pct", 0),
        "vix": g.get("vix", 0),
        "india_vix": g.get("vix", 0),
        "vix_change_pct": g.get("vix_change_pct", 0),
        "pcr": g.get("pcr", 0),
        "status": g.get("market_text", ""),
        "market_status_text": g.get("market_text", ""),
        "day_name": g.get("day_name", ""),
        "selected_expiry": g.get("selected_expiry", ""),
        "atm_strike": g.get("atm_strike", ""),
        "option_chain": g.get("option_chain", {}) if isinstance(g.get("option_chain", {}), dict) else {},
        "option_analysis": g.get("option_analysis", {}) if isinstance(g.get("option_analysis", {}), dict) else {},
        "heavyweight_analysis": g.get("heavyweight_analysis", {}) if isinstance(g.get("heavyweight_analysis", {}), dict) else {},
        "news": g.get("news", {}) if isinstance(g.get("news", {}), dict) else {},
        "final_decision": g.get("final_decision", {}) if isinstance(g.get("final_decision", {}), dict) else {},
        "option_bias": g.get("option_bias", 0),
        "price_action_bias": g.get("price_action_bias", 0),
        "heavy_bias": g.get("heavy_bias", 0),
        "market_bias": g.get("market_bias", 0),
        "smart_money_bias": g.get("smart_money_bias", 0),
        "pcr_bias": g.get("pcr_bias", 0),
        "conflict_mode": g.get("conflict_mode", False),
        "data_quality": g.get("data_quality", 0),
        "seller_risk": g.get("seller_risk", 0),
        "news_score": (g.get("news", {}) or {}).get("score", 0) if isinstance(g.get("news", {}), dict) else 0,
        "gamma_score_v7": g.get("gamma_score_v7", 0),
        "shock_score_v7": g.get("shock_score_v7", 0),
        "expiry_mode": g.get("expiry_mode", g.get("mode", "")),
        "mode": g.get("mode", ""),
        "dhan_ready": g.get("dhan_ready", False),
        "nifty_source": g.get("source_text", ""),
        "heavy_source": g.get("heavy_source", ""),
        "vix_source": g.get("vix_source", ""),
        "best_ce": g.get("best_ce", {}) if isinstance(g.get("best_ce", {}), dict) else {},
        "best_pe": g.get("best_pe", {}) if isinstance(g.get("best_pe", {}), dict) else {},
    }


def _v205_data_flow_monitor(snapshot, previous_snapshot=None):
    """Check whether every refresh is using one fresh snapshot.

    This does not change the trade decision. It only warns if data flow looks
    weak/stale/split so AI does not silently trust bad data.
    """
    try:
        oc = snapshot.get("option_chain", {}) if isinstance(snapshot.get("option_chain", {}), dict) else {}
        df = snapshot.get("data_flow", {}) if isinstance(snapshot.get("data_flow", {}), dict) else {}
        sh_label = "UNKNOWN"
        if "snapshot_health_external" in globals() and isinstance(snapshot_health_external, dict):
            sh_label = str(snapshot_health_external.get("label", "UNKNOWN"))
        prev_oc_sig = ""
        prev_sid = ""
        if isinstance(previous_snapshot, dict):
            prev_oc_sig = str(((previous_snapshot.get("option_chain", {}) or {}).get("signature", "")))
            prev_sid = str(previous_snapshot.get("snapshot_id", ""))
        oc_sig = str(oc.get("signature", ""))
        sid = str(snapshot.get("snapshot_id", ""))
        same_oc = bool(prev_oc_sig and oc_sig and prev_oc_sig == oc_sig)
        same_sid = bool(prev_sid and sid and prev_sid == sid)
        repeat_key = "v205_same_oc_repeat_count"
        if same_oc:
            st.session_state[repeat_key] = int(st.session_state.get(repeat_key, 0) or 0) + 1
        else:
            st.session_state[repeat_key] = 0
        repeat_count = int(st.session_state.get(repeat_key, 0) or 0)
        issues = []
        warnings = []
        if not oc.get("success", False):
            issues.append("Option-chain not live")
        if int(oc.get("rows_count", 0) or 0) < 5:
            issues.append("OC rows low")
        if not oc_sig:
            warnings.append("OC signature missing")
        if same_sid:
            warnings.append("Snapshot ID repeated")
        if repeat_count >= 3:
            warnings.append(f"OC unchanged {repeat_count} refresh")
        oi_lock = snapshot.get("oi_single_source", {}) if isinstance(snapshot.get("oi_single_source", {}), dict) else {}
        oi_sync_ok = bool(oi_lock.get("sync_ok", True))
        if not oi_sync_ok:
            issues.append("OI sync mismatch")
            for _m in (oi_lock.get("mismatches", []) or [])[:2]:
                warnings.append(str(_m))
        health_ok = sh_label.upper() in ("HEALTHY", "CAUTION")
        status = "FRESH" if not issues and repeat_count < 3 and health_ok else ("CAUTION" if not issues else "WEAK")
        return {
            "status": status,
            "fresh": status == "FRESH",
            "snapshot_id": sid,
            "short_id": sid[-6:] if sid else "NA",
            "oc_signature": oc_sig,
            "oc_rows": int(oc.get("rows_count", 0) or 0),
            "oc_analysis_rows": int(oc.get("analysis_rows_count", 0) or 0),
            "oc_source_id": str(oc.get("source_snapshot_id", "")),
            "oc_time": str(oc.get("fetched_at", "") or df.get("refresh_time", "")),
            "repeat_count": repeat_count,
            "snapshot_health": sh_label,
            "oi_sync": "OK" if oi_sync_ok else "MISMATCH",
            "oi_source": str(oi_lock.get("source", "NA")) if oi_lock else "NA",
            "issues": issues[:4],
            "warnings": warnings[:4],
            "line": f"Data Flow: {status} | SNAP {sid[-6:] if sid else 'NA'} | OC rows {int(oc.get('rows_count',0) or 0)} | OI {'OK' if oi_sync_ok else 'MISMATCH'} | OC same {repeat_count}x | Brain Sync OK",
        }
    except Exception as e:
        return {"status": "WEAK", "fresh": False, "snapshot_id": "", "short_id": "NA", "oc_rows": 0, "repeat_count": 0, "issues": [str(e)], "warnings": [], "line": "Data Flow: WEAK | monitor error"}


# =========================================================
# V19.9 SNAPSHOT ENGINE — SINGLE AUTHORITY
# =========================================================
# No internal snapshot fallback remains.
# Fail closed if the required snapshot module is missing.
if not V19_SNAPSHOT_ENGINE_READY:
    st.error(
        "V19.9 requires snapshot_engine.py. "
        "Snapshot authority module is missing or failed to import."
    )
    st.stop()

try:
    _previous_snapshot_v199 = st.session_state.get(
        "v199_last_market_snapshot",
        {},
    )

    _v205_snapshot_context = _v205_build_snapshot_context()

    market_snapshot = v19_build_market_snapshot(
        _v205_snapshot_context,
        fmt_time,
    )

    snapshot_delta = v19_snapshot_delta(
        market_snapshot,
        _previous_snapshot_v199,
    )

    snapshot_health_external = v19_snapshot_health(
        market_snapshot,
    )

    v205_data_flow = _v205_data_flow_monitor(
        market_snapshot,
        _previous_snapshot_v199,
    )
    market_snapshot["data_flow_monitor"] = v205_data_flow

    st.session_state["v199_last_market_snapshot"] = market_snapshot
    st.session_state["v205_active_snapshot_id"] = market_snapshot.get("snapshot_id", "")

    # Compatibility aliases for existing Developer/UI panels.
    market_snapshot_external = market_snapshot
    snapshot_delta_external = snapshot_delta

    if isinstance(final_decision, dict):
        final_decision["external_snapshot_engine"] = "READY"
        final_decision["snapshot_health"] = snapshot_health_external
        final_decision["snapshot_health_external"] = snapshot_health_external
        final_decision["single_snapshot_id"] = market_snapshot.get("snapshot_id", "")
        final_decision["data_flow_monitor"] = v205_data_flow
        final_decision["oi_single_source_lock"] = market_snapshot.get("oi_single_source", {})

except Exception as _v199_snapshot_error:
    st.error(
        "Snapshot Engine authority failed: "
        + str(_v199_snapshot_error)
    )
    st.stop()


# =========================================================
# V19.4 AI BRAIN MODULE BRIDGE
# =========================================================
# External ai_brain creates explainability and scorecard.
try:
    if V19_AI_BRAIN_READY:
        ai_brain_report = v19_build_ai_explanation(market_snapshot, final_decision)
        if isinstance(final_decision, dict):
            final_decision["ai_brain_module"] = "READY"
            final_decision["ai_explanation"] = ai_brain_report
            # Do not overwrite final action here; V19.4 is explainability-first.
            # Use confidence only for display/reporting, not trade execution.
    else:
        ai_brain_report = {}
except Exception as _v194_error:
    ai_brain_report = {"error": str(_v194_error)}
    try:
        if isinstance(final_decision, dict):
            final_decision.setdefault("warnings", []).append(f"V19.4 AI Brain module error: {_v194_error}")
    except Exception:
        pass




# =========================================================
# V19.5 RISK ENGINE MODULE BRIDGE
# =========================================================
# External risk_engine produces one explainable risk authority report.
# In this release it does NOT choose direction and does NOT overwrite final action.
try:
    if V19_RISK_ENGINE_READY:
        _health_for_risk = {}
        if isinstance(final_decision, dict):
            _health_for_risk = final_decision.get("snapshot_health", {}) or final_decision.get("snapshot_health_external", {}) or {}
        if not _health_for_risk and "snapshot_health_external" in globals():
            _health_for_risk = snapshot_health_external

        risk_engine_report = v19_build_risk_report(
            market_snapshot,
            snapshot_health=_health_for_risk,
            snapshot_delta=snapshot_delta,
            ai_report=ai_brain_report if "ai_brain_report" in globals() else {},
        )

        if isinstance(final_decision, dict):
            final_decision["risk_engine_module"] = "READY"
            final_decision["risk_report"] = risk_engine_report
            # V19.5 migration rule:
            # Risk Engine is report authority, not final decision authority yet.
            # Direction/action remains unchanged until V19.6 Decision Engine.
    else:
        risk_engine_report = {}
except Exception as _v195_error:
    risk_engine_report = {"error": str(_v195_error)}
    try:
        if isinstance(final_decision, dict):
            final_decision.setdefault("warnings", []).append(f"V19.5 Risk Engine error: {_v195_error}")
    except Exception:
        pass





# =========================================================
# V22.3 PROFESSIONAL CANDIDATE AUTHORITY
# =========================================================
# Golden Rule 22 + Rule 23:
# Candidate selection is NOT a separate brain. It is a professional-style
# filter that runs only after AI/Decision has selected an allowed strategy.
# Output is passed into Strategy Engine and then AI_MASTER. UI must not read
# this as independent advice.
def _v223_to_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace("₹", "").replace(",", "").replace("%", "").strip()
            token = ""
            started = False
            for ch in cleaned:
                if ch.isdigit() or ch in ".-+":
                    token += ch
                    started = True
                elif started:
                    break
            return float(token) if token else default
        return float(value)
    except Exception:
        return default


def _v223_to_int(value, default=0):
    try:
        return int(round(_v223_to_float(value, default)))
    except Exception:
        return default


def _v223_professional_score_row(side, row, spot, nearest_support_value=None, nearest_resistance_value=None, vix_value=0):
    """Professional option-seller candidate score.

    This is not final advice. It answers only: "If AI_MASTER has already
    approved this side, which strike is professionally cleaner?"
    """
    side = str(side or "").upper()
    if side not in ("CE", "PE") or not isinstance(row, dict):
        return None

    prefix = side.lower()
    strike = _v223_to_float(row.get("strike", 0), 0)
    spot = _v223_to_float(spot, 0)
    premium = _v223_to_float(row.get(f"{prefix}_ltp", 0), 0)
    delta_abs = abs(_v223_to_float(row.get(f"{prefix}_delta", 0), 0))
    spread_pct = _v223_to_float(row.get(f"{prefix}_spread_pct", 99), 99)
    volume_ratio = _v223_to_float(row.get(f"{prefix}_volume_ratio", 0), 0)
    oi_change_pct = _v223_to_float(row.get(f"{prefix}_oi_change_pct", 0), 0)
    iv = _v223_to_float(row.get(f"{prefix}_iv", 0), 0)
    signal = str(row.get(f"{prefix}_signal", "") or "")
    score = 0.0
    reasons = []

    if strike <= 0 or spot <= 0 or premium <= 0:
        return None

    is_otm = strike >= spot if side == "CE" else strike <= spot
    if not is_otm:
        return None
    score += 10

    # 1) Professional location: sell call above resistance, sell put below support.
    ns = _v223_to_float(nearest_support_value, 0)
    nr = _v223_to_float(nearest_resistance_value, 0)
    if side == "CE":
        distance = strike - spot
        if nr > 0 and strike >= nr:
            score += 15; reasons.append("above resistance")
        elif nr > 0 and strike < nr:
            score -= 12; reasons.append("below resistance")
    else:
        distance = spot - strike
        if ns > 0 and strike <= ns:
            score += 15; reasons.append("below support")
        elif ns > 0 and strike > ns:
            score -= 12; reasons.append("above support")

    # 2) Distance from spot: avoid too near / too far.
    if 40 <= distance <= 350:
        score += 12; reasons.append("clean OTM distance")
    elif 20 <= distance < 40:
        score += 2; reasons.append("near spot risk")
    elif distance > 350:
        score += 4; reasons.append("far OTM")
    else:
        score -= 15; reasons.append("too close")

    # 3) Premium: enough reward, not excessive risk.
    if 30 <= premium <= 150:
        score += 18; reasons.append("seller premium zone")
    elif 15 <= premium < 30 or 150 < premium <= 220:
        score += 8; reasons.append("acceptable premium")
    else:
        score -= 10; reasons.append("premium not ideal")

    # 4) Delta: seller-friendly probability zone.
    if 0.15 <= delta_abs <= 0.30:
        score += 18; reasons.append("seller delta")
    elif 0.10 <= delta_abs < 0.15 or 0.30 < delta_abs <= 0.38:
        score += 8; reasons.append("acceptable delta")
    elif delta_abs >= 0.45:
        score -= 22; reasons.append("high delta risk")

    # 5) OI/writing and flow quality.
    if "Writing" in signal:
        score += 18; reasons.append("fresh writing")
    elif "Short Covering" in signal or "Buying" in signal:
        score -= 18; reasons.append("flow risk")
    if oi_change_pct > 0:
        score += min(10, oi_change_pct * 0.35)

    # 6) Liquidity / spread.
    if 0 < spread_pct <= 0.6:
        score += 12; reasons.append("tight spread")
    elif 0.6 < spread_pct <= 1.2:
        score += 6; reasons.append("ok spread")
    elif spread_pct > 2.0:
        score -= 16; reasons.append("wide spread")
    if volume_ratio >= 1.5:
        score += 8; reasons.append("good volume")
    elif volume_ratio >= 0.75:
        score += 4

    # 7) Volatility sanity check.
    vix_value = _v223_to_float(vix_value, 0)
    if 8 <= iv <= 28:
        score += 5
    elif iv > 38:
        score -= 6; reasons.append("high IV risk")
    if vix_value >= 18 and distance < 80:
        score -= 8; reasons.append("high VIX near strike")

    row2 = dict(row)
    row2[f"{prefix}_professional_score"] = int(round(max(0, min(100, score))))
    row2[f"{prefix}_professional_reason"] = ", ".join(reasons[:5])
    row2["candidate_source"] = "V22.3_PROFESSIONAL_CANDIDATE_AUTHORITY"
    return row2


def _v223_select_professional_candidate(side, option_analysis_obj, spot, nearest_support_value=None, nearest_resistance_value=None, vix_value=0):
    rows = option_analysis_obj.get("rows", []) if isinstance(option_analysis_obj, dict) else []
    scored = []
    for rr in rows:
        scored_row = _v223_professional_score_row(side, rr, spot, nearest_support_value, nearest_resistance_value, vix_value)
        if scored_row:
            prefix = str(side).lower()
            score = _v223_to_float(scored_row.get(f"{prefix}_professional_score", 0), 0)
            if score >= 45:
                scored.append(scored_row)
    if not scored:
        return None
    prefix = str(side).lower()
    return max(scored, key=lambda r: _v223_to_float(r.get(f"{prefix}_professional_score", 0), 0))


def _v223_professional_candidate_authority(action, option_analysis_obj, spot, nearest_support_value=None, nearest_resistance_value=None, vix_value=0):
    """Run candidate selection in professional order.

    1. Trade/strategy must be decided first by AI/Decision.
    2. Candidate is selected only for the approved side(s).
    3. WAIT means no active candidate.
    """
    action = str(action or "WAIT").upper()
    result = {
        "version": "V22.3_PROFESSIONAL_CANDIDATE_AUTHORITY",
        "action": action,
        "ce": None,
        "pe": None,
        "status": "LOCKED_WAIT",
        "rule": "Strategy first, candidate second",
    }
    if not isinstance(option_analysis_obj, dict) or not option_analysis_obj.get("success"):
        result["status"] = "NO_OPTION_DATA"
        return result
    if action == "SELL CE":
        result["ce"] = _v223_select_professional_candidate("CE", option_analysis_obj, spot, nearest_support_value, nearest_resistance_value, vix_value)
        result["status"] = "CE_APPROVED" if result["ce"] else "CE_NO_CLEAN_CANDIDATE"
    elif action == "SELL PE":
        result["pe"] = _v223_select_professional_candidate("PE", option_analysis_obj, spot, nearest_support_value, nearest_resistance_value, vix_value)
        result["status"] = "PE_APPROVED" if result["pe"] else "PE_NO_CLEAN_CANDIDATE"
    elif action == "IRON CONDOR":
        result["ce"] = _v223_select_professional_candidate("CE", option_analysis_obj, spot, nearest_support_value, nearest_resistance_value, vix_value)
        result["pe"] = _v223_select_professional_candidate("PE", option_analysis_obj, spot, nearest_support_value, nearest_resistance_value, vix_value)
        result["status"] = "CONDOR_APPROVED" if result["ce"] and result["pe"] else "CONDOR_INCOMPLETE"
    return result


# =========================================================
# V19.10 STRATEGY ENGINE — SINGLE FINAL PLAN AUTHORITY
# =========================================================
try:
    _market_text_v1951, _market_day_v1951 = market_status()
    _market_open_v1951 = (_market_text_v1951 == "Market Open")
except Exception:
    _market_text_v1951, _market_day_v1951, _market_open_v1951 = (
        "Unknown",
        "",
        False,
    )

if not V19_STRATEGY_ENGINE_READY:
    st.error(
        "V19.10 requires strategy_engine.py. "
        "Final strategy-plan authority is missing or failed to import."
    )
    st.stop()

try:
    _strategy_seed_v1910 = (
        final_decision.get("strategy", {})
        if isinstance(final_decision, dict)
        and isinstance(final_decision.get("strategy", {}), dict)
        else {}
    )

    _strategy_action_v1910 = (
        str(final_decision.get("action", "WAIT")).upper()
        if isinstance(final_decision, dict)
        else "WAIT"
    )

    _strategy_conf_v1910 = (
        float(final_decision.get("confidence", confidence) or 0)
        if isinstance(final_decision, dict)
        else float(confidence or 0)
    )

    # V22.3: Professional Candidate Authority.
    # Candidate is selected only after the AI/Decision action is known.
    # Old best_ce/best_pe remain raw evidence and do not directly drive strategy.
    professional_candidate_report_v223 = _v223_professional_candidate_authority(
        _strategy_action_v1910,
        option_analysis if isinstance(option_analysis, dict) else {},
        price,
        nearest_support if "nearest_support" in globals() else None,
        nearest_resistance if "nearest_resistance" in globals() else None,
        vix if "vix" in globals() else 0,
    )
    professional_best_ce_v223 = professional_candidate_report_v223.get("ce") if isinstance(professional_candidate_report_v223, dict) else None
    professional_best_pe_v223 = professional_candidate_report_v223.get("pe") if isinstance(professional_candidate_report_v223, dict) else None

    strategy_engine_report = v19_build_strategy_plan(
        action=_strategy_action_v1910,
        best_ce=professional_best_ce_v223 if isinstance(professional_best_ce_v223, dict) else None,
        best_pe=professional_best_pe_v223 if isinstance(professional_best_pe_v223, dict) else None,
        hedge_gap=hedge_gap,
        confidence=_strategy_conf_v1910,
        gamma_score=gamma_score_v7,
        shock_score=shock_score_v7,
        base_lots=(
            int(_strategy_seed_v1910.get("lots", suggested_lots) or 0)
        ),
        existing_strategy=_strategy_seed_v1910,
        market_open=bool(_market_open_v1951),
        market_status=_market_text_v1951,
    )

    if isinstance(final_decision, dict):
        final_decision["strategy_engine_module"] = "READY"
        final_decision["strategy_engine_report"] = strategy_engine_report
        final_decision["professional_candidate_authority"] = professional_candidate_report_v223

        final_decision["strategy"] = {
            "type": strategy_engine_report.get(
                "action",
                _strategy_action_v1910,
            ),
            "sell_side": strategy_engine_report.get("side"),
            "sell_strike": strategy_engine_report.get(
                "sell_strike",
                "No Strike",
            ),
            "hedge_strike": strategy_engine_report.get(
                "hedge_strike",
                "No Hedge",
            ),
            "entry": strategy_engine_report.get(
                "entry",
                "No Trade",
            ),
            "sl": strategy_engine_report.get(
                "sl",
                "No Trade",
            ),
            "target": strategy_engine_report.get(
                "target",
                "No Trade",
            ),
            "target2": strategy_engine_report.get(
                "target2",
                "No Trade",
            ),
            "trail_after": strategy_engine_report.get(
                "trail_after",
                "No Trade",
            ),
            "lots": int(
                strategy_engine_report.get("lots", 0) or 0
            ),
            "plan_status": strategy_engine_report.get(
                "status",
                "INCOMPLETE",
            ),
            "plan_source": strategy_engine_report.get(
                "source",
                "UNKNOWN",
            ),
        }

        # Re-sync compatibility variables from one strategy authority.
        final_trade = final_decision.get("action", "WAIT")
        confidence = float(final_decision.get("confidence", 0) or 0)
        selected_strike = final_decision["strategy"].get(
            "sell_strike",
            "No Strike",
        )
        hedge = final_decision["strategy"].get(
            "hedge_strike",
            "No Hedge",
        )
        suggested_lots = int(
            final_decision["strategy"].get("lots", 0) or 0
        )
        sl_display = final_decision["strategy"].get(
            "sl",
            "No Trade",
        )
        target_display = final_decision["strategy"].get(
            "target",
            "No Trade",
        )

except Exception as _v1910_strategy_error:
    st.error(
        "Strategy Engine authority failed: "
        + str(_v1910_strategy_error)
    )
    st.stop()


# =========================================================
# V19.6 DECISION ENGINE — ONE FINAL AUTHORITY
# =========================================================
try:
    _legacy_action_v196 = str(final_decision.get("action", "WAIT")) if isinstance(final_decision, dict) else "WAIT"
    _legacy_conf_v196 = float(final_decision.get("confidence", 0) or 0) if isinstance(final_decision, dict) else 0.0

    _snapshot_health_v196 = {}
    if "snapshot_health_external" in globals() and isinstance(snapshot_health_external, dict):
        _snapshot_health_v196 = snapshot_health_external
    if not _snapshot_health_v196 and isinstance(final_decision, dict):
        _snapshot_health_v196 = (
            final_decision.get("snapshot_health_external", {})
            or final_decision.get("snapshot_health", {})
            or {}
        )

    if V19_DECISION_ENGINE_READY:
        decision_engine_report = v19_build_final_decision(
            legacy_decision=final_decision,
            snapshot=market_snapshot,
            ai_report=ai_brain_report if isinstance(ai_brain_report, dict) else {},
            risk_report=risk_engine_report if isinstance(risk_engine_report, dict) else {},
            snapshot_health=_snapshot_health_v196,
            snapshot_delta=snapshot_delta if isinstance(snapshot_delta, dict) else {},
            market_open=bool(_market_open_v1951),
            market_status=_market_text_v1951,
            freeze_state=v14_freeze if isinstance(v14_freeze, dict) else {},
        )

        if isinstance(final_decision, dict):
            final_decision["legacy_action"] = _legacy_action_v196
            final_decision["legacy_confidence"] = _legacy_conf_v196
            final_decision["analysis_action"] = decision_engine_report.get("analysis_action", _legacy_action_v196)
            final_decision["decision_engine"] = decision_engine_report
            final_decision["action"] = decision_engine_report.get("final_action", "WAIT")
            final_decision["confidence"] = decision_engine_report.get("calibrated_confidence", 0)
            final_decision["execution_status"] = decision_engine_report.get("execution_status", "WAIT")

            _st_v196 = final_decision.get("strategy", {}) if isinstance(final_decision.get("strategy", {}), dict) else {}
            _st_v196["execution_lots"] = int(decision_engine_report.get("approved_lots", 0) or 0)
            _st_v196["preview_lots"] = int(decision_engine_report.get("preview_lots", 0) or 0)
            final_decision["strategy"] = _st_v196

            _status_v196 = decision_engine_report.get("execution_status", "WAIT")
            final_decision["quality"] = {
                "APPROVED": "OK",
                "BLOCKED": "BLOCKED",
                "PREVIEW_ONLY": "PREVIEW",
                "WAIT": "WAIT",
            }.get(_status_v196, "WAIT")

            # Re-sync downstream UI to one authority.
            final_trade = final_decision.get("action", "WAIT")
            confidence = float(final_decision.get("confidence", 0) or 0)
            selected_strike = final_decision.get("strategy", {}).get("sell_strike", "No Strike")
            hedge = final_decision.get("strategy", {}).get("hedge_strike", "No Hedge")
            suggested_lots = int(decision_engine_report.get("approved_lots", 0) or 0)
            sl_display = final_decision.get("strategy", {}).get("sl", "No Trade")
            target_display = final_decision.get("strategy", {}).get("target", "No Trade")
    else:
        decision_engine_report = {}
except Exception as _v196_error:
    decision_engine_report = {"error": str(_v196_error)}
    try:
        if isinstance(final_decision, dict):
            final_decision.setdefault("warnings", []).append(f"V19.6 Decision Engine error: {_v196_error}")
    except Exception:
        pass



# =========================================================
# V19.11 INTELLIGENCE ENGINE — HUMAN EXPLANATION LAYER
# =========================================================
# Decision Engine remains final execution authority.
# Intelligence Engine explains quality, conflict, trap risk and reasoning.
if not V19_INTELLIGENCE_ENGINE_READY:
    st.error(
        "V19.11 requires intelligence_engine.py. "
        "AI intelligence/explanation module is missing or failed to import."
    )
    st.stop()

try:
    intelligence_report = v19_build_intelligence_report(
        snapshot=market_snapshot,
        ai_report=ai_brain_report if isinstance(ai_brain_report, dict) else {},
        risk_report=risk_engine_report if isinstance(risk_engine_report, dict) else {},
        strategy_report=strategy_engine_report if isinstance(strategy_engine_report, dict) else {},
        decision_report=decision_engine_report if isinstance(decision_engine_report, dict) else {},
    )

    if isinstance(final_decision, dict):
        final_decision["intelligence_engine_module"] = "READY"
        final_decision["intelligence_report"] = intelligence_report

except Exception as _v1911_intelligence_error:
    st.error(
        "Intelligence Engine failed: "
        + str(_v1911_intelligence_error)
    )
    st.stop()




# =========================================================
# V19.12 STABILITY ENGINE — PREVENT REFRESH JUMPS
# =========================================================
# Runs after Decision Engine + Intelligence Engine.
# It prevents SELL CE/PE or strike jumps from changing on one weak refresh.
if not V19_STABILITY_ENGINE_READY:
    st.error(
        "V19.12 requires stability_engine.py. "
        "Decision stability module is missing or failed to import."
    )
    st.stop()

try:
    _previous_stable_v1912 = st.session_state.get("v1912_stable_decision_lock", {})

    _material_change_v1912 = 0
    if isinstance(snapshot_delta, dict):
        _material_change_v1912 = int(snapshot_delta.get("material_change", 0) or 0)

    stability_result = v19_apply_stability_lock(
        current_decision=decision_engine_report if isinstance(decision_engine_report, dict) else {},
        previous_locked=_previous_stable_v1912,
        material_change=_material_change_v1912,
        risk_report=risk_engine_report if isinstance(risk_engine_report, dict) else {},
        intelligence_report=intelligence_report if isinstance(intelligence_report, dict) else {},
        max_strike_jump=100,
        min_change_for_new_strike=45,
        min_change_for_direction_flip=65,
    )

    stable_decision_report = stability_result.get("decision", decision_engine_report)
    stability_report = stability_result.get("stability", {})
    st.session_state["v1912_stable_decision_lock"] = stability_result.get("lock_state", {})

    decision_engine_report = stable_decision_report

    if isinstance(final_decision, dict):
        final_decision["decision_engine"] = decision_engine_report
        final_decision["stability_engine_module"] = "READY"
        final_decision["stability_report"] = stability_report

        final_decision["analysis_action"] = decision_engine_report.get("analysis_action", "WAIT")
        final_decision["action"] = decision_engine_report.get("final_action", "WAIT")
        final_decision["confidence"] = decision_engine_report.get("calibrated_confidence", 0)
        final_decision["execution_status"] = decision_engine_report.get("execution_status", "WAIT")

        _status_v1912 = decision_engine_report.get("execution_status", "WAIT")
        final_decision["quality"] = {
            "APPROVED": "OK",
            "BLOCKED": "BLOCKED",
            "PREVIEW_ONLY": "PREVIEW",
            "WAIT": "WAIT",
        }.get(_status_v1912, "WAIT")

        final_trade = final_decision.get("action", "WAIT")
        confidence = float(final_decision.get("confidence", 0) or 0)
        suggested_lots = int(decision_engine_report.get("approved_lots", 0) or 0)

except Exception as _v1912_stability_error:
    st.error("Stability Engine failed: " + str(_v1912_stability_error))
    st.stop()




# =========================================================
# V19.13 MEMORY ENGINE — SHORT TERM MARKET MEMORY
# =========================================================
# Stores recent snapshots/decisions in session_state.
# It tracks stability over time; no disk write and no broker action.
if not V19_MEMORY_ENGINE_READY:
    st.error(
        "V19.13 requires memory_engine.py. "
        "Market memory module is missing or failed to import."
    )
    st.stop()

try:
    _memory_history_v1913 = st.session_state.get("v1913_market_memory", [])

    _memory_history_v1913, memory_report = v19_update_memory(
        _memory_history_v1913,
        snapshot=market_snapshot,
        decision_report=decision_engine_report if isinstance(decision_engine_report, dict) else {},
        intelligence_report=intelligence_report if isinstance(intelligence_report, dict) else {},
        stability_report=stability_report if isinstance(stability_report, dict) else {},
        strategy_report=strategy_engine_report if isinstance(strategy_engine_report, dict) else {},
        max_items=20,
    )

    st.session_state["v1913_market_memory"] = _memory_history_v1913

    if isinstance(final_decision, dict):
        final_decision["memory_engine_module"] = "READY"
        final_decision["memory_report"] = memory_report

except Exception as _v1913_memory_error:
    st.error(
        "Memory Engine failed: "
        + str(_v1913_memory_error)
    )
    st.stop()




# =========================================================
# V19.14 OI FLOW ENGINE — WRITING / UNWINDING / MIGRATION
# =========================================================
# Tracks OI movement across refreshes using session_state.
# It is evidence for AI; Decision Engine remains final authority.
if not V19_OI_FLOW_ENGINE_READY:
    st.error(
        "V19.14 requires oi_flow_engine.py. "
        "OI Flow module is missing or failed to import."
    )
    st.stop()

try:
    _oi_flow_state_v1914 = st.session_state.get("v1914_oi_flow_state", {})

    _oi_flow_state_v1914, oi_flow_report = v19_update_oi_flow(
        _oi_flow_state_v1914,
        option_chain if isinstance(option_chain, dict) else {},
        timestamp=fmt_time(),
        max_history=20,
    )

    st.session_state["v1914_oi_flow_state"] = _oi_flow_state_v1914

    if isinstance(final_decision, dict):
        final_decision["oi_flow_engine_module"] = "READY"
        final_decision["oi_flow_report"] = oi_flow_report

except Exception as _v1914_oi_error:
    st.error("OI Flow Engine failed: " + str(_v1914_oi_error))
    st.stop()




# =========================================================
# V21.4 SINGLE ADVISOR AUTHORITY — ONE ADVICE FOR ALL UI
# =========================================================
# This is a display authority only. It does not create a separate signal.
# It reads the stabilized Decision Engine output and gives one common
# advice object to AI Final, Signal Table, Strategy Matrix and Candidates.
if not V21_ADVISOR_ENGINE_READY:
    st.error(
        "V21.4 requires advisor_engine.py. "
        "Single Advisor Authority module is missing or failed to import."
    )
    st.stop()

try:
    advisor_report = v214_build_advisor_report(
        snapshot=market_snapshot if isinstance(market_snapshot, dict) else {},
        final_decision=final_decision if isinstance(final_decision, dict) else {},
        decision_report=decision_engine_report if isinstance(decision_engine_report, dict) else {},
        strategy_report=strategy_engine_report if isinstance(strategy_engine_report, dict) else {},
        intelligence_report=intelligence_report if isinstance(intelligence_report, dict) else {},
        risk_report=risk_engine_report if isinstance(risk_engine_report, dict) else {},
        stability_report=stability_report if isinstance(stability_report, dict) else {},
    )

    if isinstance(final_decision, dict):
        final_decision["advisor_engine_module"] = "READY"
        final_decision["advisor_report"] = advisor_report
        # Re-sync visible compatibility variables from the single advisor.
        final_trade = advisor_report.get("final_action", "WAIT")
        confidence = float(advisor_report.get("confidence", 0) or 0)
        _advisor_strategy_v214 = advisor_report.get("strategy", {}) if isinstance(advisor_report.get("strategy", {}), dict) else {}
        selected_strike = _advisor_strategy_v214.get("sell_strike", selected_strike)
        hedge = _advisor_strategy_v214.get("hedge_strike", hedge)
        sl_display = _advisor_strategy_v214.get("sl", sl_display)
        target_display = _advisor_strategy_v214.get("target", target_display)

except Exception as _v214_advisor_error:
    st.error("Single Advisor Authority failed: " + str(_v214_advisor_error))
    st.stop()



# =========================================================
# V22.1 AI_MASTER SINGLE ROUTING AUTHORITY
# =========================================================
# Golden Rule 22:
# One Snapshot -> One AI Brain/Decision -> One AI_MASTER -> UI.
# The first visible matrices must read AI_MASTER only. They must not create
# their own final advice, ranking authority or stale fallback decision.
def _v221_num(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace("₹", "").replace(",", "").replace("%", "").strip()
            token = ""
            started = False
            for ch in cleaned:
                if ch.isdigit() or ch in ".-+":
                    token += ch
                    started = True
                elif started:
                    break
            return float(token) if token else default
        return float(value)
    except Exception:
        return default


def _v221_int(value, default=0):
    try:
        return int(round(_v221_num(value, default)))
    except Exception:
        return default


def _v221_signed(value):
    return max(-100.0, min(100.0, _v221_num(value, 0.0)))


def _v221_current_option_row(option_analysis_obj, strike_value):
    try:
        strike_value = int(float(strike_value or 0))
        rows = option_analysis_obj.get("rows", []) if isinstance(option_analysis_obj, dict) else []
        for rr in rows:
            if int(rr.get("strike", 0) or 0) == strike_value:
                return rr
    except Exception:
        pass
    return None


def _v221_side_plan(side, row, confidence_value):
    side = str(side or "").upper()
    if not isinstance(row, dict) or side not in ("CE", "PE"):
        return {"strike": "-", "hedge": "-", "entry": 0.0, "sl": 0.0, "target": 0.0, "target2": 0.0}
    prefix = side.lower()
    strike = _v221_int(row.get("strike", 0), 0)
    # Always re-read premium from current option_analysis row if available.
    live_row = _v221_current_option_row(option_analysis if isinstance(option_analysis, dict) else {}, strike) or row
    premium = _v221_num(live_row.get(f"{prefix}_ltp", row.get(f"{prefix}_ltp", 0)), 0.0)
    try:
        plan = v12_sl_target_for_seller(premium, confidence_value, gamma_score_v7, shock_score_v7) if premium > 0 else {}
    except Exception:
        plan = {}
    try:
        hedge_strike = v12_select_hedge_strike(strike, side, hedge_gap) if strike else 0
    except Exception:
        hedge_strike = 0
    return {
        "strike": f"{strike} {side}" if strike else "-",
        "hedge": f"{hedge_strike} {side}" if hedge_strike else "-",
        "entry": round(premium, 2) if premium else 0.0,
        "sl": round(_v221_num(plan.get("sl", 0), 0), 2),
        "target": round(_v221_num(plan.get("target1", 0), 0), 2),
        "target2": round(_v221_num(plan.get("target2", 0), 0), 2),
    }


def _v221_build_projection(snapshot_obj):
    ms = snapshot_obj if isinstance(snapshot_obj, dict) else {}
    sig = ms.get("signals", {}) if isinstance(ms.get("signals", {}), dict) else {}
    risk = ms.get("risk", {}) if isinstance(ms.get("risk", {}), dict) else {}
    market = ms.get("market", {}) if isinstance(ms.get("market", {}), dict) else {}
    pa = _v221_signed(sig.get("price_action_bias", 0))
    ob = _v221_signed(sig.get("option_bias", 0))
    hw = _v221_signed(sig.get("heavyweight_bias", 0))
    sm = _v221_signed(sig.get("smart_money_bias", 0))
    pcrb = _v221_signed(sig.get("pcr_bias", 0))
    news_score_local = _v221_num(risk.get("news_risk", 0), 0)
    vix_val = _v221_num(market.get("india_vix", vix if "vix" in globals() else 0), 0)
    raw = (pa * 0.30) + (ob * 0.25) + (hw * 0.15) + (sm * 0.08) + (pcrb * 0.03)
    risk_penalty = max(0.0, news_score_local - 45.0) * 0.08 + max(0.0, vix_val - 16.0) * 0.8
    raw = max(-100.0, min(100.0, raw))
    bullish = int(round(max(0, min(100, 50 + raw / 2 - risk_penalty / 2))))
    bearish = int(round(max(0, min(100, 100 - bullish))))
    direction = "UP" if bullish > bearish else "DOWN" if bearish > bullish else "RANGE"
    return {"raw": raw, "bullish": bullish, "bearish": bearish, "direction": direction, "probability": max(bullish, bearish)}


def _v221_build_evidence_rows(snapshot_obj, intelligence_obj):
    rows = []
    if isinstance(intelligence_obj, dict):
        src_rows = intelligence_obj.get("reliability_rows", []) or []
        if isinstance(src_rows, list):
            for r in src_rows:
                if isinstance(r, dict):
                    rr = dict(r)
                    rr.setdefault("Source", "AI_MASTER")
                    rows.append(rr)
    if not rows and isinstance(snapshot_obj, dict):
        sig = snapshot_obj.get("signals", {}) if isinstance(snapshot_obj.get("signals", {}), dict) else {}
        rows = [
            {"Signal": "Price Action", "Bias": round(_v221_signed(sig.get("price_action_bias", 0)), 1), "Status": "AI_MASTER"},
            {"Signal": "Option Chain / OI", "Bias": round(_v221_signed(sig.get("option_bias", 0)), 1), "Status": "AI_MASTER"},
            {"Signal": "Heavyweights", "Bias": round(_v221_signed(sig.get("heavyweight_bias", 0)), 1), "Status": "AI_MASTER"},
            {"Signal": "FII/DII", "Bias": round(_v221_signed(sig.get("smart_money_bias", 0)), 1), "Status": "AI_MASTER"},
            {"Signal": "PCR", "Bias": round(_v221_signed(sig.get("pcr_bias", 0)), 1), "Status": "AI_MASTER"},
            {"Signal": "Market Bias", "Bias": round(_v221_signed(sig.get("market_bias", 0)), 1), "Status": "AI_MASTER"},
        ]
    try:
        oi_lock = snapshot_obj.get("oi_single_source", {}) if isinstance(snapshot_obj, dict) else {}
        if oi_lock:
            rows.append({
                "Signal": "OI Sync",
                "Bias": "OK" if oi_lock.get("sync_ok", True) else "MISMATCH",
                "Status": str(oi_lock.get("source", "AI_MASTER")),
            })
    except Exception:
        pass
    return rows


def _v221_strategy_rows(master):
    action = str(master.get("final_action", "WAIT") or "WAIT").upper()
    status = str(master.get("execution_status", "WAIT") or "WAIT").upper()
    conf = _v221_int(master.get("confidence", 0), 0)
    strategy = master.get("strategy", {}) if isinstance(master.get("strategy", {}), dict) else {}
    ce_plan = master.get("ce_plan", {}) if isinstance(master.get("ce_plan", {}), dict) else {}
    pe_plan = master.get("pe_plan", {}) if isinstance(master.get("pe_plan", {}), dict) else {}

    def selected_score(name):
        name = str(name).upper()
        if action == name and status in ("APPROVED", "PREVIEW_ONLY"):
            return max(conf, 70)
        if action == "WAIT" and name == "WAIT":
            return max(55, min(100, 100 - conf))
        return 0

    entry_status_trade = "✅ AI_MASTER Approved" if status == "APPROVED" else ("🔒 Preview / Market Closed" if status == "PREVIEW_ONLY" else "⚠️ Wait")
    return [
        {"Strategy": "SELL CE", "Rank Score": selected_score("SELL CE"), "Sell CE": ce_plan.get("strike", "-"), "Buy CE Hedge": ce_plan.get("hedge", "-"), "Sell PE": "-", "Buy PE Hedge": "-", "Entry/Credit": ce_plan.get("entry", 0), "SL": ce_plan.get("sl", 0), "Target": ce_plan.get("target", 0), "Entry Status": entry_status_trade if action == "SELL CE" else "Not selected by AI_MASTER"},
        {"Strategy": "SELL PE", "Rank Score": selected_score("SELL PE"), "Sell CE": "-", "Buy CE Hedge": "-", "Sell PE": pe_plan.get("strike", "-"), "Buy PE Hedge": pe_plan.get("hedge", "-"), "Entry/Credit": pe_plan.get("entry", 0), "SL": pe_plan.get("sl", 0), "Target": pe_plan.get("target", 0), "Entry Status": entry_status_trade if action == "SELL PE" else "Not selected by AI_MASTER"},
        {"Strategy": "IRON CONDOR", "Rank Score": selected_score("IRON CONDOR"), "Sell CE": ce_plan.get("strike", "-"), "Buy CE Hedge": ce_plan.get("hedge", "-"), "Sell PE": pe_plan.get("strike", "-"), "Buy PE Hedge": pe_plan.get("hedge", "-"), "Entry/Credit": round(_v221_num(ce_plan.get("entry", 0)) + _v221_num(pe_plan.get("entry", 0)), 2), "SL": f"CE {ce_plan.get('sl',0)} / PE {pe_plan.get('sl',0)}", "Target": f"CE {ce_plan.get('target',0)} / PE {pe_plan.get('target',0)}", "Entry Status": entry_status_trade if action == "IRON CONDOR" else "Not selected by AI_MASTER"},
        {"Strategy": "WAIT", "Rank Score": selected_score("WAIT"), "Sell CE": "-", "Buy CE Hedge": "-", "Sell PE": "-", "Buy PE Hedge": "-", "Entry/Credit": 0, "SL": "No trade", "Target": "No trade", "Entry Status": "Capital safe / AI_MASTER Wait" if action == "WAIT" else "Backup only"},
    ]


def _v221_candidate_rows(master):
    out = []
    oc_time = ""
    try:
        oc_time = str((option_analysis or {}).get("fetched_at", "") or (option_chain or {}).get("fetched_at", ""))
    except Exception:
        oc_time = ""
    for label, side, plan in [
        ("Best CE", "CE", master.get("ce_plan", {})),
        ("Best PE", "PE", master.get("pe_plan", {})),
    ]:
        plan = plan if isinstance(plan, dict) else {}
        out.append({
            "Candidate": label,
            "Strike": plan.get("strike", "-"),
            "Entry": plan.get("entry", 0),
            "SL": plan.get("sl", 0),
            "Target": plan.get("target", 0),
            "Hedge": plan.get("hedge", "-"),
            "OC Time": oc_time or fmt_time(),
            "Fresh": "✅ AI_MASTER Fresh",
        })
    return out


# =========================================================
# V22.2 CANDIDATE + STRATEGY AUTHORITY LOCK
# =========================================================
# Professional order: Market/Decision -> Strategy -> Candidate -> Strike.
# Best CE/PE rows from old option-chain scoring remain ONLY raw evidence.
# The first four UI matrices must display only AI_MASTER-approved plans.
def _v222_parse_side_from_plan(strategy_obj):
    strategy_obj = strategy_obj if isinstance(strategy_obj, dict) else {}
    side = str(strategy_obj.get("side", "") or "").upper()
    if side in ("CE", "PE"):
        return side
    text = (str(strategy_obj.get("sell_strike", "")) + " " + str(strategy_obj.get("action", ""))).upper()
    if "CE" in text or "SELL CE" in text:
        return "CE"
    if "PE" in text or "SELL PE" in text:
        return "PE"
    return ""


def _v222_money_to_num(value, default=0.0):
    return _v221_num(value, default)


def _v222_plan_from_strategy_report(strategy_obj, action, side):
    """Build the display plan from the approved strategy report.

    This avoids Candidate Matrix reading old `best_ce` / `best_pe` directly.
    If Strategy Engine has no valid sell strike, return a locked/no-trade plan.
    """
    strategy_obj = strategy_obj if isinstance(strategy_obj, dict) else {}
    action = str(action or "WAIT").upper()
    side = str(side or "").upper()
    if action not in ("SELL CE", "SELL PE", "IRON CONDOR") or side not in ("CE", "PE"):
        return {"strike": "-", "hedge": "-", "entry": 0.0, "sl": 0.0, "target": 0.0, "target2": 0.0, "source": "AI_MASTER_LOCKED"}

    sell = strategy_obj.get("sell_strike", "No Strike")
    hedge_value = strategy_obj.get("hedge_strike", "No Hedge")
    entry = _v222_money_to_num(strategy_obj.get("entry_value", strategy_obj.get("entry", 0)), 0.0)
    sl = _v222_money_to_num(strategy_obj.get("sl_value", strategy_obj.get("sl", 0)), 0.0)
    target = _v222_money_to_num(strategy_obj.get("target_value", strategy_obj.get("target", 0)), 0.0)
    target2 = _v222_money_to_num(strategy_obj.get("target2_value", strategy_obj.get("target2", 0)), 0.0)

    # Normalize label side if Strategy Engine stores numeric strings.
    sell_num = _v221_int(sell, 0)
    hedge_num = _v221_int(hedge_value, 0)
    sell_label = f"{sell_num} {side}" if sell_num else str(sell or "-")
    hedge_label = f"{hedge_num} {side}" if hedge_num else str(hedge_value or "-")

    if sell_label in ("No Strike", "", "0") or entry <= 0:
        return {"strike": "-", "hedge": "-", "entry": 0.0, "sl": 0.0, "target": 0.0, "target2": 0.0, "source": "AI_MASTER_NO_APPROVED_CANDIDATE"}
    return {"strike": sell_label, "hedge": hedge_label, "entry": round(entry, 2), "sl": round(sl, 2), "target": round(target, 2), "target2": round(target2, 2), "source": "AI_MASTER_STRATEGY_AUTHORITY"}


def _v224_fresh_professional_candidates_for_action(action):
    """ZERO MALIK candidate source.

    Re-compute professional candidates from current option_analysis only after
    AI_MASTER/advisor action is known. Old best_ce/best_pe and old rankers are
    never used as fallback authority.
    """
    try:
        return _v223_professional_candidate_authority(
            str(action or "WAIT").upper(),
            option_analysis if isinstance(globals().get("option_analysis"), dict) else {},
            price if "price" in globals() else 0,
            nearest_support if "nearest_support" in globals() else None,
            nearest_resistance if "nearest_resistance" in globals() else None,
            vix if "vix" in globals() else 0,
        )
    except Exception as exc:
        return {"version": "V22.4_ZERO_MALIK_CANDIDATE_AUTHORITY", "action": str(action or "WAIT").upper(), "ce": None, "pe": None, "status": "ERROR", "error": str(exc)}


def _v222_authority_plans(action, strategy_obj, confidence_value):
    """Return CE/PE plans that obey AI_MASTER action.

    V22.4 ZERO MALIK:
    - Strategy Engine/advisor decides action first.
    - Candidate Authority runs after that action.
    - Old best_ce/best_pe and old v164/v203 rankers cannot act as fallback.
    """
    action = str(action or "WAIT").upper()
    locked = {"strike": "-", "hedge": "-", "entry": 0.0, "sl": 0.0, "target": 0.0, "target2": 0.0, "source": "AI_MASTER_LOCKED_ZERO_MALIK"}
    ce_plan = dict(locked)
    pe_plan = dict(locked)

    prof = _v224_fresh_professional_candidates_for_action(action)
    try:
        globals()["professional_candidate_report_v224"] = prof
    except Exception:
        pass

    if action == "SELL CE":
        _ce_raw = prof.get("ce") if isinstance(prof, dict) else None
        ce_plan = _v221_side_plan("CE", _ce_raw if isinstance(_ce_raw, dict) else {}, confidence_value)
        ce_plan["source"] = "AI_MASTER_APPROVED_V22_4_ZERO_MALIK_CANDIDATE"
    elif action == "SELL PE":
        _pe_raw = prof.get("pe") if isinstance(prof, dict) else None
        pe_plan = _v221_side_plan("PE", _pe_raw if isinstance(_pe_raw, dict) else {}, confidence_value)
        pe_plan["source"] = "AI_MASTER_APPROVED_V22_4_ZERO_MALIK_CANDIDATE"
    elif action == "IRON CONDOR":
        _ce_raw = prof.get("ce") if isinstance(prof, dict) else None
        _pe_raw = prof.get("pe") if isinstance(prof, dict) else None
        ce_plan = _v221_side_plan("CE", _ce_raw if isinstance(_ce_raw, dict) else {}, confidence_value)
        pe_plan = _v221_side_plan("PE", _pe_raw if isinstance(_pe_raw, dict) else {}, confidence_value)
        ce_plan["source"] = "AI_MASTER_CONDOR_V22_4_ZERO_MALIK_CANDIDATE"
        pe_plan["source"] = "AI_MASTER_CONDOR_V22_4_ZERO_MALIK_CANDIDATE"

    return ce_plan, pe_plan


def _v222_candidate_rows(master):
    out = []
    action = str(master.get("final_action", "WAIT") or "WAIT").upper()
    status = str(master.get("execution_status", "WAIT") or "WAIT").upper()
    oc_time = ""
    try:
        oc_time = str((option_analysis or {}).get("fetched_at", "") or (option_chain or {}).get("fetched_at", ""))
    except Exception:
        oc_time = ""
    for label, side, plan in [
        ("Best CE", "CE", master.get("ce_plan", {})),
        ("Best PE", "PE", master.get("pe_plan", {})),
    ]:
        plan = plan if isinstance(plan, dict) else {}
        is_active = (action == f"SELL {side}") or (action == "IRON CONDOR")
        approved = is_active and status in ("APPROVED", "PREVIEW_ONLY") and str(plan.get("strike", "-")) not in ("-", "No Strike", "")
        out.append({
            "Candidate": label,
            "AI Status": "✅ Approved" if approved else "🔒 Locked by AI_MASTER",
            "Strike": plan.get("strike", "-") if approved else "-",
            "Entry": plan.get("entry", 0) if approved else 0,
            "SL": plan.get("sl", 0) if approved else 0,
            "Target": plan.get("target", 0) if approved else 0,
            "Hedge": plan.get("hedge", "-") if approved else "-",
            "OC Time": oc_time or fmt_time(),
            "Source": plan.get("source", "AI_MASTER"),
        })
    return out



def _v225_strategy_from_ai_master_plans(action, status, ce_plan, pe_plan):
    """Build final strategy object only from AI_MASTER-approved plans.

    This prevents advisor/strategy reports created earlier in the run from
    leaking stale strikes into AI Final Authority.
    """
    action = str(action or "WAIT").upper()
    status = str(status or "WAIT").upper()
    ce_plan = ce_plan if isinstance(ce_plan, dict) else {}
    pe_plan = pe_plan if isinstance(pe_plan, dict) else {}
    no_trade = {
        "type": "WAIT",
        "sell_side": None,
        "sell_strike": "No Strike",
        "hedge_strike": "No Hedge",
        "entry": "No Trade",
        "sl": "No Trade",
        "target": "No Trade",
        "target2": "No Trade",
        "lots": 0,
        "plan_status": status,
        "plan_source": "AI_MASTER_V22_5_NO_TRADE",
    }
    if status not in ("APPROVED", "PREVIEW_ONLY") or action == "WAIT":
        return no_trade
    if action == "SELL CE" and str(ce_plan.get("strike", "-")) not in ("-", "", "No Strike"):
        return {
            **no_trade,
            "type": "SELL CE",
            "sell_side": "CE",
            "sell_strike": ce_plan.get("strike", "No Strike"),
            "hedge_strike": ce_plan.get("hedge", "No Hedge"),
            "entry": ce_plan.get("entry", 0),
            "sl": ce_plan.get("sl", 0),
            "target": ce_plan.get("target", 0),
            "target2": ce_plan.get("target2", 0),
            "plan_source": ce_plan.get("source", "AI_MASTER_V22_5"),
        }
    if action == "SELL PE" and str(pe_plan.get("strike", "-")) not in ("-", "", "No Strike"):
        return {
            **no_trade,
            "type": "SELL PE",
            "sell_side": "PE",
            "sell_strike": pe_plan.get("strike", "No Strike"),
            "hedge_strike": pe_plan.get("hedge", "No Hedge"),
            "entry": pe_plan.get("entry", 0),
            "sl": pe_plan.get("sl", 0),
            "target": pe_plan.get("target", 0),
            "target2": pe_plan.get("target2", 0),
            "plan_source": pe_plan.get("source", "AI_MASTER_V22_5"),
        }
    if action == "IRON CONDOR":
        ce_ok = str(ce_plan.get("strike", "-")) not in ("-", "", "No Strike")
        pe_ok = str(pe_plan.get("strike", "-")) not in ("-", "", "No Strike")
        if ce_ok and pe_ok:
            return {
                **no_trade,
                "type": "IRON CONDOR",
                "sell_side": "BOTH",
                "sell_strike": f"{ce_plan.get('strike')} + {pe_plan.get('strike')}",
                "hedge_strike": f"{ce_plan.get('hedge')} + {pe_plan.get('hedge')}",
                "entry": round(_v221_num(ce_plan.get("entry", 0)) + _v221_num(pe_plan.get("entry", 0)), 2),
                "sl": f"CE {ce_plan.get('sl', 0)} / PE {pe_plan.get('sl', 0)}",
                "target": f"CE {ce_plan.get('target', 0)} / PE {pe_plan.get('target', 0)}",
                "target2": f"CE {ce_plan.get('target2', 0)} / PE {pe_plan.get('target2', 0)}",
                "plan_source": "AI_MASTER_V22_5_CONDOR_PLANS",
            }
    return {**no_trade, "plan_status": "BLOCKED", "plan_source": "AI_MASTER_V22_5_NO_CLEAN_CANDIDATE"}


def _v225_ai_master_advice(action, status, ce_plan, pe_plan):
    """One final user-facing action line from AI_MASTER only."""
    strategy = _v225_strategy_from_ai_master_plans(action, status, ce_plan, pe_plan)
    action = str(action or "WAIT").upper()
    status = str(status or "WAIT").upper()
    if action == "WAIT" or status in ("WAIT", "BLOCKED"):
        return "WAIT — no fresh trade. Let confirmation improve."
    if strategy.get("type") == "WAIT" or str(strategy.get("sell_strike", "No Strike")) in ("No Strike", "", "-"):
        return f"{action} bias, but no clean AI_MASTER-approved candidate — WAIT."
    return f"{strategy.get('type')}: {strategy.get('sell_strike')} | Hedge {strategy.get('hedge_strike')} | Entry {strategy.get('entry')} | Confirm spread/margin."

try:
    _advisor_v221 = advisor_report if isinstance(advisor_report, dict) else {}
    _snapshot_v221 = market_snapshot if isinstance(market_snapshot, dict) else {}
    _decision_v221 = decision_engine_report if isinstance(decision_engine_report, dict) else {}
    _strategy_v221 = strategy_engine_report if isinstance(strategy_engine_report, dict) else {}
    _intelligence_v221 = intelligence_report if isinstance(intelligence_report, dict) else {}
    _risk_v221 = risk_engine_report if isinstance(risk_engine_report, dict) else {}

    _final_action_v221 = str(_advisor_v221.get("final_action", _decision_v221.get("final_action", "WAIT")) or "WAIT").upper()
    _execution_status_v221 = str(_advisor_v221.get("execution_status", _decision_v221.get("execution_status", "WAIT")) or "WAIT").upper()
    _confidence_v221 = _v221_int(_advisor_v221.get("confidence", _decision_v221.get("calibrated_confidence", 0)), 0)
    _strategy_dict_v221 = _advisor_v221.get("strategy", {}) if isinstance(_advisor_v221.get("strategy", {}), dict) else {}
    _projection_v221 = _v221_build_projection(_snapshot_v221)
    # V22.2: Candidate Authority Lock. Plans come after AI_MASTER action + Strategy Engine,
    # not directly from old best_ce/best_pe scoring.
    _ce_plan_v221, _pe_plan_v221 = _v222_authority_plans(_final_action_v221, _strategy_dict_v221, _confidence_v221)
    _strategy_authority_v225 = _v225_strategy_from_ai_master_plans(_final_action_v221, _execution_status_v221, _ce_plan_v221, _pe_plan_v221)
    _advice_v225 = _v225_ai_master_advice(_final_action_v221, _execution_status_v221, _ce_plan_v221, _pe_plan_v221)
    _evidence_rows_v221 = _v221_build_evidence_rows(_snapshot_v221, _intelligence_v221)

    AI_MASTER = {
        "version": "V22.6_DATA_OWNERSHIP_LOCK",
        "zero_malik_status": "ACTIVE",
        "legacy_ranker_status": "EVIDENCE_ONLY_NOT_AUTHORITY",
        "legacy_candidate_status": "EVIDENCE_ONLY_NOT_AUTHORITY",
        "created_at": fmt_time(),
        "snapshot_id": _advisor_v221.get("snapshot_id", _snapshot_v221.get("snapshot_id", "SNAP-NA")),
        "short_snapshot_id": _advisor_v221.get("short_snapshot_id", str(_snapshot_v221.get("snapshot_id", "SNAP-NA"))[-8:]),
        "source_of_truth": "decision_stability_then_ai_master_strategy_candidate",
        "final_action": _final_action_v221,
        "execution_status": _execution_status_v221,
        "confidence": _confidence_v221,
        "strategy": _strategy_authority_v225,
        "projection": _projection_v221,
        "reasons": list(dict.fromkeys([str(x) for x in (_advisor_v221.get("reasons", []) or []) if x]))[:3] or ["Mixed evidence — wait for confirmation."],
        "blockers": _advisor_v221.get("blockers", []) if isinstance(_advisor_v221.get("blockers", []), list) else [],
        "warnings": _advisor_v221.get("warnings", []) if isinstance(_advisor_v221.get("warnings", []), list) else [],
        "advice": _advice_v225,
        "data_flow_status": _advisor_v221.get("data_flow_status", "UNKNOWN"),
        "oi_sync_status": _advisor_v221.get("oi_sync_status", "UNKNOWN"),
        "risk_score": _advisor_v221.get("risk_score", None),
        "risk_label": _advisor_v221.get("risk_label", "NA"),
        "ce_plan": _ce_plan_v221,
        "pe_plan": _pe_plan_v221,
        "professional_candidate_authority": professional_candidate_report_v224 if isinstance(globals().get("professional_candidate_report_v224"), dict) else (professional_candidate_report_v223 if isinstance(globals().get("professional_candidate_report_v223"), dict) else {}),
        "evidence_rows": _evidence_rows_v221,
    }
    AI_MASTER["strategy_rows"] = _v221_strategy_rows(AI_MASTER)
    AI_MASTER["candidate_rows"] = _v222_candidate_rows(AI_MASTER)
    if isinstance(final_decision, dict):
        final_decision["AI_MASTER"] = AI_MASTER
except Exception as _v221_master_error:
    st.error("AI_MASTER Single Routing failed: " + str(_v221_master_error))
    st.stop()


# =========================================================
# V24.0 DEPARTMENT PIPELINE — ONE SNAPSHOT / ONE FINAL OWNER
# =========================================================
# This block adapts the existing live data into the new department hierarchy.
# Old engines remain compatibility/evidence providers only. Final UI authority
# is overwritten by the V24 AI_MASTER when the department pipeline succeeds.
try:
    if V24_DEPARTMENT_ARCHITECTURE_READY:
        _v24_rows = option_analysis.get("rows", []) if isinstance(option_analysis, dict) else []
        _v24_total_volume = sum(
            float(r.get("ce_volume", 0) or 0) + float(r.get("pe_volume", 0) or 0)
            for r in _v24_rows if isinstance(r, dict)
        )
        _v24_volume_hist = list(st.session_state.get("v24_option_volume_history", []))[-4:]
        _v24_avg_volume = (sum(_v24_volume_hist) / len(_v24_volume_hist)) if _v24_volume_hist else max(_v24_total_volume, 1.0)
        if _v24_total_volume > 0:
            _v24_volume_hist.append(_v24_total_volume)
            st.session_state["v24_option_volume_history"] = _v24_volume_hist[-5:]

        _near_support = float(nearest_support if "nearest_support" in globals() else 0)
        _near_resistance = float(nearest_resistance if "nearest_resistance" in globals() else 0)
        _barrier_touched = min(abs(float(price) - _near_support), abs(_near_resistance - float(price))) <= 20
        _barrier_respected = (_near_support <= float(price) <= _near_resistance)

        _v24_option_report = OptionIntelligenceDirector().build_report(
            price_change=float(nifty_change if "nifty_change" in globals() else 0),
            oi_change=float(put_oi_change - call_oi_change),
            current_volume=float(_v24_total_volume),
            average_volume=float(_v24_avg_volume),
            ce_change=float(call_oi_change),
            pe_change=float(put_oi_change),
            pcr=float(pcr),
            ce_oi=float(total_call_oi),
            pe_oi=float(total_put_oi),
            barrier_touched=bool(_barrier_touched),
            barrier_respected=bool(_barrier_respected),
        )

        _open_px_v24 = float(locals().get("candle15_open", float(price) - float(nifty_change or 0)))
        _high_px_v24 = float(locals().get("candle15_high", today_high))
        _low_px_v24 = float(locals().get("candle15_low", today_low))
        _close_px_v24 = float(locals().get("candle15_close", price))
        _v24_price_report = PriceActionDirector().build_report(
            price=float(price), ema20=float(ema20), ema50=float(ema50), vwap=float(vwap),
            current_range=max(float(today_high) - float(today_low), 0.0), atr=float(atr5),
            support=_near_support, resistance=_near_resistance,
            open_price=_open_px_v24, high=_high_px_v24, low=_low_px_v24, close=_close_px_v24,
            points_moved_from_open=float(price) - _open_px_v24,
            day_high=float(today_high), day_low=float(today_low),
        )

        _v24_behaviour_report = MarketBehaviourDirector().build_report(
            _v24_price_report.details, _v24_option_report.details, datetime.now(IST).hour
        )

        _hw_rows_v24 = heavy_analysis.get("rows", []) if isinstance(heavy_analysis, dict) else []
        _adv_hw_v24 = sum(1 for r in _hw_rows_v24 if float(r.get("change_pct", 0) or 0) > 0)
        _dec_hw_v24 = sum(1 for r in _hw_rows_v24 if float(r.get("change_pct", 0) or 0) < 0)
        _v24_money_report = SmartMoneyDirector().build_report(
            float(fii_today), float(dii_today), _adv_hw_v24, _dec_hw_v24, _adv_hw_v24, _dec_hw_v24
        )

        _v24_risk_report = RiskDirector().build_report(
            float(vix), bool(news.get("score", 0) >= 65), bool(is_expiry_mode),
            str(news.get("label", "") if isinstance(news, dict) else ""),
            float(nifty_change_pct),
        )

        _candidate_rows_input_v24 = []
        for _r in _v24_rows:
            if not isinstance(_r, dict):
                continue
            for _side in ("CE", "PE"):
                _prefix = _side.lower()
                _candidate_rows_input_v24.append({
                    "option_type": _side,
                    "strike": _r.get("strike", 0),
                    "premium": _r.get(f"{_prefix}_ltp", 0),
                    "volume": _r.get(f"{_prefix}_volume", 0),
                    "oi": _r.get(f"{_prefix}_oi", 0),
                    "oi_change": _r.get(f"{_prefix}_oi_change", 0),
                    "bid_ask_spread": _r.get(f"{_prefix}_spread_pct", 0),
                })
        _v24_candidate_report = CandidateDirector().build_report(
            _candidate_rows_input_v24, float(price), float(atr5), _near_support, _near_resistance
        )
        _v24_strategy_report = StrategyDirector().build_report(
            _v24_price_report, _v24_option_report, _v24_behaviour_report, _v24_money_report, _v24_risk_report
        )

        # V24.1 memory-safe snapshot: store only compact authoritative summaries.
        # Full option rows/heavyweight rows already exist in the current script
        # and must not be deep-copied again into Department 0.
        _did_payload_v24 = {
            "market": {"price": price, "change": nifty_change, "change_pct": nifty_change_pct, "vix": vix, "pcr": pcr},
            "price_action": {"ema20": ema20, "ema50": ema50, "vwap": vwap, "atr": atr5, "support": _near_support, "resistance": _near_resistance},
            "option": {
                "snapshot_id": option_analysis.get("snapshot_id", ""),
                "rows_count": len(_v24_rows),
                "call_oi": total_call_oi,
                "put_oi": total_put_oi,
                "call_oi_change": call_oi_change,
                "put_oi_change": put_oi_change,
            },
            "money": {
                "fii_today": fii_today,
                "dii_today": dii_today,
                "heavyweight_count": len(_hw_rows_v24),
                "advancing_heavyweights": _adv_hw_v24,
                "declining_heavyweights": _dec_hw_v24,
            },
            "risk": {
                "news_score": news.get("score", 0) if isinstance(news, dict) else 0,
                "news_label": news.get("label", "") if isinstance(news, dict) else "",
                "expiry": str(selected_expiry),
                "market_mode": str(market_mode),
            },
        }
        _did_quality_v24 = int(max(0, min(100, data_quality)))
        _did_snapshot_v24 = SnapshotManager().create_snapshot(_did_payload_v24, [], _did_quality_v24)
        _did_distributor_v24 = DataDistributor(_did_snapshot_v24)
        _snapshot_id_v24 = _did_distributor_v24.snapshot_id
        # V26 command hierarchy: every branch report is reviewed by its DSP,
        # consolidated by the CO, and only then forwarded to AI_MASTER.
        _data_branch_report_v26 = {
            "summary": f"Verified snapshot {_snapshot_id_v24} | quality {_did_snapshot_v24.quality_score}/100",
            "confidence": float(_did_snapshot_v24.quality_score),
            "details": {
                "snapshot_id": _snapshot_id_v24,
                "quality_score": _did_snapshot_v24.quality_score,
                "rows_count": len(option_analysis.get("rows", [])) if isinstance(option_analysis, dict) else 0,
            },
        }
        _branch_source_reports_v28 = {
            "DATA": _data_branch_report_v26,
            "OPTION": _v24_option_report,
            "PRICE_ACTION": _v24_price_report,
            "MARKET_BEHAVIOUR": _v24_behaviour_report,
            "SMART_MONEY": _v24_money_report,
            "RISK": _v24_risk_report,
            "CANDIDATE": _v24_candidate_report,
            "STRATEGY": _v24_strategy_report,
        }
        _co_case_v26 = AIOrganizationController().build_case_file(
            snapshot_id=_snapshot_id_v24,
            data_quality_score=float(_did_snapshot_v24.quality_score),
            reports=_branch_source_reports_v28,
        )
        # V28 Academy: every DSP branch gets an SOP check and bounded diary.
        # It learns observations only; it cannot alter weights or issue trades.
        _academy_v28 = DepartmentAcademy(st.session_state, memory_limit=8)
        _training_reports_v28 = _academy_v28.train_once(
            snapshot_id=_snapshot_id_v24,
            branch_reports=_co_case_v26.branch_reports,
        )
        # V32 one-shot communication bus. It creates compact branch messages,
        # CO inbox, AI_MASTER inbox, state lifecycle, and a bounded timeline.
        _communication_batch_v32 = DepartmentCommunicationBus().build_batch(
            snapshot_id=_snapshot_id_v24,
            branch_reports=_co_case_v26.branch_reports,
            co_case_file=_co_case_v26,
        )
        _communication_trace_v32 = _communication_batch_v32.to_compact_dict()
        _data_quality_ok_v24 = bool(
            _did_snapshot_v24.quality_score >= 60
            and option_analysis.get("success", False)
            and _co_case_v26.accepted
        )
        _v24_decision = AIMaster().decide(
            snapshot_id=_snapshot_id_v24, data_quality_ok=_data_quality_ok_v24,
            price_report=_v24_price_report, option_report=_v24_option_report,
            behaviour_report=_v24_behaviour_report, smart_money_report=_v24_money_report,
            risk_report=_v24_risk_report, strategy_report=_v24_strategy_report,
            candidate_report=_v24_candidate_report,
            co_case_file=_co_case_v26,
        )
        # V33 bounded case history. It stores compact case fingerprints only,
        # matches similar prior snapshots, and never changes live AI weights.
        _case_history_v33 = CaseHistoryEngine(max_cases=80, max_matches=5).process_case(
            state=st.session_state,
            snapshot_id=_snapshot_id_v24,
            case_id=_co_case_v26.case_id,
            action=_v24_decision.action,
            confidence=_v24_decision.confidence,
            market_bias=_v24_decision.market_bias,
            case_strength=_co_case_v26.case_strength,
            consensus_direction=_co_case_v26.consensus_direction,
            branch_votes=dict(_co_case_v26.branch_votes),
            accepted_evidence=list(_co_case_v26.accepted_evidence),
            warnings=list(_co_case_v26.warnings) + list(_v24_decision.warnings),
        )
        _case_history_trace_v33 = _case_history_v33.to_compact_dict()

        def _v24_candidate_plan(candidate, side, confidence_value):
            _c = candidate if isinstance(candidate, dict) else {}
            _strike = _v221_int(_c.get("strike", 0), 0)
            _row = _v221_current_option_row(option_analysis, _strike) if _strike else None
            _plan = _v221_side_plan(side, _row or {}, confidence_value)
            if _c.get("hedge_strike"):
                _plan["hedge"] = f"{_v221_int(_c.get('hedge_strike'))} {side}"
            _plan["candidate_score"] = _v221_num(_c.get("score", 0))
            _plan["candidate_status"] = _c.get("status", "Watchlist")
            _plan["source"] = "V24_DEPARTMENT_CANDIDATE"
            return _plan

        _watch_v24 = _v24_decision.watchlist or {}
        _ce_plan_v24 = _v24_candidate_plan(_watch_v24.get("best_ce"), "CE", _v24_decision.confidence)
        _pe_plan_v24 = _v24_candidate_plan(_watch_v24.get("best_pe"), "PE", _v24_decision.confidence)
        _exec_v24 = "APPROVED" if _v24_decision.trade_allowed and bool(_market_open_v1951) else ("PREVIEW_ONLY" if _v24_decision.trade_allowed else "WAIT")

        _score_map_v24 = {k: float(v) for k, v in (_v24_decision.strategy_scores or {}).items()}
        def _v24_strategy_rows():
            _rows = []
            for _name in ("SELL CE", "SELL PE", "IRON CONDOR", "WAIT"):
                _is_selected = _v24_decision.action == _name
                _rows.append({
                    "Strategy": _name,
                    "Confidence %": round(_score_map_v24.get(_name, 0.0), 1),
                    "Status": "SELECTED" if _is_selected else ("WATCH" if _score_map_v24.get(_name, 0) >= 60 else "WEAK"),
                    "Sell CE": _ce_plan_v24.get("strike", "-") if _name in ("SELL CE", "IRON CONDOR") else "-",
                    "Buy CE Hedge": _ce_plan_v24.get("hedge", "-") if _name in ("SELL CE", "IRON CONDOR") else "-",
                    "Sell PE": _pe_plan_v24.get("strike", "-") if _name in ("SELL PE", "IRON CONDOR") else "-",
                    "Buy PE Hedge": _pe_plan_v24.get("hedge", "-") if _name in ("SELL PE", "IRON CONDOR") else "-",
                    "Entry/Credit": (round(_v221_num(_ce_plan_v24.get("entry")) + _v221_num(_pe_plan_v24.get("entry")), 2) if _name == "IRON CONDOR" else _ce_plan_v24.get("entry", 0) if _name == "SELL CE" else _pe_plan_v24.get("entry", 0) if _name == "SELL PE" else 0),
                    "SL": (f"CE {_ce_plan_v24.get('sl',0)} / PE {_pe_plan_v24.get('sl',0)}" if _name == "IRON CONDOR" else _ce_plan_v24.get("sl", 0) if _name == "SELL CE" else _pe_plan_v24.get("sl", 0) if _name == "SELL PE" else "No trade"),
                    "Target": (f"CE {_ce_plan_v24.get('target',0)} / PE {_pe_plan_v24.get('target',0)}" if _name == "IRON CONDOR" else _ce_plan_v24.get("target", 0) if _name == "SELL CE" else _pe_plan_v24.get("target", 0) if _name == "SELL PE" else "No trade"),
                })
            return _rows

        def _v24_candidate_rows():
            _rows = []
            for _label, _side, _plan, _candidate in (
                ("Best CE", "CE", _ce_plan_v24, _watch_v24.get("best_ce")),
                ("Best PE", "PE", _pe_plan_v24, _watch_v24.get("best_pe")),
            ):
                _candidate = _candidate if isinstance(_candidate, dict) else {}
                _approved = _v24_decision.trade_allowed and (_v24_decision.action in (f"SELL {_side}", "IRON CONDOR"))
                _rows.append({
                    "Candidate": _label,
                    "AI Status": "APPROVED" if _approved else "WATCHLIST / WAITING CONFIRMATION",
                    "Confidence %": round(_v221_num(_candidate.get("score", 0)), 1),
                    "Strike": _plan.get("strike", "-"),
                    "Entry": _plan.get("entry", 0),
                    "SL": _plan.get("sl", 0),
                    "Target": _plan.get("target", 0),
                    "Hedge": _plan.get("hedge", "-"),
                    "Source": "V24 AI_MASTER",
                })
            return _rows

        AI_MASTER.update({
            "version": "V24.1_STABILITY_AI_MASTER",
            "final_action": _v24_decision.action,
            "execution_status": _exec_v24,
            "confidence": _v24_decision.confidence,
            "strategy": {"type": _v24_decision.action, "plan_source": "V24_DEPARTMENT_PIPELINE"},
            "reasons": [_v24_decision.reason] + list(_v24_decision.evidence[:3]),
            "warnings": list(_v24_decision.warnings),
            "advice": _v24_decision.reason,
            "source_of_truth": "ONE_SNAPSHOT_DEPARTMENTS_THEN_AI_MASTER",
            "data_flow_status": "FRESH" if _data_quality_ok_v24 else "CAUTION",
            "ce_plan": _ce_plan_v24,
            "pe_plan": _pe_plan_v24,
            "strategy_scores": _score_map_v24,
            "strategy_rows": _v24_strategy_rows(),
            "candidate_rows": _v24_candidate_rows(),
            "data_department": {"snapshot_id": _did_snapshot_v24.snapshot_id, "quality_score": _did_snapshot_v24.quality_score, "raw_signature": _did_snapshot_v24.raw_signature},
            # Compact UI trace only. Rich dataclass reports are intentionally not
            # retained inside AI_MASTER because final_decision also references
            # AI_MASTER and Streamlit reruns would otherwise retain duplicate
            # candidate/report graphs during the refresh handover.
            "department_reports": {
                "price_action": {"summary": _v24_price_report.summary, "confidence": _v24_price_report.confidence},
                "option": {"summary": _v24_option_report.summary, "confidence": _v24_option_report.confidence},
                "behaviour": {"summary": _v24_behaviour_report.summary, "confidence": _v24_behaviour_report.confidence},
                "smart_money": {"summary": _v24_money_report.summary, "confidence": _v24_money_report.confidence},
                "risk": {"summary": _v24_risk_report.summary, "confidence": _v24_risk_report.confidence},
                "strategy": {"summary": _v24_strategy_report.summary, "confidence": _v24_strategy_report.confidence},
                "candidate": {"summary": _v24_candidate_report.summary, "confidence": _v24_candidate_report.confidence},
            },
            "v24_trace": _v24_decision.trace,
            "command_hierarchy": {
                "version": "V33_CASE_HISTORY",
                "communication_bus": _communication_trace_v32,
                "case_history": _case_history_trace_v33,
                "case_id": _co_case_v26.case_id,
                "case_strength": _co_case_v26.case_strength,
                "department_readiness": _co_case_v26.department_readiness,
                "witness_score": _co_case_v26.witness_score,
                "cross_exam_score": _co_case_v26.cross_exam_score,
                "consensus_direction": _co_case_v26.consensus_direction,
                "branch_votes": dict(_co_case_v26.branch_votes),
                "cross_examinations": [
                    {
                        "question_from": _x.question_from,
                        "question_to": _x.question_to,
                        "question": _x.question,
                        "answer": _x.answer,
                        "verdict": _x.verdict,
                        "score": _x.score,
                    }
                    for _x in _co_case_v26.cross_examinations
                ],
                "court_brief": _co_case_v26.court_brief,
                "accepted_evidence": list(_co_case_v26.accepted_evidence),
                "rejected_evidence": list(_co_case_v26.rejected_evidence),
                "missing_evidence": list(_co_case_v26.missing_evidence),
                "co_status": _co_case_v26.command_status,
                "accepted": _co_case_v26.accepted,
                "agreement_score": _co_case_v26.agreement_score,
                "data_quality_score": _co_case_v26.data_quality_score,
                "conflicts": list(_co_case_v26.conflicts),
                "warnings": list(_co_case_v26.warnings),
                "branches": {
                    _name: {
                        "boss": _branch.boss,
                        "status": _branch.status,
                        "confidence": _branch.confidence,
                        "summary": _branch.summary,
                        "reasoning": _branch.reasoning,
                        "risk_note": _branch.risk_note,
                        "recommendation": _branch.recommendation,
                        "branch_vote": _branch.branch_vote,
                        "evidence_count": len(_branch.evidence),
                        "sop_status": getattr(_training_reports_v28.get(_name), "sop_status", "NOT_TRAINED"),
                        "learning_state": getattr(_training_reports_v28.get(_name), "change_from_previous", "NO_MEMORY"),
                        "memory_count": getattr(_training_reports_v28.get(_name), "memory_count", 0),
                        "experience_count": getattr(_training_reports_v28.get(_name), "experience_count", 0),
                        "reliability_score": getattr(_training_reports_v28.get(_name), "reliability_score", 0),
                        "training_status": getattr(_training_reports_v28.get(_name), "training_status", "RECRUIT"),
                        "lesson": (getattr(_training_reports_v28.get(_name), "lessons", []) or [""])[0],
                    }
                    for _name, _branch in _co_case_v26.branch_reports.items()
                },
            },
        })
        if _co_case_v26.conflicts:
            AI_MASTER.setdefault("warnings", []).extend(
                ["CO conflict: " + _x for _x in _co_case_v26.conflicts[:3]]
            )
        if not _co_case_v26.accepted:
            AI_MASTER["final_action"] = "WAIT"
            AI_MASTER["execution_status"] = "WAIT"
            AI_MASTER["advice"] = "CO HOLD: branch case file not cleared for execution."

        # V24.1 lightweight session memory. Store plain compact dictionaries,
        # not custom class instances, to reduce retained object graphs on rerun.
        _v24_hist = list(st.session_state.get("v24_compact_decision_history", []))[-7:]
        _v24_hist.append({
            "snapshot_id": _snapshot_id_v24,
            "action": _v24_decision.action,
            "confidence": _v24_decision.confidence,
            "price": round(float(price), 2),
        })
        _v24_hist = _v24_hist[-8:]
        st.session_state["v24_compact_decision_history"] = _v24_hist
        _v24_actions = [str(_x.get("action", "")) for _x in _v24_hist]
        AI_MASTER["memory_stats"] = {"snapshots": len(_v24_hist), "decisions": len(_v24_hist), "events": 0}
        AI_MASTER["decision_flip_count"] = sum(
            1 for _a, _b in zip(_v24_actions, _v24_actions[1:]) if _a and _b and _a != _b
        )

        # Drop large transient V24 lists before the UI phase. They are recreated
        # from the next verified snapshot and should not survive the rerun.
        _candidate_rows_input_v24.clear()
        del _candidate_rows_input_v24, _v24_rows, _hw_rows_v24
        gc.collect()
    else:
        AI_MASTER.setdefault("warnings", []).append("V24 department imports unavailable: " + str(globals().get("V24_DEPARTMENT_IMPORT_ERROR", "unknown")))
except Exception as _v24_pipeline_error:
    # Fail-safe: retain the proven V22.6 AI_MASTER instead of crashing the app.
    AI_MASTER.setdefault("warnings", []).append("V24 department pipeline fallback: " + str(_v24_pipeline_error))
    AI_MASTER["v24_pipeline_status"] = "FALLBACK_TO_V22_6"


# =========================================================
# V19.16 TRADER COMMAND CENTER HELPERS
# =========================================================
def _v1916_build_health_snapshot():
    try:
        engine_flags = {
            "snapshot_engine": bool(V19_SNAPSHOT_ENGINE_READY),
            "ai_brain": bool(V19_AI_BRAIN_READY),
            "risk_engine": bool(V19_RISK_ENGINE_READY),
            "decision_engine": bool(V19_DECISION_ENGINE_READY),
            "strategy_engine": bool(V19_STRATEGY_ENGINE_READY),
            "intelligence_engine": bool(V19_INTELLIGENCE_ENGINE_READY),
            "stability_engine": bool(V19_STABILITY_ENGINE_READY),
            "memory_engine": bool(V19_MEMORY_ENGINE_READY),
            "oi_flow_engine": bool(V19_OI_FLOW_ENGINE_READY),
            "advisor_engine": bool(V21_ADVISOR_ENGINE_READY),
        }
    except Exception:
        engine_flags = {}

    ready_count = sum(1 for v in engine_flags.values() if v)
    total_count = len(engine_flags)

    try:
        oc_rows = len(option_chain.get("rows", []) or []) if isinstance(option_chain, dict) else 0
    except Exception:
        oc_rows = 0

    try:
        dhan_ok = bool(dhan_ready)
    except Exception:
        dhan_ok = False

    try:
        data_source = option_chain.get("source", "UNKNOWN") if isinstance(option_chain, dict) else "UNKNOWN"
    except Exception:
        data_source = "UNKNOWN"

    try:
        market_txt = market_text
    except Exception:
        try:
            market_txt, _ = market_status()
        except Exception:
            market_txt = "UNKNOWN"

    if oc_rows > 0 and dhan_ok:
        freshness = "LIVE"
        note = "DhanHQ quote and option-chain rows available."
    elif oc_rows > 0:
        freshness = "PARTIAL"
        note = "Option-chain rows available, but Dhan heartbeat not fully confirmed."
    else:
        freshness = "STALE"
        note = "Option-chain rows missing or not loaded."

    return {
        "engines_ready": ready_count,
        "engines_total": total_count,
        "engine_flags": engine_flags,
        "dhan_ok": dhan_ok,
        "option_rows": oc_rows,
        "data_source": data_source,
        "market_status": market_txt,
        "freshness": freshness,
        "freshness_note": note,
        "last_refresh": fmt_time() if "fmt_time" in globals() else "",
    }





# =========================================================
# V19.17 PRO TRADER LAYOUT HELPERS
# =========================================================





st.markdown("""
<style>
/* V19.17 readable market/status cards */
.v17-final, .v17-final *, .v1917-readable-card, .market-mode-card, .status-card {
    color: #1f2937 !important;
    font-weight: 800 !important;
    opacity: 1 !important;
    text-shadow: none !important;
}
</style>
""", unsafe_allow_html=True)



# =========================================================
# V20 CLEAN UI HELPERS
# =========================================================
def _v20_signal_reliability_rows():
    """V22.6 DATA OWNERSHIP LOCK.

    First visible Evidence table must read AI_MASTER only.
    No final_decision/intelligence/snapshot fallback is allowed to create a
    second evidence path. If AI_MASTER is missing, show no rows so the UI
    cannot silently display stale/parallel evidence.
    """
    try:
        _m = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
        _rows = _m.get("evidence_rows", []) if isinstance(_m.get("evidence_rows", []), list) else []
        return _rows if isinstance(_rows, list) else []
    except Exception:
        return []

def _v20_compact_reasons(report, fallback=None, limit=4):
    reasons=[]
    try:
        if isinstance(report, dict):
            for key in ("blockers", "warnings", "reasons"):
                vals=report.get(key, []) or []
                if isinstance(vals, list):
                    reasons.extend([str(x) for x in vals if x])
    except Exception:
        pass
    if not reasons and fallback:
        reasons=[str(fallback)]
    return list(dict.fromkeys(reasons))[:limit]

def _v20_risk_summary():
    """Compact status risk must come from AI_MASTER, not parallel risk reports."""
    try:
        _m = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
        if _m:
            risk_score = _m.get("risk_score", None)
            safety = None
            try:
                if risk_score is not None:
                    safety = max(0, min(100, 100 - int(float(risk_score or 0))))
            except Exception:
                safety = None
            return {
                "risk_score": risk_score if risk_score is not None else 0,
                "risk_label": _m.get("risk_label", "AI_MASTER"),
                "safety_score": safety if safety is not None else "NA",
                "source": "AI_MASTER_ONLY",
            }
    except Exception:
        pass
    return {"risk_score": 0, "risk_label": "AI_MASTER_MISSING", "safety_score": "NA", "source": "NO_AI_MASTER"}


def _v20_oi_report():
    """Developer OI display must show AI_MASTER sync, not a parallel OI advice path."""
    try:
        _m = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
        if _m:
            return {
                "oi_sync_status": _m.get("oi_sync_status", "UNKNOWN"),
                "snapshot_id": _m.get("snapshot_id", "SNAP-NA"),
                "source": "AI_MASTER_ONLY",
            }
    except Exception:
        pass
    return {}

def _v201_signed(x):
    try:
        return max(-100.0, min(100.0, float(x or 0)))
    except Exception:
        return 0.0


def _v201_projection():
    """Projection is display-only and must come from AI_MASTER only."""
    try:
        _m = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
        _p = _m.get("projection", {}) if isinstance(_m.get("projection", {}), dict) else {}
        if _p:
            return _p
    except Exception:
        pass
    return {"raw": 0, "bullish": 50, "bearish": 50, "direction": "RANGE", "probability": 50, "source": "NO_AI_MASTER"}

def _v201_change_line(proj):
    current = int(proj.get("probability", 50) or 50)
    direction = str(proj.get("direction", "RANGE"))
    key = "v201_last_projection_prob"
    prev = st.session_state.get(key, None)
    st.session_state[key] = current
    if prev is None:
        return "First snapshot — next refresh se change compare hoga."
    delta = current - int(prev)
    if abs(delta) < 3:
        return "No major change vs last refresh."
    side = "Bullish" if direction == "UP" else "Bearish" if direction == "DOWN" else "Range"
    word = "increased" if delta > 0 else "reduced"
    return f"{side} pressure {abs(delta)}% {word} vs last refresh."


def _v201_top_factors(limit=3):
    """Reason lines must come from AI_MASTER only."""
    try:
        _m = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
        _r = _m.get("reasons", []) if isinstance(_m.get("reasons", []), list) else []
        if _r:
            return [str(x) for x in _r if x][:limit]
    except Exception:
        pass
    return ["AI_MASTER reason unavailable — wait for clean sync."][:limit]

def _v204_single_brain_sync():
    """Visible sync status must use AI_MASTER as final trace authority."""
    try:
        _m = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
        if _m:
            return {
                "tick": _m.get("snapshot_id", "SNAP-NA"),
                "short_id": _m.get("short_snapshot_id", "NA"),
                "time": _m.get("created_at", fmt_time()),
                "final_action": _m.get("final_action", "WAIT"),
                "execution_status": _m.get("execution_status", "WAIT"),
                "confidence": _m.get("confidence", 0),
                "snapshot_health": _m.get("data_flow_status", "NA"),
                "snapshot_score": "AI_MASTER",
                "oc_rows": 0,
                "fresh": str(_m.get("data_flow_status", "")).upper() not in ("WEAK", "STALE", "MISMATCH"),
                "data_flow_status": _m.get("data_flow_status", "NA"),
                "data_flow_line": f"AI_MASTER Data Flow: {_m.get('data_flow_status','NA')}",
                "oi_sync": _m.get("oi_sync_status", "NA"),
                "oi_source": "AI_MASTER_ONLY",
                "stale_reasons": list(_m.get("warnings", []) or [])[:4],
            }
    except Exception:
        pass
    return {"tick": "SNAP-NA", "short_id": "NA", "time": fmt_time(), "fresh": False, "stale_reasons": ["AI_MASTER missing"], "snapshot_health": "NA", "snapshot_score": "NA", "data_flow_status": "NO_AI_MASTER", "oi_sync": "NA"}

def _v201_candidate_rows():
    """Backward-compatible wrapper: candidate rows come from AI_MASTER only."""
    try:
        _m = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
        return _m.get("candidate_rows", []) if isinstance(_m.get("candidate_rows", []), list) else []
    except Exception:
        return []


# =========================================================
# UI
# =========================================================
market_text, day_name = market_status()
vix_range = v132_vix_range_engine(price, vix)
source_text = v13_source_text(dhan_ready, option_chain, nifty_source, dhan_bundle, expiry_result)

# V19.2: Top duplicate refresh controls removed. Use sidebar Refresh Control only.
st.markdown("<div class='main-title'>🧠 Nifty Seller AI V31 CO Command Organization</div>", unsafe_allow_html=True)


# =========================================================
# V21.6 SAFE TOP REFRESH — native Streamlit button, no browser/tab JS
# =========================================================
try:
    _rcol1, _rcol2 = st.columns([1, 5])
    with _rcol1:
        if st.button("🔄 Refresh", key="v216_top_safe_refresh", width="stretch"):
            v215_unified_refresh("top_safe", do_rerun=True)
except Exception:
    pass

try:
    _v20_health = _v1916_build_health_snapshot()
    _v20_rr = _v20_risk_summary()
    _safety_score = _v20_rr.get('safety_score', 100 - int(_v20_rr.get('risk_score', 0) or 0)) if _v20_rr else 'NA'
    st.markdown(
        f"<div class='v201-top-status'>"
        f"🟢 {_v20_health.get('freshness','NA')} | "
        f"⚙️ Engines {_v20_health.get('engines_ready',0)}/{_v20_health.get('engines_total',0)} | "
        f"📊 OC {_v20_health.get('option_rows',0)} | "
        f"🛡️ Risk {_safety_score}/100 | "
        f"🕒 Last {_v20_health.get('last_refresh','NA')}"
        f"</div>",
        unsafe_allow_html=True,
    )
except Exception as _v20_status_err:
    st.caption("Compact status unavailable: " + str(_v20_status_err))

# Engines still run in background; noisy repeated UI is removed from normal screen.
if developer_mode:
    try:
        _v20_oi = _v20_oi_report()
        if _v20_oi:
            with st.expander("Developer: OI Flow Engine details", expanded=False):
                st.write(_v20_oi)
    except Exception:
        pass

st.markdown(
    "<div class='sub-title'>AI Trading Organization: One Snapshot + Specialist Branches + CO Case File + AI_MASTER</div>",
    unsafe_allow_html=True,
)

# V20.1 compact market movement state used by AI Final Authority.
_oc_age_note = "Live" if option_chain.get("success") else "Not Live"
_pa_status = "Live" if price_action_result.get("success") else "Manual"
_pos_status = "Saved" if ACTIVE_POSITION_STORE.exists() else "Not saved"
_mg = locals().get("v164_move_guard", {}) or {}
_mg_label = str(_mg.get("label", "NORMAL") or "NORMAL")
_mg_move = float(_mg.get("move_points", 0) or 0)
_mg_daily = float(_mg.get("daily_pct", 0) or 0)

st.markdown(
    f"<div class='v201-top-status'>"
    f"📍 {market_text} | 📡 {source_text} | 🌪️ VIX {vix:.2f} | 📊 PCR {pcr:.2f} | "
    f"📰 News {news['label']} {news['score']}/100 | ⚡ {_mg_label} {_mg_move:+.1f} pts"
    f"</div>",
    unsafe_allow_html=True,
)
try:
    _flow_line_v205 = (v205_data_flow or {}).get("line", "") if isinstance(v205_data_flow, dict) else ""
    if _flow_line_v205:
        st.caption("📡 " + _flow_line_v205)
except Exception:
    pass

if developer_mode:
    with st.expander("Developer: Live Health Monitor", expanded=False):
        h1, h2, h3, h4, h5 = st.columns(5)
        h1.metric("Dhan API", "🟢 Ready" if dhan_ready else "🔴 Missing")
        h2.metric("Option Chain", "🟢 " + _oc_age_note if option_chain.get("success") else "🔴 " + _oc_age_note)
        h3.metric("Price Action", "🟢 " + _pa_status if price_action_result.get("success") else "🟡 " + _pa_status)
        h4.metric("Position Save", _pos_status)
        h5.metric("Last Refresh", fmt_time())
        st.caption(f"Market Move Guard: {_mg_label} | Refresh move: {_mg_move} pts | Daily: {_mg_daily}% | Score: {_mg.get('score',0)}/100")

if "INVALID/EXPIRED" in source_text:
    st.error("Dhan Access Token invalid/expired hai. DhanHQ se naya token generate karke Streamlit Secrets me DHAN_ACCESS_TOKEN update karo.")
elif "Fallback" in source_text:
    st.info("Observation Mode: live option-chain complete nahi hai. Real trade se pehle Dhan data verify karo.")

# V19.7 Decision Authority Projection
# Existing UI still reads _signal_gate_v162 for compatibility,
# but the value now comes only from decision_engine_report.
_de_gate_v197 = decision_engine_report if isinstance(decision_engine_report, dict) else {}
_de_status_v197 = str(_de_gate_v197.get("execution_status", "WAIT"))
_de_final_v197 = str(_de_gate_v197.get("final_action", "WAIT"))
_de_freeze_v197 = (
    _de_gate_v197.get("freeze", {})
    if isinstance(_de_gate_v197.get("freeze", {}), dict)
    else {}
)

_gate_reasons_v197 = []
if _de_gate_v197.get("blockers"):
    _gate_reasons_v197.extend(_de_gate_v197.get("blockers", []))
if _de_gate_v197.get("warnings"):
    _gate_reasons_v197.extend(_de_gate_v197.get("warnings", []))
if not _gate_reasons_v197:
    _gate_reasons_v197.append(
        _de_gate_v197.get("execution_reason", "Decision Engine verdict unavailable.")
    )

_signal_gate_v162 = {
    "allowed": bool(
        _de_status_v197 == "APPROVED"
        and _de_final_v197 in ("SELL CE", "SELL PE")
    ),
    "count": int(_de_freeze_v197.get("count", 0) or 0),
    "required": int(_de_freeze_v197.get("required", 3) or 3),
    "reasons": list(
        dict.fromkeys([str(x) for x in _gate_reasons_v197 if x])
    )[:16],
}

try:
    _v204_brain_sync = _v204_single_brain_sync()
except Exception:
    _v204_brain_sync = {"tick": fmt_time(), "time": fmt_time(), "fresh": False, "stale_reasons": ["Brain sync unavailable"], "snapshot_health": "NA", "snapshot_score": "NA"}

_advisor_v214 = advisor_report if isinstance(globals().get("advisor_report", {}), dict) else {}
_ai_master_v221 = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
if _advisor_v214:
    _de_final_v197 = str(_advisor_v214.get("final_action", _de_final_v197) or _de_final_v197).upper()
    _de_status_v197 = str(_advisor_v214.get("execution_status", _de_status_v197) or _de_status_v197).upper()

st.markdown("### 🧠 AI FINAL AUTHORITY")
# V22.2: AI Final Authority is now a pure AI_MASTER display.
# No globals/compatibility decision values are allowed to create visible advice here.
_m_v222 = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
_final_v222 = str(_m_v222.get("final_action", "WAIT") or "WAIT").upper()
_status_v222 = str(_m_v222.get("execution_status", "WAIT") or "WAIT").upper()
_conf_v222 = _v221_int(_m_v222.get("confidence", 0), 0)
_proj_v222 = _m_v222.get("projection", {}) if isinstance(_m_v222.get("projection", {}), dict) else {"direction":"RANGE","probability":50,"bullish":50,"bearish":50}
_change_v222 = _v201_change_line(_proj_v222)
_reasons_v222 = _m_v222.get("reasons", []) if isinstance(_m_v222.get("reasons", []), list) else []
_reason_html_v222 = "<br>".join(["• " + str(x) for x in _reasons_v222[:3]]) if _reasons_v222 else "• Mixed signals — wait for confirmation."
_status_class = "green" if _status_v222 == "APPROVED" and _final_v222 == "SELL PE" else ("red" if _status_v222 == "APPROVED" and _final_v222 == "SELL CE" else ("red" if _status_v222 == "BLOCKED" else ""))
_status_text = {
    "APPROVED": "ENTRY APPROVED ✅",
    "BLOCKED": "ENTRY BLOCKED / WAIT ⚠️",
    "PREVIEW_ONLY": "MARKET CLOSED — PLAN PREVIEW 🔒",
    "WAIT": "WAIT — NO FRESH TRADE",
}.get(_status_v222, "WAIT — NO FRESH TRADE")
_action_line_v222 = _m_v222.get("advice", "WAIT — no fresh trade.")
_news_line_v222 = f"News Risk: {news['label']} ({news['score']}/100)"

st.markdown(f"""
<div class='v201-ai-card {_status_class}'>
<h2>{_status_text} — {_final_v222}</h2>
<b>Confidence:</b> {_conf_v222}% &nbsp; | &nbsp;
<b>Market Outlook:</b> {_proj_v222.get('direction')} {_proj_v222.get('probability')}%
<span style='opacity:.72'>(Bull {_proj_v222.get('bullish')}% / Bear {_proj_v222.get('bearish')}%)</span><br>
<b>Change:</b> {_change_v222}<br>
<b>Action:</b> {_action_line_v222}<br>
<b>{_news_line_v222}</b> &nbsp; | &nbsp; <b>Last:</b> {_m_v222.get('created_at', fmt_time())}<br>
<b>Advisor:</b> Single AI_MASTER | {_m_v222.get('version','V22.2')}<br>
<b>Trace:</b> SNAP {_m_v222.get('short_snapshot_id','NA')} | {_m_v222.get('data_flow_status','NA')} | OI {_m_v222.get('oi_sync_status','NA')} | Source {_m_v222.get('source_of_truth','AI_MASTER')}
<div class='v201-reason'><b>Why:</b><br>{_reason_html_v222}</div>
</div>
""", unsafe_allow_html=True)

try:
    if not _v204_brain_sync.get("fresh", True):
        st.warning("⚠️ Brain Sync caution: " + " | ".join(_v204_brain_sync.get("stale_reasons", []) or ["Data freshness check failed"]))
except Exception:
    pass

# V27: Visible command hierarchy and CO consolidated case file.
st.markdown("### 🏛️ AI Organization — CO Command Case File")
try:
    _co_ui_v27 = AI_MASTER.get("command_hierarchy", {}) if isinstance(AI_MASTER, dict) else {}
    _render_v27_command_hierarchy(_co_ui_v27)
except Exception as _co_ui_err_v27:
    st.caption("CO command case file unavailable: " + str(_co_ui_err_v27))

# V17: Important Strategy Matrix - exact strikes for SELL/BUY/IRON CONDOR.
st.markdown("### 📶 Signal Reliability Table")
try:
    _v20_rel_rows = _v20_signal_reliability_rows()
    if _v20_rel_rows:
        _render_safe_table(_v20_rel_rows)
        st.caption(f"Brain Sync: SNAP {_v204_brain_sync.get('short_id','NA')} | {_v204_brain_sync.get('data_flow_status','NA')} | Same snapshot + Single Advisor. Ye table sirf evidence dikhata hai; advice AI Final Authority se aati hai.")
    else:
        st.info("Signal reliability rows abhi available nahi hain.")
except Exception as _v20_sig_err:
    st.caption("Signal reliability table unavailable: " + str(_v20_sig_err))

st.markdown("### 🎯 Smart Strategy Matrix — AI_MASTER Strategy Routing")
try:
    _strategy_rows_v221 = AI_MASTER.get("strategy_rows", []) if isinstance(AI_MASTER, dict) else []
    if _strategy_rows_v221:
        _render_safe_table(_strategy_rows_v221)
        st.caption(
            f"AI_MASTER: SNAP {AI_MASTER.get('short_snapshot_id','NA')} | "
            f"{AI_MASTER.get('data_flow_status','NA')} | OI {AI_MASTER.get('oi_sync_status','NA')} | "
            "Strategy Matrix ab koi independent ranker/advice nahi banati. Ye sirf AI_MASTER output display karti hai."
        )
        _best_row_v221 = _strategy_rows_v221[0]
        st.markdown(
            f"**AI_MASTER Action:** {AI_MASTER.get('final_action','WAIT')} "
            f"({AI_MASTER.get('confidence',0)}%) | "
            f"**Execution:** {AI_MASTER.get('execution_status','WAIT')}"
        )
    else:
        st.info("AI_MASTER strategy rows unavailable.")
except Exception as _v221_strategy_ui_error:
    st.caption("AI_MASTER strategy matrix unavailable: " + str(_v221_strategy_ui_error))

# V20: AI Brain + Decision Authority duplicate UI removed.


# VIX range is useful, but not required in default trading flow.
with st.expander("📊 India VIX Range Engine — Expected Move", expanded=False):
    if vix_range.get("ok"):
        vr1, vr2, vr3, vr4 = st.columns(4)
        vr1.metric("VIX Expected Move", f"±{vix_range['move_points']:.0f} pts", f"{vix_range['move_pct']:.2f}%")
        vr2.metric("Upper Range", f"{vix_range['upper']:.0f}")
        vr3.metric("Lower Range", f"{vix_range['lower']:.0f}")
        vr4.metric("Range Risk", vix_range['risk'])
        st.caption("India VIX shortcut: VIX ÷ 16 ≈ expected 1-day % move. Ye guarantee nahi, sirf option-seller range estimate hai.")
    else:
        st.info("VIX/price data missing.")

# Fake move calculation remains in AI engine, but duplicate UI is hidden.
fake_move = v133_fake_move_engine(
    price_action_bias=price_action_bias,
    option_bias=option_bias,
    heavy_bias=heavy_bias,
    pcr=pcr,
    vix=vix,
    gamma_score=gamma_score_v7,
    shock_score=shock_score_v7,
    news_score=news["score"],
    conflict_mode=conflict_mode,
    final_trade=(AI_MASTER.get("final_action", final_trade) if isinstance(globals().get("AI_MASTER", {}), dict) else final_trade),
    vix_range=vix_range,
)
if developer_mode:
    with st.expander("🚨 Fake Move + Safe Expiry Details", expanded=False):
        st.write(f"Fake Move: {fake_move['label']} ({fake_move['score']}/100)")
        for reason in fake_move.get("reasons", []):
            st.write("•", reason)
        _minutes_left_v15 = v15_minutes_to_expiry_close(selected_expiry)
        _m_dev = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
        st.write("CE Plan:", _m_dev.get("ce_plan", {}))
        st.write("PE Plan:", _m_dev.get("pe_plan", {}))

# V13: put the most actionable parts near the top for mobile trading.
# V16.3: Strategy setup moved near top as Smart Strategy Matrix.

st.markdown("### 📋 AI Candidate Matrix")
try:
    _cand_rows_v221 = AI_MASTER.get("candidate_rows", []) if isinstance(AI_MASTER, dict) else []
    if _cand_rows_v221:
        _render_safe_table(_cand_rows_v221)
        st.caption(
            f"AI_MASTER: SNAP {AI_MASTER.get('short_snapshot_id','NA')} | "
            f"{AI_MASTER.get('data_flow_status','NA')} | OI {AI_MASTER.get('oi_sync_status','NA')} | "
            "Candidate Matrix fresh CE/PE rows dikhati hai; advice/ranking sirf AI_MASTER se aati hai."
        )
    else:
        st.info("AI Candidate Matrix ke liye live option-chain active hona zaroori hai.")
except Exception as _cand_err_v221:
    st.caption("AI Candidate Matrix unavailable: " + str(_cand_err_v221))


with st.expander("💼 Active Positions + Add Position", expanded=False):
    _pf = v162_portfolio_load()
    _active_pf = _pf[_pf["Status"].astype(str).str.upper() == "ACTIVE"] if not _pf.empty else pd.DataFrame(columns=PORTFOLIO_COLUMNS)
    if _active_pf.empty:
        st.info("Abhi koi active saved position nahi hai. Neeche SELL CE/SELL PE ya IRON CONDOR entry save karo.")
    else:
        _rows = []
        _total_pnl = 0.0
        for _, _pos in _active_pf.iterrows():
            _d = _pos.to_dict()
            _a = v162_analyze_position(_d)
            _total_pnl += float(_a.get("P/L ₹", 0) or 0)
            _rows.append({
                "ID": _d.get("Position ID"),
                "Strategy": _d.get("Strategy"),
                "Leg 1": f"SELL {_d.get('Sell1 Strike')} {_d.get('Sell1 Side')} / HEDGE {_d.get('Hedge1 Strike')}",
                "Leg 2": (f"SELL {_d.get('Sell2 Strike')} {_d.get('Sell2 Side')} / HEDGE {_d.get('Hedge2 Strike')}" if str(_d.get('Sell2 Side','')) else "-"),
                "Lots": int(float(_d.get("Lots",0) or 0)),
                "P/L ₹": _a.get("P/L ₹"),
                "Net Points": _a.get("Net Points"),
                "Profit %": _a.get("Profit %"),
                "AI Action": _a.get("Action"),
                "Reason": _a.get("Reason"),
            })
        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("Active Positions", len(_active_pf))
        pc2.metric("Total P/L", f"₹{_total_pnl:,.0f}")
        pc3.metric("Portfolio Risk", "HIGH" if max(gamma_score_v7, shock_score_v7) >= 70 else "MEDIUM" if max(gamma_score_v7, shock_score_v7) >= 45 else "LOW")
        pc4.metric("Fresh Entry", "Allowed" if _signal_gate_v162.get("allowed") else "Blocked")
        _render_safe_table(_rows)
        st.caption("AI Action har refresh par live premium + hedge + risk ke hisab se update hota hai. Current price zero aaye to option chain range/strike check karo.")
        with st.expander("Position Actions — mark exit", expanded=False):
            _exit_id = st.selectbox("Position ID", list(_active_pf["Position ID"].astype(str)), key="v162_exit_id")
            if st.button("Mark Selected Position EXITED", key="v162_mark_exit"):
                if v162_update_position_status(_exit_id, "EXITED"):
                    st.success("Position exited mark ho gayi.")
                    st.rerun()

    st.markdown("#### ➕ Add New Hedged Seller Position")
    _m_pos = AI_MASTER if isinstance(globals().get("AI_MASTER", {}), dict) else {}
    _ce_pos_plan = _m_pos.get("ce_plan", {}) if isinstance(_m_pos.get("ce_plan", {}), dict) else {}
    _pe_pos_plan = _m_pos.get("pe_plan", {}) if isinstance(_m_pos.get("pe_plan", {}), dict) else {}
    _pref_ce_strike = int(str(_ce_pos_plan.get("strike", "0")).split()[0]) if str(_ce_pos_plan.get("strike", "-")).split()[0].isdigit() else 0
    _pref_pe_strike = int(str(_pe_pos_plan.get("strike", "0")).split()[0]) if str(_pe_pos_plan.get("strike", "-")).split()[0].isdigit() else 0
    _pref_ce_entry = float(_ce_pos_plan.get("entry", 0) or 0)
    _pref_pe_entry = float(_pe_pos_plan.get("entry", 0) or 0)
    with st.form("v162_add_position_form"):
        ac1, ac2, ac3, ac4 = st.columns(4)
        _new_strategy = ac1.selectbox("Strategy", ["SELL CE", "SELL PE", "IRON CONDOR"], key="v162_new_strategy")
        _new_lots = int(ac2.number_input("Lots", min_value=1, value=max(1, int(suggested_lots or 1)), step=1, key="v162_new_lots"))
        _new_lot_size = int(ac3.number_input("Lot Size", min_value=1, value=int(lot_size or 65), step=1, key="v162_new_lot_size"))
        _new_notes = ac4.text_input("Notes", value="", key="v162_new_notes")
        st.caption("CE/PE entries broker screen se confirm karke save karo. Hedge entry bhi add karo taaki true P/L aur risk analyze ho sake.")
        if _new_strategy == "SELL CE":
            c1,c2,c3,c4 = st.columns(4)
            _s1_side="CE"; _s1_strike=int(c1.number_input("Sell CE Strike", value=_pref_ce_strike, step=50, key="v162_sellce_strike")); _s1_entry=float(c2.number_input("Sell CE Entry", value=round(_pref_ce_entry,2), step=0.05, key="v162_sellce_entry")); _h1_strike=int(c3.number_input("Hedge CE Strike", value=int(_pref_ce_strike + hedge_gap if _pref_ce_strike else 0), step=50, key="v162_sellce_hedge_strike")); _h1_entry=float(c4.number_input("Hedge CE Entry", value=0.0, step=0.05, key="v162_sellce_hedge_entry"))
            _s2_side=""; _s2_strike=0; _s2_entry=0.0; _h2_strike=0; _h2_entry=0.0
        elif _new_strategy == "SELL PE":
            c1,c2,c3,c4 = st.columns(4)
            _s1_side="PE"; _s1_strike=int(c1.number_input("Sell PE Strike", value=_pref_pe_strike, step=50, key="v162_sellpe_strike")); _s1_entry=float(c2.number_input("Sell PE Entry", value=round(_pref_pe_entry,2), step=0.05, key="v162_sellpe_entry")); _h1_strike=int(c3.number_input("Hedge PE Strike", value=int(_pref_pe_strike - hedge_gap if _pref_pe_strike else 0), step=50, key="v162_sellpe_hedge_strike")); _h1_entry=float(c4.number_input("Hedge PE Entry", value=0.0, step=0.05, key="v162_sellpe_hedge_entry"))
            _s2_side=""; _s2_strike=0; _s2_entry=0.0; _h2_strike=0; _h2_entry=0.0
        else:
            c1,c2,c3,c4 = st.columns(4)
            _s1_side="CE"; _s1_strike=int(c1.number_input("Sell CE Strike", value=_pref_ce_strike, step=50, key="v162_sellce_strike")); _s1_entry=float(c2.number_input("Sell CE Entry", value=round(_pref_ce_entry,2), step=0.05, key="v162_sellce_entry")); _h1_strike=int(c3.number_input("Hedge CE Strike", value=int(_pref_ce_strike + hedge_gap if _pref_ce_strike else 0), step=50, key="v162_sellce_hedge_strike")); _h1_entry=float(c4.number_input("Hedge CE Entry", value=0.0, step=0.05, key="v162_sellce_hedge_entry"))
            p1,p2,p3,p4 = st.columns(4)
            _s2_side="PE"; _s2_strike=int(p1.number_input("Sell PE Strike", value=_pref_pe_strike, step=50, key="v162_condor_pe_strike")); _s2_entry=float(p2.number_input("Sell PE Entry", value=round(_pref_pe_entry,2), step=0.05, key="v162_condor_pe_entry")); _h2_strike=int(p3.number_input("Hedge PE Strike", value=int(_pref_pe_strike - hedge_gap if _pref_pe_strike else 0), step=50, key="v162_condor_pe_hedge_strike")); _h2_entry=float(p4.number_input("Hedge PE Entry", value=0.0, step=0.05, key="v162_condor_pe_hedge_entry"))
        slt1, slt2 = st.columns(2)
        _sl_pct = float(slt1.number_input("SL %", value=25.0, step=1.0, key="v162_sl_pct"))
        _target_pct = float(slt2.number_input("Target %", value=35.0, step=1.0, key="v162_target_pct"))
        _submit_pos = st.form_submit_button("💾 Save This Position")
        if _submit_pos:
            if v162_add_position(_new_strategy, _new_lots, _new_lot_size, _s1_side, _s1_strike, _s1_entry, _h1_strike, _h1_entry, _s2_side, _s2_strike, _s2_entry, _h2_strike, _h2_entry, _sl_pct, _target_pct, _new_notes):
                st.success("Position portfolio mein save ho gayi. Ab har refresh par iska HOLD/EXIT/TRAIL analysis update hoga.")
                st.rerun()
            else:
                st.error("Position save failed.")

# V20: duplicate Decision Engine Action Plan removed from normal UI.


# V19.5.1: duplicate VIX range UI removed; primary VIX range panel retained above.

# V20: duplicate Decision Engine Ticket removed from normal UI.


# V12 Position Manager + Expiry/Shock/Discipline panels
with st.expander("🚀 Position Manager — Hold / Exit / Trail SL", expanded=False):
    if active_side == "None" or active_lots <= 0:
        st.info("Active trade details sidebar mein enter karo: CE/PE, strike, entry premium, current premium, lots. Phir AI Hold/Exit batayegi.")
    try:
        if entry_premium > 0:
            prem_plan = v10_sl_target(entry_premium, gamma_score_v7, shock_score_v7, confidence)
            st.write(f"V10 Premium Plan: SL around {prem_plan['sl']} | Target around {prem_plan['target']} | Trail after premium reaches {prem_plan['trail_after']}")
    except Exception:
        pass
    else:
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Position AI", position_ai["action"], f"Position Score {position_ai['confidence']}%")
        p2.metric("Profit in Premium", f"{position_ai['profit_pct']:.1f}%")
        p3.metric("Trail SL", f"₹{position_ai['trail_sl']:.2f}" if position_ai["trail_sl"] else "--")
        p4.metric("Position Risk", f"{position_ai['risk']}/100")
        for reason in position_ai["reasons"]:
            st.write("✔", reason)
        if position_ai["action"] == "EXIT NOW":
            st.error("🔴 EXIT NOW: market structure/risk seller ke against ho raha hai.")
        elif "BOOK" in position_ai["action"]:
            st.warning("🟡 Profit secure karna better ho sakta hai.")
        elif "HOLD" in position_ai["action"]:
            st.success("🟢 Hold possible, but trail SL discipline zaroor rakho.")

with st.expander("🧠 Expiry + Shock + Discipline Engine", expanded=False):
    e1, e2, e3, e4, e5 = st.columns(5)
    with e1:
        v102_metric_card("Market Mode", market_mode, f"DTE: {dte if dte != 99 else 'NA'}")
    with e2:
        v102_metric_card("Historical Zone", f"{time_risk}/100", time_zone_label)
    with e3:
        v102_metric_card("Theta Score", f"{theta_score_v7}/100")
    with e4:
        v102_metric_card("Gamma Risk", f"{gamma_score_v7}/100")
    with e5:
        v102_metric_card("Shock Risk", f"{shock_score_v7}/100")
    st.write(f"**Discipline:** {discipline_text} — {discipline_reason}")
    if shock_score_v7 >= 75:
        st.error("🚨 High Shock Probability: new selling avoid / SL tight / profit protect.")
    elif shock_score_v7 >= 55:
        st.warning("⚠️ Caution Zone: quantity small, SL tight, hold decision data se confirm karo.")
    else:
        st.success("✅ Shock risk controlled by current inputs.")

# Compact source status
st.markdown(
    f"<span class='source-pill'>Nifty: {nifty_source}</span>"
    f"<span class='source-pill'>VIX: {vix_source}</span>"
    f"<span class='source-pill'>Heavyweights: {heavy_analysis.get('source','Unavailable')}</span>"
    f"<span class='source-pill'>Option Chain: {'DhanHQ' if option_chain.get('success') else 'Manual aggregate'}</span>",
    unsafe_allow_html=True,
)


# V20: Trade Checklist debug panel removed from normal UI.


# V20: lower duplicate Seller AI Radar removed; signal reliability table retained.


with st.expander("📊 Market Snapshot", expanded=False):
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Nifty", f"{price:,.2f}", f"{nifty_change_pct:+.2f}%")
    m2.metric("India VIX", f"{vix:.2f}", f"{vix_change_pct:+.2f}%")
    m3.metric("EMA20", f"{ema20:.2f}")
    m4.metric("VWAP", f"{vwap:.2f}")
    m5.metric("Nearest S/R", f"{nearest_support:.0f} / {nearest_resistance:.0f}")


with st.expander("🧠 Option Chain AI Engine — OI + Price + Greeks", expanded=False):
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("PCR", f"{pcr:.2f}")
    o2.metric("Put OI Change", f"{put_oi_change:,}")
    o3.metric("Call OI Change", f"{call_oi_change:,}")
    o4.metric("OC Bias", f"{option_bias:+.0f}", bias_label(option_bias))

    if option_analysis.get("success"):
        table_rows = []
        for row in option_analysis["rows"]:
            table_rows.append({
                "Strike": row["strike"],
                "CE LTP": round(row["ce_ltp"], 2),
                "CE Δ%": round(row["ce_price_change_pct"], 2),
                "CE OI Δ%": round(row["ce_oi_change_pct"], 2),
                "CE Signal": row["ce_signal"],
                "CE Sell": row["ce_sell_score"],
                "CE Delta": round(row["ce_delta"], 3),
                "CE IV": round(row["ce_iv"], 2),
                "CE Spread%": round(row["ce_spread_pct"], 2),
                "PE LTP": round(row["pe_ltp"], 2),
                "PE Δ%": round(row["pe_price_change_pct"], 2),
                "PE OI Δ%": round(row["pe_oi_change_pct"], 2),
                "PE Signal": row["pe_signal"],
                "PE Sell": row["pe_sell_score"],
                "PE Delta": round(row["pe_delta"], 3),
                "PE IV": round(row["pe_iv"], 2),
                "PE Spread%": round(row["pe_spread_pct"], 2),
            })
        _oc_df = pd.DataFrame(table_rows)
        try:
            _atm_strike = int(round(float(price) / 50.0) * 50)
            st.caption(f"Current/ATM Strike: {_atm_strike}")
        except Exception:
            pass
        # V24.1 stability: avoid Pandas Styler on every rerun. Styler builds a
        # large HTML representation and increases the refresh memory peak.
        _render_safe_table(_oc_df, max_rows=80)

        st.info("Best CE/PE candidate cards are shown near the top in V13 Live Candidate Cards. Yahan sirf option-chain table rakha gaya hai, taaki duplicate sections na hon.")

        # V20.1: Candidate Verdict duplicate UI removed.
        if developer_mode:
            st.caption("Developer note: old Candidate Verdict removed from main UI; candidate safety is merged into AI Final Authority + Live Best Candidates.")

        st.caption("OI+price labels are conventional inferences. Every option trade has both buyer and seller; OI alone does not prove who initiated the trade.")
        st.caption("Snapshot OI acceleration becomes active after at least two fresh Dhan snapshots. Press Refresh after 4+ seconds to compare snapshots.")
    else:
        st.info("Per-strike OI + Price Analyzer DhanHQ data se chalega. Abhi aggregate manual OI/PCR fallback active hai.")
        if prefer_dhan and dhan_ready:
            st.error(option_chain.get("message", "Dhan option chain unavailable."))


with st.expander("🏋️ Nifty Top-5 Heavyweight Driver Engine", expanded=False):
    if heavy_analysis.get("success"):
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Weighted Pressure", f"{heavy_bias:+.0f}/100", bias_label(heavy_bias))
        h2.metric("Estimated Top-5 Points", f"{heavy_analysis['estimated_points']:+.1f}")
        h3.metric("HDFC + ICICI", heavy_analysis["banking_pair"])
        h4.metric("Divergence", heavy_analysis["divergence"])

        hw_rows = []
        for r in heavy_analysis["rows"]:
            _arrow, _cls, _delta = v13_trend(f"hw_{r['symbol']}_move", r["change_pct"], 2)
            if _arrow == "↑":
                _trend_text = "🟢 ↑ rising"
            elif _arrow == "↓":
                _trend_text = "🔴 ↓ falling"
            else:
                _trend_text = "⚪ → flat/first"
            hw_rows.append({
                "Stock": r["name"],
                "Weight %": round(r["weight"], 2),
                "Move %": round(r["change_pct"], 2),
                "Trend vs Refresh": _trend_text,
                "Change vs Refresh": _delta,
                "Snapshot Shock %pt": round(r.get("shock_delta_pct", 0.0), 2),
                "Est. Nifty pts": round(price * (r["weight"] / 100) * (r["change_pct"] / 100), 1),
            })
        hw_table = pd.DataFrame(hw_rows)
        _render_safe_table(hw_table)
        st.caption(f"Heavyweight table last updated: {fmt_time()} | Green/Red trend compares current value with previous app refresh.")

        if final_trade == "SELL CE" and heavy_bias > 35:
            st.warning("CE SELL WARNING: top-5 drivers bullish hain — short-covering/upside risk.")
        if final_trade == "SELL PE" and heavy_bias < -35:
            st.warning("PE SELL WARNING: top-5 drivers bearish hain — support-break risk.")
        if heavy_analysis.get("shock_rows"):
            st.error("🚨 Heavyweight Shock: " + ", ".join(f"{r['name']} {r['shock_delta_pct']:+.2f}%pt" for r in heavy_analysis["shock_rows"]))
        st.caption("Estimated points are an approximation using constituent weights and stock returns; exact index attribution can differ.")
    else:
        st.warning(heavy_analysis.get("message", "Heavyweight data unavailable."))


if developer_mode:
    with st.expander("🚨 Automatic Market News Risk Indicator", expanded=False):
        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Final News Risk", f"{news['score']}/100", news["label"])
        n2.metric("Scheduled Event", f"{news['scheduled']}/100", "AUTO" if news["auto_calendar"] else "Manual fallback")
        n3.metric("Breaking News", f"{news['breaking']}/100", "AUTO" if news["auto_news"] else "Fallback")
        n4.metric("Market Reaction", f"{news['reaction']}/100")
    
        if news["label"] == "CRITICAL":
            st.error("⚫ CRITICAL: fresh option selling block. Event/news + market reaction risk high.")
        elif news["label"] == "HIGH":
            st.warning("🔴 HIGH: fresh selling reduce/avoid; hedge mandatory.")
        elif news["label"] == "MEDIUM":
            st.info("🟡 MEDIUM: smaller quantity and strict monitoring.")
        else:
            st.success("🟢 LOW: no major risk detected by available sources, but market risk remains.")
    
        if te_result.get("success"):
            st.caption(f"Calendar engine active | relevant high/medium events: {te_result.get('events', 0)}")
        if alpha_result.get("success"):
            st.caption(f"News-sentiment engine active | recent items scanned: {alpha_result.get('items', 0)}")
        if not news["auto_calendar"] or not news["auto_news"]:
            st.caption("Automatic APIs are optional. Until keys are added, manual fallback + live market reaction still drive the indicator.")
    

with st.expander("🏛️ FII / DII Smart Money", expanded=False):
    try:
        _fii_stats = v102_journal_stats(locals().get("fii_journal_df", pd.DataFrame()))
    except Exception:
        _fii_stats = {"rows": 0, "fii_5": fii_5day, "dii_5": dii_5day, "fii_10": 0, "dii_10": 0}
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("FII Today", f"₹{fii_today:,.0f} Cr")
    f2.metric("DII Today", f"₹{dii_today:,.0f} Cr")
    f3.metric("FII 5 Day", f"₹{fii_5day:,.0f} Cr")
    f4.metric("DII 5 Day", f"₹{dii_5day:,.0f} Cr")
    g1, g2, g3 = st.columns(3)
    g1.metric("FII Futures Contracts", f"{locals().get('fii_index_futures_contracts', 0):,.0f}")
    g2.metric("FII Long %", f"{locals().get('fii_long_pct', 0):.2f}%")
    g3.metric("FII Short %", f"{locals().get('fii_short_pct', 0):.2f}%")
    st.write(f"FII Index Futures Bias: **{fii_index_futures_bias}** | Futures Score: **{locals().get('_fut_score', 0):+.0f}**")
    st.write(f"Smart Money Bias: **{smart_money_bias:+.0f}/100 ({bias_label(smart_money_bias)})**")
    if locals().get('fii_short_pct', 0) >= 70 and fii_today > 0:
        st.warning("FII cash buying hai, lekin index futures short % high hai — mixed/caution signal.")
    st.caption(f"Journal storage: last 30 trading days | saved rows: {_fii_stats.get('rows', 0)} | 10D FII ₹{_fii_stats.get('fii_10', 0):,.0f} Cr | 10D DII ₹{_fii_stats.get('dii_10', 0):,.0f} Cr")
    if locals().get("fii_journal_df", pd.DataFrame()).shape[0] > 0:
        _render_safe_table(locals().get("fii_journal_df").sort_values("Date", ascending=False).head(10))


with st.expander("💰 Position & Risk Manager", expanded=False):
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Capital", f"₹{capital:,.0f}")
    p2.metric("Max Lots", max_lots)
    p3.metric("Current Lots", current_lots)
    p4.metric("AI Suggested Lots", suggested_lots)
    st.write(f"Estimated Margin: **₹{suggested_lots * margin_per_lot:,.0f}**")
    st.write(f"Lot Size: **{lot_size}** | Seller Risk: **{seller_risk:.0f}/100**")




with st.expander("🧪 Live Dhan API Diagnostics", expanded=False):
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Credentials", "Detected" if dhan_ready else "Missing")
    d2.metric("Market Quote", "OK" if dhan_bundle.get("success") else "Fallback")
    d3.metric("Expiry List", "OK" if expiry_result.get("success") else "Not OK")
    d4.metric("Option Chain", "OK" if option_chain.get("success") else "Not OK")
    if dhan_bundle.get("success"):
        st.success("Dhan market quote is responding. Nifty/top-5 quote layer is ready.")
    else:
        st.warning("Dhan market quote not active. Current message: " + str(dhan_bundle.get("message", "No response")))
    if not expiry_result.get("success"):
        st.warning("Expiry list issue: " + str(expiry_result.get("message", "No expiry response")))
    if not option_chain.get("success"):
        st.error("Option chain issue: " + str(option_chain.get("message", "No option-chain response")))
        st.info("If Data API subscription is still inactive on DhanHQ, option-chain/OI/PCR will stay on fallback. Once active, press Refresh Live Data after market open.")
    else:
        st.success(f"Option chain loaded for expiry {option_chain.get('expiry')} | ATM {option_chain.get('atm_strike')} | Rows {len(option_chain.get('rows', []))}")

with st.expander("🔐 DhanHQ Setup Status", expanded=False):
    if dhan_ready:
        st.success("DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN are detected from Streamlit secrets/environment.")
        st.write(f"Top-5 Security IDs resolved: **{len(top5_ids)}/5**")
        if master_result.get("success") is False:
            st.warning(master_result.get("message", "Instrument master unavailable."))
        st.caption("Dhan access token can expire; keep credentials only in Streamlit Secrets, never in app.py or GitHub.")
    else:
        st.info("Add Dhan credentials later. App remains usable with Yahoo/manual fallbacks, but per-strike Option Chain AI requires DhanHQ.")
        st.code('DHAN_CLIENT_ID = "your_client_id"\nDHAN_ACCESS_TOKEN = "your_access_token"', language="toml")
    st.caption("Optional news secrets: TRADING_ECONOMICS_API_KEY and ALPHAVANTAGE_API_KEY")


st.markdown("---")
st.markdown(
    "<div class='small-note'>V20 Clean Edition: duplicate/debug UI removed; trading screen is focused and mobile friendly. Disclaimer: Decision-support only. OI/price labels are probabilistic inferences, not proof of buyer/seller identity. Use hedges, live chart confirmation, liquidity checks and strict risk limits.</div>",
    unsafe_allow_html=True,
)
