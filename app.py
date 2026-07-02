import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Nifty Seller Alert")

st.title("📈 Nifty Seller Alert")

st.write("Welcome Sony!")
price = st.number_input("Nifty Price", value=25000)
ema20 = st.number_input("EMA 20", value=24950)
if price > ema20:
    st.success("🟢 Bullish - PE Sell Watch")
else:
    st.error("🔴 Bearish - CE Sell Watch")

st.markdown("---")
ema50 = st.number_input("EMA 50", value=24880)
atr5 = st.number_input("ATR (5 Min)", value=45)
atr15 = st.number_input("ATR (15 Min)", value=90)
confidence = 92
st.markdown("## 🤖 AI Analysis")

if price > ema20 and price > ema50:
    st.success("🟢 STRONG PE SELL")
elif price < ema20 and price < ema50:
    st.error("🔴 STRONG CE SELL")
else:
    st.warning("🟡 WAIT - NO TRADE")

st.markdown("## 🎯 AI Confidence")
st.progress(confidence)
st.write(f"Confidence : {confidence}%")

st.markdown("## 📌 ATR Stop Loss & Target")

sl_5min = atr5 * 1.5
target_5min = atr5 * 1

sl_15min = atr15 * 1.5
target_15min = atr15 * 1

st.write(f"5 Min ATR SL: {sl_5min} points")
st.write(f"5 Min ATR Target: {target_5min} points")

st.write(f"15 Min ATR SL: {sl_15min} points")
st.write(f"15 Min ATR Target: {target_15min} points")

st.markdown("---")
st.markdown("## 📋 Final Trade Plan")

entry = price
sl = price + sl_5min
target = price - target_5min

st.info(f"""
🎯 Entry : {entry}

🛑 Stop Loss : {sl}

💰 Target : {target}

📈 Risk Reward : 1 : 1.5
""")

option_price = st.number_input("Option Premium", value=180)

qty = st.number_input("Lots", value=1)

lot_size = 75

st.markdown("## 💰 Profit / Loss Calculator")

risk = (67.5 * qty * lot_size)
reward = (45 * qty * lot_size)

st.write(f"Maximum Risk : ₹{risk:,.0f}")
st.write(f"Expected Profit : ₹{reward:,.0f}")

st.markdown("---")
st.markdown("## 📊 OI Change")

call_oi = st.number_input("Call OI Change", value=150000, key="call_oi_1")
put_oi = st.number_input("Put OI Change", value=180000, key="put_oi_1")

if put_oi > call_oi:
    st.success("🟢 Buyers Strong - PE Side Strong")
elif call_oi > put_oi:
    st.error("🔴 Sellers Strong - CE Side Strong")
else:
    st.warning("🟡 OI Equal - Wait")

    st.markdown("---")

st.markdown("---")
st.markdown("## ⚡ VIX Analysis")

vix = st.number_input("India VIX", value=13.5, key="vix_input")

if vix < 14:
    st.success("🟢 VIX Low - Option Selling Friendly")
elif vix <= 18:
    st.warning("🟡 VIX Normal - Caution")
else:
    st.error("🔴 VIX High - Avoid Aggressive Selling")


st.markdown("---")
st.markdown("## 📈 PCR Analysis")

total_put_oi = st.number_input("Total Put OI", value=1800000, key="total_put_oi")
total_call_oi = st.number_input("Total Call OI", value=1500000, key="total_call_oi")

pcr = total_put_oi / total_call_oi

st.write(f"PCR : {pcr:.2f}")

if pcr > 1:
    st.success("🟢 PCR Bullish")
elif pcr < 0.8:
    st.error("🔴 PCR Bearish")
else:
    st.warning("🟡 PCR Neutral")


st.markdown("---")
st.markdown("## 🚦 Trade Quality Score")

score = 0

if price > ema20:
    score += 20

if price > ema50:
    score += 20

if put_oi > call_oi:
    score += 20

if vix < 14:
    score += 20

if pcr > 1:
    score += 20

st.progress(score)
st.write(f"Trade Score : {score}/100")

if score >= 80:
    st.success("✅ HIGH QUALITY TRADE - PE SELL POSSIBLE")
elif score >= 60:
    st.warning("🟡 AVERAGE TRADE - WAIT FOR CONFIRMATION")
else:
    st.error("❌ NO TRADE - SETUP WEAK")
    st.markdown("---")
st.markdown("## 🔊 Sound Alert")

if score >= 80:
    components.html("""
    <script>
    var msg = new SpeechSynthesisUtterance("Strong trade setup ready");
    window.speechSynthesis.speak(msg);
    </script>
    """, height=0)
    st.success("🔊 Sound Alert Active")
else:
    st.info("No sound alert - setup weak")
    st.markdown("---")
st.markdown("## 📂 CSV Upload Analysis")

uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

if uploaded_file is not None:
    import pandas as pd

    df = pd.read_csv(uploaded_file)

    st.write("CSV Data Preview")
    st.dataframe(df.head())

    if "Close" in df.columns:
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

        latest_close = df["Close"].iloc[-1]
        latest_ema20 = df["EMA20"].iloc[-1]
        latest_ema50 = df["EMA50"].iloc[-1]

        st.write(f"Latest Close: {latest_close:.2f}")
        st.write(f"EMA20: {latest_ema20:.2f}")
        st.write(f"EMA50: {latest_ema50:.2f}")

        if latest_close > latest_ema20 and latest_close > latest_ema50:
            st.success("🟢 CSV Signal: Bullish - PE Sell Watch")
        elif latest_close < latest_ema20 and latest_close < latest_ema50:
            st.error("🔴 CSV Signal: Bearish - CE Sell Watch")
        else:
            st.warning("🟡 CSV Signal: Wait")
    else:
        st.error("CSV me 'Close' column hona chahiye")
        st.markdown("---")
