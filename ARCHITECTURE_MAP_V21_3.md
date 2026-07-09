# V21.3 Clean Setup - Architecture Map

Goal: One Snapshot -> One AI Brain -> One Decision -> Strategy -> UI.

Core files kept:
- app.py: Streamlit UI/controller, DhanHQ/Yahoo fallback, top 4 tables.
- snapshot_engine.py: single market snapshot authority.
- ai_brain.py: explanation/scorecard brain layer.
- decision_engine.py: final execution decision authority.
- strategy_engine.py: strategy/strike/SL/target plan authority.
- risk_engine.py: risk report authority.
- intelligence_engine.py: explanation/reliability table support.
- stability_engine.py: prevents refresh flip-flop and strike jumps.
- memory_engine.py: short-term session memory.
- oi_flow_engine.py: OI helper/reporting layer.

Rules:
1. No direct UI decision outside final_decision/decision_engine_report.
2. Top 4 tables must share the active snapshot id.
3. OI must come from the locked snapshot source.
4. Any new feature must plug into Snapshot/AI Brain, not create a new decision brain.
