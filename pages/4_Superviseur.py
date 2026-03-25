"""Vue Superviseur — Controle global pour Ewen."""

import streamlit as st
import pandas as pd
from src.memory import get_memory_for_download, AGENT_NAMES

st.set_page_config(page_title="Superviseur", page_icon="🎯", layout="wide")
st.title("Superviseur — Controle global")

state = st.session_state.get("game_state")
if not state:
    st.error("Erreur: game_state non initialise. Rechargez l'app.")
    st.stop()

# --- Controles ---
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

with col_btn1:
    refresh = st.button("🔄 Actualiser", type="primary", use_container_width=True)

with col_btn2:
    end_game = st.button("🏁 Fin de partie", type="secondary", use_container_width=True)

# --- Executer un cycle ---
if refresh and not st.session_state.get("game_over"):
    from src.orchestrator import run_cycle
    with st.spinner("Cycle en cours... OData → Calculs → Agents IA → Affichage"):
        result = run_cycle(state)
        st.session_state.last_cycle = result
    st.rerun()

# --- Fin de partie ---
if end_game:
    st.session_state.game_over = True
    st.success("Partie terminee ! Telechargez les fichiers ci-dessous.")

# --- Metriques globales ---
if state.cycle_results:
    last = state.cycle_results[-1]
    metrics = last.metrics

    st.subheader("Metriques globales")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Round", last.round_number)
    with col2:
        st.metric("Cash", f"{metrics.cash_projection.current_cash:,.0f} EUR")
    with col3:
        st.metric("Stock central", f"{metrics.total_central_stock:,} / 4000")
    with col4:
        st.metric("Phase", metrics.game_phase.phase.capitalize())

    # Alerte plateau
    if metrics.plateau.is_plateau:
        st.error(f"⚠️ PLATEAU DETECTE — {metrics.plateau.message}")
    else:
        st.success(metrics.plateau.message)

    # Phase info
    st.info(f"**{metrics.game_phase.description}** — {metrics.game_phase.recommendation}")

    # --- Erreurs du cycle ---
    if last.errors:
        st.warning("Erreurs dans le dernier cycle:")
        for err in last.errors:
            st.markdown(f"- `{err}`")

    # --- Journal des decisions recentes ---
    st.subheader("Journal des decisions recentes")

    if last.finance_eval:
        with st.expander(f"Agent Finance (eval) — Status: {last.finance_eval.cash_status}", expanded=False):
            st.markdown(last.finance_eval.credit_assessment)
            if last.finance_eval.recommendations:
                for r in last.finance_eval.recommendations:
                    st.markdown(f"- {r}")

    if last.pricing:
        with st.expander("Agent Prix — Recommandations", expanded=True):
            st.markdown(f"**Strategie:** {last.pricing.global_strategy}")
            for rec in last.pricing.recommendations:
                arrow = "↑" if rec.recommended_price > rec.current_price else "↓" if rec.recommended_price < rec.current_price else "="
                st.markdown(
                    f"- **{rec.product}** {rec.current_price:.2f} → {rec.recommended_price:.2f} {arrow} "
                    f"({rec.confidence}) — {rec.reasoning}"
                )

    if last.stock:
        with st.expander("Agent Stock — Allocations", expanded=False):
            st.markdown(f"**Commande:** {last.stock.order_quantity} — {last.stock.order_reasoning}")
            if last.stock.allocations:
                for a in last.stock.allocations:
                    st.markdown(f"- {a.region}/{a.product}: +{a.quantity} — {a.reasoning}")

    if last.finance_veto:
        status_color = "🟢" if last.finance_veto.approved else "🔴"
        with st.expander(f"Agent Finance (veto) — {status_color} {'Approuve' if last.finance_veto.approved else 'VETO'}", expanded=not last.finance_veto.approved):
            st.markdown(last.finance_veto.credit_assessment)
            if last.finance_veto.vetoes:
                st.error("Vetoes:")
                for v in last.finance_veto.vetoes:
                    st.markdown(f"- {v}")

    # --- Garde-fous ---
    if last.guardrails and last.guardrails.vetoes:
        st.subheader("Garde-fous actifs")
        for v in last.guardrails.vetoes:
            st.error(v)

    # --- Historique rapide ---
    if len(state.cycle_results) > 1:
        st.subheader("Evolution du cash")
        cash_history = []
        for cr in state.cycle_results:
            if cr.metrics.cash_projection:
                cash_history.append({
                    "Round": cr.round_number,
                    "Cash": cr.metrics.cash_projection.current_cash,
                })
        if cash_history:
            df_cash = pd.DataFrame(cash_history)
            st.line_chart(df_cash, x="Round", y="Cash")

else:
    st.info("Cliquez **Actualiser** pour lancer le premier cycle.")

# --- Telechargements ---
st.subheader("Fichiers memoire")

for agent in AGENT_NAMES:
    content = get_memory_for_download(state.memories, agent)
    st.download_button(
        label=f"📥 memory_agent_{agent}.md",
        data=content,
        file_name=f"memory_agent_{agent}.md",
        mime="text/markdown",
        key=f"dl_{agent}",
    )

# --- Rapport PDF ---
if st.session_state.get("game_over"):
    st.subheader("Rapport PDF")
    try:
        from src.pdf_report import generate_report
        pdf_bytes = generate_report(state)
        st.download_button(
            label="📥 Telecharger le rapport PDF",
            data=pdf_bytes,
            file_name="erpsim_rapport.pdf",
            mime="application/pdf",
            key="dl_pdf",
        )
    except Exception as e:
        st.error(f"Erreur generation PDF: {e}")
