# V22.2 Operation ONE BRAIN Fix

## Goal
Fix audit findings before adding any new intelligence feature.

## Fixed
1. **AI Final Authority Lock**
   - AI Final card now reads only `AI_MASTER`.
   - Removed visible fallback from decision globals/compatibility values.

2. **Strategy Authority Lock**
   - Strategy Matrix displays only `AI_MASTER.strategy_rows`.
   - No independent strategy ranker is displayed in the first four matrices.

3. **Candidate Authority Lock**
   - Candidate Matrix now displays only AI_MASTER-approved candidates.
   - Best CE/PE are locked unless AI_MASTER action approves that side.
   - Old best CE/PE scoring remains raw evidence only; it cannot give visible advice.

4. **Professional Decision Order Applied**
   - Flow is now: Decision/Strategy -> AI_MASTER -> Candidate display.
   - Candidate is not treated as an independent advice source.

5. **Traceability**
   - AI Final shows AI_MASTER version, snapshot trace, data-flow status and OI sync.

## Not Changed
- DhanHQ data logic untouched.
- OI calculations untouched.
- Decision/Stability engines untouched.
- Strategy engine kept as strategy/strike provider.

## Test
- Python syntax check: OK (`python3 -m py_compile *.py`).

## Live Test Required
Refresh 10-20 times in live market. If market has not materially changed, AI Final / Evidence / Strategy / Candidate should remain aligned because all visible advice is routed through `AI_MASTER`.
