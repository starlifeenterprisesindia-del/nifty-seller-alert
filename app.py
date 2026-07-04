import yfinance as yf
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# =========================================================
# NIFTY SELLER AI DASHBOARD V5 LITE
# Seller-focused version: Fast UI + OI/Price Analyzer + DhanHQ-ready structure
# =========================================================

st.set_page_config(
    page_title="Nifty Seller AI Dashboard V5 Lite",
    page_icon="🧠",
    layout="wide"
)

# =========================================================
# STYLE
# =========================================================
st.markdown("""
<style>
.main-title {font-size: 2.05rem; font-weight: 850; margin-bottom: 0.2rem;}
.sub-title {font-size: 0.95rem; opacity: 0.75; margin-bottom: 1rem;}
.advisor-card {padding: 22px; border-radius: 20px; margin-bottom: 16px; border: 1px solid rgba(255,255,255,0.12); box-shadow: 0 8px 26px rgba(0,0,0,0.18);}
.card-green {background: linear-gradient(135deg, rgba(0,135,75,0.96), rgba(0,82,58,0.96));}
.card-red {background: linear-gradient(135deg, rgba(160,38,38,0.96), rgba(92,24,24,0.96));}
.card-yellow {background: linear-gradient(135deg, rgba(170,126,22,0.96), rgba(105,76,18,0.96));}
.card-wait {background: linear-gradient(135deg, rgba(82,88,99,0.96), rgba(43,48,58,0.96));}
.advisor-card h1 {color: white; font-size: 2.95rem; margin: 4px 0 8px 0;}
.advisor-card h3 {color: white; margin: 0; opacity: 0.96;}
.advisor-card p {color: white; font-size: 1rem; margin: 7px 0;}
.ribbon {padding: 10px 12px; border-radius: 14px; background: rgba(255,255,255,0.075); border: 1px solid rgba(255,255,255,0.10); text-align: center; font-weight: 750; margin-bottom: 8px;}
.small-note {opacity: 0.76; font-size: 0.88rem;}
</style>
""", unsafe_allow_html=True)

# =========================================================
# HELPERS
# =========================================================
def clamp(value, low=0, high=98):
    try:
        value = int(round(float(value)))
    except Exception:
        value = 0
    return max(low, min(high, value))


def safe_divide(a, b, default=0.0):
    try:
        if b == 0:
            return default
        return a / b
    except Exception:
        return default


def score_label(score):
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
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_weekday = now.weekday() < 5
    is_open = is_weekday and open_time <= now <= close_time
    day_name = now.strftime("%A")
    market_text = "Market Open" if is_open else "Market Closed"
    expiry_text = "Weekly Expiry" if day_name == "Thursday" else "Normal Day"
    return now, day_name, market_text, expiry_text


def classify_oi_price_signal(option_type, price_change, oi_change, volume):
    """
    OI + Price Action Analyzer.
    Price Up + OI Up = Fresh Buying
    Price Down + OI Up = Fresh Writing
    Price Up + OI Down = Short Covering
    Price Down + OI Down = Long Unwinding
    """
    if price_change > 0 and oi_change > 0:
        if option_type == "CE":
            signal = "Fresh Call Buying"
            view = "Bullish pressure"
        else:
            signal = "Fresh Put Buying"
            view = "Bearish pressure"
    elif price_change < 0 and oi_change > 0:
        if option_type == "CE":
            signal = "Fresh Call Writing"
            view = "Resistance / bearish pressure"
        else:
            signal = "Fresh Put Writing"
            view = "Support / bullish pressure"
    elif price_change > 0 and oi_change < 0:
        if option_type == "CE":
            signal = "Call Short Covering"
            view = "Bullish breakout risk"
        else:
            signal = "Put Short Covering"
            view = "Bearish breakdown risk"
    elif price_change < 0 and oi_change < 0:
        if option_type == "CE":
            signal = "Call Long Unwinding"
            view = "CE buyers weak"
        else:
            signal = "Put Long Unwinding"
            view = "PE buyers weak"
    else:
        signal = "Neutral"
        view = "No clear signal"

    strength = 50
    if abs(price_change) >= 10:
        strength += 20
    elif abs(price_change) >= 5:
        strength += 12
    elif abs(price_change) >= 2:
        strength += 6

    if abs(oi_change) >= 100000:
        strength += 20
    elif abs(oi_change) >= 50000:
        strength += 12
    elif abs(oi_change) >= 10000:
        strength += 6

    if volume >= 100000:
        strength += 10
    elif volume >= 50000:
        strength += 6

    return signal, view, clamp(strength)

