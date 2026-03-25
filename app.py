"""ERP_Sim_Agents — Point d'entree Streamlit."""

import os
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st

load_dotenv(Path(__file__).parent / ".env")

st.set_page_config(
    page_title="ERPsim Agents",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Init: charger toutes les donnees SAP ---
if "game_data" not in st.session_state:
    from src.data_loader import SAPDataLoader

    sap_url = os.getenv("SAP_BASE_URL", "")
    if sap_url:
        loader = SAPDataLoader()
        if loader.connected:
            st.session_state.game_data = loader.load_all()
            st.session_state.connected = True
        else:
            st.session_state.game_data = None
            st.session_state.connected = False
    else:
        st.session_state.game_data = None
        st.session_state.connected = False

# --- Sidebar ---
st.sidebar.title("ERPsim Agents")
st.sidebar.markdown("---")

data = st.session_state.get("game_data")
if data:
    st.sidebar.success("Connecte a SAP")
    st.sidebar.metric("Round actuel", data.current_round)
    st.sidebar.metric("Step max", data.max_elapsed_step)
    if len(data.financials) > 0:
        last_fin = data.financials.iloc[-1]
        st.sidebar.metric("Cash", f"{last_fin['cash']:,.0f} EUR")
        st.sidebar.metric("Credit", last_fin["credit"])
        st.sidebar.metric("Valorisation", f"{last_fin['valuation']:,.0f}")
    if st.sidebar.button("Rafraichir les donnees"):
        del st.session_state["game_data"]
        st.rerun()
else:
    st.sidebar.error("Non connecte a SAP")
    st.sidebar.caption("Verifiez .env (SAP_BASE_URL, SAP_USERNAME, SAP_PASSWORD)")

# --- Page d'accueil ---
st.title("ERPsim Decision Support System")

if data:
    from src.analytics import compute_real_margins

    st.markdown("### Vue rapide")
    col1, col2, col3, col4, col5 = st.columns(5)
    last = data.financials.iloc[-1]
    with col1:
        st.metric("Cash", f"{last['cash']:,.0f}", f"Loan: {last['loan']:,.0f}" if last["loan"] < 0 else None)
    with col2:
        st.metric("Profit", f"{last['profit']:,.0f}")
    with col3:
        st.metric("Valorisation", f"{last['valuation']:,.0f}")
    with col4:
        st.metric("Credit", last["credit"])
    with col5:
        st.metric("Round", f"R{last['round']:02.0f} S{last['step']:02.0f}")

    st.markdown("""
    **Pages disponibles :**
    - **Superviseur** — Timeline complete, KPIs, alertes, evolution cash/stock/profit
    - **Pricing** — Marges reelles, prix vs marche, recommandations
    - **Approvisionnement** — Heatmap stock, taux ecoulement, historique POs
    - **Distribution** — Ventes par region, allocations, preferences
    """)
else:
    st.warning("Aucune connexion SAP. Configurez votre fichier `.env`.")
