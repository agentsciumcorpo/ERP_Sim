"""Vue Approvisionnement — Stock central et commandes."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Approvisionnement", page_icon="📦", layout="wide")
st.title("Approvisionnement — Stock & Commandes")

state = st.session_state.get("game_state")
if not state or not state.cycle_results:
    st.warning("Aucun cycle execute. Le Superviseur doit cliquer **Actualiser**.")
    st.stop()

last = state.cycle_results[-1]
metrics = last.metrics

# --- Stock central ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Stock central total", f"{metrics.total_central_stock:,}")
with col2:
    st.metric("Capacite max", "4 000")
with col3:
    pct = metrics.total_central_stock / 4000 * 100
    st.metric("Remplissage", f"{pct:.0f}%")

# Alerte stock
if last.guardrails and last.guardrails.stock_alert:
    if "CRITIQUE" in last.guardrails.stock_alert:
        st.error(last.guardrails.stock_alert)
    else:
        st.warning(last.guardrails.stock_alert)

# Barre visuelle
st.progress(min(1.0, metrics.total_central_stock / 4000))

if last.is_manual_mode:
    st.warning("Mode manuel — Gerez le stock manuellement.")
    st.stop()

# --- Recommandation de commande ---
st.subheader("Recommandation de commande")

if last.stock:
    # Veto finance ?
    vetoed = last.finance_veto and not last.finance_veto.approved
    if vetoed:
        st.error("VETO Finance — Commande bloquee")
        for v in (last.finance_veto.vetoes if last.finance_veto else []):
            st.markdown(f"- {v}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("Quantite a commander", f"{last.stock.order_quantity:,}" + (" ❌" if vetoed else " ✅"))
    with col_b:
        st.markdown(f"**Raison:** {last.stock.order_reasoning}")

    # Alertes agent stock
    if last.stock.alerts:
        for alert in last.stock.alerts:
            st.warning(alert)
else:
    st.info("Pas de recommandation de commande pour ce cycle.")

# --- Cash ---
st.subheader("Etat financier")
fin = metrics.cash_projection
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    st.metric("Cash actuel", f"{fin.current_cash:,.0f} EUR")
with col_f2:
    st.metric("Projection +1 cycle", f"{fin.projected_next_cycle:,.0f} EUR")
with col_f3:
    trend_icon = {"up": "📈", "down": "📉", "stable": "➡️"}.get(fin.trend, "")
    st.metric("Tendance", f"{fin.trend} {trend_icon}")