# =========================================================
# LIVE DATA
# =========================================================
@st.cache_data(ttl=30, show_spinner=False)
def get_live_nifty_price():
    try:
        ticker = yf.Ticker("^NSEI")
        intraday = ticker.history(period="2d", interval="1m")
        if intraday is None or intraday.empty:
            intraday = ticker.history(period="5d", interval="5m")
        if intraday is None or intraday.empty:
            return {"success": False, "price": None, "change": None, "change_pct": None, "last_update": "NA", "message": "Live Nifty unavailable."}

        intraday = intraday.dropna()
        live_price = float(intraday.iloc[-1]["Close"])
        daily = ticker.history(period="7d", interval="1d").dropna()
        previous_close = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else live_price
        change = live_price - previous_close
        change_pct = (change / previous_close) * 100 if previous_close else 0
        last_time = intraday.index[-1]
        try:
            last_update = last_time.tz_convert("Asia/Kolkata").strftime("%d-%m-%Y %I:%M:%S %p")
        except Exception:
            last_update = str(last_time)
        return {"success": True, "price": round(live_price, 2), "change": round(change, 2), "change_pct": round(change_pct, 2), "last_update": last_update, "message": "OK"}
    except Exception as e:
        return {"success": False, "price": None, "change": None, "change_pct": None, "last_update": "Error", "message": f"Live Nifty error: {e}"}


@st.cache_data(ttl=60, show_spinner=False)
def get_live_india_vix():
    try:
        ticker = yf.Ticker("^INDIAVIX")
        intraday = ticker.history(period="2d", interval="1m")
        if intraday is None or intraday.empty:
            intraday = ticker.history(period="5d", interval="5m")
        if intraday is None or intraday.empty:
            intraday = ticker.history(period="7d", interval="1d")
        if intraday is None or intraday.empty:
            return {"success": False, "vix": None, "change": None, "change_pct": None, "last_update": "NA", "message": "Live VIX unavailable."}

        intraday = intraday.dropna()
        live_vix = float(intraday.iloc[-1]["Close"])
        daily = ticker.history(period="7d", interval="1d").dropna()
        previous_close = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else live_vix
        change = live_vix - previous_close
        change_pct = (change / previous_close) * 100 if previous_close else 0
        last_time = intraday.index[-1]
        try:
            last_update = last_time.tz_convert("Asia/Kolkata").strftime("%d-%m-%Y %I:%M:%S %p")
        except Exception:
            last_update = str(last_time)
        return {"success": True, "vix": round(live_vix, 2), "change": round(change, 2), "change_pct": round(change_pct, 2), "last_update": last_update, "message": "OK"}
    except Exception as e:
        return {"success": False, "vix": None, "change": None, "change_pct": None, "last_update": "Error", "message": f"Live VIX error: {e}"}


