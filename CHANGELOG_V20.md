# CHANGELOG — V20 Clean Edition

Generated: 09-07-2026 08:10:56 AM

## Goal
Clean the app into a focused, mobile-friendly trading terminal.

## Removed / hidden from normal Trading UI
- V19.17 duplicate top command center sections
- Single Brain Audit duplicate area
- AI Brain + Decision Authority duplicate area
- AI Brain Details / Developer Reasoning
- AI Intelligence Explanation panel
- Strategy Engine Plan duplicate panel
- Decision Engine Action Plan duplicate panel
- Decision Engine Ticket duplicate panel
- Premium Quality separate panel
- Risk Engine Explanation details
- V18.2 old debug reasons
- Lower duplicate Seller AI Radar
- Trade checklist debug panel

## Kept
- Live Refresh + Status
- Risk Summary
- OI Flow Engine summary
- Live Health Monitor
- Final AI Decision compact card
- Signal Reliability Table
- Smart Strategy Matrix
- India VIX Range
- Live CE/PE Candidate Cards
- Active Positions + Add Position
- Position Manager
- Option Chain AI Engine
- Top-5 Heavyweight Engine
- News Risk Engine
- FII/DII Smart Money
- Dhan Diagnostics

## Logic Safety
- DhanHQ data logic untouched
- Decision Engine logic untouched
- Strategy Engine logic untouched
- Risk/OI/Memory/Stability engines untouched
- Only UI duplicate/debug sections cleaned

## Upload
Replace GitHub files with this ZIP. Keep Streamlit Secrets unchanged.

## V20.1 — AI First Compact UI Cleanup
- Added floating manual Refresh button independent from auto-refresh.
- Redesigned top screen around AI FINAL AUTHORITY.
- Added compact market outlook: UP/DOWN probability, last-refresh change, top 3 factors.
- Kept only 4 main screens: AI Final Authority, Signal Reliability, Smart Strategy Matrix, Live Best Candidates.
- Replaced old Best CE/PE cards with compact Live Best Candidates table.
- Removed Candidate Verdict duplicate UI from normal screen.
- Removed big News Risk card from normal screen; kept it in Developer Mode.
- Converted health/risk/status into compact one-line status bars.
- Syntax checked all Python files with py_compile.

## V20.4 — Single Brain Sync + Freshness Audit
- Fixed AI Final projection/top-factor helpers using `locals()` inside functions, which could read empty local scope and show stale/neutral outlook.
- Added Single Brain Sync stamp for top 4 tables: AI Final Authority, Signal Reliability, Smart Strategy Matrix, Live Best Candidates.
- Added freshness caution when snapshot/option-chain/decision report is weak or missing.
- Confirmed top tables now display from the same snapshot/Decision Engine/Stability Lock authority.

## V20.5 — Single Snapshot Data Flow Monitor
- Upgraded Snapshot Engine to V20.5 Single Snapshot Authority.
- Removed `locals()` from the main Snapshot Engine call; snapshot now receives one explicit context only.
- Added Snapshot ID + option-chain signature for each refresh.
- Added Data Flow Monitor: checks option-chain live status, row count, repeated OC signature, repeated snapshot ID, and snapshot health.
- Top 4 tables now show the same SNAP ID / Data Flow status so stale or split data can be caught immediately.
- AI Final Authority now displays compact Brain Sync with SNAP short ID, Data Flow status, snapshot health, and OC rows.
- Data Flow compact line added near top status: Fresh/Caution/Weak, SNAP ID, OC rows, repeated OC count, Brain Sync OK.
- Best CE/PE remains linked to current option-chain row; data flow warnings appear if OC data is not refreshing.
- Syntax checked all Python files with py_compile.
