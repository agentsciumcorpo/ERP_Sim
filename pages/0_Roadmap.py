"""Roadmap de depart — Plan d'action complet pour la competition."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.title("Roadmap — Plan de bataille")

# ============================================================
# PRIX DE DEPART
# ============================================================
st.header("1. Prix de depart")

st.markdown("""
**Strategie prix Round 1 : NE PAS BOUGER.**
On garde les prix par defaut de SAP. On n'a aucune donnee d'elasticite, et si on monte trop les concurrents prennent nos clients.
Ajuster seulement a partir du **Round 2** avec des variations de **2-3% max**.
""")

default_prices = {
    "Milk": 24.52, "Cream": 77.60, "Yoghurt": 28.52,
    "Cheese": 89.15, "Butter": 65.79, "Ice Cream": 47.55,
}

cols = st.columns(6)
for i, (prod, price) in enumerate(default_prices.items()):
    with cols[i]:
        st.metric(prod, f"{price:.2f} EUR")

st.info("Si a la fin du Round 1 personne n'a bouge ses prix → on monte Milk et Yoghurt de +2% au Round 2.")

# ============================================================
# COMMANDE INITIALE
# ============================================================
st.header("2. Commande initiale — Step 1")

st.markdown("**4 400 unites — cout ~159K EUR — cash restant ~91K**")

order = pd.DataFrame([
    {"Produit": "Milk", "Quantite": 1800, "Cout": 41_310, "Priorite": "HAUTE", "Raison": "53% des 1eres ventes, volume roi"},
    {"Produit": "Yoghurt", "Quantite": 1000, "Cout": 25_850, "Priorite": "HAUTE", "Raison": "Ecoulement 88%, 2e produit"},
    {"Produit": "Ice Cream", "Quantite": 700, "Cout": 30_205, "Priorite": "HAUTE", "Raison": "Explose en fin de round"},
    {"Produit": "Butter", "Quantite": 500, "Cout": 29_940, "Priorite": "MOYENNE", "Raison": "Bon profit/unite, Nord+Sud"},
    {"Produit": "Cheese", "Quantite": 200, "Cout": 16_536, "Priorite": "BASSE", "Raison": "Se vend qu'a l'Ouest"},
    {"Produit": "Cream", "Quantite": 200, "Cout": 14_414, "Priorite": "BASSE", "Raison": "Se vend qu'au Sud"},
])
order["Cout"] = order["Cout"].apply(lambda x: f"{x:,.0f}")

st.dataframe(order, use_container_width=True, hide_index=True)

total_cost = 41_310 + 25_850 + 30_205 + 29_940 + 16_536 + 14_414 + 1_000
st.markdown(f"**Cout total : {total_cost:,.0f} EUR** (marchandise + 1 000 fee PO)")
st.markdown(f"**Cash apres paiement (Step 8) : ~{250_000 - total_cost:,.0f} EUR** → Pas de cash negatif.")

# ============================================================
# DISTRIBUTION — DES QUE LA PO ARRIVE (Step 3)
# ============================================================
st.header("3. Distribution — Step 3 (des que la PO arrive)")

st.warning("Transferer IMMEDIATEMENT. Chaque step de retard = ventes perdues + penalite stock si central > 4000.")

tab_nord, tab_sud, tab_ouest = st.tabs(["Nord", "Sud", "Ouest"])

with tab_nord:
    st.subheader("Nord — 1 110 unites")
    st.markdown("**Region #1 en volume.** Dominante sur Milk, Ice Cream.")
    nord = pd.DataFrame([
        {"Produit": "Milk", "Quantite": 500, "Raison": "43% des ventes Milk sont au Nord"},
        {"Produit": "Yoghurt", "Quantite": 250, "Raison": "36% des ventes, forte demande"},
        {"Produit": "Ice Cream", "Quantite": 200, "Raison": "36% des ventes, preference Nord"},
        {"Produit": "Butter", "Quantite": 120, "Raison": "45% des ventes Butter"},
        {"Produit": "Cheese", "Quantite": 20, "Raison": "Seulement 15% des ventes"},
        {"Produit": "Cream", "Quantite": 20, "Raison": "Faible au Nord"},
    ])
    st.dataframe(nord, use_container_width=True, hide_index=True)

with tab_sud:
    st.subheader("Sud — 1 130 unites")
    st.markdown("**Sous-estimee !** Butter, Cream et Ice Cream se vendent fort ici.")
    sud = pd.DataFrame([
        {"Produit": "Milk", "Quantite": 350, "Raison": "25% des ventes, en hausse (+68% R1→R2)"},
        {"Produit": "Yoghurt", "Quantite": 250, "Raison": "36% des ventes, egal au Nord"},
        {"Produit": "Ice Cream", "Quantite": 200, "Raison": "A explose au R2 (+156%)"},
        {"Produit": "Butter", "Quantite": 180, "Raison": "49% des ventes, region dominante"},
        {"Produit": "Cream", "Quantite": 120, "Raison": "58% des ventes Cream, region dominante"},
        {"Produit": "Cheese", "Quantite": 30, "Raison": "Faible au Sud"},
    ])
    st.dataframe(sud, use_container_width=True, hide_index=True)

with tab_ouest:
    st.subheader("Ouest — 940 unites")
    st.markdown("**Milk + Cheese.** Le reste se vend peu ici.")
    ouest = pd.DataFrame([
        {"Produit": "Milk", "Quantite": 400, "Raison": "33% des ventes Milk"},
        {"Produit": "Yoghurt", "Quantite": 200, "Raison": "28%, plus faible que Nord/Sud"},
        {"Produit": "Ice Cream", "Quantite": 150, "Raison": "33%, correct"},
        {"Produit": "Cheese", "Quantite": 130, "Raison": "59% des ventes Cheese, region dominante"},
        {"Produit": "Cream", "Quantite": 30, "Raison": "13%, tres faible"},
        {"Produit": "Butter", "Quantite": 30, "Raison": "6%, quasi rien"},
    ])
    st.dataframe(ouest, use_container_width=True, hide_index=True)

# Stock restant au central
st.subheader("Stock Central apres distribution")
central = pd.DataFrame([
    {"Produit": "Milk", "Restant": 550},
    {"Produit": "Yoghurt", "Restant": 300},
    {"Produit": "Ice Cream", "Restant": 150},
    {"Produit": "Butter", "Restant": 170},
    {"Produit": "Cheese", "Restant": 20},
    {"Produit": "Cream", "Restant": 30},
])
st.dataframe(central, use_container_width=True, hide_index=True)
st.success(f"**Stock central : ~1 220 unites** — Bien en dessous de 4 000, zero penalite.")

# ============================================================
# TIMELINE STEP BY STEP
# ============================================================
st.header("4. Timeline — Quoi faire a chaque step")

timeline = [
    {"Step": "S01", "Qui": "Superviseur", "Action": "Passer la commande (4 400 units)", "Priorite": "CRITIQUE"},
    {"Step": "S01", "Qui": "Pricing", "Action": "Garder les prix par defaut, ne rien toucher", "Priorite": "INFO"},
    {"Step": "S02", "Qui": "Tous", "Action": "Attendre la livraison", "Priorite": "—"},
    {"Step": "S03", "Qui": "Distribution", "Action": "PO ARRIVEE → Lancer TOUS les transferts (Nord 1110, Sud 1130, Ouest 940)", "Priorite": "CRITIQUE"},
    {"Step": "S04", "Qui": "Tous", "Action": "Stock en transit vers les regions", "Priorite": "—"},
    {"Step": "S05", "Qui": "Superviseur", "Action": "PREMIERES VENTES — Verifier que tout se vend. Actualiser le dashboard.", "Priorite": "IMPORTANT"},
    {"Step": "S06-S07", "Qui": "Superviseur", "Action": "Surveiller les ventes. Si un produit s'ecoule vite → noter pour la prochaine commande", "Priorite": "IMPORTANT"},
    {"Step": "S07", "Qui": "Stock", "Action": "Re-transferer depuis Central si une region a un produit < 50 unites", "Priorite": "MOYENNE"},
    {"Step": "S08", "Qui": "Superviseur", "Action": "PAIEMENT PO (~159K). Verifier le cash. Si cash > 100K → preparer commande #2", "Priorite": "CRITIQUE"},
    {"Step": "S08-S09", "Qui": "Stock", "Action": "Si cash > 100K : commande #2 (surtout Milk + Yoghurt)", "Priorite": "IMPORTANT"},
    {"Step": "S10", "Qui": "Pricing", "Action": "Fin de Round 1 — analyser les volumes. Preparer ajustements prix Round 2.", "Priorite": "IMPORTANT"},
]

df_timeline = pd.DataFrame(timeline)

# Coloriser les priorites
def color_priority(val):
    if val == "CRITIQUE":
        return "background-color: #e74c3c; color: white"
    elif val == "IMPORTANT":
        return "background-color: #f39c12; color: white"
    elif val == "MOYENNE":
        return "background-color: #3498db; color: white"
    return ""

styled = df_timeline.style.applymap(color_priority, subset=["Priorite"])
st.dataframe(styled, use_container_width=True, hide_index=True)

# ============================================================
# ROUND 2+ — AJUSTEMENTS
# ============================================================
st.header("5. A partir du Round 2 — Ajustements")

st.subheader("Prix")
st.markdown("""
| Condition | Action |
|-----------|--------|
| Produit s'ecoule > 80% et concurrents plus chers | **Monter de +2-3%** |
| Produit s'ecoule > 80% mais concurrents au meme prix | **Monter de +1%** prudemment |
| Produit s'ecoule 50-80% | **Ne pas bouger** |
| Produit s'ecoule < 45% | **Baisser de -2 a -4%** |
| Nos prix > concurrents et nos volumes baissent | **Baisser immediatement** |
""")

st.subheader("Commandes")
st.markdown("""
| Condition | Action |
|-----------|--------|
| Stock total < 2 500 | Commander |
| Milk ou Yoghurt restant < 1 round de ventes | Commander en priorite |
| Cash < 80K | **Ne PAS commander** — attendre les paiements clients |
| Cash negatif imminent | **VETO — aucune commande** |
""")

st.subheader("Distribution")
st.markdown("""
| Condition | Action |
|-----------|--------|
| Stock region < 50 sur un produit qui se vend | Transferer depuis Central |
| Stock Central > 2 000 | Distribuer pour descendre sous 1 500 |
| Stock Central > 3 800 | **URGENCE** — distribuer tout de suite |
""")

# ============================================================
# RAPPELS IMPORTANTS
# ============================================================
st.header("6. Rappels critiques")

st.error("""
**NE JAMAIS FAIRE :**
- Commander plus de 200K en une fois (risque cash negatif)
- Laisser le stock Central > 4 000 (penalite 300 EUR/jour)
- Changer les prix de plus de 5% en un round
- Oublier de distribuer apres une livraison PO
""")

st.success("""
**TOUJOURS FAIRE :**
- Distribuer des que la PO arrive (Step 3, Step 8...)
- Garder 60K de cash en reserve minimum
- Surponderer Milk et Yoghurt dans les commandes
- Verifier le dashboard apres chaque cycle de ventes
""")
