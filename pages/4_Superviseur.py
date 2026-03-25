"""Vue Superviseur — Timeline complete, KPIs, evolution step-by-step."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Superviseur", page_icon="🎯", layout="wide")
st.title("Superviseur — Pilotage global")

data = st.session_state.get("game_data")
if not data:
    st.warning("Aucune donnee. Retournez a l'accueil.")
    st.stop()

from src.analytics import (
    compute_stock_timeline, compute_penalty_steps,
    compute_po_summary, compute_cash_flow_events,
)

# ============================================================
# KPIs HEADER
# ============================================================
last = data.financials.iloc[-1]
col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric("Cash", f"{last['cash']:,.0f}")
with col2:
    delta_color = "inverse" if last["loan"] < 0 else "off"
    st.metric("Loan", f"{abs(last['loan']):,.0f}" if last["loan"] < 0 else "0", delta_color=delta_color)
with col3:
    st.metric("Profit", f"{last['profit']:,.0f}")
with col4:
    st.metric("Valorisation", f"{last['valuation']:,.0f}")
with col5:
    st.metric("Credit", last["credit"])
with col6:
    risk = last["risk_company"] + last["risk_market"]
    st.metric("Taux risque", f"{risk:.1f}%")

# ============================================================
# ALERTES
# ============================================================
penalties = compute_penalty_steps(data)
if len(penalties) > 0:
    total_penalty = len(penalties) * 300
    st.error(f"Penalites de stockage : {len(penalties)} steps x 300 EUR = **{total_penalty:,} EUR** de profit perdu")

if last["loan"] < 0:
    st.warning(f"Pret actif : **{abs(last['loan']):,.0f} EUR** — interets en cours")

if last["cash"] < 50000:
    st.error(f"Cash critique : {last['cash']:,.0f} EUR (seuil minimum: 50 000)")

# ============================================================
# EVOLUTION CASH + PROFIT + VALORISATION
# ============================================================
st.subheader("Evolution financiere step-by-step")

fig_fin = go.Figure()
fig_fin.add_trace(go.Scatter(
    x=data.financials["elapsed"], y=data.financials["cash"],
    name="Cash", line=dict(color="#2ecc71", width=2),
))
fig_fin.add_trace(go.Scatter(
    x=data.financials["elapsed"], y=data.financials["profit"],
    name="Profit", line=dict(color="#3498db", width=2),
))
fig_fin.add_trace(go.Scatter(
    x=data.financials["elapsed"], y=data.financials["loan"].abs(),
    name="Loan", line=dict(color="#e74c3c", width=2, dash="dash"),
))

# Marquer les PO livraisons
po_summary = compute_po_summary(data)
if len(po_summary) > 0:
    for _, po in po_summary.iterrows():
        fig_fin.add_vline(
            x=po["delivery_elapsed"], line_dash="dot", line_color="orange",
            annotation_text=f"PO {po['total_qty']}u",
        )

# Zone danger cash
fig_fin.add_hline(y=50000, line_dash="dash", line_color="red", opacity=0.5,
                  annotation_text="Seuil cash 50K")
fig_fin.add_hline(y=0, line_color="red", opacity=0.3)

fig_fin.update_layout(
    height=400, xaxis_title="Step", yaxis_title="EUR",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    hovermode="x unified",
)

# Ajouter les labels de round sur l'axe X
round_starts = data.financials.drop_duplicates("round")[["elapsed", "round"]]
fig_fin.update_xaxes(
    tickvals=round_starts["elapsed"].tolist(),
    ticktext=[f"R{int(r)}" for r in round_starts["round"].tolist()],
)

st.plotly_chart(fig_fin, use_container_width=True)

# ============================================================
# EVOLUTION STOCK
# ============================================================
st.subheader("Evolution stock step-by-step")

stock_timeline = compute_stock_timeline(data)
if len(stock_timeline) > 0:
    fig_stock = go.Figure()
    fig_stock.add_trace(go.Scatter(
        x=stock_timeline["elapsed"], y=stock_timeline["total"],
        name="Stock total", fill="tozeroy", line=dict(color="#9b59b6"),
    ))
    fig_stock.add_trace(go.Scatter(
        x=stock_timeline["elapsed"], y=stock_timeline["central"],
        name="Central", line=dict(color="#e67e22", width=2),
    ))
    fig_stock.add_trace(go.Scatter(
        x=stock_timeline["elapsed"], y=stock_timeline["regions"],
        name="Regions", line=dict(color="#1abc9c", width=2),
    ))
    fig_stock.add_hline(y=4000, line_dash="dash", line_color="red",
                        annotation_text="Capacite max 4000")
    fig_stock.add_hline(y=3800, line_dash="dot", line_color="orange",
                        annotation_text="Seuil alerte 3800")

    # PO livraisons
    if len(po_summary) > 0:
        for _, po in po_summary.iterrows():
            fig_stock.add_vline(
                x=po["delivery_elapsed"], line_dash="dot", line_color="orange",
                annotation_text=f"PO +{po['total_qty']}u",
            )

    fig_stock.update_layout(
        height=400, xaxis_title="Step", yaxis_title="Unites",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    fig_stock.update_xaxes(
        tickvals=round_starts["elapsed"].tolist(),
        ticktext=[f"R{int(r)}" for r in round_starts["round"].tolist()],
    )
    st.plotly_chart(fig_stock, use_container_width=True)

# ============================================================
# VALORISATION
# ============================================================
st.subheader("Evolution valorisation")

fig_val = go.Figure()
fig_val.add_trace(go.Scatter(
    x=data.financials["elapsed"], y=data.financials["valuation"],
    name="Valorisation", line=dict(color="#f39c12", width=3),
    fill="tozeroy",
))
fig_val.update_layout(
    height=300, xaxis_title="Step", yaxis_title="EUR",
    hovermode="x unified",
)
fig_val.update_xaxes(
    tickvals=round_starts["elapsed"].tolist(),
    ticktext=[f"R{int(r)}" for r in round_starts["round"].tolist()],
)
st.plotly_chart(fig_val, use_container_width=True)

# ============================================================
# PURCHASE ORDERS
# ============================================================
st.subheader("Historique des commandes")

if len(po_summary) > 0:
    for _, po in po_summary.iterrows():
        with st.expander(f"PO {po['po_number']} — {po['delivery']} — {int(po['total_qty'])} unites — {po['total_cost']:,.0f} EUR"):
            st.markdown(f"**Produits:** {po['products']}")
            st.markdown(f"**Cout marchandise:** {po['goods_cost']:,.0f} EUR + 1 000 EUR fee = **{po['total_cost']:,.0f} EUR**")

# ============================================================
# EVENEMENTS TIMELINE
# ============================================================
st.subheader("Evenements financiers")

events = compute_cash_flow_events(data)
if len(events) > 0:
    st.dataframe(
        events[["elapsed", "type", "description", "amount"]].rename(columns={
            "elapsed": "Step", "type": "Type", "description": "Detail", "amount": "Montant EUR"
        }),
        use_container_width=True, hide_index=True,
    )

# ============================================================
# TABLE FINANCIERE COMPLETE
# ============================================================
with st.expander("Donnees financieres brutes (step-by-step)"):
    display_cols = ["label", "cash", "profit", "loan", "credit", "valuation"]
    st.dataframe(
        data.financials[display_cols].rename(columns={
            "label": "Step", "cash": "Cash", "profit": "Profit",
            "loan": "Loan", "credit": "Credit", "valuation": "Valorisation",
        }),
        use_container_width=True, hide_index=True,
    )
