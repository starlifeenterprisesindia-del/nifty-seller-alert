# V22.4 Operation ZERO MALIK Authority

## Goal
Ensure no old ranker/candidate/freeze logic can behave like a second decision owner.

## Fixes Applied
1. **Legacy V14 freeze** is now evidence-only.
   - It no longer overwrites `final_trade`, strike, hedge, lots, SL, or target.
   - Active stability is handled by `stability_engine` + `advisor_engine`.

2. **Legacy V16.4 unified decision engine** is evidence-only.
   - It no longer overwrites `final_trade` or `confidence`.
   - It no longer reorders strategy rows.

3. **Legacy V16.4 / V20.3 candidate selectors** are evidence-only.
   - They no longer overwrite `best_ce`, `best_pe`, `ce_strike`, or `pe_strike`.

4. **AI_MASTER candidate plans** are rebuilt after the final AI action is known.
   - Candidate selection now happens after AI/advisor action.
   - Old `best_ce/best_pe` cannot act as fallback authority.

5. **AI_MASTER includes trace fields**:
   - `zero_malik_status = ACTIVE`
   - `legacy_ranker_status = EVIDENCE_ONLY_NOT_AUTHORITY`
   - `legacy_candidate_status = EVIDENCE_ONLY_NOT_AUTHORITY`

## Golden Rule 22 Result
- One Advisor / AI_MASTER remains the visible authority.
- Old engines can provide evidence only.
- No old path is allowed to become owner of final advice.

## Syntax Check
Passed: `python -m py_compile app.py`
