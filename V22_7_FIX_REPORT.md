# Nifty Seller AI V22.7 Fix Report

Fixes applied:

1. Position Manager bug fixed: `entry_premium` replaced with `active_entry_price` in the Hold/Exit/Trail SL premium plan block.
2. Data storage made configurable through `NIFTY_DATA_DIR` in Streamlit secrets or environment. Default remains local `data/`.
3. Storage/runtime exceptions for active position, portfolio, and FII/DII journal now go to a Developer Mode error log instead of being silently hidden.
4. `requirements.txt` versions pinned to reduce future Streamlit/pandas/yfinance breaking-change risk.
5. Added `.gitignore` to avoid committing `__pycache__`, compiled files, secrets, and local CSV data.
6. Removed `__pycache__` from the final package.

Important note:
Streamlit Cloud's normal local file system can still reset on redeploy/restart. For strong long-term persistence, set `NIFTY_DATA_DIR` to a mounted persistent path where available, or later upgrade to Google Sheets/Supabase.
