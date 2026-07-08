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
# NIFTY SELLER AI DASHBOARD V17 - SMART LITE EDITION
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
    page_title="Nifty Seller AI Dashboard V17 Smart Lite",
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
.v13-card {padding: 16px; border-radius: 16px; border: 1px solid rgba(128,128,128,0.25); background: rgba(128,128,128,0.06); margin: 8px 0 14px 0;}
.v13-green {color:#16a34a; font-weight:800;}
.v13-red {color:#dc2626; font-weight:800;}
.v13-flat {color:#6b7280; font-weight:800;}
.v13-badge {display:inline-block; padding:4px 8px; border-radius:10px; background:rgba(128,128,128,0.12); margin:2px; font-weight:700;}

.super-card {padding:18px; border-radius:18px; border:1px solid rgba(128,128,128,.25); background:rgba(128,128,128,.07); margin:10px 0;}
.super-good {background:rgba(22,163,74,.16); border-left:5px solid #16a34a; padding:12px; border-radius:12px;}
.super-warn {background:rgba(234,179,8,.16); border-left:5px solid #eab308; padding:12px; border-radius:12px;}
.super-bad {background:rgba(220,38,38,.16); border-left:5px solid #dc2626; padding:12px; border-radius:12px;}
.super-muted {opacity:.76; font-size:.88rem;}
</style>
<style>
.v17-strip {padding:14px 18px;border-radius:14px;margin:10px 0 12px 0;font-weight:800;border-left:7px solid rgba(255,255,255,.3);}
.v17-red {background:rgba(170,38,38,.25); border-left-color:#ef4444; color:#fecaca;}
.v17-green {background:rgba(22,135,75,.23); border-left-color:#22c55e; color:#bbf7d0;}
.v17-yellow {background:rgba(170,126,22,.22); border-left-color:#f59e0b; color:#fde68a;}
.v17-grey {background:rgba(82,88,99,.22); border-left-color:#94a3b8; color:#e5e7eb;}
.v17-final {padding:24px;border-radius:18px;margin:12px 0 16px 0;border-left:8px solid #f59e0b;background:rgba(170,126,22,.22);}
.v17-final.green {border-left-color:#22c55e;background:rgba(22,135,75,.24);}
.v17-final.red {border-left-color:#ef4444;background:rgba(170,38,38,.24);}
.v17-kpi {padding:16px;border-radius:14px;background:rgba(128,128,128,.08);border:1px solid rgba(128,128,128,.25);}
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



@st.cache_data(ttl=10, show_spinner=False)
def get_yahoo_price_action():
    """Automatic Price Action from Nifty intraday candles.
    Dhan option-chain remains primary; this gives live auto EMA/VWAP/ATR/High-Low fallback
    instead of stale manual sidebar values.
    """
    try:
        ticker = yf.Ticker("^NSEI")
        df = ticker.history(period="5d", interval="5m").dropna()
        if df.empty or len(df) < 60:
            return {"success": False, "message": "Not enough Nifty candles for Price Action."}
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(IST)
        else:
            df.index = df.index.tz_convert(IST)
        close = df["Close"].astype(float)
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series([0]*len(df), index=df.index)
        ema20_v = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50_v = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        # VWAP for current trading date. If volume is unavailable/zero, fall back to typical price mean.
        today_date = df.index[-1].date()
        today_df = df[df.index.date == today_date].copy()
        if today_df.empty:
            today_df = df.tail(75).copy()
        typical = (today_df["High"] + today_df["Low"] + today_df["Close"]) / 3.0
        vol = today_df["Volume"] if "Volume" in today_df.columns else pd.Series([0]*len(today_df), index=today_df.index)
        if float(vol.sum() or 0) > 0:
            vwap_v = float((typical * vol).sum() / vol.sum())
        else:
            vwap_v = float(typical.mean())
        prev_dates = sorted(set(df.index.date))
        prev_day_high_v = float(high.max())
        prev_day_low_v = float(low.min())
        if len(prev_dates) >= 2:
            prev_df = df[df.index.date == prev_dates[-2]]
            if not prev_df.empty:
                prev_day_high_v = float(prev_df["High"].max())
                prev_day_low_v = float(prev_df["Low"].min())
        today_high_v = float(today_df["High"].max())
        today_low_v = float(today_df["Low"].min())
        # Opening range 09:15 to 09:30/09:45 if available
        or_df = today_df.between_time("09:15", "09:45")
        if or_df.empty:
            or_df = today_df.head(6)
        or_high_v = float(or_df["High"].max()) if not or_df.empty else today_high_v
        or_low_v = float(or_df["Low"].min()) if not or_df.empty else today_low_v
        prev_close = close.shift(1)
        tr = pd.concat([(high-low).abs(), (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
        atr5_v = float(tr.rolling(14).mean().dropna().iloc[-1]) if not tr.rolling(14).mean().dropna().empty else 0.0
        return {
            "success": True,
            "ema20": ema20_v,
            "ema50": ema50_v,
            "vwap": vwap_v,
            "atr5": atr5_v,
            "previous_day_high": prev_day_high_v,
            "previous_day_low": prev_day_low_v,
            "today_high": today_high_v,
            "today_low": today_low_v,
            "opening_range_high": or_high_v,
            "opening_range_low": or_low_v,
            "fetched_at": fmt_time(),
            "source": "Yahoo candles auto",
            "message": "OK",
        }
    except Exception as exc:
        return {"success": False, "message": f"Price Action auto error: {exc}", "source": "Manual"}

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

# =========================================================
# V18 CLEAN BASE ADDITIONS - ONE SNAPSHOT / ONE AI BRAIN
# Removed old duplicate decision layers (V9/V10/V11/V14/V16.4 UI overwrite chain).
# Kept: data layer, option intelligence, heavyweight engine, news risk, position manager.
# =========================================================
from pathlib import Path as _Path
import time

FII_DII_STORE = _Path("data/fii_dii_journal.csv")


def load_fii_dii_journal():
    cols = ["Date", "FII Cash Cr", "DII Cash Cr", "FII Index Futures Contracts", "FII Long %", "FII Short %", "FII Index Futures Bias", "Notes"]
    try:
        if FII_DII_STORE.exists():
            df = pd.read_csv(FII_DII_STORE)
            for col in cols:
                if col not in df.columns:
                    df[col] = "" if col in ["FII Index Futures Bias", "Notes"] else 0.0
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
            return df[cols].dropna(subset=["Date"])
    except Exception:
        pass
    return pd.DataFrame(columns=cols)


def save_fii_dii_journal(df):
    try:
        FII_DII_STORE.parent.mkdir(parents=True, exist_ok=True)
        out = df.copy()
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.date.astype(str)
        out.to_csv(FII_DII_STORE, index=False)
        return True
    except Exception:
        return False


def journal_row_by_date(df, target_date):
    try:
        if df is None or df.empty:
            return None
        d = df.copy()
        d["Date"] = pd.to_datetime(d["Date"], errors="coerce").dt.date
        rows = d[d["Date"] == pd.to_datetime(target_date).date()]
        return rows.iloc[-1].to_dict() if not rows.empty else None
    except Exception:
        return None


def latest_journal_date(df):
    try:
        if df is None or df.empty:
            return now_ist().date()
        d = df.copy()
        d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
        d = d.dropna(subset=["Date"]).sort_values("Date")
        return d["Date"].iloc[-1].date() if not d.empty else now_ist().date()
    except Exception:
        return now_ist().date()


def journal_stats(df, lookback=30):
    if df is None or df.empty:
        return {"rows": 0, "fii_5": 0.0, "dii_5": 0.0, "bias": 0.0, "label": "No data"}
    d = df.copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d = d.dropna(subset=["Date"]).sort_values("Date").tail(int(lookback))
    for col in ["FII Cash Cr", "DII Cash Cr"]:
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0.0)
    last5 = d.tail(5)
    fii5 = float(last5["FII Cash Cr"].sum()) if not last5.empty else 0.0
    dii5 = float(last5["DII Cash Cr"].sum()) if not last5.empty else 0.0
    bias = 0.0
    bias += 35 if fii5 > 1000 else -35 if fii5 < -1000 else fii5 / 30.0
    bias += 15 if dii5 > 1000 else -15 if dii5 < -1000 else dii5 / 70.0
    return {"rows": len(d), "fii_5": fii5, "dii_5": dii5, "bias": signed_clamp(bias), "label": bias_label(bias)}


def auto_fut_bias(long_pct, short_pct):
    try:
        long_pct, short_pct = float(long_pct or 0), float(short_pct or 0)
    except Exception:
        return "Neutral"
    if short_pct >= 65 and short_pct - long_pct >= 25:
        return "Bearish"
    if long_pct >= 65 and long_pct - short_pct >= 25:
        return "Bullish"
    return "Neutral"


def fut_bias_score(long_pct, short_pct, manual_bias="Neutral"):
    try:
        spread = float(long_pct or 0) - float(short_pct or 0)
    except Exception:
        spread = 0.0
    score = signed_clamp(spread * 0.45, -30, 30)
    if abs(score) < 3:
        score = 22 if manual_bias == "Bullish" else -22 if manual_bias == "Bearish" else 0
    return score


def safe_float_from_row(row, key, default=0.0):
    try:
        return float((row or {}).get(key, default) or default)
    except Exception:
        return default


# ------------------------- Refresh Engine -------------------------
def qp_get(name, default=""):
    try:
        val = st.query_params.get(name, default)
        return val[0] if isinstance(val, list) and val else val
    except Exception:
        return default


def qp_set(name, value):
    try:
        if str(st.query_params.get(name, "")) != str(value):
            st.query_params[name] = str(value)
    except Exception:
        pass


def init_refresh_state():
    if "auto_refresh" not in st.session_state:
        st.session_state["auto_refresh"] = str(qp_get("auto_refresh", "0")).lower() in ("1", "true", "yes", "on")
    if "refresh_interval" not in st.session_state:
        try:
            st.session_state["refresh_interval"] = int(float(qp_get("refresh_interval", "20") or 20))
        except Exception:
            st.session_state["refresh_interval"] = 20
    st.session_state["refresh_interval"] = int(max(20, min(300, st.session_state["refresh_interval"])))


def set_auto_refresh(enabled, interval=20):
    st.session_state["auto_refresh"] = bool(enabled)
    st.session_state["refresh_interval"] = int(max(20, min(300, int(interval or 20))))
    qp_set("auto_refresh", "1" if enabled else "0")
    qp_set("refresh_interval", str(st.session_state["refresh_interval"]))


def trigger_refresh():
    st.session_state["manual_refresh_counter"] = st.session_state.get("manual_refresh_counter", 0) + 1
    # Do not clear the full cache. TTL handles data freshness and avoids slow reload.
    st.rerun()


# ------------------------- Lightweight Strategy Helpers -------------------------
def round_strike(x, step=50):
    try:
        return int(round(float(x) / step) * step)
    except Exception:
        return 0


def hedge_strike(sell_strike, side, hedge_gap=100):
    sell_strike = int(sell_strike or 0)
    return sell_strike + int(hedge_gap) if side == "CE" else sell_strike - int(hedge_gap)


def seller_sl_target(premium, confidence=0, risk=0):
    premium = float(premium or 0)
    if premium <= 0:
        return {"entry": 0.0, "sl": 0.0, "target1": 0.0, "target2": 0.0, "trail_after": 0.0}
    sl_mult = 1.28 if confidence >= 80 and risk < 55 else 1.22 if risk < 70 else 1.16
    t1_mult = 0.72 if confidence >= 75 else 0.78
    t2_mult = 0.55 if confidence >= 75 else 0.62
    return {
        "entry": round(premium, 2),
        "sl": round(premium * sl_mult, 2),
        "target1": round(premium * t1_mult, 2),
        "target2": round(premium * t2_mult, 2),
        "trail_after": round(premium * 0.82, 2),
    }


def price_action_bias_engine(price, ema20, ema50, vwap, opening_high, opening_low, prev_high, prev_low):
    score = 0.0
    reasons = []
    if price > ema20:
        score += 18; reasons.append("Price EMA20 ke upar")
    else:
        score -= 18; reasons.append("Price EMA20 ke neeche")
    if ema20 > ema50:
        score += 16; reasons.append("EMA20 > EMA50")
    else:
        score -= 16; reasons.append("EMA20 < EMA50")
    if price > vwap:
        score += 16; reasons.append("Price VWAP ke upar")
    else:
        score -= 16; reasons.append("Price VWAP ke neeche")
    if opening_high and price > opening_high:
        score += 18; reasons.append("Opening range breakout")
    elif opening_low and price < opening_low:
        score -= 18; reasons.append("Opening range breakdown")
    if prev_high and price > prev_high:
        score += 12; reasons.append("Previous high ke upar")
    elif prev_low and price < prev_low:
        score -= 12; reasons.append("Previous low ke neeche")
    return signed_clamp(score), reasons[:4]


def pcr_bias_engine(pcr):
    pcr = float(pcr or 0)
    if pcr >= 1.35:
        return 28, "PCR bullish support zone"
    if pcr <= 0.75 and pcr > 0:
        return -28, "PCR bearish pressure zone"
    if 0.95 <= pcr <= 1.20:
        return 8, "PCR balanced/slightly supportive"
    return 0, "PCR neutral"


def data_quality_score(dhan_ready, option_ok, nifty_source, hw_source, vix_source, price_action_source):
    score = 0
    reasons = []
    if dhan_ready:
        score += 20; reasons.append("Dhan credentials detected")
    else:
        reasons.append("Dhan token missing")
    if option_ok:
        score += 35; reasons.append("Live Dhan option-chain active")
    else:
        reasons.append("Option-chain unavailable/manual fallback")
    if str(nifty_source).lower().startswith("dhan"):
        score += 18; reasons.append("Nifty from DhanHQ")
    elif str(nifty_source):
        score += 8; reasons.append(f"Nifty source: {nifty_source}")
    if str(hw_source).lower().startswith(("dhan", "yahoo")):
        score += 12; reasons.append(f"Heavyweights: {hw_source}")
    if str(vix_source):
        score += 7; reasons.append(f"VIX: {vix_source}")
    if str(price_action_source).lower().startswith("yahoo"):
        score += 8; reasons.append("Auto price action active")
    return int(clamp(score)), reasons


def select_candidate(option_analysis, side, manual_strike, hedge_gap, confidence=0, risk=0):
    row = None
    if option_analysis.get("success"):
        row = option_analysis.get("best_ce") if side == "CE" else option_analysis.get("best_pe")
    strike = int(row.get("strike", manual_strike) if row else manual_strike)
    premium = float(row.get(f"{side.lower()}_ltp", 0) if row else 0)
    plan = seller_sl_target(premium, confidence, risk)
    return {"side": side, "strike": strike, "hedge": hedge_strike(strike, side, hedge_gap), "premium": premium, "plan": plan, "row": row}


def build_market_snapshot(**kwargs):
    snap = dict(kwargs)
    snap["created_at"] = fmt_time()
    snap["id"] = f"{kwargs.get('price',0):.2f}|{kwargs.get('pcr',0):.3f}|{kwargs.get('vix',0):.2f}|{fmt_time()}"
    return snap


def snapshot_material_change(snapshot):
    prev = st.session_state.get("last_snapshot_for_stability")
    st.session_state["last_snapshot_for_stability"] = snapshot
    if not prev:
        return True, ["First clean snapshot"]
    reasons = []
    if abs(float(snapshot.get("price",0))-float(prev.get("price",0))) >= max(20, float(snapshot.get("atr5",40))*0.35):
        reasons.append("Nifty materially changed")
    if abs(float(snapshot.get("pcr",0))-float(prev.get("pcr",0))) >= 0.08:
        reasons.append("PCR materially changed")
    if abs(float(snapshot.get("vix_change_pct",0))-float(prev.get("vix_change_pct",0))) >= 1.5:
        reasons.append("VIX pressure changed")
    if abs(float(snapshot.get("option_bias",0))-float(prev.get("option_bias",0))) >= 18:
        reasons.append("Option-chain bias changed")
    return bool(reasons), reasons or ["No material change"]


def v18_ai_brain(snapshot):
    price_bias = float(snapshot.get("price_action_bias", 0))
    option_bias = float(snapshot.get("option_bias", 0))
    heavy_bias = float(snapshot.get("heavy_bias", 0))
    smart_bias = float(snapshot.get("smart_money_bias", 0))
    pcr_bias = float(snapshot.get("pcr_bias", 0))
    data_quality = int(snapshot.get("data_quality", 0))
    seller_risk = float(snapshot.get("seller_risk", 0))
    news_score = float(snapshot.get("news_score", 0))
    gamma_score = float(snapshot.get("gamma_score", 0))
    shock_score = float(snapshot.get("shock_score", 0))
    best_ce_score = float(snapshot.get("best_ce_score", 0))
    best_pe_score = float(snapshot.get("best_pe_score", 0))

    directional = signed_clamp(
        price_bias * 0.30 + option_bias * 0.30 + heavy_bias * 0.18 + smart_bias * 0.12 + pcr_bias * 0.10
    )
    blockers = []
    reasons = []
    if data_quality < 55:
        blockers.append(f"Data quality low ({data_quality}/100)")
    if news_score >= 78:
        blockers.append(f"News/event risk high ({news_score:.0f}/100)")
    if seller_risk >= 82:
        blockers.append(f"Seller risk high ({seller_risk:.0f}/100)")
    if gamma_score >= 82:
        blockers.append(f"Gamma risk high ({gamma_score:.0f}/100)")
    if shock_score >= 82:
        blockers.append(f"Shock risk high ({shock_score:.0f}/100)")

    # Direction meaning: positive = bullish market, seller usually sells PE. negative = bearish market, seller sells CE.
    if blockers:
        action = "WAIT"
        reasons = blockers[:]
    elif abs(directional) <= 18 and seller_risk < 55 and best_ce_score >= 68 and best_pe_score >= 68:
        action = "IRON CONDOR"
        reasons.append("Market balanced hai aur dono side seller candidates acceptable hain")
    elif directional >= 24 and best_pe_score >= 58:
        action = "SELL PE"
        reasons.append("Bullish alignment: downside PE selling side better")
    elif directional <= -24 and best_ce_score >= 58:
        action = "SELL CE"
        reasons.append("Bearish alignment: upside CE selling side better")
    else:
        action = "WAIT"
        reasons.append("Directional edge clear nahi hai")

    raw_conf = 42 + abs(directional) * 0.42 + data_quality * 0.18 - seller_risk * 0.16 - news_score * 0.08
    if action == "IRON CONDOR":
        raw_conf = 58 + min(best_ce_score, best_pe_score) * 0.25 - seller_risk * 0.18
    if action == "WAIT":
        raw_conf = min(raw_conf, 64)
    confidence = int(round(clamp(raw_conf, 0, 96)))

    material_change, change_reasons = snapshot_material_change(snapshot)
    last_decision = st.session_state.get("v18_last_decision")
    if last_decision and not material_change and action != last_decision.get("action") and confidence < 78:
        reasons.insert(0, "Decision stability lock: market materially change nahi hua")
        action = last_decision.get("action", "WAIT")
        confidence = min(confidence, int(last_decision.get("confidence", confidence)))
    decision = {
        "action": action,
        "confidence": confidence,
        "directional_score": int(round(directional)),
        "risk": int(round(seller_risk)),
        "reasons": reasons[:5],
        "change_reasons": change_reasons[:4],
        "material_change": material_change,
        "blockers": blockers,
    }
    st.session_state["v18_last_decision"] = decision
    return decision


# =========================================================
# APP UI - V18 CLEAN BASE
# =========================================================
init_refresh_state()
client_id, access_token = dhan_credentials()
dhan_ready = bool(client_id and access_token)

st.sidebar.title("⚙️ V18 Clean Base")
st.sidebar.caption("One Snapshot • One AI Brain • Lightweight UI")
if dhan_ready:
    st.sidebar.success("DhanHQ credentials detected")
else:
    st.sidebar.warning("Dhan token missing — fallback/manual mode")

with st.sidebar.expander("1️⃣ Data / Refresh", expanded=True):
    prefer_dhan = st.checkbox("Prefer DhanHQ Live Data", value=dhan_ready, disabled=not dhan_ready)
    nifty_security_id = int(st.number_input("Nifty Dhan Security ID", value=DEFAULT_NIFTY_SECURITY_ID, step=1))
    strikes_each_side = st.slider("Option strikes each side", 3, 10, 6)
    refresh_interval = st.slider("Auto refresh interval seconds", 20, 300, int(st.session_state.get("refresh_interval", 20)), step=5)
    auto_refresh = st.checkbox("Auto Refresh", value=bool(st.session_state.get("auto_refresh", False)))
    if auto_refresh != st.session_state.get("auto_refresh") or refresh_interval != st.session_state.get("refresh_interval"):
        set_auto_refresh(auto_refresh, refresh_interval)
    if st.button("🔄 Manual Refresh", width="stretch"):
        trigger_refresh()

with st.sidebar.expander("2️⃣ Manual Fallback", expanded=False):
    manual_nifty = st.number_input("Manual Nifty", value=25000.0, step=1.0)
    manual_nifty_change_pct = st.number_input("Manual Nifty Change %", value=0.0, step=0.05)
    manual_vix = st.number_input("Manual India VIX", value=13.5, step=0.1)
    manual_vix_change_pct = st.number_input("Manual VIX Change %", value=0.0, step=0.1)
    manual_ce_strike = int(st.number_input("Manual CE Sell Strike", value=25100, step=50))
    manual_pe_strike = int(st.number_input("Manual PE Sell Strike", value=24900, step=50))
    hedge_gap = int(st.number_input("Hedge Gap", value=100, step=50))

with st.sidebar.expander("3️⃣ Price Action", expanded=False):
    auto_price_action = st.checkbox("Auto Price Action", value=True)
    manual_ema20 = st.number_input("Manual EMA 20", value=24950.0, step=1.0)
    manual_ema50 = st.number_input("Manual EMA 50", value=24900.0, step=1.0)
    manual_vwap = st.number_input("Manual VWAP", value=24940.0, step=1.0)
    manual_atr5 = st.number_input("Manual ATR 5 Min", value=45.0, step=1.0)
    manual_previous_day_high = st.number_input("Manual Previous Day High", value=25150.0, step=1.0)
    manual_previous_day_low = st.number_input("Manual Previous Day Low", value=24850.0, step=1.0)
    manual_opening_range_high = st.number_input("Opening Range High", value=25060.0, step=1.0)
    manual_opening_range_low = st.number_input("Opening Range Low", value=24940.0, step=1.0)

with st.sidebar.expander("4️⃣ FII/DII Journal", expanded=False):
    journal_df = load_fii_dii_journal()
    data_date = st.date_input("Data Date", value=latest_journal_date(journal_df))
    saved = journal_row_by_date(journal_df, data_date)
    date_key = pd.to_datetime(data_date).strftime("%Y%m%d")
    fii_today = st.number_input("FII Cash ₹ Cr", value=safe_float_from_row(saved, "FII Cash Cr", 0.0), step=100.0, key=f"fii_{date_key}")
    dii_today = st.number_input("DII Cash ₹ Cr", value=safe_float_from_row(saved, "DII Cash Cr", 0.0), step=100.0, key=f"dii_{date_key}")
    fut_contracts = st.number_input("FII Index Futures Contracts", value=safe_float_from_row(saved, "FII Index Futures Contracts", 0.0), step=1000.0, key=f"fut_{date_key}")
    long_pct = st.number_input("FII Long %", value=safe_float_from_row(saved, "FII Long %", 0.0), min_value=0.0, max_value=100.0, step=0.01, key=f"long_{date_key}")
    short_pct = st.number_input("FII Short %", value=safe_float_from_row(saved, "FII Short %", 0.0), min_value=0.0, max_value=100.0, step=0.01, key=f"short_{date_key}")
    fut_bias = auto_fut_bias(long_pct, short_pct)
    if st.button("💾 Save FII/DII", width="stretch"):
        new_row = pd.DataFrame([{"Date": data_date, "FII Cash Cr": fii_today, "DII Cash Cr": dii_today, "FII Index Futures Contracts": fut_contracts, "FII Long %": long_pct, "FII Short %": short_pct, "FII Index Futures Bias": fut_bias, "Notes": "V18 clean base"}])
        out_df = pd.concat([journal_df, new_row], ignore_index=True)
        out_df["Date"] = pd.to_datetime(out_df["Date"], errors="coerce")
        out_df = out_df.dropna(subset=["Date"]).drop_duplicates(subset=["Date"], keep="last").sort_values("Date").tail(60)
        st.success("Saved" if save_fii_dii_journal(out_df) else "Save failed")

with st.sidebar.expander("5️⃣ Risk Controls", expanded=False):
    capital = st.number_input("Trading Capital ₹", value=500000.0, step=10000.0)
    margin_per_lot = st.number_input("Approx Margin Per Lot ₹", value=50000.0, step=5000.0)
    manual_news_risk = st.selectbox("Manual News/Event Risk", ["Low", "Medium", "High", "Critical"], index=0)
    te_key = get_secret("TRADING_ECONOMICS_KEY", "")
    alpha_key = get_secret("ALPHA_VANTAGE_KEY", "")

developer_mode = st.sidebar.checkbox("🛠️ Developer Mode", value=False)
max_lots = int(max(0, capital // margin_per_lot)) if margin_per_lot else 0

# ------------------------- Fetch One Snapshot -------------------------
master = get_dhan_instrument_master() if prefer_dhan else {"success": False, "df": pd.DataFrame()}
top5_ids = resolve_top5_security_ids(master.get("df", pd.DataFrame())) if master.get("success") else {}
dhan_bundle = get_dhan_market_bundle(client_id, access_token, top5_ids, nifty_security_id) if prefer_dhan else {"success": False, "message": "Dhan disabled"}

# Nifty
price = manual_nifty
nifty_change_pct = manual_nifty_change_pct
nifty_source = "Manual"
if prefer_dhan and dhan_bundle.get("success"):
    try:
        idx = dhan_bundle.get("data", {}).get("IDX_I", {})
        item = idx.get(str(nifty_security_id), {}) or idx.get(int(nifty_security_id), {}) or {}
        if item:
            price = float(item.get("last_price", manual_nifty) or manual_nifty)
            prev_close = float((item.get("ohlc", {}) or {}).get("close", 0) or 0)
            nifty_change_pct = pct_change(price, prev_close) if prev_close else manual_nifty_change_pct
            nifty_source = "DhanHQ"
    except Exception:
        pass
if nifty_source == "Manual":
    yn = get_yahoo_nifty()
    if yn.get("success"):
        price = yn.get("price", price)
        nifty_change_pct = yn.get("change_pct", nifty_change_pct)
        nifty_source = yn.get("source", "Yahoo fallback")

# VIX
vix = manual_vix
vix_change_pct = manual_vix_change_pct
vix_source = "Manual"
yv = get_yahoo_vix()
if yv.get("success"):
    vix = yv.get("vix", vix)
    vix_change_pct = yv.get("change_pct", vix_change_pct)
    vix_source = yv.get("source", "Yahoo fallback")

# Expiry + Option Chain
expiry_result = get_dhan_expiries(client_id, access_token, nifty_security_id) if prefer_dhan else {"success": False, "expiries": []}
expiry = expiry_result.get("expiries", [""])[0] if expiry_result.get("expiries") else ""
option_chain = get_dhan_option_chain(client_id, access_token, expiry, nifty_security_id, DEFAULT_NIFTY_SEGMENT, strikes_each_side) if expiry else {"success": False, "message": "No expiry"}
option_analysis = analyze_option_chain(option_chain) if option_chain.get("success") else {"success": False, "rows": [], "bias": 0, "best_ce": None, "best_pe": None}

if option_chain.get("success"):
    price = float(option_chain.get("underlying", price) or price)
    pcr = float(option_chain.get("pcr", 0) or 0)
    call_oi_change = int(option_chain.get("call_oi_change", 0) or 0)
    put_oi_change = int(option_chain.get("put_oi_change", 0) or 0)
else:
    pcr = 0.0
    call_oi_change = 0
    put_oi_change = 0

# Price Action
ema20, ema50, vwap, atr5 = manual_ema20, manual_ema50, manual_vwap, manual_atr5
prev_high, prev_low = manual_previous_day_high, manual_previous_day_low
or_high, or_low = manual_opening_range_high, manual_opening_range_low
price_action_source = "Manual"
if auto_price_action:
    pa = get_yahoo_price_action()
    if pa.get("success"):
        ema20, ema50, vwap, atr5 = pa["ema20"], pa["ema50"], pa["vwap"], pa["atr5"]
        prev_high, prev_low = pa["previous_day_high"], pa["previous_day_low"]
        or_high, or_low = pa["opening_range_high"], pa["opening_range_low"]
        price_action_source = pa.get("source", "Yahoo candles auto")

price_action_bias, price_action_reasons = price_action_bias_engine(price, ema20, ema50, vwap, or_high, or_low, prev_high, prev_low)
pcr_bias, pcr_note = pcr_bias_engine(pcr)

# Heavyweights
hw_data = parse_dhan_heavyweights(dhan_bundle, top5_ids, {k: v["weight"] for k, v in TOP5_DEFAULT.items()}) if prefer_dhan and dhan_bundle.get("success") else {"success": False, "rows": []}
if not hw_data.get("success"):
    hw_data = get_yahoo_heavyweights()
hw_analysis = analyze_heavyweights(hw_data, price, nifty_change_pct) if hw_data.get("success") else {"success": False, "pressure": 0, "estimated_points": 0, "shock_score": 0, "rows": [], "source": "Unavailable"}
heavy_bias = float(hw_analysis.get("pressure", 0) or 0)

# FII/DII smart money
journal_df = load_fii_dii_journal()
stats = journal_stats(journal_df)
smart_money_bias = signed_clamp(float(stats.get("bias", 0)) + fut_bias_score(long_pct, short_pct, fut_bias))

# News/risk
te_result = get_te_calendar_risk(te_key)
alpha_result = get_alpha_news_risk(alpha_key)
reaction_score = market_reaction_risk(nifty_change_pct, vix_change_pct, hw_analysis)
news = build_news_risk(manual_news_risk, te_result, alpha_result, reaction_score, vix_change_pct, hw_analysis.get("shock_score", 0))
expiry_mode, dte = detect_expiry_mode(expiry, news.get("score", 0))
time_risk, time_zone = historical_time_zone_risk(expiry_mode == "EXPIRY MODE")
gamma_score = gamma_risk_score(expiry_mode == "EXPIRY MODE", vix_change_pct, hw_analysis.get("shock_score", 0), option_analysis.get("bias", 0), heavy_bias)
shock_score = shock_probability_score(time_risk, clamp(max(vix_change_pct, 0) * 10), option_analysis.get("bias", 0), heavy_bias, news.get("score", 0))
seller_risk = clamp(news.get("score", 0) * 0.30 + gamma_score * 0.25 + shock_score * 0.25 + max(vix - 12, 0) * 3.0 + time_risk * 0.10)

data_quality, data_reasons = data_quality_score(dhan_ready, option_chain.get("success"), nifty_source, hw_data.get("source", "Unavailable"), vix_source, price_action_source)

best_ce = option_analysis.get("best_ce")
best_pe = option_analysis.get("best_pe")
best_ce_score = int(best_ce.get("ce_sell_score", 0) if best_ce else 0)
best_pe_score = int(best_pe.get("pe_sell_score", 0) if best_pe else 0)

snapshot = build_market_snapshot(
    price=price, nifty_change_pct=nifty_change_pct, vix=vix, vix_change_pct=vix_change_pct,
    pcr=pcr, call_oi_change=call_oi_change, put_oi_change=put_oi_change,
    price_action_bias=price_action_bias, option_bias=option_analysis.get("bias", 0), heavy_bias=heavy_bias,
    smart_money_bias=smart_money_bias, pcr_bias=pcr_bias, data_quality=data_quality, seller_risk=seller_risk,
    news_score=news.get("score", 0), gamma_score=gamma_score, shock_score=shock_score, atr5=atr5,
    best_ce_score=best_ce_score, best_pe_score=best_pe_score, expiry=expiry, dte=dte,
    sources={"nifty": nifty_source, "vix": vix_source, "price_action": price_action_source, "heavyweights": hw_data.get("source", "Unavailable"), "option_chain": option_chain.get("source", "Unavailable") if option_chain.get("success") else "Unavailable"},
)
decision = v18_ai_brain(snapshot)

ce_candidate = select_candidate(option_analysis, "CE", manual_ce_strike, hedge_gap, decision["confidence"], seller_risk)
pe_candidate = select_candidate(option_analysis, "PE", manual_pe_strike, hedge_gap, decision["confidence"], seller_risk)

if decision["action"] == "SELL CE":
    chosen = ce_candidate
elif decision["action"] == "SELL PE":
    chosen = pe_candidate
else:
    chosen = None

# ------------------------- Main Screen -------------------------
st.markdown("<div class='main-title'>🧠 Nifty Seller AI — V18 Clean Base</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Cleaned architecture: old duplicate AI layers removed. One Snapshot → One AI Brain → One Final Decision.</div>", unsafe_allow_html=True)

status, day_name = market_status()
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Nifty", f"{price:,.2f}", f"{nifty_change_pct:.2f}%")
k2.metric("India VIX", f"{vix:.2f}", f"{vix_change_pct:.2f}%")
k3.metric("PCR", f"{pcr:.2f}" if pcr else "NA")
k4.metric("Data Quality", f"{data_quality}/100")
k5.metric("Seller Risk", f"{seller_risk:.0f}/100")

card_class = "card-wait"
if decision["action"] == "SELL PE":
    card_class = "card-green"
elif decision["action"] == "SELL CE":
    card_class = "card-red"
elif decision["action"] == "IRON CONDOR":
    card_class = "card-yellow"

st.markdown(f"""
<div class='advisor-card {card_class}'>
<h3>V18 Final AI Decision</h3>
<h1>{decision['action']}</h1>
<p><b>Confidence:</b> {decision['confidence']}% &nbsp; | &nbsp; <b>Directional Score:</b> {decision['directional_score']} &nbsp; | &nbsp; <b>Risk:</b> {decision['risk']}/100</p>
<p><b>Stability:</b> {'Material change detected' if decision['material_change'] else 'Locked because no material change'}</p>
</div>
""", unsafe_allow_html=True)

left, right = st.columns([1.15, 0.85])
with left:
    st.subheader("🎯 Trade Ticket")
    if decision["action"] == "SELL CE" and chosen:
        st.success(f"SELL {chosen['strike']} CE | Hedge BUY {chosen['hedge']} CE")
        st.write(f"Entry ₹{chosen['plan']['entry']:.2f} | SL ₹{chosen['plan']['sl']:.2f} | Target ₹{chosen['plan']['target1']:.2f} / ₹{chosen['plan']['target2']:.2f}")
    elif decision["action"] == "SELL PE" and chosen:
        st.success(f"SELL {chosen['strike']} PE | Hedge BUY {chosen['hedge']} PE")
        st.write(f"Entry ₹{chosen['plan']['entry']:.2f} | SL ₹{chosen['plan']['sl']:.2f} | Target ₹{chosen['plan']['target1']:.2f} / ₹{chosen['plan']['target2']:.2f}")
    elif decision["action"] == "IRON CONDOR":
        ce, pe = ce_candidate, pe_candidate
        st.info(f"CE Side: SELL {ce['strike']} CE / BUY {ce['hedge']} CE | PE Side: SELL {pe['strike']} PE / BUY {pe['hedge']} PE")
        st.write(f"CE Entry ₹{ce['plan']['entry']:.2f}, SL ₹{ce['plan']['sl']:.2f}, Target ₹{ce['plan']['target1']:.2f}")
        st.write(f"PE Entry ₹{pe['plan']['entry']:.2f}, SL ₹{pe['plan']['sl']:.2f}, Target ₹{pe['plan']['target1']:.2f}")
    else:
        st.warning("No fresh trade. WAIT is active.")

    st.subheader("🧾 Why AI Decided This")
    for reason in decision["reasons"]:
        st.write(f"• {reason}")
    st.caption("Change check: " + "; ".join(decision["change_reasons"]))

with right:
    st.subheader("📌 Snapshot Summary")
    st.write(f"**Market:** {status} ({day_name})")
    st.write(f"**Expiry Mode:** {expiry_mode} | DTE: {dte}")
    st.write(f"**Time Zone Risk:** {time_zone} ({time_risk}/100)")
    st.write(f"**News Risk:** {news.get('label')} ({news.get('score')}/100)")
    st.write(f"**Max Lots by Capital:** {max_lots}")
    st.write(f"**Snapshot:** {snapshot['created_at']}")

st.subheader("🧠 One-Brain Input Scores")
score_df = pd.DataFrame([
    {"Factor": "Price Action", "Score": round(price_action_bias, 1), "Note": ", ".join(price_action_reasons)},
    {"Factor": "Option Chain", "Score": round(option_analysis.get("bias", 0), 1), "Note": f"CE score {best_ce_score}, PE score {best_pe_score}"},
    {"Factor": "Heavyweights", "Score": round(heavy_bias, 1), "Note": hw_analysis.get("divergence", "")},
    {"Factor": "Smart Money", "Score": round(smart_money_bias, 1), "Note": stats.get("label", "")},
    {"Factor": "PCR", "Score": round(pcr_bias, 1), "Note": pcr_note},
])
st.dataframe(score_df, width="stretch", hide_index=True)

st.subheader("📊 Smart Strategy Matrix")
matrix = []
for label, cand, conf_adj in [("SELL CE", ce_candidate, -snapshot["directional_score"]), ("SELL PE", pe_candidate, snapshot["directional_score"] )]:
    allowed = decision["action"] == label
    matrix.append({
        "Strategy": label,
        "Sell Strike": cand["strike"],
        "Hedge": cand["hedge"],
        "Entry": cand["plan"]["entry"],
        "SL": cand["plan"]["sl"],
        "Target": cand["plan"]["target1"],
        "Candidate Score": best_ce_score if label == "SELL CE" else best_pe_score,
        "Status": "✅ Final" if allowed else "⚠️ Wait",
    })
matrix.append({
    "Strategy": "IRON CONDOR", "Sell Strike": f"CE {ce_candidate['strike']} + PE {pe_candidate['strike']}",
    "Hedge": f"CE {ce_candidate['hedge']} + PE {pe_candidate['hedge']}",
    "Entry": round(ce_candidate['plan']['entry'] + pe_candidate['plan']['entry'], 2),
    "SL": f"CE {ce_candidate['plan']['sl']} / PE {pe_candidate['plan']['sl']}",
    "Target": f"CE {ce_candidate['plan']['target1']} / PE {pe_candidate['plan']['target1']}",
    "Candidate Score": min(best_ce_score, best_pe_score),
    "Status": "✅ Final" if decision["action"] == "IRON CONDOR" else "⚠️ Wait",
})
st.dataframe(pd.DataFrame(matrix), width="stretch", hide_index=True)

if option_analysis.get("success"):
    with st.expander("📈 Option Chain Near ATM", expanded=False):
        rows = option_analysis.get("rows", [])
        oc_df = pd.DataFrame(rows)
        show_cols = [c for c in ["strike", "ce_ltp", "ce_oi", "ce_oi_change", "ce_signal", "ce_sell_score", "pe_ltp", "pe_oi", "pe_oi_change", "pe_signal", "pe_sell_score"] if c in oc_df.columns]
        st.dataframe(oc_df[show_cols], width="stretch", hide_index=True)
else:
    st.info("Live option-chain unavailable. Add/refresh Dhan token for full strike engine.")

if developer_mode:
    st.subheader("🛠️ Developer Diagnostics")
    st.json({"snapshot": snapshot, "decision": decision, "data_reasons": data_reasons, "option_message": option_chain.get("message"), "dhan_message": dhan_bundle.get("message")})
    if hw_analysis.get("rows"):
        st.dataframe(pd.DataFrame(hw_analysis["rows"]), width="stretch", hide_index=True)

st.markdown("<div class='small-note'>V18 Clean Base: old duplicate AI decision layers removed. Educational decision-support only, not financial advice. Use hedge, strict SL and position sizing.</div>", unsafe_allow_html=True)

# Lightweight auto refresh at end.
if st.session_state.get("auto_refresh", False):
    time.sleep(int(st.session_state.get("refresh_interval", 20)))
    st.rerun()
