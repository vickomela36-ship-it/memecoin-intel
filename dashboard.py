"""Streamlit dashboard for memecoin intel."""

import streamlit as st
import pandas as pd
from signals import get_signals
from tracker import get_open_trades, get_total_pnl
from meteora import get_position_summary

st.set_page_config(page_title="Memecoin Intel", layout="wide")
st.title("Memecoin Intel Dashboard")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total PnL", f"${get_total_pnl():,.2f}")

with col2:
    open_trades = get_open_trades()
    st.metric("Open Trades", len(open_trades))

with col3:
    lp = get_position_summary()
    st.metric("LP Fees Earned", f"${lp['total_fees_usd']:,.2f}")

st.divider()
st.subheader("Live Signals")

with st.spinner("Fetching signals..."):
    signals = get_signals()

if signals:
    df = pd.DataFrame(signals)
    df = df.sort_values("signal").reset_index(drop=True)
    st.dataframe(
        df.style.applymap(
            lambda v: "background-color: #d4edda" if v == "buy now"
            else "background-color: #f8d7da" if v == "sell"
            else "",
            subset=["signal"],
        ),
        use_container_width=True,
    )
else:
    st.info("No memecoin signals found.")

st.divider()
st.subheader("Open Trades")
if open_trades:
    st.dataframe(pd.DataFrame(open_trades), use_container_width=True)
else:
    st.info("No open trades.")
