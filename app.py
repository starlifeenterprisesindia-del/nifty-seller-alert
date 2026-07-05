import os
from io import StringIO
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# =========================================================
# NIFTY SELLER AI DASHBOARD V6 - SELLER INTELLIGENCE
# DhanHQ-ready | OI+Price | Heavyweights | News Risk | FII/DII
# =========================================================

IST = ZoneInfo("Asia/Kolkata")
DHAN_BASE = "https://api.dhan.co/v2"
DHAN_INSTRUMENT_MASTER = "https://images.dhan.co/api-data/api-scrip-master.csv"
DEFAULT_NIFTY_SECURITY_ID = 13
DEFAULT_NIFTY_SEGMENT = "IDX_I"

# Official Nifty 50 factsheet dated 30-Jun-2026.
# Keep editable in the sidebar because weights change over time.
TOP5_DEFAULT = {
    "HDFCBANK": {"name": "HDFC Bank", "weight": 11.18, "yahoo": "HDFCBANK.NS"},
    "ICICIBANK": {"name": "ICICI Bank", "weight": 9.01, "yahoo": "ICICIBANK.NS"},
    "RELIANCE": {"name": "Reliance", "weight": 8.00, "yahoo": "RELIANCE.NS"},
    "BHARTIARTL": {"name": "Bharti Airtel", "weight": 5.15, "yahoo": "BHARTIARTL.NS"},
    "LT": {"name": "Larsen & Toubro", "weight": 4.44, "yahoo": "LT.NS"},
}

st.set_page_config(
    page_title="Nifty Seller AI Dashboard V6",
    page_icon="🧠",
    layout="wide",
)

