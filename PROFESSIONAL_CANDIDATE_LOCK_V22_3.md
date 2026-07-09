# V22.3 Professional Candidate Authority Lock

## Goal
Best CE / Best PE should be selected like a professional option seller:

Market/AI decision first -> strategy approval -> candidate filtering -> strike/SL/target.

## Golden Rule 22 Status
- No second brain added.
- Candidate logic does not give visible advice.
- Candidate logic runs only after AI/Decision action is known.
- AI_MASTER remains the only visible authority for AI Final, Strategy and Candidate matrices.

## What Changed
1. Added `V22.3 Professional Candidate Authority` inside `app.py`.
2. Strategy Engine now receives professional candidates instead of raw old `best_ce` / `best_pe`.
3. Best CE/PE old score remains raw evidence only.
4. Candidate Matrix remains locked unless AI_MASTER action approves that side.
5. AI_MASTER version updated to `V22.3_PROFESSIONAL_CANDIDATE_LOCK`.

## Professional Checklist Used
For each approved side, candidate score considers:
- OTM location
- CE above resistance / PE below support
- clean distance from spot
- seller-friendly premium zone
- seller-friendly delta
- OI/writing inference
- liquidity/spread
- volume ratio
- IV/VIX risk sanity

## Important Rule
WAIT means no active candidate. Candidate is selected only after strategy permission.

## Syntax Check
`python3 -m py_compile *.py` passed.