@st.cache_data(ttl=60, show_spinner=True)
def get_live_option_chain(spot_price=None, strike_gap=50, strikes_each_side=4):
    """
    Option Chain AI Engine V1.
    NSE/Yahoo fallback now. DhanHQ can be connected later by replacing this function only.
    """
    try:
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.nseindia.com/option-chain",
            "Connection": "keep-alive",
        }
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"success": False, "message": f"NSE option chain failed. Status: {response.status_code}"}

        data = response.json()
        records = data.get("records", {})
        option_data = records.get("data", [])
        if not option_data:
            return {"success": False, "message": "NSE option chain data empty."}

        underlying_value = records.get("underlyingValue", spot_price)
        if underlying_value is None:
            return {"success": False, "message": "Underlying value not available."}
        underlying_value = float(underlying_value)

        expiry_dates = records.get("expiryDates", [])
        selected_expiry = expiry_dates[0] if expiry_dates else None
        if not selected_expiry:
            return {"success": False, "message": "Expiry date not available."}

        atm_strike = int(round(underlying_value / strike_gap) * strike_gap)
        lower_strike = atm_strike - (strikes_each_side * strike_gap)
        upper_strike = atm_strike + (strikes_each_side * strike_gap)
        option_rows = []

        for row in option_data:
            if row.get("expiryDate") != selected_expiry:
                continue
            strike = row.get("strikePrice")
            if strike is None:
                continue
            strike = int(strike)
            if lower_strike <= strike <= upper_strike:
                ce = row.get("CE", {}) or {}
                pe = row.get("PE", {}) or {}
                option_rows.append({
                    "strike": strike,
                    "ce_ltp": float(ce.get("lastPrice", 0) or 0),
                    "ce_change": float(ce.get("change", 0) or 0),
                    "ce_oi": int(ce.get("openInterest", 0) or 0),
                    "ce_change_oi": int(ce.get("changeinOpenInterest", 0) or 0),
                    "ce_volume": int(ce.get("totalTradedVolume", 0) or 0),
                    "ce_iv": float(ce.get("impliedVolatility", 0) or 0),
                    "pe_ltp": float(pe.get("lastPrice", 0) or 0),
                    "pe_change": float(pe.get("change", 0) or 0),
                    "pe_oi": int(pe.get("openInterest", 0) or 0),
                    "pe_change_oi": int(pe.get("changeinOpenInterest", 0) or 0),
                    "pe_volume": int(pe.get("totalTradedVolume", 0) or 0),
                    "pe_iv": float(pe.get("impliedVolatility", 0) or 0),
                })

        if not option_rows:
            return {"success": False, "message": "No option chain rows found near ATM."}

        total_call_oi = sum(row["ce_oi"] for row in option_rows)
        total_put_oi = sum(row["pe_oi"] for row in option_rows)
        call_oi_change = sum(row["ce_change_oi"] for row in option_rows)
        put_oi_change = sum(row["pe_change_oi"] for row in option_rows)
        pcr = safe_divide(total_put_oi, total_call_oi, 0.0)

        ce_candidates = [row for row in option_rows if row["strike"] >= atm_strike]
        pe_candidates = [row for row in option_rows if row["strike"] <= atm_strike]
        strongest_ce = max(ce_candidates, key=lambda x: x["ce_oi"], default=None)
        strongest_pe = max(pe_candidates, key=lambda x: x["pe_oi"], default=None)

        return {
            "success": True,
            "underlying": round(underlying_value, 2),
            "expiry": selected_expiry,
            "atm_strike": atm_strike,
            "call_oi_change": int(call_oi_change),
            "put_oi_change": int(put_oi_change),
            "total_call_oi": int(total_call_oi),
            "total_put_oi": int(total_put_oi),
            "pcr": round(pcr, 2),
            "ce_sell_strike": int(strongest_ce["strike"] if strongest_ce else atm_strike + strike_gap),
            "pe_sell_strike": int(strongest_pe["strike"] if strongest_pe else atm_strike - strike_gap),
            "option_rows": option_rows,
            "rows_count": len(option_rows),
            "last_update": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M:%S %p"),
            "message": "Live option chain fetched successfully."
        }
    except Exception as e:
        return {"success": False, "message": f"Live option chain fetch error: {e}"}

# =========================================================
# SIDEBAR INPUTS
# =========================================================
st.sidebar.title("⚙️ V5 Lite Inputs")
st.sidebar.caption("DhanHQ-ready seller dashboard. Abhi NSE/Yahoo fallback use ho raha hai.")

