"""Streamlit dashboard — visualises recent signals and PnL log."""

import os
import pandas as pd
import streamlit as st

PNL_LOG = os.getenv("PNL_LOG_FILE", "pnl_log.csv")

st.set_page_config(page_title="Memecoin Intel", page_icon="📈", layout="wide")
st.title("📈 Memecoin Intel Dashboard")

if not os.path.exists(PNL_LOG):
    st.info("No signal data yet — run `python daily_runner.py` first.")
    st.stop()

df = pd.read_csv(PNL_LOG, parse_dates=["timestamp"])
df = df.sort_values("timestamp", ascending=False)

col1, col2, col3 = st.columns(3)
col1.metric("Total Signals Logged", len(df))
col2.metric("Buy Now", (df["signal"] == "buy now").sum())
col3.metric("Coins Tracked", df["coin"].nunique())

st.subheader("Signal History")
st.dataframe(
    df.style.applymap(
        lambda v: "color: #22c55e; font-weight: bold" if v == "buy now" else
                  "color: #ef4444" if v == "sell" else "",
        subset=["signal"],
    ),
    use_container_width=True,
)

buy_df = df[df["signal"] == "buy now"]
if not buy_df.empty:
    st.subheader("Buy Now History")
    st.bar_chart(buy_df.groupby("coin").size().sort_values(ascending=False))
