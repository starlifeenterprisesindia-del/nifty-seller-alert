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