with st.sidebar.expander("1️⃣ Market Snapshot", expanded=True):
    use_live_nifty = st.checkbox("Use Live Nifty Price", value=True)
    manual_price = st.number_input("Manual Nifty Price", value=25000.0, step=1.0)
    live_nifty_data = get_live_nifty_price() if use_live_nifty else {"success": False}
    if use_live_nifty and live_nifty_data.get("success"):
        price = live_nifty_data["price"]
        st.success(f"Nifty: {price} | {live_nifty_data['change']} pts ({live_nifty_data['change_pct']}%)")
        st.caption(f"Last Update: {live_nifty_data['last_update']}")
    else:
        price = manual_price
        if use_live_nifty:
            st.warning("Live Nifty unavailable. Manual price used.")

    ema20 = st.number_input("EMA 20", value=24950.0, step=1.0)
    ema50 = st.number_input("EMA 50", value=24900.0, step=1.0)
    vwap = st.number_input("VWAP", value=24940.0, step=1.0)
    atr5 = st.number_input("ATR 5 Min", value=45.0, step=1.0)

    use_live_vix = st.checkbox("Use Live India VIX", value=True)
    manual_vix = st.number_input("Manual India VIX", value=13.5, step=0.1)
    live_vix_data = get_live_india_vix() if use_live_vix else {"success": False}
    if use_live_vix and live_vix_data.get("success"):
        vix = live_vix_data["vix"]
        st.success(f"VIX: {vix} | {live_vix_data['change']} ({live_vix_data['change_pct']}%)")
    else:
        vix = manual_vix
        if use_live_vix:
            st.warning("Live VIX unavailable. Manual VIX used.")

with st.sidebar.expander("2️⃣ Option Chain / OI / PCR", expanded=True):
    use_live_option_chain = st.checkbox("Use Live Option Chain", value=False)
    strikes_each_side = st.slider("Strikes Each Side", 2, 8, 4)

    manual_call_oi_change = st.number_input("Manual Call OI Change", value=150000, step=1000)
    manual_put_oi_change = st.number_input("Manual Put OI Change", value=180000, step=1000)
    manual_total_call_oi = st.number_input("Manual Total Call OI", value=1500000, step=10000)
    manual_total_put_oi = st.number_input("Manual Total Put OI", value=1800000, step=10000)
    manual_ce_strike = st.number_input("Manual CE Sell Strike", value=25100, step=50)
    manual_pe_strike = st.number_input("Manual PE Sell Strike", value=24900, step=50)
    hedge_gap = st.number_input("Hedge Gap", value=100, step=50)

    live_option_chain_data = {"success": False, "message": "Live option chain OFF."}
    if use_live_option_chain:
        live_option_chain_data = get_live_option_chain(price, 50, strikes_each_side)

    call_oi_change = manual_call_oi_change
    put_oi_change = manual_put_oi_change
    total_call_oi = manual_total_call_oi
    total_put_oi = manual_total_put_oi
    ce_strike = manual_ce_strike
    pe_strike = manual_pe_strike

    if use_live_option_chain and live_option_chain_data.get("success"):
        call_oi_change = live_option_chain_data["call_oi_change"]
        put_oi_change = live_option_chain_data["put_oi_change"]
        total_call_oi = live_option_chain_data["total_call_oi"]
        total_put_oi = live_option_chain_data["total_put_oi"]
        ce_strike = live_option_chain_data["ce_sell_strike"]
        pe_strike = live_option_chain_data["pe_sell_strike"]
        st.success(f"Live OC: {live_option_chain_data['expiry']} | ATM {live_option_chain_data['atm_strike']} | PCR {live_option_chain_data['pcr']}")
    elif use_live_option_chain:
        st.warning("Live Option Chain unavailable. Manual values used.")
        st.caption(live_option_chain_data.get("message", "No message"))
    else:
        st.info("Manual Option Chain values used.")

with st.sidebar.expander("3️⃣ Support / Resistance", expanded=False):
    previous_day_high = st.number_input("Previous Day High", value=25150.0, step=1.0)
    previous_day_low = st.number_input("Previous Day Low", value=24850.0, step=1.0)
    today_high = st.number_input("Today High", value=25080.0, step=1.0)
    today_low = st.number_input("Today Low", value=24920.0, step=1.0)
    opening_range_high = st.number_input("Opening Range High", value=25060.0, step=1.0)
    opening_range_low = st.number_input("Opening Range Low", value=24940.0, step=1.0)

with st.sidebar.expander("4️⃣ Volume", expanded=False):
    current_volume = st.number_input("Current Volume", value=120000, step=1000)
    average_volume = st.number_input("Average Volume", value=80000, step=1000)
    breakout_type = st.selectbox("Breakout / Breakdown", ["No Breakout", "Resistance Breakout", "Support Breakdown"])

