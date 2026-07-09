# V22.6 Data Ownership Lock

Goal: after ZERO MALIK, ensure helper indicators/engines cannot feed visible UI through parallel fallback paths.

Changes:
- Evidence table reads AI_MASTER only.
- Projection/reasons read AI_MASTER only.
- Compact risk/OI status reads AI_MASTER trace only.
- Brain Sync trace reads AI_MASTER first.
- Old `_v201_candidate_rows()` wrapper now returns AI_MASTER candidate rows only.
- Developer fake-move detail no longer displays raw best_ce/best_pe safe verdict; it displays AI_MASTER plans.
- Add-position default strikes now use AI_MASTER CE/PE plans instead of raw old best_ce/best_pe.

Kept intentionally:
- Raw option_analysis best_ce/best_pe can exist as raw evidence inside Option Analysis, but not as visible advice/authority.
- Strategy/decision/risk engines still produce reports, but visible top matrices use AI_MASTER.

Syntax: OK.
