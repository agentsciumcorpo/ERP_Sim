"""Vue Pricing — Recommandations de prix pour Karim."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Pricing", page_icon="💰", layout="wide")
st.title("Pricing — Recommandations de prix")

state = st.session_state.get("game_state")
if not state or not state.cycle_results:
    st.warning("Aucun cycle execute. Le Superviseur doit cliquer **Actualiser**.")
    st.stop()

last = state.cycle_results[-1]
metrics = last.metrics

# --- Phase et contexte ---
phase = metrics.game_phase
st.info(f"**Phase:** {phase.phase.capitalize()} — {phase.description}")

if last.is_manual_mode:
    st.warning("Mode manuel — Pas de recommandation IA pour ce round. Decidez manuellement.")
    st.stop()

# --- Tableau des recommandations ---
if last.pricing:
    st.subheader("Recommandations de prix")

    rows = []
    for rec in last.pricing.recommendations:
        # Verifier si garde-fou a ajuste le prix
        adjusted = rec.recommended_price
        flag = ""
        if last.guardrails and rec.product in last.guardrails.price_checks:
            check = last.guardrails.price_checks[rec.product]
            if not check.allowed:
                adjusted = check.adjusted_value
                flag = " ⚠️"

        change = ((adjusted - rec.current_price) / rec.current_price * 100) if rec.current_price > 0 else 0
        rows.append({
            "Produit": rec.product,
            "Prix actuel": f"{rec.current_price:.2f}",
            "Prix recommande": f"{adjusted:.2f}{flag}",
            "Variation": f"{change:+.1f}%",
            "Confiance": rec.confidence,
            "Raisonnement": rec.reasoning,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if last.pricing.global_strategy:
        st.markdown(f"**Strategie globale:** {last.pricing.global_strategy}")

    # Alertes garde-fous
    if last.guardrails and last.guardrails.vetoes:
        st.error("**Garde-fous actifs:**")
        for v in last.guardrails.vetoes:
            st.markdown(f"- {v}")
else:
    st.info("Pas de recommandation de prix pour ce cycle.")

# --- Metriques produits ---
st.subheader("Metriques detaillees")
metric_rows = []
for m in metrics.product_metrics:
    elasticity_str = f"{m.elasticity}" if m.elasticity is not None else "—"
    metric_rows.append({
        "Produit": m.product,
        "Prix": f"{m.current_price:.2f}",
        "Quantite vendue": m.total_quantity,
        "Revenu": f"{m.total_revenue:.0f}",
        "Marge nette": f"{m.net_margin:.2f}",
        "Marge %": f"{m.margin_pct:.1f}%",
        "Elasticite": elasticity_str,
        "Contribution": f"{m.contribution:.0f}",
    })

df_metrics = pd.DataFrame(metric_rows)
st.dataframe(df_metrics, use_container_width=True, hide_index=True)
