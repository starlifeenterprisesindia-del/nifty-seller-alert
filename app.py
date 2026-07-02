import yfinance as yf
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# =========================================================
# NIFTY SELLER AI DASHBOARD V4
# Clean Professional Version
# =========================================================

st.set_page_config(
    page_title="Nifty Seller AI Dashboard V4",
    page_icon="🧠",
    layout="wide"
)

# =========================================================
# STYLE
# =========================================================
st.markdown("""
<style>
.main-title {
    font-size: 2.15rem;
    font-weight: 850;
    margin-bottom: 0.2rem;
}
.sub-title {
    font-size: 0.96rem;
    opacity: 0.75;
    margin-bottom: 1.1rem;
}
.advisor-card {
    padding: 24px;
    border-radius: 20px;
    margin-bottom: 18px;
    border: 1px solid rgba(255,255,255,0.12);
    box-shadow: 0 8px 26px rgba(0,0,0,0.18);
}
.card-green {
    background: linear-gradient(135deg, rgba(0,135,75,0.96), rgba(0,82,58,0.96));
}
.card-red {
    background: linear-gradient(135deg, rgba(160,38,38,0.96), rgba(92,24,24,0.96));
}
.card-yellow {
    background: linear-gradient(135deg, rgba(170,126,22,0.96), rgba(105,76,18,0.96));
}
.card-wait {
    background: linear-gradient(135deg, rgba(82,88,99,0.96), rgba(43,48,58,0.96));
}
.advisor-card h1 {
    color: white;
    font-size: 3.1rem;
    margin: 4px 0 8px 0;
}
.advisor-card h3 {
    color: white;
    margin: 0;
    opacity: 0.96;
}
.advisor-card p {
    color: white;
    font-size: 1rem;
    margin: 7px 0;
}
.ribbon {
    padding: 11px 14px;
    border-radius: 14px;
    background: rgba(255,255,255,0.075);
    border: 1px solid rgba(255,255,255,0.10);
    text-align: center;
    font-weight: 750;
    margin-bottom: 8px;
}
.small-note {
    opacity: 0.76;
    font-size: 0.88rem;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# HELPERS
# =========================================================
# =========================================================
# =========================================================
# LIVE DATA - FEATURE 1: LIVE NIFTY PRICE
# =========================================================
@st.cache_data(ttl=30)
def get_live_nifty_price():
    """
    Fetch near-live NIFTY 50 price from Yahoo Finance using yfinance.
    Ticker: ^NSEI
    Cache TTL: 30 seconds
    """
    try:
        ticker = yf.Ticker("^NSEI")

        intraday = ticker.history(period="2d", interval="1m")

        if intraday is None or intraday.empty:
            intraday = ticker.history(period="5d", interval="5m")

        if intraday is None or intraday.empty:
            return {
                "success": False,
                "price": None,
                "change": None,
                "change_pct": None,
                "last_update": "Not Available",
                "message": "Live Nifty data not available right now."
            }

        intraday = intraday.dropna()
        latest_row = intraday.iloc[-1]
        live_price = float(latest_row["Close"])

        daily = ticker.history(period="7d", interval="1d")
        previous_close = None

        if daily is not None and not daily.empty:
            daily = daily.dropna()
            if len(daily) >= 2:
                previous_close = float(daily["Close"].iloc[-2])
            elif len(daily) == 1:
                previous_close = float(daily["Close"].iloc[-1])

        if previous_close:
            change = live_price - previous_close
            change_pct = (change / previous_close) * 100
        else:
            change = 0.0
            change_pct = 0.0

        last_time = intraday.index[-1]

        try:
            last_update = last_time.tz_convert("Asia/Kolkata").strftime("%d-%m-%Y %I:%M:%S %p")
        except Exception:
            last_update = str(last_time)

        return {
            "success": True,
            "price": round(live_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "last_update": last_update,
            "message": "Live Nifty price fetched successfully."
        }

    except Exception as e:
        return {
            "success": False,
            "price": None,
            "change": None,
            "change_pct": None,
            "last_update": "Error",
            "message": f"Live Nifty fetch error: {e}"
        }


# =========================================================
# LIVE DATA - FEATURE 2: LIVE INDIA VIX
# =========================================================
@st.cache_data(ttl=60)
def get_live_india_vix():
    """
    Fetch near-live India VIX from Yahoo Finance using yfinance.
    Ticker: ^INDIAVIX
    Cache TTL: 60 seconds
    """
    try:
        ticker = yf.Ticker("^INDIAVIX")
        intraday = ticker.history(period="2d", interval="1m")

        if intraday is None or intraday.empty:
            intraday = ticker.history(period="5d", interval="5m")

        if intraday is None or intraday.empty:
            daily = ticker.history(period="7d", interval="1d")

            if daily is None or daily.empty:
                return {
                    "success": False,
                    "vix": None,
                    "change": None,
                    "change_pct": None,
                    "last_update": "Not Available",
                    "message": "Live India VIX data not available right now."
                }

            intraday = daily

        intraday = intraday.dropna()
        latest_row = intraday.iloc[-1]
        live_vix = float(latest_row["Close"])

        daily = ticker.history(period="7d", interval="1d")
        previous_close = None

        if daily is not None and not daily.empty:
            daily = daily.dropna()
            if len(daily) >= 2:
                previous_close = float(daily["Close"].iloc[-2])
            elif len(daily) == 1:
                previous_close = float(daily["Close"].iloc[-1])

        if previous_close:
            change = live_vix - previous_close
            change_pct = (change / previous_close) * 100
        else:
            change = 0.0
            change_pct = 0.0

        last_time = intraday.index[-1]

        try:
            last_update = last_time.tz_convert("Asia/Kolkata").strftime("%d-%m-%Y %I:%M:%S %p")
        except Exception:
            last_update = str(last_time)

        return {
            "success": True,
            "vix": round(live_vix, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "last_update": last_update,
            "message": "Live India VIX fetched successfully."
        }

    except Exception as e:
        return {
            "success": False,
            "vix": None,
            "change": None,
            "change_pct": None,
            "last_update": "Error",
            "message": f"Live India VIX fetch error: {e}"
        }


# =========================================================
# LIVE DATA - FEATURE 3: LIVE OPTION CHAIN / OI / PCR
# =========================================================
@st.cache_data(ttl=60)
def get_live_option_chain(spot_price=None, strike_gap=50, strikes_each_side=4):
    """
    Fetch live NIFTY option chain from NSE.
    It returns OI, OI Change, PCR, support/resistance and suggested strikes.
    If NSE blocks or data is unavailable, it returns success=False.
    """
    try:
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.nseindia.com/option-chain",
            "Connection": "keep-alive",
        }

        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        response = session.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return {
                "success": False,
                "message": f"NSE option chain request failed. Status: {response.status_code}"
            }

        data = response.json()

        records = data.get("records", {})
        option_data = records.get("data", [])

        if not option_data:
            return {
                "success": False,
                "message": "NSE option chain data empty."
            }

        underlying_value = records.get("underlyingValue", None)

        if underlying_value is None:
            underlying_value = spot_price

        if underlying_value is None:
            return {
                "success": False,
                "message": "Underlying value not available."
            }

        underlying_value = float(underlying_value)

        expiry_dates = records.get("expiryDates", [])
        selected_expiry = expiry_dates[0] if expiry_dates else None

        if not selected_expiry:
            return {
                "success": False,
                "message": "Expiry date not available."
            }

        atm_strike = int(round(underlying_value / strike_gap) * strike_gap)

        lower_strike = atm_strike - (strikes_each_side * strike_gap)
        upper_strike = atm_strike + (strikes_each_side * strike_gap)

        filtered_rows = []

        for row in option_data:
            if row.get("expiryDate") != selected_expiry:
                continue

            strike_price = row.get("strikePrice")

            if strike_price is None:
                continue

            if lower_strike <= int(strike_price) <= upper_strike:
                ce = row.get("CE", {})
                pe = row.get("PE", {})

                filtered_rows.append({
                    "strike": int(strike_price),
                    "ce_oi": int(ce.get("openInterest", 0) or 0),
                    "pe_oi": int(pe.get("openInterest", 0) or 0),
                    "ce_change_oi": int(ce.get("changeinOpenInterest", 0) or 0),
                    "pe_change_oi": int(pe.get("changeinOpenInterest", 0) or 0),
                    "ce_volume": int(ce.get("totalTradedVolume", 0) or 0),
                    "pe_volume": int(pe.get("totalTradedVolume", 0) or 0),
                })

        if not filtered_rows:
            return {
                "success": False,
                "message": "No option chain rows found near ATM."
            }

        total_call_oi = sum(row["ce_oi"] for row in filtered_rows)
        total_put_oi = sum(row["pe_oi"] for row in filtered_rows)

        call_oi_change = sum(row["ce_change_oi"] for row in filtered_rows)
        put_oi_change = sum(row["pe_change_oi"] for row in filtered_rows)

        pcr_value = total_put_oi / total_call_oi if total_call_oi else 0.0

        ce_candidates = [row for row in filtered_rows if row["strike"] >= atm_strike]
        pe_candidates = [row for row in filtered_rows if row["strike"] <= atm_strike]

        strongest_ce = max(ce_candidates, key=lambda x: x["ce_oi"], default=None)
        strongest_pe = max(pe_candidates, key=lambda x: x["pe_oi"], default=None)

        ce_sell_strike = strongest_ce["strike"] if strongest_ce else atm_strike + strike_gap
        pe_sell_strike = strongest_pe["strike"] if strongest_pe else atm_strike - strike_gap

        last_update = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M:%S %p")

        return {
            "success": True,
            "underlying": round(underlying_value, 2),
            "expiry": selected_expiry,
            "atm_strike": atm_strike,
            "call_oi_change": int(call_oi_change),
            "put_oi_change": int(put_oi_change),
            "total_call_oi": int(total_call_oi),
            "total_put_oi": int(total_put_oi),
            "pcr": round(pcr_value, 2),
            "ce_sell_strike": int(ce_sell_strike),
            "pe_sell_strike": int(pe_sell_strike),
            "rows_count": len(filtered_rows),
            "last_update": last_update,
            "message": "Live option chain fetched successfully."
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Live option chain fetch error: {e}"
        }
def clamp(value, low=0, high=98):
    """Convert score to safe integer percentage."""
    try:
        value = int(round(float(value)))
    except Exception:
        value = 0

    return max(low, min(high, value))


def safe_divide(a, b, default=0.0):
    """Safely divide two numbers."""
    try:
        if b == 0:
            return default
        return a / b
    except Exception:
        return default


def score_label(score):
    """Convert numeric score into text label."""
    score = clamp(score)

    if score >= 75:
        return "Strong"
    if score >= 60:
        return "Positive"
    if score >= 45:
        return "Neutral"
    if score >= 30:
        return "Weak"

    return "Very Weak"


def get_market_status():
    """Return current market status based on India time."""
    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)

    is_weekday = now.weekday() < 5
    is_open = is_weekday and open_time <= now <= close_time

    day_name = now.strftime("%A")
    market_text = "Market Open" if is_open else "Market Closed"
    expiry_text = "Weekly Expiry" if day_name == "Thursday" else "Normal Day"

    return now, day_name, market_text, expiry_text

# =========================================================
# SIDEBAR INPUTS
# =========================================================
st.sidebar.title("⚙️ V4 Inputs")

with st.sidebar.expander("1️⃣ Market Snapshot", expanded=True):
    live_nifty_data = get_live_nifty_price()

    if not isinstance(live_nifty_data, dict):
        live_nifty_data = {
            "success": False,
            "price": None,
            "change": None,
            "change_pct": None,
            "last_update": "Not Available",
            "message": "Invalid live Nifty data"
        }

    use_live_nifty = st.checkbox("Use Live Nifty Price", value=True)

    manual_price = st.number_input(
        "Manual Nifty Price",
        value=25000.0,
        step=1.0
    )

    if use_live_nifty and live_nifty_data.get("success", False):
        price = live_nifty_data["price"]
        st.success(
            f"Live Nifty: {price} | "
            f"{live_nifty_data['change']} pts "
            f"({live_nifty_data['change_pct']}%)"
        )
        st.caption(f"Last Update: {live_nifty_data['last_update']}")
    else:
        price = manual_price
        if use_live_nifty:
            st.warning("Live Nifty unavailable. Manual price is being used.")

    ema20 = st.number_input("EMA 20", value=24950.0, step=1.0)
    ema50 = st.number_input("EMA 50", value=24900.0, step=1.0)
    vwap = st.number_input("VWAP", value=24940.0, step=1.0)
    atr5 = st.number_input("ATR 5 Min", value=45.0, step=1.0)
    atr15 = st.number_input("ATR 15 Min", value=90.0, step=1.0)

    live_vix_data = get_live_india_vix()

    if not isinstance(live_vix_data, dict):
        live_vix_data = {
            "success": False,
            "vix": None,
            "change": None,
            "change_pct": None,
            "last_update": "Not Available",
            "message": "Invalid live VIX data"
        }

    use_live_vix = st.checkbox("Use Live India VIX", value=True)

    manual_vix = st.number_input(
        "Manual India VIX",
        value=13.5,
        step=0.1
    )

    vix = manual_vix

    if use_live_vix and live_vix_data.get("success", False):
        vix = live_vix_data["vix"]
        st.success(
            f"Live India VIX: {vix} | "
            f"{live_vix_data['change']} "
            f"({live_vix_data['change_pct']}%)"
        )
        st.caption(f"VIX Last Update: {live_vix_data['last_update']}")
    else:
        if use_live_vix:
            st.warning("Live India VIX unavailable. Manual VIX is being used.")


with st.sidebar.expander("2️⃣ Option Chain / OI / PCR", expanded=True):
    call_oi_change = st.number_input("Call OI Change", value=150000, step=1000)
    put_oi_change = st.number_input("Put OI Change", value=180000, step=1000)
    total_call_oi = st.number_input("Total Call OI", value=1500000, step=10000)
    total_put_oi = st.number_input("Total Put OI", value=1800000, step=10000)
    ce_strike = st.number_input("CE Sell Strike", value=25100, step=50)
    pe_strike = st.number_input("PE Sell Strike", value=24900, step=50)
    hedge_gap = st.number_input("Hedge Gap", value=100, step=50)


with st.sidebar.expander("3️⃣ Price Action / Support-Resistance", expanded=False):
    previous_day_high = st.number_input("Previous Day High", value=25150.0, step=1.0)
    previous_day_low = st.number_input("Previous Day Low", value=24850.0, step=1.0)
    today_high = st.number_input("Today High", value=25080.0, step=1.0)
    today_low = st.number_input("Today Low", value=24920.0, step=1.0)
    opening_range_high = st.number_input("Opening Range High", value=25060.0, step=1.0)
    opening_range_low = st.number_input("Opening Range Low", value=24940.0, step=1.0)


with st.sidebar.expander("4️⃣ Volume AI", expanded=False):
    current_volume = st.number_input("Current Volume", value=120000, step=1000)
    average_volume = st.number_input("Average Volume", value=80000, step=1000)
    breakout_type = st.selectbox(
        "Breakout / Breakdown",
        ["No Breakout", "Resistance Breakout", "Support Breakdown"]
    )


with st.sidebar.expander("5️⃣ FII / DII Smart Money", expanded=False):
    fii_today = st.number_input("FII Today ₹ Cr", value=0.0, step=100.0)
    dii_today = st.number_input("DII Today ₹ Cr", value=0.0, step=100.0)
    fii_5day = st.number_input("FII 5 Day Net ₹ Cr", value=0.0, step=100.0)
    dii_5day = st.number_input("DII 5 Day Net ₹ Cr", value=0.0, step=100.0)
    fii_index_futures_bias = st.selectbox(
        "FII Index Futures Bias",
        ["Neutral", "Bullish", "Bearish"]
    )


with st.sidebar.expander("6️⃣ Confirmation Panel", expanded=False):
    rsi = st.number_input("RSI", value=55.0, step=0.5)
    macd = st.selectbox("MACD", ["Neutral", "Bullish", "Bearish"])
    bollinger = st.selectbox(
        "Bollinger Band",
        ["Normal", "Squeeze", "Upper Breakout", "Lower Breakdown"]
    )
    supertrend = st.selectbox("Supertrend", ["Neutral", "Bullish", "Bearish"])


with st.sidebar.expander("7️⃣ Risk / Position", expanded=True):
    news_risk = st.selectbox("News Risk", ["Low", "Medium", "High"])
    capital = st.number_input("Capital ₹", value=500000, step=10000)
    margin_per_lot = st.number_input("Margin Per Lot ₹", value=100000, step=5000)
    current_lots = st.number_input("Current Lots Holding", value=0, step=1)
    lot_size = st.number_input("Lot Size", value=50, step=25)
# CORE CALCULATIONS
# =========================================================
pcr = safe_divide(total_put_oi, total_call_oi, 0.0)
rvol = safe_divide(current_volume, average_volume, 0.0)

support_levels = [previous_day_low, today_low, opening_range_low]
resistance_levels = [previous_day_high, today_high, opening_range_high]

nearest_support = max([x for x in support_levels if x <= price], default=min(support_levels))
nearest_resistance = min([x for x in resistance_levels if x >= price], default=max(resistance_levels))

support_distance = max(price - nearest_support, 0)
resistance_distance = max(nearest_resistance - price, 0)


# =========================================================
# SCORE ENGINE
# =========================================================

# 1. Price Action
price_action_score = 50
price_action_score += 10 if price > ema20 else -10
price_action_score += 10 if price > ema50 else -10
price_action_score += 15 if price > vwap else -15
price_action_score += 10 if ema20 > ema50 else -10

if price > opening_range_high:
    price_action_score += 8
elif price < opening_range_low:
    price_action_score -= 8

price_action_score = clamp(price_action_score)

# 2. Support / Resistance
sr_score = 50

if support_distance <= 30:
    sr_score += 25
elif support_distance <= 60:
    sr_score += 10

if resistance_distance <= 30:
    sr_score -= 25
elif resistance_distance <= 60:
    sr_score -= 10

if price > opening_range_high:
    sr_score += 10
elif price < opening_range_low:
    sr_score -= 10

sr_score = clamp(sr_score)

# 3. Volume
volume_score = 50

if rvol >= 2:
    volume_score += 30
elif rvol >= 1.5:
    volume_score += 20
elif rvol >= 1:
    volume_score += 5
else:
    volume_score -= 20

if breakout_type in ["Resistance Breakout", "Support Breakdown"] and rvol >= 1.5:
    volume_score += 12

volume_score = clamp(volume_score)

# 4. OI
oi_score = 50

if put_oi_change > call_oi_change:
    oi_score += 25
elif call_oi_change > put_oi_change:
    oi_score -= 25

oi_diff_ratio = safe_divide(
    abs(put_oi_change - call_oi_change),
    max(abs(call_oi_change), abs(put_oi_change)),
    0.0
)

if oi_diff_ratio >= 0.35:
    oi_score += 10 if put_oi_change > call_oi_change else -10

oi_score = clamp(oi_score)

# 5. PCR
pcr_score = 50

if 0.95 <= pcr <= 1.20:
    pcr_score += 20
elif 1.20 < pcr <= 1.45:
    pcr_score += 10
elif pcr > 1.45:
    pcr_score -= 5
elif 0.75 <= pcr < 0.95:
    pcr_score -= 10
else:
    pcr_score -= 25

pcr_score = clamp(pcr_score)

# 6. VIX
vix_score = 50

if vix <= 13:
    vix_score += 25
elif vix <= 15:
    vix_score += 15
elif vix <= 18:
    vix_score -= 5
else:
    vix_score -= 30

vix_score = clamp(vix_score)

# 7. FII / DII Smart Money
smart_money_score = 50
smart_money_score += 15 if fii_today > 0 else -15 if fii_today < 0 else 0
smart_money_score += 8 if dii_today > 0 else -8 if dii_today < 0 else 0
smart_money_score += 15 if fii_5day > 0 else -15 if fii_5day < 0 else 0
smart_money_score += 6 if dii_5day > 0 else -6 if dii_5day < 0 else 0

if fii_index_futures_bias == "Bullish":
    smart_money_score += 14
elif fii_index_futures_bias == "Bearish":
    smart_money_score -= 14

smart_money_score = clamp(smart_money_score)

# 8. News Risk
news_score = 50

if news_risk == "Low":
    news_score += 25
elif news_risk == "Medium":
    news_score -= 5
else:
    news_score -= 35

news_score = clamp(news_score)

# 9. Confirmation Panel
confirmation_score = 50

if 45 <= rsi <= 65:
    confirmation_score += 10
elif rsi > 70 or rsi < 30:
    confirmation_score -= 10

if macd == "Bullish":
    confirmation_score += 10
elif macd == "Bearish":
    confirmation_score -= 10

if bollinger == "Upper Breakout":
    confirmation_score += 8
elif bollinger == "Lower Breakdown":
    confirmation_score -= 8
elif bollinger == "Squeeze":
    confirmation_score -= 5

if supertrend == "Bullish":
    confirmation_score += 12
elif supertrend == "Bearish":
    confirmation_score -= 12

confirmation_score = clamp(confirmation_score)


# =========================================================
# FINAL DECISION ENGINE
# =========================================================
bullish_probability = (
    price_action_score * 0.20 +
    sr_score * 0.15 +
    volume_score * 0.10 +
    oi_score * 0.15 +
    pcr_score * 0.12 +
    vix_score * 0.10 +
    smart_money_score * 0.10 +
    news_score * 0.05 +
    confirmation_score * 0.03
)

bearish_probability = (
    (98 - price_action_score) * 0.20 +
    (98 - sr_score) * 0.15 +
    volume_score * 0.10 +
    (98 - oi_score) * 0.15 +
    (98 - pcr_score) * 0.12 +
    vix_score * 0.10 +
    (98 - smart_money_score) * 0.10 +
    news_score * 0.05 +
    (98 - confirmation_score) * 0.03
)

bullish_probability = clamp(bullish_probability)
bearish_probability = clamp(bearish_probability)

signal_gap = abs(bullish_probability - bearish_probability)
best_probability = max(bullish_probability, bearish_probability)

high_risk_block = news_risk == "High" or vix > 18

if high_risk_block:
    final_trade = "WAIT"
    probability = clamp(best_probability - 20)
elif signal_gap < 7:
    final_trade = "WAIT"
    probability = best_probability
elif bullish_probability >= bearish_probability and bullish_probability >= 60:
    final_trade = "SELL PE"
    probability = bullish_probability
elif bearish_probability > bullish_probability and bearish_probability >= 60:
    final_trade = "SELL CE"
    probability = bearish_probability
else:
    final_trade = "WAIT"
    probability = best_probability

confidence = clamp((signal_gap * 1.2) + (probability * 0.55))

if final_trade == "SELL PE":
    selected_strike = f"{int(pe_strike)} PE"
    hedge = f"{int(pe_strike - hedge_gap)} PE"
elif final_trade == "SELL CE":
    selected_strike = f"{int(ce_strike)} CE"
    hedge = f"{int(ce_strike + hedge_gap)} CE"
else:
    selected_strike = "No Strike"
    hedge = "No Hedge"

max_lots = int(capital / margin_per_lot) if margin_per_lot > 0 else 0

if final_trade == "WAIT":
    suggested_lots = 0
elif probability >= 88 and news_risk == "Low" and vix <= 14:
    suggested_lots = max_lots
elif probability >= 75:
    suggested_lots = max(1, int(max_lots * 0.60))
elif probability >= 60:
    suggested_lots = max(1, int(max_lots * 0.30))
else:
    suggested_lots = 0

sl_points = round(max(atr5 * 1.5, 20), 2)
target_points = round(max(atr5 * 1.0, 15), 2)

now, day_name, market_text, expiry_text = get_market_status()

if vix <= 14:
    vix_text = "VIX Low"
elif vix <= 18:
    vix_text = "VIX Normal"
else:
    vix_text = "VIX High"


# =========================================================
# HEADER
# =========================================================
st.markdown("<div class='main-title'>🧠 Nifty Seller AI Dashboard V4</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-title'>Option Seller Decision Engine: Price Action + Support/Resistance + Volume + OI + PCR + VIX + FII/DII + News</div>",
    unsafe_allow_html=True
)

# =========================================================
# TOP STATUS RIBBON
# =========================================================
r1, r2, r3, r4, r5 = st.columns(5)
r1.markdown(f"<div class='ribbon'>{market_text}</div>", unsafe_allow_html=True)
r2.markdown(f"<div class='ribbon'>{expiry_text}</div>", unsafe_allow_html=True)
r3.markdown(f"<div class='ribbon'>News: {news_risk}</div>", unsafe_allow_html=True)
r4.markdown(f"<div class='ribbon'>{vix_text}</div>", unsafe_allow_html=True)
r5.markdown(f"<div class='ribbon'>PCR: {pcr:.2f}</div>", unsafe_allow_html=True)

# =========================================================
# FINAL ADVISOR CARD
# =========================================================
if final_trade == "SELL PE":
    card_class = "card-green"
    status_text = "🟢 Bullish Option Selling Setup"
elif final_trade == "SELL CE":
    card_class = "card-red"
    status_text = "🔴 Bearish Option Selling Setup"
elif probability >= 55:
    card_class = "card-yellow"
    status_text = "🟡 Mixed Setup - Wait"
else:
    card_class = "card-wait"
    status_text = "⚪ No Clear Trade"

st.markdown(f"""
<div class="advisor-card {card_class}">
    <h3>{status_text}</h3>
    <h1>{final_trade}</h1>
    <p><b>Trade Probability:</b> {probability}% &nbsp;&nbsp; | &nbsp;&nbsp; <b>AI Confidence:</b> {confidence}%</p>
    <p><b>Strike:</b> {selected_strike} &nbsp;&nbsp; | &nbsp;&nbsp; <b>Hedge:</b> {hedge}</p>
    <p><b>Suggested Lots:</b> {suggested_lots} / {max_lots} &nbsp;&nbsp; | &nbsp;&nbsp; <b>SL:</b> {sl_points} pts &nbsp;&nbsp; | &nbsp;&nbsp; <b>Target:</b> {target_points} pts</p>
</div>
""", unsafe_allow_html=True)

st.progress(probability)

if final_trade == "WAIT":
    st.warning("AI Advice: Clear edge nahi hai. Is setup me trade avoid karo ya fresh confirmation ka wait karo.")
elif final_trade == "SELL PE":
    st.success("AI Advice: Bullish bias hai. PE sell sirf hedge aur strict SL ke saath.")
else:
    st.error("AI Advice: Bearish bias hai. CE sell sirf hedge aur strict SL ke saath.")


# =========================================================
# WHY AI
# =========================================================
why = []

if price_action_score >= 65:
    why.append("Price Action bullish hai: price EMA/VWAP ke upar hai.")
elif price_action_score <= 35:
    why.append("Price Action bearish hai: price EMA/VWAP ke neeche hai.")

if sr_score >= 65:
    why.append("Support zone favourable hai.")
elif sr_score <= 35:
    why.append("Resistance pressure / S-R risk high hai.")

if volume_score >= 65:
    why.append("Volume confirmation strong hai.")
elif volume_score <= 35:
    why.append("Volume weak hai, false move ka risk hai.")

if oi_score >= 65:
    why.append("Put OI stronger hai, bullish support mil raha hai.")
elif oi_score <= 35:
    why.append("Call OI stronger hai, bearish pressure mil raha hai.")

if pcr_score >= 65:
    why.append("PCR supportive zone me hai.")
elif pcr_score <= 35:
    why.append("PCR weak/risky zone me hai.")

if vix_score <= 35:
    why.append("VIX high hai, option selling risk zyada hai.")

if smart_money_score >= 65:
    why.append("FII/DII smart money supportive hai.")
elif smart_money_score <= 35:
    why.append("FII/DII smart money weak hai.")

if news_score <= 35:
    why.append("News risk high hai, trade avoid better.")

with st.expander("✅ Why AI gave this decision", expanded=True):
    if why:
        for item in why:
            st.write("✔", item)
    else:
        st.write("Signals mixed hain. Isliye AI aggressive trade nahi de raha.")


# =========================================================
# AI RADAR
# =========================================================
st.markdown("## 📡 AI Radar")

a1, a2, a3 = st.columns(3)

with a1:
    st.metric("Price Action", f"{price_action_score}%", score_label(price_action_score))
    st.progress(price_action_score)
    st.metric("Support / Resistance", f"{sr_score}%", score_label(sr_score))
    st.progress(sr_score)

with a2:
    st.metric("Volume AI", f"{volume_score}%", f"{rvol:.2f}x RVOL")
    st.progress(volume_score)
    st.metric("OI Change", f"{oi_score}%", score_label(oi_score))
    st.progress(oi_score)

with a3:
    st.metric("PCR", f"{pcr_score}%", f"{pcr:.2f}")
    st.progress(pcr_score)
    risk_combo = clamp((vix_score + news_score) / 2)
    st.metric("VIX + News Risk", f"{risk_combo}%", f"VIX {vix:.2f}")
    st.progress(risk_combo)

b1, b2 = st.columns(2)

with b1:
    st.metric("FII / DII Smart Money", f"{smart_money_score}%", score_label(smart_money_score))
    st.progress(smart_money_score)

with b2:
    st.metric("Confirmation Panel", f"{confirmation_score}%", score_label(confirmation_score))
    st.progress(confirmation_score)


# =========================================================
# DASHBOARD SECTIONS
# =========================================================
with st.expander("📊 Market Snapshot", expanded=True):
    m1, m2, m3, m4 = st.columns(4)

    if use_live_nifty and live_nifty_data["success"]:
        m1.metric(
            "Nifty Live",
            f"{price:.2f}",
            f"{live_nifty_data['change']} pts / {live_nifty_data['change_pct']}%"
        )
    else:
        m1.metric("Nifty Manual", f"{price:.2f}")

    m2.metric("EMA20", f"{ema20:.2f}")
    m3.metric("EMA50", f"{ema50:.2f}")
    m4.metric("VWAP", f"{vwap:.2f}")

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("ATR 5m", f"{atr5:.2f}")
    m6.metric("ATR 15m", f"{atr15:.2f}")
    m7.metric("India VIX", f"{vix:.2f}")
    m8.metric("News Risk", news_risk)
with st.expander("📍 Support / Resistance AI", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nearest Support", f"{nearest_support:.2f}")
    c2.metric("Support Distance", f"{support_distance:.2f} pts")
    c3.metric("Nearest Resistance", f"{nearest_resistance:.2f}")
    c4.metric("Resistance Distance", f"{resistance_distance:.2f} pts")

    if support_distance <= 30 and final_trade == "SELL PE":
        st.success("Price support ke paas hai. PE selling setup better ho sakta hai.")
    elif resistance_distance <= 30 and final_trade == "SELL PE":
        st.error("Price resistance ke paas hai. PE sell risky ho sakta hai.")
    elif resistance_distance <= 30 and final_trade == "SELL CE":
        st.success("Price resistance ke paas hai. CE selling setup better ho sakta hai.")
    elif support_distance <= 30 and final_trade == "SELL CE":
        st.error("Price support ke paas hai. CE sell risky ho sakta hai.")
    else:
        st.info("Price middle zone me hai. Breakout/breakdown confirmation important hai.")

with st.expander("📊 Option Chain / Strike & Hedge Finder", expanded=False):
    oc1, oc2, oc3, oc4 = st.columns(4)
    oc1.metric("PCR", f"{pcr:.2f}")
    oc2.metric("Put OI Change", f"{put_oi_change:,}")
    oc3.metric("Call OI Change", f"{call_oi_change:,}")
    oc4.metric(
        "OI Bias",
        "Bullish" if put_oi_change > call_oi_change else "Bearish" if call_oi_change > put_oi_change else "Neutral"
    )

    if final_trade == "SELL PE":
        st.success(f"Recommended: Sell {int(pe_strike)} PE")
        st.info(f"Hedge: Buy {int(pe_strike - hedge_gap)} PE")
    elif final_trade == "SELL CE":
        st.error(f"Recommended: Sell {int(ce_strike)} CE")
        st.info(f"Hedge: Buy {int(ce_strike + hedge_gap)} CE")
    else:
        st.warning("No strike selected because final decision is WAIT.")

with st.expander("📊 Volume AI", expanded=False):
    st.write(f"Relative Volume: **{rvol:.2f}x**")
    st.write(f"Breakout Type: **{breakout_type}**")

    if rvol >= 2:
        st.success("Strong volume spike detected.")
    elif rvol >= 1.5:
        st.warning("Volume above average hai.")
    elif rvol >= 1:
        st.info("Volume normal hai.")
    else:
        st.error("Volume weak hai.")

with st.expander("🏛️ FII / DII Smart Money", expanded=False):
    sm1, sm2, sm3, sm4 = st.columns(4)
    sm1.metric("FII Today", f"₹{fii_today:,.0f} Cr")
    sm2.metric("DII Today", f"₹{dii_today:,.0f} Cr")
    sm3.metric("FII 5 Day", f"₹{fii_5day:,.0f} Cr")
    sm4.metric("DII 5 Day", f"₹{dii_5day:,.0f} Cr")

    st.write(f"FII Index Futures Bias: **{fii_index_futures_bias}**")

    if smart_money_score >= 65:
        st.success("Institutional bias supportive hai.")
    elif smart_money_score <= 35:
        st.error("Institutional bias weak hai.")
    else:
        st.warning("Institutional data mixed hai.")

with st.expander("✅ Confirmation Panel", expanded=False):
    cp1, cp2, cp3, cp4 = st.columns(4)
    cp1.metric("RSI", f"{rsi:.1f}")
    cp2.metric("MACD", macd)
    cp3.metric("Bollinger", bollinger)
    cp4.metric("Supertrend", supertrend)

    st.write(f"Confirmation Score: **{confirmation_score}%**")
    st.progress(confirmation_score)

with st.expander("💰 Position Manager", expanded=False):
    pm1, pm2, pm3, pm4 = st.columns(4)
    pm1.metric("Capital", f"₹{capital:,.0f}")
    pm2.metric("Max Lots", max_lots)
    pm3.metric("Current Lots", current_lots)
    pm4.metric("AI Suggested Lots", suggested_lots)

    if suggested_lots == 0:
        st.warning("No fresh position suggested.")
    elif suggested_lots > current_lots:
        st.success(f"AI ke hisaab se {suggested_lots - current_lots} lot add possible hai.")
    elif suggested_lots < current_lots:
        st.error(f"AI ke hisaab se {current_lots - suggested_lots} lot reduce karo.")
    else:
        st.info("Current lots AI suggestion ke equal hain.")

    estimated_margin = suggested_lots * margin_per_lot
    st.write(f"Estimated Margin Required: **₹{estimated_margin:,.0f}**")
    st.write(f"Lot Size: **{lot_size}**")

with st.expander("📅 Expiry / Carry Forward / News Risk", expanded=False):
    carry_probability = probability

    if day_name == "Thursday":
        carry_probability -= 25
    if news_risk == "Medium":
        carry_probability -= 15
    elif news_risk == "High":
        carry_probability -= 40
    if vix > 18:
        carry_probability -= 25

    carry_probability = clamp(carry_probability)

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Today", day_name)
    e2.metric("Mode", expiry_text)
    e3.metric("News Risk", news_risk)
    e4.metric("Carry Probability", f"{carry_probability}%")

    st.progress(carry_probability)

    if carry_probability >= 80:
        st.success("Carry possible hai, lekin hedge mandatory rakho.")
    elif carry_probability >= 60:
        st.warning("Carry only with strict hedge and small quantity.")
    else:
        st.error("Carry avoid. Intraday exit better.")

with st.expander("📂 CSV Upload Analysis", expanded=False):
    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.dataframe(df.head(20), use_container_width=True)

            if "Close" in df.columns:
                df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
                df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

                latest_close = float(df["Close"].iloc[-1])
                latest_ema20 = float(df["EMA20"].iloc[-1])
                latest_ema50 = float(df["EMA50"].iloc[-1])

                c1, c2, c3 = st.columns(3)
                c1.metric("Latest Close", f"{latest_close:.2f}")
                c2.metric("CSV EMA20", f"{latest_ema20:.2f}")
                c3.metric("CSV EMA50", f"{latest_ema50:.2f}")

                if latest_close > latest_ema20 > latest_ema50:
                    st.success("CSV Trend: Bullish")
                elif latest_close < latest_ema20 < latest_ema50:
                    st.error("CSV Trend: Bearish")
                else:
                    st.warning("CSV Trend: Mixed / Sideways")
            else:
                st.error("CSV me 'Close' column hona chahiye.")

        except Exception as e:
            st.error(f"CSV read error: {e}")


# =========================================================
# FOOTER
# =========================================================
st.markdown("---")
st.markdown(
    "<div class='small-note'>Disclaimer: Ye tool decision-support ke liye hai. Final trade se pehle live chart, liquidity, slippage aur risk management zaroor check karein.</div>",
    unsafe_allow_html=True
)
