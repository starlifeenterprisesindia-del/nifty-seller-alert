# Operation ZERO MALIK Deep Audit & Fix V22.5

## What was checked
Searched decision-owner patterns across every `.py` file:
- `final_trade`, `final_action`, `final_decision`, `confidence`
- `best_ce`, `best_pe`, `selected_strike`, `strategy`
- old rankers/selectors: `v11_strategy_ranker`, `v164_unified_decision_engine`, `v164_select_best_strikes`, `_v203_candidate_freshness_guard`
- UI display routes after `AI_MASTER` creation

## Findings

### 1. Visible matrices are mostly AI_MASTER routed
- AI Final reads `AI_MASTER`.
- Strategy Matrix reads `AI_MASTER["strategy_rows"]`.
- Candidate Matrix reads `AI_MASTER["candidate_rows"]`.
- Evidence Matrix first reads `AI_MASTER["evidence_rows"]`.

### 2. Old strategy/candidate code still exists, but V22.4 mostly downgraded it to evidence
The following old logic still runs earlier in app.py:
- `v11_strategy_ranker`
- `v164_unified_decision_engine`
- `v164_select_best_strikes`
- `_v203_candidate_freshness_guard`

V22.4 already prevents these from directly owning visible strategy/candidate output.

### 3. Critical remaining issue found
`strategy_engine_report` was built before final Decision/Stability/Advisor output. Then `advisor_engine` could use that earlier strategy report to build its advice line.

Risk:
- AI_MASTER action could be fresh/stable.
- Advisor advice line could still contain stale strike/hedge from an earlier strategy report.

This was the most important remaining possible “malik” leak.

## V22.5 Fix

### Strategy-after-decision lock
Added:
- `_v225_strategy_from_ai_master_plans()`
- `_v225_ai_master_advice()`

AI_MASTER now builds its final strategy and user-facing advice only after:
1. Decision/Stability/Advisor action is known
2. AI_MASTER candidate authority selects CE/PE plan
3. Strategy object is rebuilt from those AI_MASTER-approved plans

## Result

After V22.5:
- AI Final action line does not use stale advisor/strategy report.
- Strategy Matrix and Candidate Matrix still read AI_MASTER only.
- Old rankers/candidate selectors remain evidence/helper only.
- Syntax check OK.

## Next safe cleanup later
- Remove dead `_v201_candidate_rows()` function if confirmed unused.
- Rename old V-title comments later; they are not active decision owners.
