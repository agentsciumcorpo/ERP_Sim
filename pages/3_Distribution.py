"""Vue Distribution — Transferts recommandes + stock par region."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from src.data_loader import PRODUCTS, REGIONS

st.set_page_config(page_title="Distribution", page_icon="🚛", layout="wide")
st.title("Distribution")

data = st.session_state.get("game_data")
results = st.session_state.get("agent_results", {})
if not data:
    st.info("Cliquez **Actualiser** dans la vue Superviseur.")
    st.stop()

from src.analytics import compute_stock_heatmap

# ============================================================
# TRANSFERTS RECOMMANDES — EN HAUT, EN GRAND
# ============================================================
stock_reco = results.get("stock", {})
transfers = stock_reco.get("transfers", [])

if transfers:
    st.subheader(f"Transferts a faire — {len(transfers)} operations")

    # Grouper par region
    for region in REGIONS:
        region_transfers = [t for t in transfers if t.get("to") == region]
        if not region_transfers:
            continue

        st.markdown(f"### → {region}")
        cols = st.columns(len(region_transfers))
        for i, t in enumerate(region_transfers):
            with cols[i]:
                st.metric(t["product"], f"+{t['quantity']}")
                st.caption(t.get("reason", ""))

    total_units = sum(t["quantity"] for t in transfers)
    total_cost = len(transfers) * 100
    st.info(f"**Total : {total_units:,} unites — cout transfert : {total_cost:,} EUR**")
else:
    st.success("Aucun transfert necessaire pour le moment.")

# ============================================================
# STOCK PAR REGION — TABLEAU SIMPLE COLORE
# ============================================================
st.markdown("---")
st.subheader("Stock actuel par region")

heatmap = compute_stock_heatmap(data)
if len(heatmap) > 0:
    fig = go.Figure(data=go.Heatmap(
        z=heatmap.values,
        x=heatmap.columns.tolist(),
        y=heatmap.index.tolist(),
        text=heatmap.values.astype(int).astype(str),
        texttemplate="%{text}",
        textfont=dict(size=14),
        colorscale=[
            [0, "#e74c3c"],
            [0.05, "#e67e22"],
            [0.15, "#f1c40f"],
            [0.4, "#2ecc71"],
            [1.0, "#27ae60"],
        ],
        showscale=False,
    ))
    fig.update_layout(height=350, title="Stock (rouge = critique, vert = ok)")
    st.plotly_chart(fig, use_container_width=True)

    # Alertes rupture
    for prod in PRODUCTS:
        if prod in heatmap.index:
            for loc in ["Central"] + REGIONS:
                if loc in heatmap.columns:
                    val = int(heatmap.loc[prod, loc])
                    if val == 0:
                        st.error(f"RUPTURE : {prod} @ {loc} = 0")
                    elif val < 50:
                        st.warning(f"Stock bas : {prod} @ {loc} = {val}")
