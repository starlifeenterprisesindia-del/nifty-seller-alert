# Nifty Seller AI — V50.6 Dhan Automatic Feed Fix

## Scope
This patch only repairs the automatic live-data layer. It does not create a second brain or change AI_MASTER authority, strategy rules, thresholds, execution permission, candidate ranking, or the V50.5 recovery/OI logic.

## Repairs
1. India VIX is now requested in the same Dhan Market Quote call as Nifty using IDX_I security ID 21.
2. Automatic Nifty price action now uses Dhan `/charts/intraday` 5-minute candles as the primary source.
3. Yahoo remains a secondary automatic fallback; manual values are used only after both automatic sources fail.
4. Dhan/Yahoo candles are normalized through one calculation path for EMA20, EMA50, VWAP, ATR, previous-day high/low, session high/low, opening range, and the latest 15-minute candle.
5. During market hours, an automatic candle older than 15 minutes is rejected as stale.
6. Source Registry now distinguishes `AUTO_DHAN`, `AUTO_YAHOO`, `MANUAL`, and `UNAVAILABLE`.
7. Live Gate failure text now includes the actual automatic-feed error instead of only a generic unavailable message.
8. Version/UI/report labels updated to V50.6.

## Source order
- Nifty quote: Dhan -> Yahoo -> Manual
- India VIX: Dhan -> Yahoo -> Manual
- Price Action candles: Dhan 5m -> Yahoo 5m -> unavailable/manual according to the existing sidebar mode

## Verification performed
- Python compile check on all project modules.
- Isolated mocked Dhan Market Quote test confirmed request body includes Nifty security ID 13 and India VIX security ID 21.
- Isolated mocked Dhan Intraday test confirmed INDEX/IDX_I/5-minute request parsing and EMA/VWAP/ATR/session calculations.
- Full mocked Streamlit runtime test completed with zero application exceptions using Dhan quote, expiry, option chain, heavyweight, India VIX, and intraday-candle responses.

## Live validation
The real account must still confirm that its Dhan Data API entitlement permits `/charts/intraday` and that the daily access token is current. When successful, the app should show Price Action `AUTO_DHAN`, VIX `AUTO_DHAN`, and the compact status should become LIVE once all other core feeds and snapshot freshness are ready.
