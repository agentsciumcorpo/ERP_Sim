"""Vue Approvisionnement — Stock heatmap, ecoulement, POs."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Approvisionnement", page_icon="📦", layout="wide")
st.title("Approvisionnement — Stock & Commandes")

data = st.session_state.get("game_data")
if not data:
    st.warning("Aucune donnee. Retournez a l'accueil.")
    st.stop()

from src.analytics import (
    compute_stock_heatmap, compute_real_margins,
    compute_po_summary, compute_stock_timeline,
)
from src.data_loader import PRODUCTS

# ============================================================
# STOCK CENTRAL - JAUGE
# ============================================================
st.subheader("Stock central")

if len(data.current_stock) > 0:
    central = data.current_stock[data.current_stock["location"] == "Central"]
    central_total = int(central["stock"].sum())

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Stock central total", f"{central_total:,}")
    with col2:
        st.metric("Capacite max", "4 000")
    with col3:
        pct = central_total / 4000 * 100
        color = "normal" if pct < 95 else "inverse"
        st.metric("Remplissage", f"{pct:.0f}%", delta_color=color)

    if central_total > 4000:
        st.error(f"PENALITE ACTIVE — Stock {central_total} > 4000 = 300 EUR/jour!")
    elif central_total > 3800:
        st.warning(f"Attention — Stock {central_total} proche du seuil 4000")

    st.progress(min(1.0, central_total / 4000))

# ============================================================
# HEATMAP STOCK ACTUEL
# ============================================================
st.subheader("Stock actuel par produit & location")

heatmap = compute_stock_heatmap(data)
if len(heatmap) > 0:
    # Coloriser : rouge si < 50, orange si < 100, vert sinon
    fig_heat = go.Figure(data=go.Heatmap(
        z=heatmap.values,
        x=heatmap.columns.tolist(),
        y=heatmap.index.tolist(),
        text=heatmap.values.astype(int).astype(str),
        texttemplate="%{text}",
        colorscale=[
            [0, "#e74c3c"],       # 0 = rouge
            [0.05, "#e67e22"],    # < 50 = orange
            [0.15, "#f1c40f"],    # < 150 = jaune
            [0.4, "#2ecc71"],     # normal = vert
            [1.0, "#27ae60"],     # beaucoup = vert fonce
        ],
        showscale=True,
        colorbar=dict(title="Unites"),
    ))
    fig_heat.update_layout(
        height=350, title="Stock actuel (0 = rupture, rouge = critique)",
        xaxis_title="Location", yaxis_title="Produit",
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    # Tableau
    st.dataframe(heatmap.astype(int), use_container_width=True)

# ============================================================
# TAUX D'ECOULEMENT
# ============================================================
st.subheader("Taux d'ecoulement par produit")

margins = compute_real_margins(data)
if len(margins) > 0:
    col_a, col_b = st.columns(2)
    with col_a:
        fig_turn = go.Figure()
        colors = ["#2ecc71" if t > 75 else "#f39c12" if t > 50 else "#e74c3c" for t in margins["turnover_pct"]]
        fig_turn.add_trace(go.Bar(
            x=margins["product"], y=margins["turnover_pct"],
            marker_color=colors,
            text=[f"{t:.0f}%" for t in margins["turnover_pct"]],
            textposition="outside",
        ))
        fig_turn.add_hline(y=80, line_dash="dash", line_color="green")
        fig_turn.add_hline(y=50, line_dash="dash", line_color="red")
        fig_turn.update_layout(height=350, title="% ecoule (vendu / commande)",
                               yaxis_title="%", xaxis_title="")
        st.plotly_chart(fig_turn, use_container_width=True)

    with col_b:
        # Stock restant par produit
        fig_remain = go.Figure()
        fig_remain.add_trace(go.Bar(
            x=margins["product"], y=margins["qty_remaining"],
            marker_color="#e74c3c",
            text=margins["qty_remaining"].astype(int).astype(str),
            textposition="outside",
            name="Restant",
        ))
        fig_remain.add_trace(go.Bar(
            x=margins["product"], y=margins["qty_sold"],
            marker_color="#2ecc71",
            text=margins["qty_sold"].astype(int).astype(str),
            textposition="outside",
            name="Vendu",
        ))
        fig_remain.update_layout(
            barmode="stack", height=350,
            title="Commande vs Vendu vs Restant",
            yaxis_title="Unites",
        )
        st.plotly_chart(fig_remain, use_container_width=True)

# ============================================================
# EVOLUTION STOCK PAR STEP
# ============================================================
st.subheader("Evolution stock total step-by-step")

stock_timeline = compute_stock_timeline(data)
if len(stock_timeline) > 0:
    fig_st = go.Figure()
    fig_st.add_trace(go.Scatter(
        x=stock_timeline["elapsed"], y=stock_timeline["total"],
        name="Total", fill="tozeroy", line=dict(color="#9b59b6"),
    ))
    fig_st.add_trace(go.Scatter(
        x=stock_timeline["elapsed"], y=stock_timeline["central"],
        name="Central", line=dict(color="#e67e22", width=2),
    ))
    fig_st.add_hline(y=4000, line_dash="dash", line_color="red",
                     annotation_text="Penalite 4000")

    # PO markers
    po_summary = compute_po_summary(data)
    if len(po_summary) > 0:
        for _, po in po_summary.iterrows():
            fig_st.add_vline(
                x=po["delivery_elapsed"], line_dash="dot", line_color="green",
                annotation_text=f"+{int(po['total_qty'])}u",
            )

    fig_st.update_layout(
        height=400, xaxis_title="Step", yaxis_title="Unites",
        legend=dict(orientation="h"),
        hovermode="x unified",
    )
    st.plotly_chart(fig_st, use_container_width=True)

# ============================================================
# HISTORIQUE POs
# ============================================================
st.subheader("Historique des commandes (Purchase Orders)")

po_summary = compute_po_summary(data)
if len(po_summary) > 0:
    st.dataframe(
        po_summary[[
            "po_number", "delivery", "total_qty", "goods_cost", "po_fee", "total_cost", "products"
        ]].rename(columns={
            "po_number": "PO", "delivery": "Livraison", "total_qty": "Quantite",
            "goods_cost": "Cout marchandise", "po_fee": "Fee PO",
            "total_cost": "Cout total", "products": "Detail",
        }),
        use_container_width=True, hide_index=True,
    )

    total_spent = po_summary["total_cost"].sum()
    st.info(f"**Total depense en POs : {total_spent:,.0f} EUR**")

# ============================================================
# RECOMMANDATION COMMANDE
# ============================================================
st.subheader("Recommandation prochaine commande")

if len(margins) > 0:
    st.markdown("Base sur le taux d'ecoulement et le stock restant :")
    reco_rows = []
    for _, row in margins.iterrows():
        prod = row["product"]
        turn = row["turnover_pct"]
        remain = row["qty_remaining"]

        if turn > 75 and remain < 200:
            priority = "HAUTE"
            qty = 800
            reason = f"Ecoule a {turn:.0f}%, stock bas ({remain})"
        elif turn > 50 and remain < 400:
            priority = "MOYENNE"
            qty = 400
            reason = f"Ecoulement moyen ({turn:.0f}%), renforcer"
        elif turn < 40:
            priority = "BASSE"
            qty = 0
            reason = f"Ecoulement faible ({turn:.0f}%), stock abondant ({remain})"
        else:
            priority = "BASSE"
            qty = 200
            reason = f"Stock suffisant ({remain})"

        reco_rows.append({
            "Produit": prod, "Priorite": priority,
            "Qte recommandee": qty, "Raison": reason,
        })

    df_reco = pd.DataFrame(reco_rows)
    st.dataframe(df_reco, use_container_width=True, hide_index=True)
    total_reco = sum(r["Qte recommandee"] for r in reco_rows)
    est_cost = sum(
        r["Qte recommandee"] * data.purchase_costs.get(r["Produit"], 50)
        for r in reco_rows
    )
    st.info(f"**Total recommande : {total_reco:,} unites — cout estime : {est_cost:,.0f} EUR + 1 000 fee**")
