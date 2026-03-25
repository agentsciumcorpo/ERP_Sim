"""Vue Distribution — Ventes par region, stock regional, allocations."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Distribution", page_icon="🚛", layout="wide")
st.title("Distribution — Analyse regionale")

data = st.session_state.get("game_data")
if not data:
    st.warning("Aucune donnee. Retournez a l'accueil.")
    st.stop()

from src.analytics import compute_sales_by_region, compute_stock_heatmap
from src.data_loader import PRODUCTS, REGIONS

# ============================================================
# VENTES PAR REGION
# ============================================================
st.subheader("Ventes par region & produit")

sales_region = compute_sales_by_region(data)
if len(sales_region) > 0:
    # Pivot pour afficher un tableau region x produit
    pivot_qty = sales_region.pivot_table(
        index="product", columns="region", values="qty", fill_value=0, aggfunc="sum"
    )
    pivot_qty = pivot_qty.reindex(columns=[r for r in REGIONS if r in pivot_qty.columns], fill_value=0)
    pivot_qty["Total"] = pivot_qty.sum(axis=1)
    pivot_qty = pivot_qty.sort_values("Total", ascending=False)

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Quantites vendues**")
        st.dataframe(pivot_qty.astype(int), use_container_width=True)

    with col_b:
        pivot_rev = sales_region.pivot_table(
            index="product", columns="region", values="revenue", fill_value=0, aggfunc="sum"
        )
        pivot_rev = pivot_rev.reindex(columns=[r for r in REGIONS if r in pivot_rev.columns], fill_value=0)
        pivot_rev["Total"] = pivot_rev.sum(axis=1)
        pivot_rev = pivot_rev.sort_values("Total", ascending=False)
        st.markdown("**Revenu EUR**")
        st.dataframe(pivot_rev.astype(int), use_container_width=True)

    # Heatmap ventes
    fig_sales_heat = go.Figure(data=go.Heatmap(
        z=pivot_qty.drop(columns="Total").values,
        x=[r for r in REGIONS if r in pivot_qty.columns],
        y=pivot_qty.index.tolist(),
        text=pivot_qty.drop(columns="Total").values.astype(int).astype(str),
        texttemplate="%{text}",
        colorscale="Greens",
        showscale=True,
    ))
    fig_sales_heat.update_layout(
        height=350, title="Heatmap ventes (quantite par region & produit)",
    )
    st.plotly_chart(fig_sales_heat, use_container_width=True)

    # Bar chart par region
    fig_region = px.bar(
        sales_region, x="region", y="revenue", color="product",
        barmode="stack",
        labels={"region": "Region", "revenue": "Revenu EUR", "product": "Produit"},
        title="Revenu par region",
    )
    st.plotly_chart(fig_region, use_container_width=True)

# ============================================================
# STOCK REGIONAL ACTUEL
# ============================================================
st.subheader("Stock regional actuel")

heatmap = compute_stock_heatmap(data)
if len(heatmap) > 0:
    # Retirer Central et Total pour la vue regionale
    regional_cols = [c for c in heatmap.columns if c not in ["Central", "Total"]]
    heatmap_regional = heatmap[regional_cols].copy()
    heatmap_regional["Total regions"] = heatmap_regional.sum(axis=1)

    fig_reg_heat = go.Figure(data=go.Heatmap(
        z=heatmap_regional.drop(columns="Total regions").values,
        x=regional_cols,
        y=heatmap_regional.index.tolist(),
        text=heatmap_regional.drop(columns="Total regions").values.astype(int).astype(str),
        texttemplate="%{text}",
        colorscale=[
            [0, "#e74c3c"],
            [0.03, "#e67e22"],
            [0.1, "#f1c40f"],
            [0.3, "#2ecc71"],
            [1.0, "#27ae60"],
        ],
        showscale=True,
    ))
    fig_reg_heat.update_layout(
        height=350, title="Stock par region (rouge = rupture / critique)",
    )
    st.plotly_chart(fig_reg_heat, use_container_width=True)

    st.dataframe(heatmap_regional.astype(int), use_container_width=True)

# ============================================================
# PREFERENCES REGIONALES vs REALITE
# ============================================================
st.subheader("Preferences regionales vs ventes reelles")

from src.config import REGIONAL_PREFERENCES

if len(sales_region) > 0:
    pref_rows = []
    for region in REGIONS:
        for prod in PRODUCTS:
            pref = REGIONAL_PREFERENCES.get(region, {}).get(prod, 1.0)
            actual_sales = sales_region[
                (sales_region["region"] == region) & (sales_region["product"] == prod)
            ]
            actual_qty = int(actual_sales["qty"].sum()) if len(actual_sales) > 0 else 0

            # Stock actuel dans cette region
            current = data.current_stock[
                (data.current_stock["location"] == region) &
                (data.current_stock["product"] == prod)
            ] if len(data.current_stock) > 0 else pd.DataFrame()
            stock = int(current["stock"].sum()) if len(current) > 0 else 0

            status = ""
            if stock == 0 and actual_qty > 50:
                status = "RUPTURE - forte demande!"
            elif stock < 50 and pref >= 1.5:
                status = "Stock critique"
            elif stock > 300 and actual_qty < 100:
                status = "Surstock"

            pref_rows.append({
                "Region": region, "Produit": prod,
                "Preference": "Forte" if pref >= 1.5 else "Standard",
                "Ventes": actual_qty, "Stock": stock, "Alerte": status,
            })

    df_pref = pd.DataFrame(pref_rows)

    # Filtrer par region
    for region in REGIONS:
        with st.expander(f"Region {region}", expanded=True):
            region_data = df_pref[df_pref["Region"] == region].drop(columns="Region")
            st.dataframe(region_data, use_container_width=True, hide_index=True)

# ============================================================
# TRANSFERTS RECOMMANDES
# ============================================================
st.subheader("Transferts recommandes")

if len(sales_region) > 0 and len(data.current_stock) > 0:
    transfer_rows = []
    for region in REGIONS:
        for prod in PRODUCTS:
            pref = REGIONAL_PREFERENCES.get(region, {}).get(prod, 1.0)

            # Stock regional
            reg_stock = data.current_stock[
                (data.current_stock["location"] == region) &
                (data.current_stock["product"] == prod)
            ]
            stock = int(reg_stock["stock"].sum()) if len(reg_stock) > 0 else 0

            # Ventes moyennes par round
            prod_region_sales = data.sales[
                (data.sales["region"] == region) & (data.sales["product"] == prod)
            ] if len(data.sales) > 0 else pd.DataFrame()

            if len(prod_region_sales) > 0:
                sales_per_round = prod_region_sales.groupby("round")["qty"].sum()
                avg_sales = sales_per_round.mean()
            else:
                avg_sales = 0

            # Stock central disponible
            central_stock = data.current_stock[
                (data.current_stock["location"] == "Central") &
                (data.current_stock["product"] == prod)
            ]
            available = int(central_stock["stock"].sum()) if len(central_stock) > 0 else 0

            # Recommandation
            if stock < avg_sales * 0.5 and available > 0 and avg_sales > 20:
                qty = min(int(avg_sales), available)
                transfer_rows.append({
                    "De": "Central", "Vers": region, "Produit": prod,
                    "Quantite": qty,
                    "Raison": f"Stock {stock} < 50% ventes moy ({avg_sales:.0f}/round)",
                    "Cout": 100,
                })

    if transfer_rows:
        df_transfers = pd.DataFrame(transfer_rows)
        st.dataframe(df_transfers, use_container_width=True, hide_index=True)
        total_transfer = sum(t["Quantite"] for t in transfer_rows)
        total_cost = len(transfer_rows) * 100
        st.info(f"**{len(transfer_rows)} transferts recommandes — {total_transfer:,} unites — cout: {total_cost:,} EUR**")
    else:
        st.success("Aucun transfert urgent necessaire.")