st.markdown(
    """
<style>
.main-title {font-size: 2.05rem; font-weight: 850; margin-bottom: 0.15rem;}
.sub-title {font-size: 0.94rem; opacity: 0.75; margin-bottom: 0.95rem;}
.advisor-card {padding: 22px; border-radius: 20px; margin-bottom: 16px; border: 1px solid rgba(255,255,255,0.12); box-shadow: 0 8px 26px rgba(0,0,0,0.18);}
.card-green {background: linear-gradient(135deg, rgba(0,135,75,0.96), rgba(0,82,58,0.96));}
.card-red {background: linear-gradient(135deg, rgba(160,38,38,0.96), rgba(92,24,24,0.96));}
.card-yellow {background: linear-gradient(135deg, rgba(170,126,22,0.96), rgba(105,76,18,0.96));}
.card-wait {background: linear-gradient(135deg, rgba(82,88,99,0.96), rgba(43,48,58,0.96));}
.advisor-card h1 {color: white; font-size: 2.9rem; margin: 4px 0 8px 0;}
.advisor-card h3 {color: white; margin: 0; opacity: 0.96;}
.advisor-card p {color: white; font-size: 1rem; margin: 7px 0;}
.ribbon {padding: 10px 12px; border-radius: 14px; background: rgba(255,255,255,0.075); border: 1px solid rgba(255,255,255,0.10); text-align: center; font-weight: 750; margin-bottom: 8px;}
.small-note {opacity: 0.74; font-size: 0.86rem;}
.source-pill {padding: 5px 9px; border-radius: 10px; background: rgba(255,255,255,0.07); display: inline-block; margin-right: 6px; font-size: 0.84rem;}
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# GENERIC HELPERS
# =========================================================
def clamp(value, low=0, high=100):
    try:
        value = float(value)
    except Exception:
        value = 0.0
    return max(low, min(high, value))


def signed_clamp(value, low=-100, high=100):
    try:
        value = float(value)
    except Exception:
        value = 0.0
    return max(low, min(high, value))


def safe_divide(a, b, default=0.0):
    try:
        b = float(b)
        if b == 0:
            return default
        return float(a) / b
    except Exception:
        return default


def pct_change(current, previous, default=0.0):
    try:
        previous = float(previous)
        if previous == 0:
            return default
        return ((float(current) - previous) / abs(previous)) * 100.0
    except Exception:
        return default


def get_secret(name, default=""):
    try:
        return str(st.secrets[name]).strip()
    except Exception:
        return str(os.getenv(name, default)).strip()


def now_ist():
    return datetime.now(IST)


def fmt_time(dt=None):
    dt = dt or now_ist()
    return dt.strftime("%d-%m-%Y %I:%M:%S %p")


def market_status():
    now = now_ist()
    open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_open = now.weekday() < 5 and open_time <= now <= close_time
    return "Market Open" if is_open else "Market Closed", now.strftime("%A")


def risk_label(score):
    score = clamp(score)
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


def bias_label(score):
    score = signed_clamp(score)
    if score >= 55:
        return "STRONG BULLISH"
    if score >= 20:
        return "BULLISH"
    if score <= -55:
        return "STRONG BEARISH"
    if score <= -20:
        return "BEARISH"
    return "MIXED"


def manual_risk_score(label):
    return {"Low": 15, "Medium": 45, "High": 70, "Critical": 92}.get(label, 15)


def dhan_credentials():
    return get_secret("DHAN_CLIENT_ID"), get_secret("DHAN_ACCESS_TOKEN")


def dhan_headers(client_id, access_token):
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "client-id": str(client_id),
        "access-token": str(access_token),
    }


# =========================================================
# DHANHQ DATA LAYER
# =========================================================
@st.cache_data(ttl=86400, show_spinner=False)
def get_dhan_instrument_master():
    """Fetch Dhan compact instrument master and return a DataFrame."""
    try:
        response = requests.get(DHAN_INSTRUMENT_MASTER, timeout=25)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text), low_memory=False)
        return {"success": True, "df": df, "message": "Dhan instrument master loaded."}
    except Exception as exc:
        return {"success": False, "df": pd.DataFrame(), "message": f"Instrument master error: {exc}"}


def resolve_top5_security_ids(master_df):
    """Resolve NSE equity security IDs from Dhan instrument master."""
    if master_df is None or master_df.empty:
        return {}

    required = {
        "exchange": "SEM_EXM_EXCH_ID",
        "segment": "SEM_SEGMENT",
        "security": "SEM_SMST_SECURITY_ID",
        "symbol": "SEM_TRADING_SYMBOL",
    }
    if not all(column in master_df.columns for column in required.values()):
        return {}

    work = master_df.copy()
    work[required["exchange"]] = work[required["exchange"]].astype(str).str.upper().str.strip()
    work[required["segment"]] = work[required["segment"]].astype(str).str.upper().str.strip()
    work[required["symbol"]] = work[required["symbol"]].astype(str).str.upper().str.strip()

    eq = work[(work[required["exchange"]] == "NSE") & (work[required["segment"]] == "E")]
    result = {}
    for symbol in TOP5_DEFAULT:
        rows = eq[eq[required["symbol"]] == symbol]
        if not rows.empty:
            try:
                result[symbol] = int(float(rows.iloc[0][required["security"]]))
            except Exception:
                pass
    return result


@st.cache_data(ttl=4, show_spinner=False)
def get_dhan_market_bundle(client_id, access_token, top5_ids, nifty_security_id=DEFAULT_NIFTY_SECURITY_ID):
    """One Dhan Market Quote request for Nifty + top-5 equities."""
    if not client_id or not access_token:
        return {"success": False, "message": "Dhan credentials missing."}
    try:
        body = {"IDX_I": [int(nifty_security_id)]}
        if top5_ids:
            body["NSE_EQ"] = [int(v) for v in top5_ids.values()]

        response = requests.post(
            f"{DHAN_BASE}/marketfeed/quote",
            headers=dhan_headers(client_id, access_token),
            json=body,
            timeout=12,
        )
        if response.status_code != 200:
            return {"success": False, "message": f"Dhan Market Quote HTTP {response.status_code}: {response.text[:180]}"}
        payload = response.json()
        if payload.get("status") != "success":
            return {"success": False, "message": f"Dhan Market Quote failed: {payload}"}
        return {"success": True, "data": payload.get("data", {}), "fetched_at": fmt_time(), "message": "OK"}
    except Exception as exc:
        return {"success": False, "message": f"Dhan Market Quote error: {exc}"}


@st.cache_data(ttl=600, show_spinner=False)
def get_dhan_expiries(client_id, access_token, underlying_scrip=DEFAULT_NIFTY_SECURITY_ID, underlying_seg=DEFAULT_NIFTY_SEGMENT):
    if not client_id or not access_token:
        return {"success": False, "expiries": [], "message": "Dhan credentials missing."}
    try:
        response = requests.post(
            f"{DHAN_BASE}/optionchain/expirylist",
            headers=dhan_headers(client_id, access_token),
            json={"UnderlyingScrip": int(underlying_scrip), "UnderlyingSeg": underlying_seg},
            timeout=12,
        )
        if response.status_code != 200:
            return {"success": False, "expiries": [], "message": f"Dhan expiry HTTP {response.status_code}: {response.text[:180]}"}
        payload = response.json()
        expiries = payload.get("data", []) if payload.get("status") == "success" else []
        return {"success": bool(expiries), "expiries": expiries, "message": "OK" if expiries else f"No expiries: {payload}"}
    except Exception as exc:
        return {"success": False, "expiries": [], "message": f"Dhan expiry error: {exc}"}


def parse_dhan_leg(leg):
    leg = leg or {}
    greeks = leg.get("greeks", {}) or {}
    ltp = float(leg.get("last_price", 0) or 0)
    prev_close = float(leg.get("previous_close_price", 0) or 0)
    oi = int(leg.get("oi", 0) or 0)
    prev_oi = int(leg.get("previous_oi", 0) or 0)
    volume = int(leg.get("volume", 0) or 0)
    prev_volume = int(leg.get("previous_volume", 0) or 0)
    bid = float(leg.get("top_bid_price", 0) or 0)
    ask = float(leg.get("top_ask_price", 0) or 0)
    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else max(ltp, 0)
    spread = max(ask - bid, 0) if ask > 0 and bid > 0 else 0

    return {
        "ltp": ltp,
        "previous_close": prev_close,
        "price_change": ltp - prev_close if prev_close else 0.0,
        "price_change_pct": pct_change(ltp, prev_close),
        "oi": oi,
        "previous_oi": prev_oi,
        "oi_change": oi - prev_oi,
        "oi_change_pct": pct_change(oi, prev_oi),
        "volume": volume,
        "previous_volume": prev_volume,
        "volume_ratio": safe_divide(volume, prev_volume, 0.0),
        "iv": float(leg.get("implied_volatility", 0) or 0),
        "delta": float(greeks.get("delta", 0) or 0),
        "theta": float(greeks.get("theta", 0) or 0),
        "gamma": float(greeks.get("gamma", 0) or 0),
        "vega": float(greeks.get("vega", 0) or 0),
        "bid": bid,
        "ask": ask,
        "bid_qty": int(leg.get("top_bid_quantity", 0) or 0),
        "ask_qty": int(leg.get("top_ask_quantity", 0) or 0),
        "spread": spread,
        "spread_pct": safe_divide(spread, mid, 0.0) * 100 if mid else 0.0,
        "security_id": int(leg.get("security_id", 0) or 0),
        "average_price": float(leg.get("average_price", 0) or 0),
    }


@st.cache_data(ttl=4, show_spinner=False)
def get_dhan_option_chain(client_id, access_token, expiry, underlying_scrip=DEFAULT_NIFTY_SECURITY_ID, underlying_seg=DEFAULT_NIFTY_SEGMENT, strikes_each_side=6, strike_gap=50):
    """Fetch and normalize Dhan option chain. Official API minimum unique request window is 3 seconds."""
    if not client_id or not access_token or not expiry:
        return {"success": False, "message": "Dhan credentials/expiry missing."}
    try:
        response = requests.post(
            f"{DHAN_BASE}/optionchain",
            headers=dhan_headers(client_id, access_token),
            json={
                "UnderlyingScrip": int(underlying_scrip),
                "UnderlyingSeg": underlying_seg,
                "Expiry": str(expiry),
            },
            timeout=15,
        )
        if response.status_code != 200:
            return {"success": False, "message": f"Dhan Option Chain HTTP {response.status_code}: {response.text[:220]}"}
        payload = response.json()
        if payload.get("status") != "success":
            return {"success": False, "message": f"Dhan Option Chain failed: {payload}"}

        data = payload.get("data", {}) or {}
        spot = float(data.get("last_price", 0) or 0)
        raw_oc = data.get("oc", {}) or {}
        if not raw_oc:
            return {"success": False, "message": "Dhan option chain returned no strikes."}

        atm = int(round(spot / strike_gap) * strike_gap) if spot else 0
        lower = atm - strikes_each_side * strike_gap
        upper = atm + strikes_each_side * strike_gap
        rows = []

        for strike_key, strike_data in raw_oc.items():
            try:
                strike = int(round(float(strike_key)))
            except Exception:
                continue
            if atm and not (lower <= strike <= upper):
                continue

            ce = parse_dhan_leg((strike_data or {}).get("ce", {}))
            pe = parse_dhan_leg((strike_data or {}).get("pe", {}))
            row = {"strike": strike}
            for prefix, leg in (("ce", ce), ("pe", pe)):
                for key, value in leg.items():
                    row[f"{prefix}_{key}"] = value
            rows.append(row)

        rows.sort(key=lambda x: x["strike"])
        if not rows:
            return {"success": False, "message": "No Dhan strikes found near ATM."}

        total_call_oi = sum(r["ce_oi"] for r in rows)
        total_put_oi = sum(r["pe_oi"] for r in rows)
        call_oi_change = sum(r["ce_oi_change"] for r in rows)
        put_oi_change = sum(r["pe_oi_change"] for r in rows)

        return {
            "success": True,
            "source": "DhanHQ",
            "underlying": spot,
            "expiry": str(expiry),
            "atm_strike": atm,
            "rows": rows,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "call_oi_change": call_oi_change,
            "put_oi_change": put_oi_change,
            "pcr": safe_divide(total_put_oi, total_call_oi, 0.0),
            "fetched_at": fmt_time(),
            "snapshot_id": f"{expiry}|{fmt_time()}|{sum(r['ce_oi'] + r['pe_oi'] for r in rows)}",
            "message": "OK",
        }
    except Exception as exc:
        return {"success": False, "message": f"Dhan Option Chain error: {exc}"}


# =========================================================
# YAHOO FALLBACKS (NO NSE OPTION-CHAIN SCRAPING)
# =========================================================
@st.cache_data(ttl=30, show_spinner=False)
def get_yahoo_nifty():
    try:
        ticker = yf.Ticker("^NSEI")
        intraday = ticker.history(period="2d", interval="1m").dropna()
        if intraday.empty:
            intraday = ticker.history(period="5d", interval="5m").dropna()
        if intraday.empty:
            return {"success": False, "message": "Yahoo Nifty unavailable."}
        ltp = float(intraday["Close"].iloc[-1])
        daily = ticker.history(period="7d", interval="1d").dropna()
        prev = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else ltp
        return {
            "success": True,
            "price": ltp,
            "change": ltp - prev,
            "change_pct": pct_change(ltp, prev),
            "source": "Yahoo fallback",
            "fetched_at": fmt_time(),
        }
    except Exception as exc:
        return {"success": False, "message": f"Yahoo Nifty error: {exc}"}


@st.cache_data(ttl=60, show_spinner=False)
def get_yahoo_vix():
    try:
        ticker = yf.Ticker("^INDIAVIX")
        intraday = ticker.history(period="2d", interval="1m").dropna()
        if intraday.empty:
            intraday = ticker.history(period="5d", interval="5m").dropna()
        if intraday.empty:
            return {"success": False, "message": "Yahoo VIX unavailable."}
        ltp = float(intraday["Close"].iloc[-1])
        daily = ticker.history(period="7d", interval="1d").dropna()
        prev = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else ltp
        return {
            "success": True,
            "vix": ltp,
            "change": ltp - prev,
            "change_pct": pct_change(ltp, prev),
            "source": "Yahoo fallback",
            "fetched_at": fmt_time(),
        }
    except Exception as exc:
        return {"success": False, "message": f"Yahoo VIX error: {exc}"}


@st.cache_data(ttl=60, show_spinner=False)
def get_yahoo_heavyweights():
    """Batch fallback for top-5 stock moves; 5-minute bars to keep it lighter."""
    try:
        symbols = [cfg["yahoo"] for cfg in TOP5_DEFAULT.values()]
        intraday = yf.download(
            tickers=symbols,
            period="2d",
            interval="5m",
            group_by="column",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        daily = yf.download(
            tickers=symbols,
            period="7d",
            interval="1d",
            group_by="column",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        rows = []
        for symbol, cfg in TOP5_DEFAULT.items():
            ysym = cfg["yahoo"]
            try:
                if isinstance(intraday.columns, pd.MultiIndex):
                    close_series = intraday["Close"][ysym].dropna()
                    vol_series = intraday["Volume"][ysym].dropna() if "Volume" in intraday.columns.get_level_values(0) else pd.Series(dtype=float)
                else:
                    close_series = intraday["Close"].dropna()
                    vol_series = intraday.get("Volume", pd.Series(dtype=float)).dropna()
                if isinstance(daily.columns, pd.MultiIndex):
                    day_close = daily["Close"][ysym].dropna()
                else:
                    day_close = daily["Close"].dropna()
                if close_series.empty:
                    continue
                ltp = float(close_series.iloc[-1])
                prev = float(day_close.iloc[-2]) if len(day_close) >= 2 else ltp
                momentum_5m = pct_change(ltp, float(close_series.iloc[-2])) if len(close_series) >= 2 else 0.0
                rows.append({
                    "symbol": symbol,
                    "name": cfg["name"],
                    "weight": cfg["weight"],
                    "ltp": ltp,
                    "previous_close": prev,
                    "change_pct": pct_change(ltp, prev),
                    "momentum_pct": momentum_5m,
                    "volume": int(vol_series.iloc[-1]) if not vol_series.empty else 0,
                })
            except Exception:
                continue
        return {"success": bool(rows), "rows": rows, "source": "Yahoo fallback", "fetched_at": fmt_time(), "message": "OK" if rows else "No heavyweight rows."}
    except Exception as exc:
        return {"success": False, "rows": [], "message": f"Yahoo heavyweight error: {exc}"}


# =========================================================
# SNAPSHOT DELTAS + OPTION INTELLIGENCE
# =========================================================
def attach_option_snapshot_deltas(rows, snapshot_id):
    """Add snapshot-to-snapshot deltas for OI acceleration. First snapshot is day-change only."""
    current_map = {}
    for row in rows:
        for side in ("ce", "pe"):
            current_map[(row["strike"], side)] = {
                "ltp": row.get(f"{side}_ltp", 0),
                "oi": row.get(f"{side}_oi", 0),
                "volume": row.get(f"{side}_volume", 0),
            }

    last_id = st.session_state.get("oc_snapshot_id")
    previous_map = st.session_state.get("oc_snapshot_map", {})
    stored_deltas = st.session_state.get("oc_snapshot_deltas", {})

    if snapshot_id != last_id:
        deltas = {}
        for key, current in current_map.items():
            previous = previous_map.get(key)
            if previous:
                deltas[key] = {
                    "price": current["ltp"] - previous["ltp"],
                    "price_pct": pct_change(current["ltp"], previous["ltp"]),
                    "oi": current["oi"] - previous["oi"],
                    "oi_pct": pct_change(current["oi"], previous["oi"]),
                    "volume": current["volume"] - previous["volume"],
                    "ready": True,
                }
            else:
                deltas[key] = {"price": 0.0, "price_pct": 0.0, "oi": 0, "oi_pct": 0.0, "volume": 0, "ready": False}
        st.session_state["oc_snapshot_map"] = current_map
        st.session_state["oc_snapshot_id"] = snapshot_id
        st.session_state["oc_snapshot_deltas"] = deltas
        stored_deltas = deltas

    output = []
    for row in rows:
        row = row.copy()
        for side in ("ce", "pe"):
            delta = stored_deltas.get((row["strike"], side), {})
            row[f"{side}_snap_price_change"] = delta.get("price", 0.0)
            row[f"{side}_snap_price_change_pct"] = delta.get("price_pct", 0.0)
            row[f"{side}_snap_oi_change"] = delta.get("oi", 0)
            row[f"{side}_snap_oi_change_pct"] = delta.get("oi_pct", 0.0)
            row[f"{side}_snap_volume_change"] = delta.get("volume", 0)
            row[f"{side}_snapshot_ready"] = bool(delta.get("ready", False))
        output.append(row)
    return output


def classify_oi_price_signal(side, row):
    """Conventional OI/price inference; not proof of buyer/seller identity."""
    prefix = side.lower()
    use_snapshot = bool(row.get(f"{prefix}_snapshot_ready", False)) and (
        abs(row.get(f"{prefix}_snap_price_change_pct", 0)) >= 0.02
        or abs(row.get(f"{prefix}_snap_oi_change_pct", 0)) >= 0.02
    )

    if use_snapshot:
        price_delta = row.get(f"{prefix}_snap_price_change", 0.0)
        price_pct = row.get(f"{prefix}_snap_price_change_pct", 0.0)
        oi_delta = row.get(f"{prefix}_snap_oi_change", 0)
        oi_pct = row.get(f"{prefix}_snap_oi_change_pct", 0.0)
        basis = "Snapshot"
    else:
        price_delta = row.get(f"{prefix}_price_change", 0.0)
        price_pct = row.get(f"{prefix}_price_change_pct", 0.0)
        oi_delta = row.get(f"{prefix}_oi_change", 0)
        oi_pct = row.get(f"{prefix}_oi_change_pct", 0.0)
        basis = "Day"

    if price_delta > 0 and oi_delta > 0:
        signal = f"Likely Fresh {side} Buying"
        market_bias = 1 if side == "CE" else -1
    elif price_delta < 0 and oi_delta > 0:
        signal = f"Likely Fresh {side} Writing"
        market_bias = -1 if side == "CE" else 1
    elif price_delta > 0 and oi_delta < 0:
        signal = f"{side} Short Covering"
        market_bias = 1 if side == "CE" else -1
    elif price_delta < 0 and oi_delta < 0:
        signal = f"{side} Long Unwinding"
        market_bias = -0.45 if side == "CE" else 0.45
    else:
        signal = "Neutral"
        market_bias = 0

    strength = 25
    strength += min(abs(price_pct) * 8, 25)
    strength += min(abs(oi_pct) * 2.5, 25)

    volume_ratio = row.get(f"{prefix}_volume_ratio", 0.0)
    if volume_ratio >= 2:
        strength += 15
    elif volume_ratio >= 1.2:
        strength += 10
    elif volume_ratio >= 0.7:
        strength += 5

    spread_pct = row.get(f"{prefix}_spread_pct", 0.0)
    if 0 < spread_pct <= 0.5:
        strength += 10
    elif spread_pct <= 1.0:
        strength += 6
    elif spread_pct > 2.0:
        strength -= 10

    if use_snapshot:
        strength += 8

    strength = int(round(clamp(strength, 0, 98)))
    directional_score = market_bias * strength
    return {
        "signal": signal,
        "basis": basis,
        "strength": strength,
        "directional_score": directional_score,
        "price_pct": price_pct,
        "oi_pct": oi_pct,
        "oi_delta": oi_delta,
    }


def score_sell_candidate(side, row, signal_info, spot):
    prefix = side.lower()
    score = 35.0
    reasons = []
    strike = row["strike"]

    is_otm = strike >= spot if side == "CE" else strike <= spot
    if is_otm:
        score += 10
        reasons.append("OTM/ATM side")
    else:
        score -= 18
        reasons.append("ITM risk")

    signal = signal_info["signal"]
    if "Writing" in signal:
        score += 24
        reasons.append("writing inference")
    elif "Short Covering" in signal:
        score -= 30
        reasons.append("short-covering risk")
    elif "Buying" in signal:
        score -= 24
        reasons.append("buyer pressure")
    elif "Long Unwinding" in signal:
        score += 2

    delta_abs = abs(row.get(f"{prefix}_delta", 0.0))
    if 0.15 <= delta_abs <= 0.32:
        score += 18
        reasons.append("seller-friendly delta")
    elif 0.10 <= delta_abs <= 0.40:
        score += 10
    elif delta_abs >= 0.48:
        score -= 20
        reasons.append("high delta")

    spread_pct = row.get(f"{prefix}_spread_pct", 0.0)
    if 0 < spread_pct <= 0.5:
        score += 12
        reasons.append("tight spread")
    elif spread_pct <= 1.0:
        score += 7
    elif spread_pct > 2.0:
        score -= 15
        reasons.append("wide spread")

    volume_ratio = row.get(f"{prefix}_volume_ratio", 0.0)
    if volume_ratio >= 1.5:
        score += 8
    elif volume_ratio >= 0.75:
        score += 4

    oi_change_pct = row.get(f"{prefix}_oi_change_pct", 0.0)
    if oi_change_pct > 0:
        score += min(oi_change_pct * 0.4, 8)

    iv = row.get(f"{prefix}_iv", 0.0)
    if 8 <= iv <= 25:
        score += 6
    elif iv > 35:
        score -= 6
        reasons.append("very high IV risk")

    theta = row.get(f"{prefix}_theta", 0.0)
    if theta < -3:
        score += 4

    return int(round(clamp(score, 0, 98))), ", ".join(reasons[:4])


def analyze_option_chain(option_chain):
    if not option_chain.get("success"):
        return {"success": False, "rows": [], "bias": 0, "message": option_chain.get("message", "No option chain")}

    rows = attach_option_snapshot_deltas(option_chain["rows"], option_chain["snapshot_id"])
    spot = option_chain["underlying"]
    atm = option_chain["atm_strike"]
    analyzed = []
    directional_total = 0.0
    directional_weight = 0.0

    for row in rows:
        ce_info = classify_oi_price_signal("CE", row)
        pe_info = classify_oi_price_signal("PE", row)
        ce_sell_score, ce_reason = score_sell_candidate("CE", row, ce_info, spot)
        pe_sell_score, pe_reason = score_sell_candidate("PE", row, pe_info, spot)

        distance = abs(row["strike"] - atm)
        near_weight = max(0.35, 1.0 - (distance / 500.0))
        directional_total += (ce_info["directional_score"] + pe_info["directional_score"]) * near_weight
        directional_weight += 2 * 98 * near_weight

        analyzed.append({
            **row,
            "ce_signal": ce_info["signal"],
            "ce_signal_basis": ce_info["basis"],
            "ce_signal_strength": ce_info["strength"],
            "ce_sell_score": ce_sell_score,
            "ce_sell_reason": ce_reason,
            "pe_signal": pe_info["signal"],
            "pe_signal_basis": pe_info["basis"],
            "pe_signal_strength": pe_info["strength"],
            "pe_sell_score": pe_sell_score,
            "pe_sell_reason": pe_reason,
        })

    bias = signed_clamp(safe_divide(directional_total, directional_weight, 0.0) * 100, -100, 100)
    ce_candidates = [r for r in analyzed if r["strike"] >= spot]
    pe_candidates = [r for r in analyzed if r["strike"] <= spot]
    best_ce = max(ce_candidates, key=lambda r: r["ce_sell_score"], default=None)
    best_pe = max(pe_candidates, key=lambda r: r["pe_sell_score"], default=None)

    return {
        "success": True,
        "rows": analyzed,
        "bias": bias,
        "best_ce": best_ce,
        "best_pe": best_pe,
        "message": "OK",
    }


# =========================================================
# HEAVYWEIGHT DRIVER ENGINE
# =========================================================
def parse_dhan_heavyweights(bundle, top5_ids, weights):
    if not bundle.get("success") or not top5_ids:
        return {"success": False, "rows": [], "message": bundle.get("message", "No Dhan bundle")}
    try:
        eq = (bundle.get("data", {}) or {}).get("NSE_EQ", {}) or {}
        rows = []
        for symbol, sec_id in top5_ids.items():
            item = eq.get(str(sec_id), {}) or eq.get(int(sec_id), {}) or {}
            if not item:
                continue
            cfg = TOP5_DEFAULT[symbol]
            ltp = float(item.get("last_price", 0) or 0)
            ohlc = item.get("ohlc", {}) or {}
            prev = float(ohlc.get("close", 0) or 0)
            rows.append({
                "symbol": symbol,
                "name": cfg["name"],
                "weight": float(weights.get(symbol, cfg["weight"])),
                "ltp": ltp,
                "previous_close": prev,
                "change_pct": pct_change(ltp, prev),
                "momentum_pct": 0.0,
                "volume": int(item.get("volume", 0) or 0),
            })
        return {"success": bool(rows), "rows": rows, "source": "DhanHQ", "fetched_at": bundle.get("fetched_at", fmt_time()), "message": "OK" if rows else "No Dhan heavyweight rows."}
    except Exception as exc:
        return {"success": False, "rows": [], "message": f"Dhan heavyweight parse error: {exc}"}


def attach_heavyweight_shocks(rows, snapshot_id):
    current = {r["symbol"]: r["change_pct"] for r in rows}
    last_id = st.session_state.get("hw_snapshot_id")
    previous = st.session_state.get("hw_snapshot_map", {})
    shocks = st.session_state.get("hw_snapshot_shocks", {})

    if snapshot_id != last_id:
        new_shocks = {}
        for symbol, change_pct_value in current.items():
            if symbol in previous:
                new_shocks[symbol] = change_pct_value - previous[symbol]
            else:
                new_shocks[symbol] = 0.0
        st.session_state["hw_snapshot_id"] = snapshot_id
        st.session_state["hw_snapshot_map"] = current
        st.session_state["hw_snapshot_shocks"] = new_shocks
        shocks = new_shocks

    output = []
    for row in rows:
        row = row.copy()
        row["shock_delta_pct"] = float(shocks.get(row["symbol"], 0.0))
        output.append(row)
    return output


def analyze_heavyweights(hw_data, nifty_level, nifty_change_pct):
    if not hw_data.get("success") or not hw_data.get("rows"):
        return {"success": False, "rows": [], "pressure": 0, "estimated_points": 0, "message": hw_data.get("message", "No heavyweight data")}

    snapshot_id = f"{hw_data.get('fetched_at','')}|{sum(round(r['change_pct'],4) for r in hw_data['rows'])}"
    rows = attach_heavyweight_shocks(hw_data["rows"], snapshot_id)
    combined_weight = sum(r["weight"] for r in rows) or 1.0
    weighted_return = sum(r["weight"] * r["change_pct"] for r in rows) / combined_weight
    pressure = signed_clamp(weighted_return * 75, -100, 100)
    estimated_points = sum(nifty_level * (r["weight"] / 100.0) * (r["change_pct"] / 100.0) for r in rows)

    hdfc = next((r for r in rows if r["symbol"] == "HDFCBANK"), None)
    icici = next((r for r in rows if r["symbol"] == "ICICIBANK"), None)
    banking_pair = "MIXED"
    if hdfc and icici:
        if hdfc["change_pct"] > 0.15 and icici["change_pct"] > 0.15:
            banking_pair = "BULLISH"
        elif hdfc["change_pct"] < -0.15 and icici["change_pct"] < -0.15:
            banking_pair = "BEARISH"

    divergence = "NONE"
    if nifty_change_pct >= 0.20 and pressure <= -20:
        divergence = "NIFTY UP / HEAVYWEIGHTS WEAK"
    elif nifty_change_pct <= -0.20 and pressure >= 20:
        divergence = "NIFTY DOWN / HEAVYWEIGHTS STRONG"
    elif abs(nifty_change_pct) <= 0.10 and abs(pressure) >= 45:
        divergence = "HIDDEN HEAVYWEIGHT PRESSURE"

    shock_rows = [r for r in rows if abs(r.get("shock_delta_pct", 0.0)) >= 0.30]
    max_shock = max((abs(r.get("shock_delta_pct", 0.0)) for r in rows), default=0.0)
    shock_score = clamp(max_shock * 120, 0, 100)

    return {
        "success": True,
        "rows": rows,
        "pressure": pressure,
        "estimated_points": estimated_points,
        "banking_pair": banking_pair,
        "divergence": divergence,
        "shock_rows": shock_rows,
        "shock_score": shock_score,
        "source": hw_data.get("source", "Unknown"),
        "message": "OK",
    }


# =========================================================
# AUTOMATIC NEWS RISK ENGINE (OPTIONAL KEYS + MARKET REACTION)
# =========================================================
@st.cache_data(ttl=900, show_spinner=False)
def get_te_calendar_risk(api_key):
    """Optional Trading Economics calendar risk for India + United States."""
    if not api_key:
        return {"success": False, "score": 0, "events": 0, "message": "TE key missing."}
    try:
        all_events = []
        for country in ("india", "united states"):
            url = f"https://api.tradingeconomics.com/calendar/country/{quote(country)}?c={quote(api_key)}"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, list):
                    all_events.extend(payload)

        now = now_ist()
        max_score = 0.0
        relevant = 0
        nearest_minutes = None
        for event in all_events:
            importance = int(event.get("Importance", 0) or 0)
            if importance < 2:
                continue
            raw_date = event.get("Date") or event.get("date")
            if not raw_date:
                continue
            try:
                dt = pd.to_datetime(raw_date, utc=True).to_pydatetime().astimezone(IST)
            except Exception:
                continue
            minutes = (dt - now).total_seconds() / 60.0
            if -30 <= minutes <= 24 * 60:
                relevant += 1
                nearest_minutes = minutes if nearest_minutes is None else min(nearest_minutes, minutes, key=abs)
                if importance >= 3:
                    score = 92 if abs(minutes) <= 30 else 82 if minutes <= 90 else 68 if minutes <= 240 else 52
                else:
                    score = 65 if abs(minutes) <= 30 else 52 if minutes <= 120 else 35
                max_score = max(max_score, score)

        return {
            "success": True,
            "score": clamp(max_score),
            "events": relevant,
            "nearest_minutes": nearest_minutes,
            "message": "OK",
        }
    except Exception as exc:
        return {"success": False, "score": 0, "events": 0, "message": f"TE calendar error: {exc}"}


@st.cache_data(ttl=900, show_spinner=False)
def get_alpha_news_risk(api_key):
    """Optional Alpha Vantage news sentiment risk. Headlines are not displayed."""
    if not api_key:
        return {"success": False, "score": 0, "items": 0, "message": "Alpha Vantage key missing."}
    try:
        params = {
            "function": "NEWS_SENTIMENT",
            "topics": "financial_markets,economy_macro",
            "sort": "LATEST",
            "limit": 50,
            "apikey": api_key,
        }
        response = requests.get("https://www.alphavantage.co/query", params=params, timeout=18)
        if response.status_code != 200:
            return {"success": False, "score": 0, "items": 0, "message": f"Alpha HTTP {response.status_code}"}
        payload = response.json()
        feed = payload.get("feed", []) if isinstance(payload, dict) else []
        if not feed:
            return {"success": False, "score": 0, "items": 0, "message": payload.get("Information", "No news feed") if isinstance(payload, dict) else "No news feed"}

        now = datetime.utcnow()
        keywords = {
            "war", "attack", "tariff", "sanction", "default", "emergency", "recession",
            "inflation", "rate hike", "rate cut", "fed", "rbi", "crude", "oil shock",
            "budget", "election", "missile", "conflict", "bank failure", "downgrade",
        }
        max_score = 0.0
        counted = 0
        for item in feed:
            raw_time = str(item.get("time_published", ""))
            try:
                dt = datetime.strptime(raw_time[:15], "%Y%m%dT%H%M%S")
                age_hours = max((now - dt).total_seconds() / 3600.0, 0)
            except Exception:
                age_hours = 24
            if age_hours > 24:
                continue
            counted += 1
            sentiment = abs(float(item.get("overall_sentiment_score", 0) or 0))
            text = f"{item.get('title','')} {item.get('summary','')}".lower()
            keyword_hits = sum(1 for key in keywords if key in text)
            recency = max(0, 1 - age_hours / 24)
            score = sentiment * 45 + min(keyword_hits * 10, 35) + recency * 20
            max_score = max(max_score, score)

        return {"success": True, "score": clamp(max_score), "items": counted, "message": "OK"}
    except Exception as exc:
        return {"success": False, "score": 0, "items": 0, "message": f"Alpha news error: {exc}"}


def market_reaction_risk(nifty_change_pct, vix_change_pct, heavyweight_analysis):
    score = 0.0
    score += min(abs(nifty_change_pct) * 32, 35)
    score += min(max(vix_change_pct, 0) * 4.5, 30)
    score += min(abs(heavyweight_analysis.get("pressure", 0)) * 0.20, 20)
    score += min(heavyweight_analysis.get("shock_score", 0) * 0.25, 25)
    if heavyweight_analysis.get("divergence") != "NONE":
        score += 10
    return clamp(score)


def build_news_risk(manual_label, te_result, alpha_result, reaction_score, vix_change_pct, heavyweight_shock_score):
    scheduled = te_result.get("score", 0) if te_result.get("success") else manual_risk_score(manual_label)
    breaking = alpha_result.get("score", 0) if alpha_result.get("success") else manual_risk_score(manual_label) * 0.70
    shock = clamp(max(vix_change_pct, 0) * 8 + heavyweight_shock_score * 0.5)
    score = scheduled * 0.35 + breaking * 0.25 + reaction_score * 0.25 + shock * 0.15
    return {
        "score": int(round(clamp(score))),
        "label": risk_label(score),
        "scheduled": int(round(clamp(scheduled))),
        "breaking": int(round(clamp(breaking))),
        "reaction": int(round(clamp(reaction_score))),
        "shock": int(round(clamp(shock))),
        "auto_calendar": bool(te_result.get("success")),
        "auto_news": bool(alpha_result.get("success")),
    }


# =========================================================
# V7 UPGRADE: POSITION MANAGER + EXPIRY/SHOCK/DISCIPLINE
# =========================================================
def detect_expiry_mode(expiry_text, news_score):
    """Auto mode: Normal / Near Expiry / Expiry / Event Risk."""
    if news_score >= 80:
        return "EVENT RISK MODE", 99
    try:
        today = now_ist().date()
        exp_date = pd.to_datetime(str(expiry_text)).date()
        dte = (exp_date - today).days
    except Exception:
        dte = 99
    if dte == 0:
        return "EXPIRY MODE", dte
    if dte in (1, 2):
        return "NEAR EXPIRY MODE", dte
    return "NORMAL DAY MODE", dte


def historical_time_zone_risk(is_expiry):
    """Historical caution zones: prediction nahi, sirf precaution."""
    t = now_ist().time()
    score = 18
    label = "Normal Zone"
    if datetime.strptime("09:15", "%H:%M").time() <= t <= datetime.strptime("09:45", "%H:%M").time():
        score, label = 65, "Opening Volatility Zone"
    elif datetime.strptime("10:00", "%H:%M").time() <= t <= datetime.strptime("10:20", "%H:%M").time():
        score, label = 45, "First Trend Test Zone"
    elif datetime.strptime("11:30", "%H:%M").time() <= t <= datetime.strptime("12:00", "%H:%M").time():
        score, label = 35, "Midday False Move Zone"
    elif datetime.strptime("13:45", "%H:%M").time() <= t <= datetime.strptime("14:15", "%H:%M").time():
        score, label = 42, "Post-Lunch Setup Zone"
    elif datetime.strptime("14:30", "%H:%M").time() <= t <= datetime.strptime("15:15", "%H:%M").time():
        score, label = 58, "Last Hour Move Zone"
    if is_expiry and datetime.strptime("14:15", "%H:%M").time() <= t <= datetime.strptime("15:25", "%H:%M").time():
        score, label = max(score, 78), "Expiry Gamma Danger Zone"
    return int(clamp(score)), label


def theta_decay_score(is_expiry, entry_price, current_price):
    decay_pct = 0.0
    if entry_price and entry_price > 0 and current_price >= 0:
        decay_pct = ((entry_price - current_price) / entry_price) * 100.0
    score = 20 + (35 if is_expiry else 0)
    if decay_pct >= 35:
        score += 35
    elif decay_pct >= 20:
        score += 25
    elif decay_pct >= 10:
        score += 12
    return int(clamp(score)), decay_pct


def gamma_risk_score(is_expiry, vix_change_pct, shock_score, option_bias, heavy_bias):
    score = 18 + (35 if is_expiry else 0)
    if vix_change_pct > 5:
        score += 25
    elif vix_change_pct > 2:
        score += 12
    score += min(abs(option_bias) * 0.15, 12)
    score += min(abs(heavy_bias) * 0.12, 10)
    score += shock_score * 0.22
    return int(clamp(score))


def shock_probability_score(time_risk, vix_risk, option_bias, heavy_bias, news_score):
    oi_shift_risk = clamp(abs(option_bias))
    hw_risk = clamp(abs(heavy_bias))
    score = time_risk * 0.20 + vix_risk * 0.20 + oi_shift_risk * 0.20 + hw_risk * 0.20 + news_score * 0.20
    return int(round(clamp(score)))


def active_position_manager(side, strike, entry_price, current_price, lots, theta_score, gamma_score, shock_score, final_trade, confidence):
    if side == "None" or lots <= 0 or entry_price <= 0:
        return {"action": "NO ACTIVE POSITION", "confidence": 0, "risk": 0, "trail_sl": 0.0, "profit_pct": 0.0, "reasons": ["Active trade details not entered."]}
    profit_pct = ((entry_price - current_price) / entry_price) * 100.0
    reasons = [f"Premium move from ₹{entry_price:.2f} to ₹{current_price:.2f}: approx {profit_pct:.1f}% in seller favour."]
    opposite = (side == "CE" and final_trade == "SELL PE") or (side == "PE" and final_trade == "SELL CE")
    if shock_score >= 78 or gamma_score >= 78:
        reasons += ["Shock/Gamma risk high.", "Capital protection priority."]
        return {"action": "EXIT NOW", "confidence": 88, "risk": max(shock_score, gamma_score), "trail_sl": 0.0, "profit_pct": profit_pct, "reasons": reasons}
    if opposite and confidence >= 60:
        reasons += ["Fresh AI direction is opposite to current sold side.", "Hold risk has increased."]
        return {"action": "EXIT / BOOK PROFIT", "confidence": 82, "risk": max(shock_score, gamma_score), "trail_sl": 0.0, "profit_pct": profit_pct, "reasons": reasons}
    if profit_pct >= 30 and (shock_score >= 55 or gamma_score >= 60):
        reasons += ["Good profit available but risk is rising.", "Book full/partial profit is safer."]
        return {"action": "BOOK PROFIT", "confidence": 84, "risk": max(shock_score, gamma_score), "trail_sl": 0.0, "profit_pct": profit_pct, "reasons": reasons}
    if profit_pct >= 22 and theta_score >= 60 and shock_score < 55:
        trail = round(max(current_price * 1.15, current_price + 3), 2)
        reasons += ["Theta decay still supportive.", f"Trail SL around ₹{trail:.2f} premium."]
        return {"action": "HOLD + TRAIL SL", "confidence": 78, "risk": shock_score, "trail_sl": trail, "profit_pct": profit_pct, "reasons": reasons}
    if theta_score >= 65 and shock_score < 50 and gamma_score < 55:
        reasons += ["Theta favourable and live danger controlled."]
        return {"action": "HOLD", "confidence": 70, "risk": shock_score, "trail_sl": 0.0, "profit_pct": profit_pct, "reasons": reasons}
    reasons += ["No strong edge for aggressive hold.", "Tight SL recommended."]
    return {"action": "TIGHTEN SL", "confidence": 62, "risk": max(shock_score, gamma_score), "trail_sl": round(current_price * 1.10, 2), "profit_pct": profit_pct, "reasons": reasons}


def discipline_status(trades_taken, daily_loss_hit, confidence, seller_risk):
    if daily_loss_hit:
        return "STOP TRADING TODAY", 15, "Daily loss hit: recovery/revenge trade avoid karo."
    if trades_taken >= 3:
        return "OVERTRADING WARNING", 35, "3 or more trades: discipline mode active."
    if confidence < 58:
        return "NO TRADE - LOW CONFIDENCE", 45, "AI confidence low hai. Wait is better."
    if seller_risk >= 70:
        return "RISK HIGH - REDUCE SIZE", 55, "Seller risk high hai; quantity reduce/avoid."
    return "DISCIPLINE OK", 85, "Rules ke andar trade allowed only if setup clear."


def trade_quality_score(confidence, seller_risk, shock_score):
    return int(round(clamp(confidence * 0.55 + (100 - seller_risk) * 0.25 + (100 - shock_score) * 0.20)))


# =========================================================
# SIDEBAR + SOURCE CONFIG
# =========================================================
client_id, access_token = dhan_credentials()
dhan_ready = bool(client_id and access_token)

st.sidebar.title("⚙️ V6 Seller Intelligence")
if st.sidebar.button("🔄 Refresh Live Data", use_container_width=True):
    st.cache_data.clear()

if dhan_ready:
    st.sidebar.success("DhanHQ credentials detected")
else:
    st.sidebar.info("DhanHQ credentials not added yet — safe fallbacks active")

with st.sidebar.expander("1️⃣ Data Source", expanded=True):
    prefer_dhan = st.checkbox("Prefer DhanHQ Live Data", value=dhan_ready, disabled=not dhan_ready)
    nifty_security_id = int(st.number_input("Nifty Dhan Security ID", value=DEFAULT_NIFTY_SECURITY_ID, step=1))
    strikes_each_side = st.slider("Option strikes each side", 3, 10, 6)
    st.caption("NSE direct option-chain scraping removed. DhanHQ is the intended live source.")

with st.sidebar.expander("2️⃣ Manual Market Fallback", expanded=False):
    manual_nifty = st.number_input("Manual Nifty", value=25000.0, step=1.0)
    manual_nifty_change_pct = st.number_input("Manual Nifty Change %", value=0.0, step=0.05)
    manual_vix = st.number_input("Manual India VIX", value=13.5, step=0.1)
    manual_vix_change_pct = st.number_input("Manual VIX Change %", value=0.0, step=0.1)

with st.sidebar.expander("3️⃣ Price Action", expanded=False):
    ema20 = st.number_input("EMA 20", value=24950.0, step=1.0)
    ema50 = st.number_input("EMA 50", value=24900.0, step=1.0)
    vwap = st.number_input("VWAP", value=24940.0, step=1.0)
    atr5 = st.number_input("ATR 5 Min", value=45.0, step=1.0)
    previous_day_high = st.number_input("Previous Day High", value=25150.0, step=1.0)
    previous_day_low = st.number_input("Previous Day Low", value=24850.0, step=1.0)
    today_high = st.number_input("Today High", value=25080.0, step=1.0)
    today_low = st.number_input("Today Low", value=24920.0, step=1.0)
    opening_range_high = st.number_input("Opening Range High", value=25060.0, step=1.0)
    opening_range_low = st.number_input("Opening Range Low", value=24940.0, step=1.0)

with st.sidebar.expander("4️⃣ Manual Option Fallback", expanded=False):
    manual_call_oi_change = st.number_input("Call OI Change", value=150000, step=1000)
    manual_put_oi_change = st.number_input("Put OI Change", value=180000, step=1000)
    manual_total_call_oi = st.number_input("Total Call OI", value=1500000, step=10000)
    manual_total_put_oi = st.number_input("Total Put OI", value=1800000, step=10000)
    manual_ce_strike = int(st.number_input("Manual CE Sell Strike", value=25100, step=50))
    manual_pe_strike = int(st.number_input("Manual PE Sell Strike", value=24900, step=50))
    hedge_gap = int(st.number_input("Hedge Gap", value=100, step=50))

with st.sidebar.expander("5️⃣ FII / DII — Daily Manual", expanded=True):
    fii_today = st.number_input("FII Today ₹ Cr", value=0.0, step=100.0)
    dii_today = st.number_input("DII Today ₹ Cr", value=0.0, step=100.0)
    fii_5day = st.number_input("FII 5 Day Net ₹ Cr", value=0.0, step=100.0)
    dii_5day = st.number_input("DII 5 Day Net ₹ Cr", value=0.0, step=100.0)
    fii_index_futures_bias = st.selectbox("FII Index Futures Bias", ["Neutral", "Bullish", "Bearish"])

with st.sidebar.expander("6️⃣ News Risk", expanded=True):
    manual_news_risk = st.selectbox("Manual fallback", ["Low", "Medium", "High", "Critical"])
    use_auto_news = st.checkbox("Use automatic news APIs when keys exist", value=True)
    st.caption("Optional secrets: TRADING_ECONOMICS_API_KEY, ALPHAVANTAGE_API_KEY")

with st.sidebar.expander("7️⃣ Top-5 Weights", expanded=False):
    st.caption("Defaults: official Nifty 50 factsheet, 30-Jun-2026")
    weights = {}
    for symbol, cfg in TOP5_DEFAULT.items():
        weights[symbol] = st.number_input(f"{cfg['name']} weight %", value=float(cfg["weight"]), step=0.01)

with st.sidebar.expander("8️⃣ Risk / Position", expanded=True):
    capital = st.number_input("Capital ₹", value=500000, step=10000)
    margin_per_lot = st.number_input("Margin Per Lot ₹", value=100000, step=5000)
    current_lots = int(st.number_input("Current Lots", value=0, step=1))
    lot_size = int(st.number_input("Lot Size", value=50, step=25))


with st.sidebar.expander("9️⃣ V8 Active Trade / Discipline", expanded=True):
    active_side = st.selectbox("Active Sold Side", ["None", "CE", "PE"])
    active_strike = int(st.number_input("Active Strike", value=0, step=50))
    active_entry_price = st.number_input("Entry Premium ₹", value=0.0, step=0.05)
    active_current_price = st.number_input("Current Premium ₹", value=0.0, step=0.05)
    active_lots = int(st.number_input("Active Lots", value=0, step=1))
    trades_taken_today = int(st.number_input("Trades Taken Today", value=0, step=1))
    daily_loss_hit = st.checkbox("Daily Loss Hit / Stop Trading", value=False)


# =========================================================
# FETCH LIVE SOURCES
# =========================================================
master_result = get_dhan_instrument_master() if (prefer_dhan and dhan_ready) else {"success": False, "df": pd.DataFrame()}
top5_ids = resolve_top5_security_ids(master_result.get("df", pd.DataFrame())) if master_result.get("success") else {}
dhan_bundle = get_dhan_market_bundle(client_id, access_token, top5_ids, nifty_security_id) if (prefer_dhan and dhan_ready) else {"success": False, "message": "Dhan disabled."}

# Nifty
nifty_source = "Manual"
if dhan_bundle.get("success"):
    idx_data = (dhan_bundle.get("data", {}) or {}).get("IDX_I", {}) or {}
    idx_item = idx_data.get(str(nifty_security_id), {}) or idx_data.get(int(nifty_security_id), {}) or {}
    if idx_item:
        price = float(idx_item.get("last_price", 0) or manual_nifty)
        idx_ohlc = idx_item.get("ohlc", {}) or {}
        idx_prev = float(idx_ohlc.get("close", 0) or 0)
        nifty_change = price - idx_prev if idx_prev else 0.0
        nifty_change_pct = pct_change(price, idx_prev) if idx_prev else manual_nifty_change_pct
        nifty_source = "DhanHQ"
    else:
        yahoo_nifty = get_yahoo_nifty()
        price = yahoo_nifty.get("price", manual_nifty) if yahoo_nifty.get("success") else manual_nifty
        nifty_change = yahoo_nifty.get("change", 0.0) if yahoo_nifty.get("success") else 0.0
        nifty_change_pct = yahoo_nifty.get("change_pct", manual_nifty_change_pct) if yahoo_nifty.get("success") else manual_nifty_change_pct
        nifty_source = yahoo_nifty.get("source", "Manual") if yahoo_nifty.get("success") else "Manual"
else:
    yahoo_nifty = get_yahoo_nifty()
    price = yahoo_nifty.get("price", manual_nifty) if yahoo_nifty.get("success") else manual_nifty
    nifty_change = yahoo_nifty.get("change", 0.0) if yahoo_nifty.get("success") else 0.0
    nifty_change_pct = yahoo_nifty.get("change_pct", manual_nifty_change_pct) if yahoo_nifty.get("success") else manual_nifty_change_pct
    nifty_source = yahoo_nifty.get("source", "Manual") if yahoo_nifty.get("success") else "Manual"

# VIX
yahoo_vix = get_yahoo_vix()
if yahoo_vix.get("success"):
    vix = float(yahoo_vix["vix"])
    vix_change_pct = float(yahoo_vix["change_pct"])
    vix_source = yahoo_vix.get("source", "Yahoo fallback")
else:
    vix = manual_vix
    vix_change_pct = manual_vix_change_pct
    vix_source = "Manual"

# Heavyweights
if dhan_bundle.get("success") and top5_ids:
    heavy_raw = parse_dhan_heavyweights(dhan_bundle, top5_ids, weights)
else:
    heavy_raw = get_yahoo_heavyweights()
    if heavy_raw.get("success"):
        for row in heavy_raw["rows"]:
            row["weight"] = float(weights.get(row["symbol"], row["weight"]))
heavy_analysis = analyze_heavyweights(heavy_raw, price, nifty_change_pct)

# Option chain - Dhan only; manual aggregate fallback otherwise
option_chain = {"success": False, "message": "Waiting for Dhan expiry/option-chain response. Check Data API subscription, expiry list and token."}
selected_expiry = None
expiry_result = {"success": False, "expiries": [], "message": "Dhan not attempted."}
if prefer_dhan and dhan_ready:
    expiry_result = get_dhan_expiries(client_id, access_token, nifty_security_id, DEFAULT_NIFTY_SEGMENT)
    if expiry_result.get("success"):
        selected_expiry = st.sidebar.selectbox("📅 Dhan Nifty Expiry", expiry_result["expiries"], index=0)
        option_chain = get_dhan_option_chain(
            client_id,
            access_token,
            selected_expiry,
            nifty_security_id,
            DEFAULT_NIFTY_SEGMENT,
            strikes_each_side,
            50,
        )
    else:
        option_chain = {"success": False, "message": "Expiry list unavailable: " + str(expiry_result.get("message", "Unknown Dhan expiry error"))}

option_analysis = analyze_option_chain(option_chain) if option_chain.get("success") else {"success": False, "rows": [], "bias": 0}

# Aggregates
if option_chain.get("success"):
    total_call_oi = option_chain["total_call_oi"]
    total_put_oi = option_chain["total_put_oi"]
    call_oi_change = option_chain["call_oi_change"]
    put_oi_change = option_chain["put_oi_change"]
    pcr = option_chain["pcr"]
else:
    total_call_oi = manual_total_call_oi
    total_put_oi = manual_total_put_oi
    call_oi_change = manual_call_oi_change
    put_oi_change = manual_put_oi_change
    pcr = safe_divide(total_put_oi, total_call_oi, 0.0)

# News risk
te_key = get_secret("TRADING_ECONOMICS_API_KEY")
alpha_key = get_secret("ALPHAVANTAGE_API_KEY")
te_result = get_te_calendar_risk(te_key) if use_auto_news and te_key else {"success": False, "score": 0}
alpha_result = get_alpha_news_risk(alpha_key) if use_auto_news and alpha_key else {"success": False, "score": 0}
reaction_score = market_reaction_risk(nifty_change_pct, vix_change_pct, heavy_analysis)
news = build_news_risk(manual_news_risk, te_result, alpha_result, reaction_score, vix_change_pct, heavy_analysis.get("shock_score", 0))


# =========================================================
# SELLER INTELLIGENCE ENGINE
# =========================================================
support_levels = [previous_day_low, today_low, opening_range_low]
resistance_levels = [previous_day_high, today_high, opening_range_high]
nearest_support = max([x for x in support_levels if x <= price], default=min(support_levels))
nearest_resistance = min([x for x in resistance_levels if x >= price], default=max(resistance_levels))
support_distance = max(price - nearest_support, 0)
resistance_distance = max(nearest_resistance - price, 0)

price_action_bias = 0.0
price_action_bias += 22 if price > ema20 else -22
price_action_bias += 18 if price > ema50 else -18
price_action_bias += 25 if price > vwap else -25
price_action_bias += 15 if ema20 > ema50 else -15
if price > opening_range_high:
    price_action_bias += 18
elif price < opening_range_low:
    price_action_bias -= 18
price_action_bias = signed_clamp(price_action_bias)

sr_bias = 0.0
if support_distance <= 30:
    sr_bias += 55
elif support_distance <= 60:
    sr_bias += 25
if resistance_distance <= 30:
    sr_bias -= 55
elif resistance_distance <= 60:
    sr_bias -= 25
sr_bias = signed_clamp(sr_bias)

# Option-chain directional bias. When Dhan is absent, use aggregate OI + PCR only.
if option_analysis.get("success"):
    option_bias = float(option_analysis.get("bias", 0))
else:
    oi_delta_base = max(abs(call_oi_change), abs(put_oi_change), 1)
    option_bias = signed_clamp(((put_oi_change - call_oi_change) / oi_delta_base) * 65)

pcr_bias = 0.0
if 0.95 <= pcr <= 1.25:
    pcr_bias = 35
elif 1.25 < pcr <= 1.55:
    pcr_bias = 18
elif pcr > 1.55:
    pcr_bias = -5
elif 0.75 <= pcr < 0.95:
    pcr_bias = -22
else:
    pcr_bias = -45

smart_money_bias = 0.0
smart_money_bias += 22 if fii_today > 0 else -22 if fii_today < 0 else 0
smart_money_bias += 10 if dii_today > 0 else -10 if dii_today < 0 else 0
smart_money_bias += 18 if fii_5day > 0 else -18 if fii_5day < 0 else 0
smart_money_bias += 8 if dii_5day > 0 else -8 if dii_5day < 0 else 0
smart_money_bias += 22 if fii_index_futures_bias == "Bullish" else -22 if fii_index_futures_bias == "Bearish" else 0
smart_money_bias = signed_clamp(smart_money_bias)

heavy_bias = float(heavy_analysis.get("pressure", 0)) if heavy_analysis.get("success") else 0.0

# Weighted directional model
final_direction = (
    price_action_bias * 0.24
    + option_bias * 0.24
    + heavy_bias * 0.19
    + smart_money_bias * 0.12
    + pcr_bias * 0.09
    + sr_bias * 0.12
)
final_direction = signed_clamp(final_direction)

# Risk model for an option seller
vix_risk = 15 if vix <= 14 else 30 if vix <= 18 else 65 if vix <= 24 else 90
liquidity_risk = 0
if option_analysis.get("success"):
    selected_rows = [r for r in option_analysis["rows"] if abs(r["strike"] - price) <= 200]
    wide = [r for r in selected_rows if max(r.get("ce_spread_pct", 0), r.get("pe_spread_pct", 0)) > 2.0]
    liquidity_risk = safe_divide(len(wide), len(selected_rows), 0) * 100 if selected_rows else 0

divergence_risk = 35 if heavy_analysis.get("divergence") != "NONE" else 0
seller_risk = (
    news["score"] * 0.42
    + vix_risk * 0.25
    + heavy_analysis.get("shock_score", 0) * 0.18
    + divergence_risk * 0.08
    + liquidity_risk * 0.07
)
seller_risk = clamp(seller_risk)

component_signs = [price_action_bias, option_bias, heavy_bias, smart_money_bias, pcr_bias, sr_bias]
positive_components = sum(1 for x in component_signs if x >= 15)
negative_components = sum(1 for x in component_signs if x <= -15)
agreement = max(positive_components, negative_components) / len(component_signs)
confidence = clamp(abs(final_direction) * 0.72 + agreement * 35 + (100 - seller_risk) * 0.18, 0, 98)

hard_block = news["score"] >= 80 or seller_risk >= 82
if hard_block:
    final_trade = "WAIT"
elif final_direction >= 24 and confidence >= 58:
    final_trade = "SELL PE"
elif final_direction <= -24 and confidence >= 58:
    final_trade = "SELL CE"
else:
    final_trade = "WAIT"

# Strike selection from Dhan ranking when available; manual fallback otherwise.
best_ce = option_analysis.get("best_ce") if option_analysis.get("success") else None
best_pe = option_analysis.get("best_pe") if option_analysis.get("success") else None
ce_strike = int(best_ce["strike"]) if best_ce else manual_ce_strike
pe_strike = int(best_pe["strike"]) if best_pe else manual_pe_strike

if final_trade == "SELL PE":
    selected_strike = f"{pe_strike} PE"
    hedge = f"{pe_strike - hedge_gap} PE"
    selected_strike_score = best_pe.get("pe_sell_score", 0) if best_pe else 0
elif final_trade == "SELL CE":
    selected_strike = f"{ce_strike} CE"
    hedge = f"{ce_strike + hedge_gap} CE"
    selected_strike_score = best_ce.get("ce_sell_score", 0) if best_ce else 0
else:
    selected_strike = "No Strike"
    hedge = "No Hedge"
    selected_strike_score = 0

max_lots = int(capital / margin_per_lot) if margin_per_lot > 0 else 0
if final_trade == "WAIT":
    suggested_lots = 0
else:
    risk_multiplier = max(0.0, (100 - seller_risk) / 100)
    confidence_multiplier = confidence / 100
    raw_lots = int(max_lots * risk_multiplier * confidence_multiplier)
    suggested_lots = max(1, min(max_lots, raw_lots)) if max_lots > 0 else 0

sl_points = round(max(atr5 * (1.25 if seller_risk < 50 else 1.6), 20), 2)
target_points = round(max(atr5 * 0.85, 15), 2)


# V7 advanced management layer
market_mode, dte = detect_expiry_mode(selected_expiry, news["score"])
is_expiry_mode = market_mode in ("EXPIRY MODE", "NEAR EXPIRY MODE")
time_risk, time_zone_label = historical_time_zone_risk(is_expiry_mode)
theta_score_v7, active_profit_pct = theta_decay_score(is_expiry_mode, active_entry_price, active_current_price)
gamma_score_v7 = gamma_risk_score(is_expiry_mode, vix_change_pct, time_risk, option_bias, heavy_bias)
shock_score_v7 = shock_probability_score(time_risk, vix_risk, option_bias, heavy_bias, news["score"])
position_ai = active_position_manager(active_side, active_strike, active_entry_price, active_current_price, active_lots, theta_score_v7, gamma_score_v7, shock_score_v7, final_trade, confidence)
discipline_text, discipline_score, discipline_reason = discipline_status(trades_taken_today, daily_loss_hit, confidence, seller_risk)
trade_quality = trade_quality_score(confidence, seller_risk, shock_score_v7)


# =========================================================
# UI
# =========================================================
market_text, day_name = market_status()
if option_chain.get("success"):
    source_text = "DhanHQ Live OC"
elif nifty_source == "DhanHQ":
    source_text = "DhanHQ Quote"
elif dhan_ready:
    source_text = "Fallback (Dhan token OK)"
else:
    source_text = "Fallback"

st.markdown("<div class='main-title'>🧠 Nifty Seller AI Dashboard V6</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-title'>Seller Intelligence: DhanHQ Option Chain + OI/Price + Top-5 Drivers + News Risk + FII/DII</div>",
    unsafe_allow_html=True,
)

r1, r2, r3, r4, r5 = st.columns(5)
r1.markdown(f"<div class='ribbon'>{market_text}</div>", unsafe_allow_html=True)
r2.markdown(f"<div class='ribbon'>Data: {source_text}</div>", unsafe_allow_html=True)
r3.markdown(f"<div class='ribbon'>News {news['label']} {news['score']}/100</div>", unsafe_allow_html=True)
r4.markdown(f"<div class='ribbon'>HW: {bias_label(heavy_bias)}</div>", unsafe_allow_html=True)
r5.markdown(f"<div class='ribbon'>PCR: {pcr:.2f}</div>", unsafe_allow_html=True)
r6, r7, r8 = st.columns(3)
r6.markdown(f"<div class='ribbon'>Mode: {market_mode}</div>", unsafe_allow_html=True)
r7.markdown(f"<div class='ribbon'>Shock: {shock_score_v7}/100</div>", unsafe_allow_html=True)
r8.markdown(f"<div class='ribbon'>Discipline: {discipline_score}/100</div>", unsafe_allow_html=True)

if final_trade == "SELL PE":
    card_class = "card-green"
    status_text = "🟢 Bullish Seller Setup"
elif final_trade == "SELL CE":
    card_class = "card-red"
    status_text = "🔴 Bearish Seller Setup"
elif seller_risk >= 70:
    card_class = "card-yellow"
    status_text = "🟡 Risk Block / Wait"
else:
    card_class = "card-wait"
    status_text = "⚪ No Clear Edge"

st.markdown(
    f"""
<div class="advisor-card {card_class}">
    <h3>{status_text}</h3>
    <h1>{final_trade}</h1>
    <p><b>Direction:</b> {final_direction:+.1f}/100 &nbsp;&nbsp; | &nbsp;&nbsp; <b>Confidence:</b> {confidence:.0f}% &nbsp;&nbsp; | &nbsp;&nbsp; <b>Seller Risk:</b> {seller_risk:.0f}%</p>
    <p><b>Strike:</b> {selected_strike} &nbsp;&nbsp; | &nbsp;&nbsp; <b>Hedge:</b> {hedge} &nbsp;&nbsp; | &nbsp;&nbsp; <b>Strike Score:</b> {selected_strike_score}/98</p>
    <p><b>Suggested Lots:</b> {suggested_lots}/{max_lots} &nbsp;&nbsp; | &nbsp;&nbsp; <b>SL:</b> {sl_points} pts &nbsp;&nbsp; | &nbsp;&nbsp; <b>Target:</b> {target_points} pts</p>
    <p><b>V8 Mode:</b> {market_mode} &nbsp;&nbsp; | &nbsp;&nbsp; <b>Shock:</b> {shock_score_v7}/100 &nbsp;&nbsp; | &nbsp;&nbsp; <b>Trade Quality:</b> {trade_quality}/100</p>
</div>
""",
    unsafe_allow_html=True,
)

if hard_block:
    st.error("Fresh selling blocked: critical news/event risk ya overall seller risk bahut high hai.")
elif final_trade == "SELL PE":
    st.success("PE side preferred — hedge aur strict SL ke saath. Heavyweight/OI confirmation ko priority do.")
elif final_trade == "SELL CE":
    st.error("CE side preferred — hedge aur strict SL ke saath. Short-covering warning ko ignore mat karo.")
else:
    st.warning("Clear edge nahi hai. WAIT is a valid seller decision.")


# V7 Position Manager + Expiry/Shock/Discipline panels
with st.expander("🚀 V8 AI Position Manager — Hold / Exit / Trail SL", expanded=True):
    if active_side == "None" or active_lots <= 0:
        st.info("Active trade details sidebar mein enter karo: CE/PE, strike, entry premium, current premium, lots. Phir AI Hold/Exit batayegi.")
    else:
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Position AI", position_ai["action"], f"Confidence {position_ai['confidence']}%")
        p2.metric("Profit in Premium", f"{position_ai['profit_pct']:.1f}%")
        p3.metric("Trail SL", f"₹{position_ai['trail_sl']:.2f}" if position_ai["trail_sl"] else "--")
        p4.metric("Position Risk", f"{position_ai['risk']}/100")
        for reason in position_ai["reasons"]:
            st.write("✔", reason)
        if position_ai["action"] == "EXIT NOW":
            st.error("🔴 EXIT NOW: market structure/risk seller ke against ho raha hai.")
        elif "BOOK" in position_ai["action"]:
            st.warning("🟡 Profit secure karna better ho sakta hai.")
        elif "HOLD" in position_ai["action"]:
            st.success("🟢 Hold possible, but trail SL discipline zaroor rakho.")

with st.expander("🧠 V8 Expiry + Shock + Discipline Engine", expanded=True):
    e1, e2, e3, e4, e5 = st.columns(5)
    e1.metric("Market Mode", market_mode, f"DTE: {dte if dte != 99 else 'NA'}")
    e2.metric("Historical Zone", f"{time_risk}/100", time_zone_label)
    e3.metric("Theta Score", f"{theta_score_v7}/100")
    e4.metric("Gamma Risk", f"{gamma_score_v7}/100")
    e5.metric("Shock Risk", f"{shock_score_v7}/100")
    st.write(f"**Discipline:** {discipline_text} — {discipline_reason}")
    if shock_score_v7 >= 75:
        st.error("🚨 High Shock Probability: new selling avoid / SL tight / profit protect.")
    elif shock_score_v7 >= 55:
        st.warning("⚠️ Caution Zone: quantity small, SL tight, hold decision data se confirm karo.")
    else:
        st.success("✅ Shock risk controlled by current inputs.")

# Compact source status
st.markdown(
    f"<span class='source-pill'>Nifty: {nifty_source}</span>"
    f"<span class='source-pill'>VIX: {vix_source}</span>"
    f"<span class='source-pill'>Heavyweights: {heavy_analysis.get('source','Unavailable')}</span>"
    f"<span class='source-pill'>Option Chain: {'DhanHQ' if option_chain.get('success') else 'Manual aggregate'}</span>",
    unsafe_allow_html=True,
)


with st.expander("✅ Why AI gave this decision", expanded=True):
    reasons = [
        f"Price Action bias: {price_action_bias:+.0f}/100",
        f"Option Chain bias: {option_bias:+.0f}/100",
        f"Top-5 Heavyweight pressure: {heavy_bias:+.0f}/100",
        f"FII/DII Smart Money: {smart_money_bias:+.0f}/100",
        f"News Risk: {news['label']} ({news['score']}/100)",
        f"India VIX: {vix:.2f} ({vix_change_pct:+.2f}%)",
    ]
    for item in reasons:
        st.write("✔", item)
    if heavy_analysis.get("divergence") != "NONE":
        st.warning(f"Divergence: {heavy_analysis['divergence']}")
    if heavy_analysis.get("shock_rows"):
        names = ", ".join(r["name"] for r in heavy_analysis["shock_rows"])
        st.warning(f"Heavyweight shock detected: {names}")




with st.expander("✅ V8 Trade Checklist — Entry Allowed Only If Green", expanded=True):
    checks = [
        ("Dhan credentials detected", bool(dhan_ready)),
        ("Live or fallback market price available", price > 0),
        ("Option-chain edge not opposite", abs(option_bias) >= 8),
        ("Seller risk acceptable", seller_risk < 65),
        ("News risk not high", news["score"] < 60),
        ("VIX risk acceptable", vix_risk < 65),
        ("AI confidence acceptable", confidence >= 58),
        ("No hard block", not hard_block),
    ]
    passed = sum(1 for _, ok in checks if ok)
    checklist_score = int((passed / len(checks)) * 100)
    st.metric("Checklist Score", f"{checklist_score}/100", f"{passed}/{len(checks)} green")
    for label, ok in checks:
        st.write(("✅" if ok else "❌"), label)
    if checklist_score < 75:
        st.warning("NO TRADE / SMALL SIZE: checklist fully green nahi hai. Capital protection priority.")
    else:
        st.success("Checklist strong hai. Still hedge + SL mandatory.")


st.markdown("## 📡 Seller AI Radar")
a1, a2, a3, a4 = st.columns(4)
with a1:
    st.metric("Price Action", f"{price_action_bias:+.0f}", bias_label(price_action_bias))
with a2:
    st.metric("OI + Price", f"{option_bias:+.0f}", bias_label(option_bias))
with a3:
    st.metric("Heavyweights", f"{heavy_bias:+.0f}", bias_label(heavy_bias))
with a4:
    st.metric("News Risk", f"{news['score']}/100", news["label"])


with st.expander("📊 Market Snapshot", expanded=True):
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Nifty", f"{price:,.2f}", f"{nifty_change_pct:+.2f}%")
    m2.metric("India VIX", f"{vix:.2f}", f"{vix_change_pct:+.2f}%")
    m3.metric("EMA20", f"{ema20:.2f}")
    m4.metric("VWAP", f"{vwap:.2f}")
    m5.metric("Nearest S/R", f"{nearest_support:.0f} / {nearest_resistance:.0f}")


with st.expander("🧠 Option Chain AI Engine — OI + Price + Greeks", expanded=True):
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("PCR", f"{pcr:.2f}")
    o2.metric("Put OI Change", f"{put_oi_change:,}")
    o3.metric("Call OI Change", f"{call_oi_change:,}")
    o4.metric("OC Bias", f"{option_bias:+.0f}", bias_label(option_bias))

    if option_analysis.get("success"):
        table_rows = []
        for row in option_analysis["rows"]:
            table_rows.append({
                "Strike": row["strike"],
                "CE LTP": round(row["ce_ltp"], 2),
                "CE Δ%": round(row["ce_price_change_pct"], 2),
                "CE OI Δ%": round(row["ce_oi_change_pct"], 2),
                "CE Signal": row["ce_signal"],
                "CE Sell": row["ce_sell_score"],
                "CE Delta": round(row["ce_delta"], 3),
                "CE IV": round(row["ce_iv"], 2),
                "CE Spread%": round(row["ce_spread_pct"], 2),
                "PE LTP": round(row["pe_ltp"], 2),
                "PE Δ%": round(row["pe_price_change_pct"], 2),
                "PE OI Δ%": round(row["pe_oi_change_pct"], 2),
                "PE Signal": row["pe_signal"],
                "PE Sell": row["pe_sell_score"],
                "PE Delta": round(row["pe_delta"], 3),
                "PE IV": round(row["pe_iv"], 2),
                "PE Spread%": round(row["pe_spread_pct"], 2),
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

        c1, c2 = st.columns(2)
        with c1:
            if best_ce:
                st.subheader(f"🔴 Best CE Candidate: {best_ce['strike']} CE")
                st.write(f"Signal: **{best_ce['ce_signal']}** ({best_ce['ce_signal_basis']})")
                st.write(f"Sell Score: **{best_ce['ce_sell_score']}/98** | Delta: **{best_ce['ce_delta']:.3f}** | IV: **{best_ce['ce_iv']:.2f}**")
                st.caption(best_ce.get("ce_sell_reason", ""))
                if "Short Covering" in best_ce["ce_signal"] or "Buying" in best_ce["ce_signal"]:
                    st.warning("CE sell risk: upside pressure detected.")
        with c2:
            if best_pe:
                st.subheader(f"🟢 Best PE Candidate: {best_pe['strike']} PE")
                st.write(f"Signal: **{best_pe['pe_signal']}** ({best_pe['pe_signal_basis']})")
                st.write(f"Sell Score: **{best_pe['pe_sell_score']}/98** | Delta: **{best_pe['pe_delta']:.3f}** | IV: **{best_pe['pe_iv']:.2f}**")
                st.caption(best_pe.get("pe_sell_reason", ""))
                if "Short Covering" in best_pe["pe_signal"] or "Buying" in best_pe["pe_signal"]:
                    st.warning("PE sell risk: downside pressure detected.")

        st.caption("OI+price labels are conventional inferences. Every option trade has both buyer and seller; OI alone does not prove who initiated the trade.")
        st.caption("Snapshot OI acceleration becomes active after at least two fresh Dhan snapshots. Press Refresh after 4+ seconds to compare snapshots.")
    else:
        st.info("Per-strike OI + Price Analyzer DhanHQ data se chalega. Abhi aggregate manual OI/PCR fallback active hai.")
        if prefer_dhan and dhan_ready:
            st.error(option_chain.get("message", "Dhan option chain unavailable."))


with st.expander("🏋️ Nifty Top-5 Heavyweight Driver Engine", expanded=True):
    if heavy_analysis.get("success"):
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Weighted Pressure", f"{heavy_bias:+.0f}/100", bias_label(heavy_bias))
        h2.metric("Estimated Top-5 Points", f"{heavy_analysis['estimated_points']:+.1f}")
        h3.metric("HDFC + ICICI", heavy_analysis["banking_pair"])
        h4.metric("Divergence", heavy_analysis["divergence"])

        hw_table = pd.DataFrame([
            {
                "Stock": r["name"],
                "Weight %": round(r["weight"], 2),
                "Move %": round(r["change_pct"], 2),
                "Snapshot Shock %pt": round(r.get("shock_delta_pct", 0.0), 2),
                "Est. Nifty pts": round(price * (r["weight"] / 100) * (r["change_pct"] / 100), 1),
            }
            for r in heavy_analysis["rows"]
        ])
        st.dataframe(hw_table, use_container_width=True, hide_index=True)

        if final_trade == "SELL CE" and heavy_bias > 35:
            st.warning("CE SELL WARNING: top-5 drivers bullish hain — short-covering/upside risk.")
        if final_trade == "SELL PE" and heavy_bias < -35:
            st.warning("PE SELL WARNING: top-5 drivers bearish hain — support-break risk.")
        if heavy_analysis.get("shock_rows"):
            st.error("🚨 Heavyweight Shock: " + ", ".join(f"{r['name']} {r['shock_delta_pct']:+.2f}%pt" for r in heavy_analysis["shock_rows"]))
        st.caption("Estimated points are an approximation using constituent weights and stock returns; exact index attribution can differ.")
    else:
        st.warning(heavy_analysis.get("message", "Heavyweight data unavailable."))


with st.expander("🚨 Automatic Market News Risk Indicator", expanded=True):
    n1, n2, n3, n4 = st.columns(4)
    n1.metric("Final News Risk", f"{news['score']}/100", news["label"])
    n2.metric("Scheduled Event", f"{news['scheduled']}/100", "AUTO" if news["auto_calendar"] else "Manual fallback")
    n3.metric("Breaking News", f"{news['breaking']}/100", "AUTO" if news["auto_news"] else "Fallback")
    n4.metric("Market Reaction", f"{news['reaction']}/100")

    if news["label"] == "CRITICAL":
        st.error("⚫ CRITICAL: fresh option selling block. Event/news + market reaction risk high.")
    elif news["label"] == "HIGH":
        st.warning("🔴 HIGH: fresh selling reduce/avoid; hedge mandatory.")
    elif news["label"] == "MEDIUM":
        st.info("🟡 MEDIUM: smaller quantity and strict monitoring.")
    else:
        st.success("🟢 LOW: no major risk detected by available sources, but market risk remains.")

    if te_result.get("success"):
        st.caption(f"Calendar engine active | relevant high/medium events: {te_result.get('events', 0)}")
    if alpha_result.get("success"):
        st.caption(f"News-sentiment engine active | recent items scanned: {alpha_result.get('items', 0)}")
    if not news["auto_calendar"] or not news["auto_news"]:
        st.caption("Automatic APIs are optional. Until keys are added, manual fallback + live market reaction still drive the indicator.")


with st.expander("🏛️ FII / DII Smart Money", expanded=False):
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("FII Today", f"₹{fii_today:,.0f} Cr")
    f2.metric("DII Today", f"₹{dii_today:,.0f} Cr")
    f3.metric("FII 5 Day", f"₹{fii_5day:,.0f} Cr")
    f4.metric("DII 5 Day", f"₹{dii_5day:,.0f} Cr")
    st.write(f"FII Index Futures Bias: **{fii_index_futures_bias}**")
    st.write(f"Smart Money Bias: **{smart_money_bias:+.0f}/100 ({bias_label(smart_money_bias)})**")


with st.expander("💰 Position & Risk Manager", expanded=False):
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Capital", f"₹{capital:,.0f}")
    p2.metric("Max Lots", max_lots)
    p3.metric("Current Lots", current_lots)
    p4.metric("AI Suggested Lots", suggested_lots)
    st.write(f"Estimated Margin: **₹{suggested_lots * margin_per_lot:,.0f}**")
    st.write(f"Lot Size: **{lot_size}** | Seller Risk: **{seller_risk:.0f}/100**")




with st.expander("🧪 V8 Live Dhan API Diagnostics", expanded=True):
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Credentials", "Detected" if dhan_ready else "Missing")
    d2.metric("Market Quote", "OK" if dhan_bundle.get("success") else "Fallback")
    d3.metric("Expiry List", "OK" if expiry_result.get("success") else "Not OK")
    d4.metric("Option Chain", "OK" if option_chain.get("success") else "Not OK")
    if dhan_bundle.get("success"):
        st.success("Dhan market quote is responding. Nifty/top-5 quote layer is ready.")
    else:
        st.warning("Dhan market quote not active. Current message: " + str(dhan_bundle.get("message", "No response")))
    if not expiry_result.get("success"):
        st.warning("Expiry list issue: " + str(expiry_result.get("message", "No expiry response")))
    if not option_chain.get("success"):
        st.error("Option chain issue: " + str(option_chain.get("message", "No option-chain response")))
        st.info("If Data API subscription is still inactive on DhanHQ, option-chain/OI/PCR will stay on fallback. Once active, press Refresh Live Data after market open.")
    else:
        st.success(f"Live option chain loaded for expiry {option_chain.get('expiry')} | ATM {option_chain.get('atm_strike')} | Rows {len(option_chain.get('rows', []))}")

with st.expander("🔐 DhanHQ Setup Status", expanded=False):
    if dhan_ready:
        st.success("DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN are detected from Streamlit secrets/environment.")
        st.write(f"Top-5 Security IDs resolved: **{len(top5_ids)}/5**")
        if master_result.get("success") is False:
            st.warning(master_result.get("message", "Instrument master unavailable."))
        st.caption("Dhan access token can expire; keep credentials only in Streamlit Secrets, never in app.py or GitHub.")
    else:
        st.info("Add Dhan credentials later. App remains usable with Yahoo/manual fallbacks, but per-strike Option Chain AI requires DhanHQ.")
        st.code('DHAN_CLIENT_ID = "your_client_id"\nDHAN_ACCESS_TOKEN = "your_access_token"', language="toml")
    st.caption("Optional news secrets: TRADING_ECONOMICS_API_KEY and ALPHAVANTAGE_API_KEY")


st.markdown("---")
st.markdown(
    "<div class='small-note'>V8 build: live-data diagnostics + checklist + position intelligence. Disclaimer: Decision-support only. OI/price labels are probabilistic inferences, not proof of buyer/seller identity. Use hedges, live chart confirmation, liquidity checks and strict risk limits.</div>",
    unsafe_allow_html=True,
)
