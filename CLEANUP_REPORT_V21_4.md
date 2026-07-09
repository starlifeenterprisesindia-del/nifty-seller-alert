# V21.4 Single Advisor Authority

## Goal
Ensure every visible suggestion/advice comes from one final AI authority so the app does not confuse the user with multiple brains.

## What changed
- Added `advisor_engine.py` as a final display/advice authority.
- Advisor reads only the stabilized Decision Engine output plus Strategy/Risk/Intelligence reports as evidence.
- Advisor does not fetch data and does not generate a separate trade signal.
- App now builds one `advisor_report` after Stability/OI/Memory engines are ready.
- AI Final Authority, Signal Reliability, Strategy Matrix and Live Best Candidates now reference the same Single Advisor / same Snapshot.

## Architecture rule
Live Data -> Snapshot Engine -> AI Evidence Engines -> Decision Engine -> Stability Lock -> Advisor Engine -> Top 4 UI Tables

## Safety
- DhanHQ logic untouched.
- Option-chain/OI logic untouched.
- Decision Engine untouched.
- Stability Engine untouched.
- Strategy Engine untouched.
- Syntax check OK.

## Important note
`advisor_engine.py` is not a second brain. It is a display/advice wrapper around the final stabilized Decision Engine. This prevents UI sections from making their own separate advice.
