"""Vue Approvisionnement — Recommandation commande + 2 graphes."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Approvisionnement", page_icon="📦", layout="wide")
st.title("Approvisionnement")

data = st.session_state.get("game_data")
results = st.session_state.get("agent_results", {})
if not data:
    st.info("Cliquez **Actualiser** dans la vue Superviseur.")
    st.stop()

from src.analytics import compute_real_margins, compute_stock_timeline, compute_po_summary

# ============================================================
# RECOMMANDATION COMMANDE — EN HAUT, EN GRAND
# ============================================================
stock_reco = results.get("stock", {})

if stock_reco:
    order_now = stock_reco.get("order_now", False)
    order_qty = stock_reco.get("order_quantity", 0)
    reasoning = stock_reco.get("order_reasoning", "")

    if order_now:
        st.error(f"### COMMANDER MAINTENANT — {order_qty:,} unites")
    else:
        st.success("### Pas de commande necessaire pour l'instant")

    st.markdown(f"**Raison :** {reasoning}")

    # Detail par produit
    detail = stock_reco.get("order_detail", [])
    if detail:
        st.markdown("**Detail de la commande :**")
        detail_cols = st.columns(len(detail))
        for i, d in enumerate(detail):
            with detail_cols[i]:
                st.metric(d["product"], f"{d['quantity']}")

        # Estimation cout
        total_qty = sum(d["quantity"] for d in detail)
        est_cost = sum(
            d["quantity"] * data.purchase_costs.get(d["product"], 50)
            for d in detail
        ) + 1000  # fee PO
        last_cash = data.financials.iloc[-1]["cash"]
        remaining = last_cash - est_cost

        st.markdown(f"**Cout estime : {est_cost:,.0f} EUR** | Cash apres : {remaining:,.0f} EUR")
        if remaining < 50000:
            st.warning(f"Attention : cash apres commande ({remaining:,.0f}) proche du seuil 50K")
else:
    st.warning("Pas de recommandation. Cliquez **Actualiser** dans Superviseur.")

# ============================================================
# GRAPHE 1 : Stock total step-by-step
# ============================================================
st.markdown("---")
st.subheader("Evolution du stock")

stock_tl = compute_stock_timeline(data)
if len(stock_tl) > 0:
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=stock_tl["elapsed"], y=stock_tl["total"],
        name="Stock total", fill="tozeroy", line=dict(color="#9b59b6"),
    ))
    fig1.add_hline(y=4000, line_dash="dash", line_color="red",
                   annotation_text="Penalite 4000")

    po_summary = compute_po_summary(data)
    if len(po_summary) > 0:
        for _, po in po_summary.iterrows():
            fig1.add_vline(x=po["delivery_elapsed"], line_dash="dot",
                           line_color="green", annotation_text=f"+{int(po['total_qty'])}")

    round_starts = data.financials.drop_duplicates("round")[["elapsed", "round"]]
    fig1.update_xaxes(
        tickvals=round_starts["elapsed"].tolist(),
        ticktext=[f"R{int(r)}" for r in round_starts["round"].tolist()],
    )
    fig1.update_layout(height=350, hovermode="x unified")
    st.plotly_chart(fig1, use_container_width=True)

# ============================================================
# GRAPHE 2 : Ecoulement par produit
# ============================================================
st.subheader("Ecoulement (vendu vs restant)")

margins = compute_real_margins(data)
if len(margins) > 0:
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=margins["product"], y=margins["qty_sold"],
        name="Vendu", marker_color="#2ecc71",
    ))
    fig2.add_trace(go.Bar(
        x=margins["product"], y=margins["qty_remaining"],
        name="Restant", marker_color="#e74c3c",
    ))
    fig2.update_layout(
        barmode="stack", height=350,
        yaxis_title="Unites",
        legend=dict(orientation="h", y=1.05),
    )
    st.plotly_chart(fig2, use_container_width=True)
