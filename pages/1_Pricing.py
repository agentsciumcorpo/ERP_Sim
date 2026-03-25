"""Vue Pricing — Marges reelles, prix vs marche, evolution volumes."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Pricing", page_icon="💰", layout="wide")
st.title("Pricing — Analyse des marges & prix")

data = st.session_state.get("game_data")
if not data:
    st.warning("Aucune donnee. Retournez a l'accueil.")
    st.stop()

from src.analytics import compute_real_margins, compute_market_comparison, compute_volume_evolution

# ============================================================
# MARGES REELLES
# ============================================================
st.subheader("Marges reelles (cout achat PO)")

margins = compute_real_margins(data)

# Metrics header : top 3 contributeurs
top3 = margins.head(3)
cols = st.columns(3)
for i, (_, row) in enumerate(top3.iterrows()):
    with cols[i]:
        st.metric(
            f"#{i+1} {row['product']}",
            f"{row['contribution']:,.0f} EUR",
            f"Marge {row['margin_pct']}%",
        )

# Tableau complet
st.dataframe(
    margins[[
        "product", "price", "cost", "margin", "margin_pct",
        "qty_sold", "revenue", "qty_ordered", "qty_remaining", "turnover_pct", "contribution"
    ]].rename(columns={
        "product": "Produit", "price": "Prix vente", "cost": "Cout achat",
        "margin": "Marge/u", "margin_pct": "Marge %",
        "qty_sold": "Vendu", "revenue": "Revenu",
        "qty_ordered": "Commande", "qty_remaining": "Restant",
        "turnover_pct": "Ecoulement %", "contribution": "Contribution",
    }),
    use_container_width=True, hide_index=True,
)

# Graphe contribution par produit
fig_contrib = px.bar(
    margins, x="product", y="contribution",
    color="margin_pct", color_continuous_scale="RdYlGn",
    labels={"product": "Produit", "contribution": "Contribution EUR", "margin_pct": "Marge %"},
    title="Contribution par produit (marge x volume)",
)
st.plotly_chart(fig_contrib, use_container_width=True)

# Graphe ecoulement
fig_turn = px.bar(
    margins, x="product", y="turnover_pct",
    color="turnover_pct", color_continuous_scale="RdYlGn",
    labels={"product": "Produit", "turnover_pct": "% Ecoule"},
    title="Taux d'ecoulement par produit (% vendu / commande)",
)
fig_turn.add_hline(y=80, line_dash="dash", line_color="green", annotation_text="Bon (80%)")
fig_turn.add_hline(y=50, line_dash="dash", line_color="red", annotation_text="Probleme (50%)")
st.plotly_chart(fig_turn, use_container_width=True)

# ============================================================
# PRIX VS MARCHE
# ============================================================
st.subheader("Nos prix vs le marche")

market = compute_market_comparison(data)
if len(market) > 0:
    col_a, col_b = st.columns(2)

    with col_a:
        st.dataframe(
            market[[
                "product", "our_price", "market_price", "price_vs_market_pct",
                "our_qty", "market_qty", "market_share_pct",
            ]].rename(columns={
                "product": "Produit", "our_price": "Notre prix",
                "market_price": "Prix marche", "price_vs_market_pct": "Ecart %",
                "our_qty": "Nos ventes", "market_qty": "Ventes marche",
                "market_share_pct": "Part de marche %",
            }),
            use_container_width=True, hide_index=True,
        )

    with col_b:
        # Graphe prix comparison
        fig_price = go.Figure()
        fig_price.add_trace(go.Bar(
            x=market["product"], y=market["our_price"],
            name="Notre prix", marker_color="#3498db",
        ))
        fig_price.add_trace(go.Bar(
            x=market["product"], y=market["market_price"],
            name="Prix marche", marker_color="#95a5a6",
        ))
        fig_price.update_layout(
            barmode="group", height=350,
            title="Notre prix vs prix moyen marche",
        )
        st.plotly_chart(fig_price, use_container_width=True)

    # Part de marche
    fig_share = px.bar(
        market, x="product", y="market_share_pct",
        color="market_share_pct", color_continuous_scale="Blues",
        labels={"product": "Produit", "market_share_pct": "Part de marche %"},
        title="Part de marche par produit",
    )
    fig_share.add_hline(y=20, line_dash="dash", line_color="gray",
                        annotation_text="5 equipes = 20% si egal")
    st.plotly_chart(fig_share, use_container_width=True)
else:
    st.info("Donnees de marche non disponibles.")

# ============================================================
# EVOLUTION VOLUMES PAR ROUND
# ============================================================
st.subheader("Evolution des volumes par round")

vol = compute_volume_evolution(data)
if len(vol) > 0:
    fig_vol = px.bar(
        vol, x="round", y="qty", color="product",
        barmode="group",
        labels={"round": "Round", "qty": "Quantite vendue", "product": "Produit"},
        title="Volumes par produit et par round",
    )
    st.plotly_chart(fig_vol, use_container_width=True)

    # Evolution revenus
    fig_rev = px.bar(
        vol, x="round", y="revenue", color="product",
        barmode="stack",
        labels={"round": "Round", "revenue": "Revenu EUR", "product": "Produit"},
        title="Revenu par produit et par round",
    )
    st.plotly_chart(fig_rev, use_container_width=True)
