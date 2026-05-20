import streamlit as st

from meteora import get_positions
from signals import get_signals
from tracker import get_pnl_summary

st.set_page_config(page_title="Memecoin Intel", page_icon="🚀", layout="wide")
st.title("🚀 Memecoin Intel")

col_signals, col_pnl = st.columns([3, 1])

with col_signals:
    st.subheader("Live Signals")
    with st.spinner("Fetching..."):
        signals = get_signals()

    for sig in signals:
        if sig.signal == "buy now":
            badge = ":green[BUY NOW]"
        elif sig.signal == "sell":
            badge = ":red[SELL]"
        else:
            badge = ":gray[HOLD]"

        st.markdown(
            f"**{sig.coin}** — {badge} "
            f"@ `${sig.price_usd:.8g}` "
            f"| conf {sig.confidence:.0%} "
            f"| {sig.reason}"
        )

with col_pnl:
    st.subheader("PnL")
    pnl = get_pnl_summary()
    st.metric("Invested", f"${pnl['total_invested']:,.2f}")
    st.metric("Returned", f"${pnl['total_returned']:,.2f}")
    st.metric("Net PnL", f"${pnl['pnl']:,.2f}", delta=f"{pnl['pnl']:+,.2f}")

    st.subheader("Meteora LP")
    positions = get_positions()
    if positions:
        for pos in positions:
            st.json(pos)
    else:
        st.info("No LP positions (or wallet not set).")
