# V21.1 Deep Architecture Cleanup Report

Goal: keep the app working while reducing hidden/unused code that can confuse the single AI flow.

## What was cleaned
- Removed unused `v19_utils.py` helper file.
- Removed optional `v19_utils` import bridge from `app.py`.
- Removed unused `timedelta` import.
- Removed unused `v161_qp_set()` query-param helper.
- Removed unused `_v1917_premium_quality()` helper.
- Removed `__pycache__` from package.
- Kept all active engines intact: snapshot, AI brain, decision, strategy, risk, intelligence, stability, memory, OI flow.

## Why this cleanup is safe
- No live DhanHQ logic changed.
- No option-chain/OI formulas changed.
- No strategy/strike engine formulas changed.
- No final UI table structure changed.
- Python syntax check passed for all `.py` files.

## Current active architecture
Live Data → Snapshot Engine → AI Brain → Risk Engine → Strategy Engine → Decision Engine → Intelligence/Stability → UI

## Important note
Some old V14/V16/V18 compatibility blocks are still active in the running flow, so they were not deleted in this safe pass. They should be refactored carefully in the next pass only after live comparison screenshots confirm no behavior break.

## Next cleanup target
V21.2 should focus on moving/removing active legacy compatibility blocks one-by-one:
- V14 memory/freeze/regime helpers
- V16 candidate helpers
- V18 legacy decision seed
- Old V10/V11 ranking helpers

