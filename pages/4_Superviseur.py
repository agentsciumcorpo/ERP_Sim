"""Vue Superviseur — Controle, Actualiser, KPIs essentiels."""

import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Superviseur", page_icon="🎯", layout="wide")
st.title("Superviseur")

# ============================================================
# BOUTON ACTUALISER
# ============================================================

col_btn1, col_btn2, _ = st.columns([1, 1, 3])
with col_btn1:
    refresh = st.button("Actualiser", type="primary", use_container_width=True)
with col_btn2:
    if st.button("Rafraichir donnees SAP", use_container_width=True):
        for key in ["game_data", "agent_results"]:
            st.session_state.pop(key, None)
        st.rerun()

# --- Charger les donnees et lancer les agents ---
if refresh:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    from src.data_loader import SAPDataLoader
    from src.analytics import compute_real_margins, compute_stock_heatmap, compute_sales_by_region
    from src.agents_v2 import run_all_agents

    with st.spinner("Chargement SAP + Agents IA..."):
        loader = SAPDataLoader()
        if not loader.connected:
            st.error("Connexion SAP echouee.")
            st.stop()

        data = loader.load_all()
        st.session_state.game_data = data

        # Calculer les metriques
        margins = compute_real_margins(data)
        stock_heatmap = compute_stock_heatmap(data)
        sales_region = compute_sales_by_region(data)

        # Lancer les agents IA
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        st.session_state.agent_results = run_all_agents(data, margins, stock_heatmap, sales_region, api_key)

    st.rerun()


# ============================================================
# AFFICHAGE
# ============================================================

data = st.session_state.get("game_data")
if not data:
    st.info("Cliquez **Actualiser** pour charger les donnees et lancer les agents.")
    st.stop()

results = st.session_state.get("agent_results", {})
from src.analytics import compute_stock_timeline, compute_po_summary

# --- KPIs ---
last = data.financials.iloc[-1]
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Cash", f"{last['cash']:,.0f}")
with c2:
    loan_str = f"-{abs(last['loan']):,.0f}" if last['loan'] < 0 else "0"
    st.metric("Loan", loan_str)
with c3:
    st.metric("Profit", f"{last['profit']:,.0f}")
with c4:
    st.metric("Valorisation", f"{last['valuation']:,.0f}")
with c5:
    st.metric("Credit", last["credit"])

# --- Alertes agents ---
finance = results.get("finance")
if finance:
    if finance.get("vetoes"):
        for v in finance["vetoes"]:
            st.error(f"VETO Finance : {v}")
    if finance.get("cash_status") == "critique":
        st.error(f"Cash critique — {finance.get('assessment', '')}")
    elif finance.get("cash_status") == "attention":
        st.warning(f"Cash attention — {finance.get('assessment', '')}")
    else:
        st.success(f"Finances saines — {finance.get('assessment', '')}")

# --- Graphe 1 : Cash + Profit ---
st.subheader("Cash & Profit")

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=data.financials["elapsed"], y=data.financials["cash"],
    name="Cash", line=dict(color="#2ecc71", width=2),
))
fig.add_trace(go.Scatter(
    x=data.financials["elapsed"], y=data.financials["profit"],
    name="Profit", line=dict(color="#3498db", width=2),
))
fig.add_hline(y=50000, line_dash="dash", line_color="red", opacity=0.5)
fig.add_hline(y=0, line_color="red", opacity=0.3)

po_summary = compute_po_summary(data)
if len(po_summary) > 0:
    for _, po in po_summary.iterrows():
        fig.add_vline(x=po["delivery_elapsed"], line_dash="dot", line_color="orange")

round_starts = data.financials.drop_duplicates("round")[["elapsed", "round"]]
fig.update_xaxes(
    tickvals=round_starts["elapsed"].tolist(),
    ticktext=[f"R{int(r)}" for r in round_starts["round"].tolist()],
)
fig.update_layout(height=350, hovermode="x unified",
                  legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig, use_container_width=True)

# --- Graphe 2 : Stock total ---
st.subheader("Stock total")

stock_tl = compute_stock_timeline(data)
if len(stock_tl) > 0:
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=stock_tl["elapsed"], y=stock_tl["total"],
        name="Total", fill="tozeroy", line=dict(color="#9b59b6"),
    ))
    fig2.add_hline(y=4000, line_dash="dash", line_color="red")
    fig2.update_xaxes(
        tickvals=round_starts["elapsed"].tolist(),
        ticktext=[f"R{int(r)}" for r in round_starts["round"].tolist()],
    )
    fig2.update_layout(height=300, hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)
