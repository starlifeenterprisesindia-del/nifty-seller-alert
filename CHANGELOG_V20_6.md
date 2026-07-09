# V20.6 — OI Single Source Lock

## Main Fix
- OI data now has a single authority inside `snapshot_engine.py`.
- Option-chain row aggregate is preferred over mixed top-level/global OI values.
- Signal Reliability table now prefers `final_decision.intelligence_report` and adds OI Sync row.
- AI Final projection now reads Price Action / Option Bias / Heavyweight Bias from `market_snapshot` first.
- Data Flow monitor now shows `OI OK` or `OI MISMATCH`.

## Why
Earlier risk: one section could read fresh option-chain rows while another section could read old top-level OI/change values. This could make Signal Reliability, AI Final and Best Candidates inconsistent.

## Safety
- If OI top-level totals and current row aggregates mismatch beyond tolerance, app warns with `OI MISMATCH`.
- Snapshot health score is reduced when OI mismatch is detected.
- Syntax check passed.
