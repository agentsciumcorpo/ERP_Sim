"""Vue Pricing — Recommandations prix + 2 graphes essentiels."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Pricing", page_icon="💰", layout="wide")
st.title("Pricing")

data = st.session_state.get("game_data")
results = st.session_state.get("agent_results", {})
if not data:
    st.info("Cliquez **Actualiser** dans la vue Superviseur.")
    st.stop()

from src.analytics import compute_real_margins, compute_volume_evolution

# ============================================================
# RECOMMANDATIONS PRIX — EN HAUT, EN GRAND
# ============================================================
pricing = results.get("pricing", [])

if pricing:
    st.subheader("Recommandations pour le prochain round")

    cols = st.columns(len(pricing))
    for i, rec in enumerate(pricing):
        with cols[i]:
            current = rec.get("current_price", 0)
            recommended = rec.get("recommended_price", current)
            change = rec.get("change_pct", 0)
            conf = rec.get("confidence", "?")

            arrow = "↑" if change > 0 else "↓" if change < 0 else "="
            color = "normal" if change >= 0 else "inverse"

            st.metric(
                rec.get("product", "?"),
                f"{recommended:.2f}",
                f"{arrow} {change:+.1f}%",
                delta_color=color,
            )
            conf_colors = {"haute": "🟢", "moyenne": "🟡", "basse": "🔴"}
            st.caption(f"{conf_colors.get(conf, '⚪')} {conf}")

    # Raisonnements
    st.markdown("---")
    for rec in pricing:
        reasoning = rec.get("reasoning", "")
        if reasoning:
            change = rec.get("change_pct", 0)
            arrow = "↑" if change > 0 else "↓" if change < 0 else "="
            st.markdown(f"**{rec['product']}** {arrow} — {reasoning}")
else:
    st.warning("Pas de recommandation. Cliquez **Actualiser** dans Superviseur.")

# ============================================================
# GRAPHE 1 : Contribution par produit (marge x volume)
# ============================================================
st.markdown("---")
st.subheader("Contribution par produit")

margins = compute_real_margins(data)
if len(margins) > 0:
    colors = ["#2ecc71" if t > 70 else "#f39c12" if t > 45 else "#e74c3c"
              for t in margins["turnover_pct"]]

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=margins["product"], y=margins["contribution"],
        marker_color=colors,
        text=[f"{c:,.0f}€<br>{m:.1f}%" for c, m in zip(margins["contribution"], margins["margin_pct"])],
        textposition="outside",
    ))
    fig1.update_layout(
        height=350, yaxis_title="Contribution EUR",
        title="Marge x Volume (vert = bon ecoulement, rouge = mauvais)",
    )
    st.plotly_chart(fig1, use_container_width=True)

# ============================================================
# GRAPHE 2 : Evolution volumes par round
# ============================================================
st.subheader("Evolution des ventes par round")

vol = compute_volume_evolution(data)
if len(vol) > 0:
    fig2 = go.Figure()
    for prod in vol["product"].unique():
        prod_data = vol[vol["product"] == prod]
        fig2.add_trace(go.Scatter(
            x=prod_data["round"], y=prod_data["qty"],
            name=prod, mode="lines+markers",
        ))
    fig2.update_layout(
        height=350, xaxis_title="Round", yaxis_title="Quantite vendue",
        legend=dict(orientation="h", y=1.1),
        hovermode="x unified",
    )
    st.plotly_chart(fig2, use_container_width=True)
