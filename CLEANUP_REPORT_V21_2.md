# V21.2 Final Duplicate Brain Cleanup

## Goal
Keep one visible authority for the first four tables:

`One Snapshot -> Decision Engine Authority -> Strategy Matrix/UI`

## What changed

1. **Strategy Matrix authority lock**
   - Strategy Matrix now respects `decision_engine_report.final_action` first.
   - Old V11 ranker remains only a background ranking provider.
   - If Decision Engine says SELL CE / SELL PE / IRON CONDOR, that action is forced as the visible authority row.

2. **Snapshot-only projection inputs**
   - AI Final projection now reads FII/DII and PCR bias from `market_snapshot.signals`.
   - Reduced direct global fallbacks in top AI card logic.

3. **Snapshot Engine expanded**
   - `smart_money_bias` and `pcr_bias` added to `market_snapshot.signals`.
   - This keeps AI Final, Signal Reliability, and projection on the same snapshot payload.

4. **Signal Reliability fallback improved**
   - Snapshot fallback now includes FII/DII and PCR rows.

5. **Dead helper removed**
   - Removed unused `_v1917_num()` helper from `app.py`.

## Safety
- DhanHQ/API logic untouched.
- Option-chain parsing untouched.
- OI single-source lock untouched.
- Best CE/PE freshness guard untouched.
- Existing engine modules kept.
- Python syntax check passed.

## Remaining safe future cleanup
- Move Strategy Matrix UI helpers out of `app.py` into `strategy_engine.py` or a future `ui_tables.py`.
- Gradually remove old V11/V16/V18 compatibility layers after 2-3 live market tests prove Decision Engine output is stable.
