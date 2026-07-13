NIFTY SELLER AI V50.7 — RECOVERY CONFIRMATION FIX

PURPOSE
This fixes the exact live-market mismatch seen on 13-07-2026:
- Price below EMA20, EMA50 and VWAP must not be shown as confirmed bullish recovery.
- Strong PE OI/PCR support remains evidence, but cannot independently inflate SELL PE to an executable setup.
- During WAIT, CE/PE rows remain visible as future watchlist candidates, with execution clearly blocked.
- AI_MASTER remains the only final authority.

CHANGED FILES
1. app.py
2. price_action.py
3. strategy_department.py
4. ai_master.py

NOT CHANGED
- DhanHQ/API/data fetch
- Option-chain rows or premium refresh
- Refresh controller
- Position Manager
- FII/DII journal
- Risk rules unrelated to confirmation
- V50 Headquarters, CO, Replay, Learning or PDF engine

HOW TO APPLY ON WINDOWS
1. Put these three patch files inside the extracted Nifty Seller AI project folder.
2. Confirm the same folder contains app.py, price_action.py, strategy_department.py and ai_master.py.
3. Double-click APPLY_V50_7_FIX.bat.
4. A backup folder is created automatically.
5. After PASS, upload the four changed Python files to GitHub.

COMMAND-LINE METHOD
python apply_v50_7_fix.py .

CHECK ONLY, WITHOUT CHANGING FILES
python apply_v50_7_fix.py . --dry-run

EXPECTED BEHAVIOUR FOR THE SHARED 11:54 SNAPSHOT
- Market Outlook: RECOVERY ATTEMPT, normally capped near 55% while confirmation conflicts remain.
- SELL PE: watch/future candidate, normally capped around 60–62 in this setup.
- Final action: WAIT until direction is confirmed.
- Candidate quality can remain high, but it is explicitly not execution confidence.
