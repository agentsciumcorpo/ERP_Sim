"""ERP_Sim_Agents — Point d'entree Streamlit."""

import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

st.set_page_config(
    page_title="ERPsim Agents",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Init session state ---
if "game_state" not in st.session_state:
    from src.odata_client import MockODataClient
    from src.orchestrator import GameState

    client = MockODataClient()
    api_key = os.getenv("OPENROUTER_API_KEY", "")

    st.session_state.game_state = GameState(
        client=client,
        use_ai=bool(api_key),
        api_key=api_key,
    )
    st.session_state.last_cycle = None
    st.session_state.game_over = False

# --- Sidebar ---
st.sidebar.title("ERPsim Agents")
st.sidebar.markdown("---")

state = st.session_state.game_state
if state.cycle_results:
    last = state.cycle_results[-1]
    st.sidebar.metric("Round", last.round_number)
    st.sidebar.metric("Phase", last.metrics.game_phase.phase.capitalize())
    if last.metrics.cash_projection:
        st.sidebar.metric("Cash", f"{last.metrics.cash_projection.current_cash:,.0f} EUR")
    st.sidebar.metric("Cycles joues", len(state.cycle_results))
else:
    st.sidebar.info("Cliquez sur Actualiser dans la vue Superviseur pour demarrer")

st.sidebar.markdown("---")
mode = "IA" if state.use_ai else "Calculs seuls"
st.sidebar.caption(f"Mode: {mode} | Modele: {state.api_key[:8]}..." if state.api_key else f"Mode: {mode}")

# --- Page d'accueil ---
st.title("ERPsim Decision Support System")
st.markdown("""
Bienvenue dans le systeme d'aide a la decision ERPsim.

**Naviguez vers votre vue de role via le menu lateral :**
- **Pricing** — Recommandations de prix par produit
- **Approvisionnement** — Stock central et commandes
- **Distribution** — Transferts vers les regions
- **Superviseur** — Controle global, Actualiser, Fin de partie
""")

if not state.cycle_results:
    st.info("En attente du premier cycle. Le Superviseur doit cliquer **Actualiser** pour demarrer.")