with st.sidebar.expander("5️⃣ FII / DII Smart Money", expanded=True):
    fii_today = st.number_input("FII Today ₹ Cr", value=0.0, step=100.0)
    dii_today = st.number_input("DII Today ₹ Cr", value=0.0, step=100.0)
    fii_5day = st.number_input("FII 5 Day Net ₹ Cr", value=0.0, step=100.0)
    dii_5day = st.number_input("DII 5 Day Net ₹ Cr", value=0.0, step=100.0)
    fii_index_futures_bias = st.selectbox("FII Index Futures Bias", ["Neutral", "Bullish", "Bearish"])

with st.sidebar.expander("6️⃣ Risk / Position", expanded=True):
    news_risk = st.selectbox("News Risk", ["Low", "Medium", "High"])
    capital = st.number_input("Capital ₹", value=500000, step=10000)
    margin_per_lot = st.number_input("Margin Per Lot ₹", value=100000, step=5000)
    current_lots = st.number_input("Current Lots Holding", value=0, step=1)
    lot_size = st.number_input("Lot Size", value=50, step=25)

# =========================================================
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

# Price Action Score
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

# Support/Resistance Score
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

# Volume Score
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

# OI Score
oi_score = 50
if put_oi_change > call_oi_change:
    oi_score += 25
elif call_oi_change > put_oi_change:
    oi_score -= 25
oi_diff_ratio = safe_divide(abs(put_oi_change - call_oi_change), max(abs(call_oi_change), abs(put_oi_change)), 0.0)
if oi_diff_ratio >= 0.35:
    oi_score += 10 if put_oi_change > call_oi_change else -10
oi_score = clamp(oi_score)

# PCR Score
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

# VIX Score
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

# FII/DII Score
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

# News Score
news_score = 50
if news_risk == "Low":
    news_score += 25
elif news_risk == "Medium":
    news_score -= 5
else:
    news_score -= 35
news_score = clamp(news_score)

