# Nifty Seller AI — V50.5 Recovery & Data Integrity Fix

**Base source:** `nifty-seller-alert-v50-4-1-top-priority-tables.zip`  
**Architecture preserved:** One verified snapshot → one Commanding Officer case file → one AI_MASTER judgement → one final advisor.

## What was corrected

1. **Live recovery and pullback detection**
   - Added same-day 1/3/5-minute price memory, session high/low tracking and recovery-from-low / pullback-from-high measurements.
   - Recovery is now first-class evidence, so a sharp recovery cannot remain hidden behind an older bearish EMA/VWAP structure.
   - Fresh CE selling is suppressed during an active recovery until rejection/continuation is confirmed.

2. **Option-chain OI + premium interpretation**
   - CE/PE buying, writing, short covering and unwinding are evaluated from both premium movement and OI movement.
   - Near-ATM strikes receive higher relevance.
   - PE support and CE resistance are measured separately.
   - Two-sided writing is classified as a range/conflict instead of being forced into an extreme bearish or bullish score.

3. **Single source-status registry**
   - OI, option chain, VIX and Price Action status now come from one central registry.
   - This removes contradictions such as `OI OK` in one panel and `OI UNKNOWN` in another.
   - Manual VIX is explicitly labelled Manual; it is not presented as an automatic live feed.

4. **Missing Price Action is fail-closed**
   - When automatic candles are unavailable, stale sidebar defaults no longer generate a numeric bearish/bullish Price Action score.
   - The evidence row shows `N/A — UNAVAILABLE / NOT USED`.

5. **Persistent live snapshots**
   - Compact same-day market, projection, option-delta and latest-snapshot state is stored in `.runtime_state`.
   - Browser refresh/reconnect can reuse the latest valid same-day state instead of repeatedly showing “First snapshot”.
   - The transient state is excluded from Git with `.gitignore`.

6. **Data-quality and confidence clarity**
   - Data Quality is now based on usable feeds, not merely imported modules or available credentials.
   - Decision Confidence, Direction Confidence and Data Confidence are shown separately.
   - Candidate values are labelled `Candidate Quality`, not execution confidence.
   - Strategy score is not presented as final authority.

7. **Iron Condor premium label correction**
   - When hedge premiums are unavailable, the displayed amount is labelled **Gross Sold Premium**, not Net Credit.
   - A true net credit must subtract both hedge costs.

8. **Native PDF download**
   - Added a Streamlit `Download Full App PDF Report` control using ReportLab.
   - This creates real PDF bytes inside the app, avoiding dependence on mobile browser Print/Save behaviour.

## Files added

- `live_market_state.py`
- `report_pdf.py`

## Main files updated

- `app.py`
- `ai_master.py`
- `snapshot_engine.py`
- `price_action.py`
- `option_intelligence.py`
- `strategy_department.py`
- `market_behaviour.py`
- `requirements.txt`
- `.gitignore`

## Validation completed

- Full Python compile check for project and `core/` modules.
- Synthetic 95–106 point recovery test: detected as `STRONG_RECOVERY` rather than increasing bearish probability.
- Missing automatic Price Action test: no phantom numeric direction score.
- Balanced CE/PE writing test: classified as two-sided/range evidence.
- PE-support-dominant and CE-resistance-dominant option-chain tests.
- Strategy test during recovery: WAIT/recovery protection outranked fresh continuation selling.
- App runtime smoke test without Dhan credentials: zero unhandled exceptions.
- Fully mocked DhanHQ quote, expiry and option-chain runtime test: option chain loaded with zero errors/exceptions.
- Native PDF generated and rendered successfully as a multi-page document.

## Live-market validation status

V50.5 has passed static, synthetic and mocked-runtime checks. It still requires observation with the user's real DhanHQ feed during live market conditions before any real-money reliance. The app remains a decision-support and risk-control system; it is not a guarantee of prediction accuracy or profitability.
