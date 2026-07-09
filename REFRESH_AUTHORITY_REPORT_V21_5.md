# V21.5 Refresh Authority Hotfix

## Goal
Manual refresh, floating refresh and auto-refresh must not use separate paths that can create old data, cache mismatch or different AI outputs.

## Changes
- Added `v215_unified_refresh()` as the single refresh controller.
- Sidebar refresh buttons now call the same controller.
- Floating refresh no longer uses a plain anchor link; it triggers same-page refresh through the same query-param controller.
- Auto-refresh now runs through the same master refresh path using `auto_refresh_tick`.
- Every refresh path clears Streamlit cache once through the master controller.
- Refresh source is stored in `last_refresh_source` for debugging.
- 30-minute auto mode is controlled by `auto_refresh_until` and auto-disables after expiry.

## Golden Rule 22 Check
- No second brain added.
- No AI/strategy/OI logic changed.
- Only refresh routing fixed.
- Same refresh means same snapshot and same AI advisor flow.

## Test
- Python syntax check: OK.
