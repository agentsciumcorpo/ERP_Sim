"""Vue Distribution — Transferts vers les regions pour Sophia."""

import streamlit as st
import pandas as pd
from src.config import PRODUCTS, REGIONS

st.set_page_config(page_title="Distribution", page_icon="🚛", layout="wide")
st.title("Distribution — Transferts regionaux")

state = st.session_state.get("game_state")
if not state or not state.cycle_results:
    st.warning("Aucun cycle execute. Le Superviseur doit cliquer **Actualiser**.")
    st.stop()

last = state.cycle_results[-1]
metrics = last.metrics

# --- Stock regionaux actuels ---
st.subheader("Stocks regionaux actuels")

stock_data = []
for region in REGIONS:
    row = {"Region": region}
    for product in PRODUCTS:
        qty = metrics.regional_stock.get(region, {}).get(product, 0)
        row[product] = qty
    stock_data.append(row)

df_stock = pd.DataFrame(stock_data)
st.dataframe(df_stock, use_container_width=True, hide_index=True)

if last.is_manual_mode:
    st.warning("Mode manuel — Gerez la distribution manuellement selon les preferences regionales.")
    st.markdown("""
    **Rappel preferences:**
    - **Nord:** Lait, Glace
    - **Sud:** Yaourt, Glace
    - **Ouest:** Fromage
    """)
    st.stop()

# --- Transferts recommandes ---
st.subheader("Transferts recommandes")

if last.stock and last.stock.allocations:
    # Veto finance ?
    vetoed = last.finance_veto and not last.finance_veto.approved
    if vetoed:
        st.error("VETO Finance — Certains transferts peuvent etre bloques")

    # Tableau des transferts
    transfer_rows = []
    for alloc in last.stock.allocations:
        transfer_rows.append({
            "Region": alloc.region,
            "Produit": alloc.product,
            "Quantite": f"+{alloc.quantity}",
            "Raison": alloc.reasoning,
        })

    df_transfers = pd.DataFrame(transfer_rows)
    st.dataframe(df_transfers, use_container_width=True, hide_index=True)

    # Resume par region
    st.subheader("Resume par region")
    for region in REGIONS:
        region_allocs = [a for a in last.stock.allocations if a.region == region]
        if region_allocs:
            total = sum(a.quantity for a in region_allocs)
            items = ", ".join(f"+{a.quantity} {a.product}" for a in region_allocs)
            st.markdown(f"**{region}:** {items} (total: +{total})")
        else:
            st.markdown(f"**{region}:** Aucun transfert")
else:
    st.info("Pas de transfert recommande pour ce cycle.")
