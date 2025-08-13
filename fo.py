# app.py
"""
Simple Options Scalper – Streamlit

What it does
- Lets you log a buy trade (e.g., MIDCPNIFTY 14000 CE), set a target & stop-loss, and monitor live P&L.
- You can manually update LTP; any trade with Auto-Close enabled will close at the target when LTP >= target (for Calls) or LTP <= target (for Puts).
- Tracks status (OPEN/CLOSED), P&L (₹), and exports your blotter to CSV.

Notes
- Default lot size for MIDCPNIFTY is prefilled as 140 (as per NSE circulars effective Apr 25, 2025). Verify with your broker before trading.
- This demo does NOT place real orders. To integrate with a broker API (e.g., Zerodha/Kite), wire up the `place_order` and `exit_order` stubs where marked.

Run locally
    pip install streamlit pandas
    streamlit run app.py
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, asdict
import pandas as pd
import streamlit as st

# -----------------------------
# Helpers & State
# -----------------------------
@dataclass
class Trade:
    id: str
    ts: str
    symbol: str        # e.g., MIDCPNIFTY
    option_type: str   # CE/PE
    strike: float
    expiry: str        # free text (e.g., 14-Aug-2025)
    lot_size: int
    lots: int
    entry: float       # premium paid
    target: float      # target premium to exit
    stop: float        # stop-loss premium to exit
    auto_close: bool
    status: str        # OPEN/CLOSED
    exit_price: float  # last traded price at exit
    pnl: float         # in rupees


def init_state():
    if "trades" not in st.session_state:
        st.session_state.trades: list[dict] = []
    if "default_symbol" not in st.session_state:
        st.session_state.default_symbol = "MIDCPNIFTY"
    if "default_lot" not in st.session_state:
        st.session_state.default_lot = 140  # Verify with broker
    if "last_form" not in st.session_state:
        st.session_state.last_form = {}


def to_df() -> pd.DataFrame:
    if not st.session_state.trades:
        return pd.DataFrame(columns=[
            "id","ts","symbol","option_type","strike","expiry","lot_size","lots","entry","target","stop","auto_close","status","exit_price","pnl"
        ])
    return pd.DataFrame(st.session_state.trades)


def save_trade(trade: Trade):
    st.session_state.trades.append(asdict(trade))


def update_trade_exit(trade_id: str, exit_price: float):
    for t in st.session_state.trades:
        if t["id"] == trade_id and t["status"] == "OPEN":
            # P&L per lot = (exit - entry) * lot_size; total lots multiply again
            sign = 1 if t["option_type"] == "CE" else -1  # for simple buy logic on PE, profit if exit < entry
            # For Puts (buy), P&L = (exit - entry) * lot_size * lots, but monitoring target uses inverse condition below
            pnl = (exit_price - t["entry"]) * t["lot_size"] * t["lots"]
            t["status"] = "CLOSED"
            t["exit_price"] = float(exit_price)
            t["pnl"] = float(pnl)
            st.toast(f"Closed {t['symbol']} {int(t['strike'])}{t['option_type']} @ {exit_price:.2f} | P&L ₹{pnl:.2f}")
            break


def auto_close_if_hit(ltp_map: dict[str, float]):
    # ltp_map: symbol -> LTP (premium)
    for t in st.session_state.trades:
        if t["status"] != "OPEN":
            continue
        sym = t["symbol"]
        if sym not in ltp_map:
            continue
        ltp = ltp_map[sym]
        if t["option_type"] == "CE":
            hit_target = ltp >= t["target"]
            hit_stop = (t["stop"] > 0) and (ltp <= t["stop"])
        else:  # PE (buy)
            hit_target = ltp >= t["target"]  # keep same if user sets target on premium itself
            hit_stop = (t["stop"] > 0) and (ltp <= t["stop"])  # same logic on premium
        if t["auto_close"]:
            if hit_target:
                update_trade_exit(t["id"], t["target"])  # close exactly at target for accounting
            elif hit_stop:
                update_trade_exit(t["id"], t["stop"])    # close at stop


# -----------------------------
# UI
# -----------------------------
init_state()
st.set_page_config(page_title="Simple Options Scalper", layout="wide")
st.title("🟢 Simple Options Scalper")
st.caption("Track intra-day option buys, set target/SL, and auto-close on profit.")

with st.sidebar:
    st.subheader("Defaults")
    st.session_state.default_symbol = st.text_input("Default Symbol", st.session_state.default_symbol)
    st.session_state.default_lot = st.number_input("Default Lot Size", min_value=1, step=1, value=st.session_state.default_lot)
    st.markdown("---")
    st.write("**Quick LTP Update** (per symbol)")
    ltp_inputs = {}
    for sym in sorted({t["symbol"] for t in st.session_state.trades}):
        ltp_inputs[sym] = st.number_input(f"{sym} LTP (premium)", min_value=0.0, step=0.05, format="%.2f", key=f"ltp_{sym}")
    if st.button("Apply LTP & Auto-Close"):
        auto_close_if_hit(ltp_inputs)

# --- New Trade Form
st.header("Enter New Trade")
col1, col2, col3, col4 = st.columns([1.2, 0.8, 0.8, 1.0])
with col1:
    symbol = st.text_input("Symbol", st.session_state.default_symbol)
with col2:
    option_type = st.selectbox("Type", ["CE", "PE"], index=0)
with col3:
    strike = st.number_input("Strike", min_value=0.0, step=50.0, value=14000.0, format="%.2f")
with col4:
    expiry = st.text_input("Expiry (e.g., 14-Aug-2025)", datetime.today().strftime("%d-%b-%Y"))

col5, col6, col7, col8 = st.columns([0.7, 0.7, 0.7, 0.9])
with col5:
    lot_size = st.number_input("Lot Size", min_value=1, step=1, value=st.session_state.default_lot)
with col6:
    lots = st.number_input("Lots", min_value=1, step=1, value=1)
with col7:
    entry = st.number_input("Entry (₹)", min_value=0.0, step=0.05, value=2.40, format="%.2f")
with col8:
    target = st.number_input("Target (₹)", min_value=0.0, step=0.05, value=3.10, format="%.2f")

col9, col10, col11 = st.columns([0.9, 1.0, 1.1])
with col9:
    stop = st.number_input("Stop-Loss (₹)", min_value=0.0, step=0.05, value=0.00, format="%.2f", help="Optional. If > 0, Auto-Close can use this.")
with col10:
    auto_close = st.checkbox("Auto-Close at Target/SL", value=True)
with col11:
    st.write(" ")
    if st.button("➕ Add Trade"):
        t = Trade(
            id=str(uuid.uuid4())[:8],
            ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            symbol=symbol.strip().upper(),
            option_type=option_type,
            strike=float(strike),
            expiry=expiry.strip(),
            lot_size=int(lot_size),
            lots=int(lots),
            entry=float(entry),
            target=float(target),
            stop=float(stop),
            auto_close=bool(auto_close),
            status="OPEN",
            exit_price=0.0,
            pnl=0.0,
        )
        save_trade(t)
        st.success(f"Added {t.symbol} {int(t.strike)}{t.option_type} | Entry ₹{t.entry:.2f}, Target ₹{t.target:.2f}, Lot {t.lot_size} x {t.lots}")

# Show Instant P&L preview for the current form
st.markdown(":small_blue_diamond: **Per-lot profit at target** = (Target − Entry) × Lot Size")
per_lot_profit = (target - entry) * lot_size
st.info(f"Per-lot profit at target = ₹{per_lot_profit:.2f}; For {lots} lot(s): ₹{per_lot_profit * lots:.2f}")

# --- Blotter & Actions
st.header("Trades Blotter")
df = to_df()
if df.empty:
    st.warning("No trades yet. Add a trade above.")
else:
    # Order by newest first
    df = df.sort_values("ts", ascending=False)

    # Action buttons (close selected, export)
    sel_col, act_col1, act_col2 = st.columns([1.2, 0.5, 0.5])
    with sel_col:
        ids = df["id"].tolist()
        pick = st.selectbox("Select Trade ID", ids)
    with act_col1:
        close_px = st.number_input("Manual Close @ (₹)", min_value=0.0, step=0.05, format="%.2f")
        if st.button("Close Selected"):
            update_trade_exit(pick, close_px)
    with act_col2:
        if st.button("Export CSV"):
            export_df = to_df()
            file = "scalper_trades.csv"
            export_df.to_csv(file, index=False)
            st.success(f"Exported {len(export_df)} rows → {file}")
            st.download_button(label="Download CSV", file_name=file, data=export_df.to_csv(index=False), mime="text/csv")

    # Color rows by status
    def _style_status(row):
        if row["status"] == "CLOSED":
            return ["background-color: #e8ffe8" for _ in row]
        return ["" for _ in row]

    st.dataframe(df, use_container_width=True)

# -----------------------------
# Broker API placeholders
# -----------------------------
# def place_order(...):
#     """Integrate your broker API here (e.g., Kite/Zerodha)."""
#     pass
#
# def exit_order(...):
#     """Send exit order to broker here."""
#     pass