st.markdown("## 📊 Option Chain Strike & Hedge Finder")

spot = st.number_input("Nifty Spot Price", value=25000, key="spot_oc")
strike_gap = st.number_input("Strike Gap", value=50, key="strike_gap")
hedge_gap = st.number_input("Hedge Gap", value=100, key="hedge_gap")

st.markdown("### PE Side")
pe_support_strike = st.number_input("Strong PE Support Strike", value=24900, key="pe_support")
pe_premium = st.number_input("PE Sell Premium", value=120, key="pe_premium")

st.markdown("### CE Side")
ce_resistance_strike = st.number_input("Strong CE Resistance Strike", value=25100, key="ce_resistance")
ce_premium = st.number_input("CE Sell Premium", value=115, key="ce_premium")

st.markdown("### Hedge Suggestion")

pe_hedge = pe_support_strike - hedge_gap
ce_hedge = ce_resistance_strike + hedge_gap

if score >= 80 and put_oi > call_oi and price > ema20 and price > ema50:
    st.success("✅ Best Trade: PE SELL")
    st.info(f"""
    Sell PE Strike: {pe_support_strike} PE  
    Buy Hedge: {pe_hedge} PE  
    Sell Premium: ₹{pe_premium}  
    Hedge Gap: {hedge_gap} points  
    Confidence: {score}%
    """)

elif score >= 80 and call_oi > put_oi and price < ema20 and price < ema50:
    st.error("✅ Best Trade: CE SELL")
    st.info(f"""
    Sell CE Strike: {ce_resistance_strike} CE  
    Buy Hedge: {ce_hedge} CE  
    Sell Premium: ₹{ce_premium}  
    Hedge Gap: {hedge_gap} points  
    Confidence: {score}%
    """)

else:
    st.warning("⏳ No clear strike selection - Wait")


st.markdown("---")
st.markdown("## 💰 Position Size & Risk")

capital = st.number_input("Capital", value=400000, key="capital")
risk_percent = st.number_input("Risk % Per Trade", value=1.0, key="risk_percent")
lot_size = st.number_input("Lot Size", value=50, key="lot_size2")

risk_amount = capital * risk_percent / 100

st.write(f"Maximum Risk Allowed: ₹{risk_amount:,.0f}")

suggested_lots = max(1, int(risk_amount / 2500))

st.write(f"Suggested Lots: {suggested_lots}")

st.warning("⚠️ Final trade lene se pehle real option chain, spread aur liquidity zaroor check karo.")
from datetime import datetime
import streamlit as st

st.markdown("---")
st.markdown("## 📅 Market Session & Expiry AI")

today = datetime.now()

days = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday"
]

day_name = days[today.weekday()]
current_time = today.strftime("%H:%M")

st.write(f"### 📅 Today : {day_name}")
st.write(f"### ⏰ Time : {current_time}")

market_open = today.hour > 9 or (today.hour == 9 and today.minute >= 15)
market_close = today.hour >= 15 and today.minute >= 30

if market_open and not market_close:
    st.success("🟢 MARKET OPEN")
else:
    st.error("🔴 MARKET CLOSED")

# Expiry Mode
if day_name == "Thursday":
    st.warning("🔥 WEEKLY EXPIRY MODE")
    expiry = True
else:
    st.info("📈 NORMAL TRADING DAY")
    expiry = False

st.markdown("---")
st.markdown("## 🌙 Carry Forward AI")

carry_score = 0

if score >= 80:
    carry_score += 30

if price > ema20:
    carry_score += 20

if price > ema50:
    carry_score += 20

if not expiry:
    carry_score += 30

st.progress(carry_score)

if carry_score >= 80:
    st.success("✅ Carry Forward Possible")
elif carry_score >= 60:
    st.warning("⚠️ Carry Only With Hedge")
else:
    st.error("❌ Exit Today Better")

st.write(f"Carry Confidence : {carry_score}%")

st.markdown("---")
st.markdown("## 🚨 News Risk Alert")

news_mode = st.selectbox(
    "Today's News Impact",
    [
        "No Major News",
        "RBI Policy",
        "Fed Meeting",
        "US CPI",
        "Budget",
        "Election",
        "War / Geopolitical",
        "Company Results"
    ]
)

if news_mode == "No Major News":
    st.success("🟢 Safe for Option Selling")

elif news_mode in ["Company Results"]:
    st.warning("🟡 Trade Carefully")

else:
    st.error("🔴 High Impact News - Reduce Position Size")

st.markdown("---")
st.markdown("## 🤖 Final AI Decision")

if score >= 90 and carry_score >= 80 and news_mode == "No Major News":
    st.success("✅ FULL CONFIDENCE TRADE")

elif score >= 75:
    st.warning("⚠️ Moderate Confidence")

else:
    st.error("❌ WAIT FOR BETTER SETUP")