# Final Decision Engine - seller focused
bullish_probability = (
    price_action_score * 0.23 +
    sr_score * 0.16 +
    volume_score * 0.11 +
    oi_score * 0.18 +
    pcr_score * 0.12 +
    vix_score * 0.10 +
    smart_money_score * 0.07 +
    news_score * 0.03
)
bearish_probability = (
    (98 - price_action_score) * 0.23 +
    (98 - sr_score) * 0.16 +
    volume_score * 0.11 +
    (98 - oi_score) * 0.18 +
    (98 - pcr_score) * 0.12 +
    vix_score * 0.10 +
    (98 - smart_money_score) * 0.07 +
    news_score * 0.03
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
vix_text = "VIX Low" if vix <= 14 else "VIX Normal" if vix <= 18 else "VIX High"

# =========================================================
# HEADER + TOP VIEW
# =========================================================
st.markdown("<div class='main-title'>🧠 Nifty Seller AI Dashboard V5 Lite</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Fast seller-focused dashboard: Live Nifty + VIX + OI/PCR + OI Price Analyzer + FII/DII + Risk</div>", unsafe_allow_html=True)

r1, r2, r3, r4, r5 = st.columns(5)
r1.markdown(f"<div class='ribbon'>{market_text}</div>", unsafe_allow_html=True)
r2.markdown(f"<div class='ribbon'>{expiry_text}</div>", unsafe_allow_html=True)
r3.markdown(f"<div class='ribbon'>News: {news_risk}</div>", unsafe_allow_html=True)
r4.markdown(f"<div class='ribbon'>{vix_text}</div>", unsafe_allow_html=True)
r5.markdown(f"<div class='ribbon'>PCR: {pcr:.2f}</div>", unsafe_allow_html=True)

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
    st.warning("AI Advice: Clear edge nahi hai. Trade avoid karo ya fresh confirmation ka wait karo.")
elif final_trade == "SELL PE":
    st.success("AI Advice: Bullish bias hai. PE sell sirf hedge aur strict SL ke saath.")
else:
    st.error("AI Advice: Bearish bias hai. CE sell sirf hedge aur strict SL ke saath.")

# =========================================================
# MAIN DASHBOARD
# =========================================================
with st.expander("✅ Why AI gave this decision", expanded=True):
    reasons = []
    if price_action_score >= 65:
        reasons.append("Price Action bullish: price EMA/VWAP ke upar hai.")
    elif price_action_score <= 35:
        reasons.append("Price Action bearish: price EMA/VWAP ke neeche hai.")
    if sr_score >= 65:
        reasons.append("Support zone favourable hai.")
    elif sr_score <= 35:
        reasons.append("Resistance pressure / S-R risk high hai.")
    if oi_score >= 65:
        reasons.append("Put OI stronger hai, bullish support mil raha hai.")
    elif oi_score <= 35:
        reasons.append("Call OI stronger hai, bearish pressure mil raha hai.")
    if vix_score <= 35:
        reasons.append("VIX high hai, option selling risk zyada hai.")
    if smart_money_score >= 65:
        reasons.append("FII/DII smart money supportive hai.")
    elif smart_money_score <= 35:
        reasons.append("FII/DII smart money weak hai.")
    if news_score <= 35:
        reasons.append("News risk high hai, trade avoid better.")

    if reasons:
        for item in reasons:
            st.write("✔", item)
    else:
        st.write("Signals mixed hain. Isliye AI aggressive trade nahi de raha.")

st.markdown("## 📡 AI Radar")
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Price Action", f"{price_action_score}%", score_label(price_action_score))
    st.progress(price_action_score)
with c2:
    st.metric("OI + PCR", f"{clamp((oi_score + pcr_score) / 2)}%", f"PCR {pcr:.2f}")
    st.progress(clamp((oi_score + pcr_score) / 2))
with c3:
    st.metric("VIX + News", f"{clamp((vix_score + news_score) / 2)}%", f"VIX {vix:.2f}")
    st.progress(clamp((vix_score + news_score) / 2))
with c4:
    st.metric("Smart Money", f"{smart_money_score}%", score_label(smart_money_score))
    st.progress(smart_money_score)

with st.expander("📊 Market Snapshot", expanded=True):
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Nifty", f"{price:.2f}")
    m2.metric("EMA20", f"{ema20:.2f}")
    m3.metric("EMA50", f"{ema50:.2f}")
    m4.metric("VWAP", f"{vwap:.2f}")
    m5.metric("India VIX", f"{vix:.2f}")

with st.expander("🧠 Option Chain AI Engine", expanded=True):
    oc1, oc2, oc3, oc4 = st.columns(4)
    oc1.metric("PCR", f"{pcr:.2f}")
    oc2.metric("Put OI Change", f"{put_oi_change:,}")
    oc3.metric("Call OI Change", f"{call_oi_change:,}")
    oc4.metric("OI Bias", "Bullish" if put_oi_change > call_oi_change else "Bearish" if call_oi_change > put_oi_change else "Neutral")

    if final_trade == "SELL PE":
        st.success(f"Recommended: Sell {int(pe_strike)} PE | Hedge: Buy {int(pe_strike - hedge_gap)} PE")
    elif final_trade == "SELL CE":
        st.error(f"Recommended: Sell {int(ce_strike)} CE | Hedge: Buy {int(ce_strike + hedge_gap)} CE")
    else:
        st.warning("No strike selected because final decision is WAIT.")

    st.markdown("---")
    st.subheader("OI + Price Action Analyzer")

    if use_live_option_chain and live_option_chain_data.get("success"):
        option_rows = live_option_chain_data.get("option_rows", [])
        if option_rows:
            analyzer_rows = []
            for row in option_rows:
                ce_signal, ce_view, ce_strength = classify_oi_price_signal("CE", row["ce_change"], row["ce_change_oi"], row["ce_volume"])
                pe_signal, pe_view, pe_strength = classify_oi_price_signal("PE", row["pe_change"], row["pe_change_oi"], row["pe_volume"])
                analyzer_rows.append({
                    "Strike": row["strike"],
                    "CE LTP": round(row["ce_ltp"], 2),
                    "CE Chg": round(row["ce_change"], 2),
                    "CE OI Chg": row["ce_change_oi"],
                    "CE Vol": row["ce_volume"],
                    "CE Signal": ce_signal,
                    "CE Strength": ce_strength,
                    "PE LTP": round(row["pe_ltp"], 2),
                    "PE Chg": round(row["pe_change"], 2),
                    "PE OI Chg": row["pe_change_oi"],
                    "PE Vol": row["pe_volume"],
                    "PE Signal": pe_signal,
                    "PE Strength": pe_strength,
                })
            analyzer_df = pd.DataFrame(analyzer_rows)
            st.dataframe(analyzer_df, use_container_width=True)

            strongest_ce = analyzer_df.sort_values("CE Strength", ascending=False).iloc[0]
            strongest_pe = analyzer_df.sort_values("PE Strength", ascending=False).iloc[0]
            x1, x2 = st.columns(2)
            with x1:
                st.subheader("🔴 CE Side")
                st.write(f"Strongest CE: **{int(strongest_ce['Strike'])} CE**")
                st.write(f"Signal: **{strongest_ce['CE Signal']}** | Strength: **{int(strongest_ce['CE Strength'])}%**")
                if "Writing" in strongest_ce["CE Signal"]:
                    st.error("Fresh Call Writing: resistance signal.")
                elif "Short Covering" in strongest_ce["CE Signal"] or "Buying" in strongest_ce["CE Signal"]:
                    st.warning("CE sell risky: upside pressure/covering possible.")
                else:
                    st.info("CE side neutral/weak.")
            with x2:
                st.subheader("🟢 PE Side")
                st.write(f"Strongest PE: **{int(strongest_pe['Strike'])} PE**")
                st.write(f"Signal: **{strongest_pe['PE Signal']}** | Strength: **{int(strongest_pe['PE Strength'])}%**")
                if "Writing" in strongest_pe["PE Signal"]:
                    st.success("Fresh Put Writing: support signal.")
                elif "Short Covering" in strongest_pe["PE Signal"] or "Buying" in strongest_pe["PE Signal"]:
                    st.warning("PE sell risky: downside pressure/covering possible.")
                else:
                    st.info("PE side neutral/weak.")

            ce_write_count = len(analyzer_df[analyzer_df["CE Signal"] == "Fresh Call Writing"])
            pe_write_count = len(analyzer_df[analyzer_df["PE Signal"] == "Fresh Put Writing"])
            ce_cover_count = len(analyzer_df[analyzer_df["CE Signal"] == "Call Short Covering"])
            pe_cover_count = len(analyzer_df[analyzer_df["PE Signal"] == "Put Short Covering"])
            st.markdown("### 🤖 Overall Option Chain Reading")
            if pe_write_count > ce_write_count and ce_cover_count == 0:
                st.success("Put Writing stronger hai. Market ko neeche support mil sakta hai.")
            elif ce_write_count > pe_write_count and pe_cover_count == 0:
                st.error("Call Writing stronger hai. Upar resistance aa sakta hai.")
            elif ce_cover_count > 0:
                st.warning("CE Short Covering detect hui. CE sell avoid ya tight SL.")
            elif pe_cover_count > 0:
                st.warning("PE Short Covering detect hui. PE sell avoid ya tight SL.")
            else:
                st.info("Mixed option chain. Clear edge ke liye wait better.")
        else:
            st.warning("Option chain rows available nahi hain.")
    else:
        st.warning("OI + Price Analyzer ke liye sidebar se Use Live Option Chain ON karo.")

with st.expander("📍 Support / Resistance + Volume", expanded=False):
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Nearest Support", f"{nearest_support:.2f}")
    s2.metric("Support Distance", f"{support_distance:.2f} pts")
    s3.metric("Nearest Resistance", f"{nearest_resistance:.2f}")
    s4.metric("Resistance Distance", f"{resistance_distance:.2f} pts")
    st.write(f"Relative Volume: **{rvol:.2f}x** | Breakout Type: **{breakout_type}**")

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
    st.write(f"Estimated Margin Required: **₹{suggested_lots * margin_per_lot:,.0f}** | Lot Size: **{lot_size}**")

st.markdown("---")
st.markdown("<div class='small-note'>Disclaimer: Ye tool decision-support ke liye hai. Final trade se pehle live chart, liquidity, slippage aur risk management zaroor check karein.</div>", unsafe_allow_html=True)
