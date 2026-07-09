# V21 AI Architecture Cleanup Report

## Goal
One Snapshot -> One AI Brain -> One Decision -> One Strategy/UI.

## Safe cleanup done
- Removed `__pycache__/` compiled files.
- Removed old backup file `app_backup_before_v20_1.py`.
- Removed `.devcontainer/` from user deploy ZIP to keep package light.
- Removed 18 uncalled/dead helper functions from `app.py` after static call audit.

## Files kept as active
- `app.py` — UI/controller + live data flow.
- `snapshot_engine.py` — single snapshot authority.
- `ai_brain.py` — AI explanation/evidence layer.
- `decision_engine.py` — final decision authority.
- `strategy_engine.py` — strategy plan authority.
- `risk_engine.py` — risk authority.
- `intelligence_engine.py` — signal/reliability explanation.
- `stability_engine.py` — decision stability lock.
- `memory_engine.py` — previous snapshot/decision memory.
- `oi_flow_engine.py` — OI flow tracking.
- `v19_utils.py` — shared formatting/helpers.

## Lines after cleanup
- app.py: 5764 lines
- Total Python code: 8603 lines

## Safety checks
- Python compile check passed for all `.py` files.
- No active engine file removed.
- No DhanHQ/secrets logic changed.
- No strategy/decision/snapshot engine behavior intentionally changed.

## Next cleanup phase
Deeper refactor can move old active helper logic from `app.py` into modules, but should be done in smaller tested phases because several old V14/V16/V18 functions are still actively called by the app.
