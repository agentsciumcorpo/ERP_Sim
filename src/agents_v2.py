"""Agents IA v2 — Strategie competitionnelle ERPsim via OpenRouter."""

from __future__ import annotations

import json
import os
import pandas as pd
from src.config import OPENROUTER_BASE_URL, DEFAULT_MODEL, MAX_AGENT_TOKENS, PRODUCTS, REGIONS
from src.data_loader import GameData


def _call_llm(prompt: str, api_key: str) -> dict:
    """Appel OpenRouter, retourne le JSON parse."""
    import openai
    client = openai.OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    response = client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content.strip()
    if "```" in text:
        lines = text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```") and not in_block:
                in_block = True
                continue
            if line.strip().startswith("```") and in_block:
                break
            if in_block:
                json_lines.append(line)
        text = "\n".join(json_lines)
    return json.loads(text)


# ================================================================
# CONTEXTE STRATEGIQUE (injecte dans tous les prompts)
# ================================================================
STRATEGY_CONTEXT = """
CONTEXTE COMPETITION ERPSIM:
- 5 equipes en competition, marche produits laitiers, 6 produits, 3 regions (Nord, Sud, Ouest)
- Classement final = Valorisation = Profit Annuel / Taux de Risque
- Taux de risque = Company Risk Rate + Market Risk Rate. On controle UNIQUEMENT le Company Risk Rate via la cote de credit.
- Si cash negatif → pret automatique + degradation cote de credit IRREVERSIBLE → valorisation chute.
- Capacite entrepot central: 4000 unites. Au-dela: penalite 300 EUR/jour.
- Cout fixe par Purchase Order: 1000 EUR. Lead time livraison: 1-2 jours.
- Paiement fournisseur: 5 jours apres livraison. Paiement clients: 4 jours apres vente.
- Ce gap de tresorerie (on paye le fournisseur 1 jour apres les premiers encaissements clients) est CRITIQUE.

LECONS DES PARTIES PRECEDENTES:
- Milk et Yoghurt s'ecoulent a 83-88% → moteurs de volume, surponderer dans les commandes
- Cream et Cheese s'ecoulent a 34-36% → capital immobilise, sous-ponderer fortement
- Butter et Ice Cream a 51-61% → intermediaires
- La grosse commande initiale (6600 units) donne l'avance en ventes mais le mix etait desequilibre
- Les penalites stock (central > 4000 pendant 10 steps) ont coute ~3000 EUR
- Le cash negatif R1 a genere un pret de 62K avec interets
- Preferences regionales confirmees: Nord=Milk/IceCream, Sud=Yoghurt/IceCream, Ouest=Cheese
- Les marges sont serrees (6-9%) → le profit vient du VOLUME, pas du prix unitaire
""".strip()


def run_all_agents(
    data: GameData,
    margins: pd.DataFrame,
    stock_heatmap: pd.DataFrame,
    sales_region: pd.DataFrame,
    api_key: str,
) -> dict:
    """Lance les 3 agents et retourne un dict avec les resultats."""
    last_fin = data.financials.iloc[-1]
    cash = last_fin["cash"]
    loan = last_fin["loan"]
    credit = last_fin["credit"]
    profit = last_fin["profit"]
    current_round = data.current_round

    # Contexte marche
    market_ctx = _build_market_context(data)
    # Contexte ventes
    sales_ctx = _build_sales_context(data, margins)

    results = {}
    results["finance"] = _run_finance(cash, loan, credit, profit, current_round, api_key)
    results["pricing"] = _run_pricing(margins, market_ctx, sales_ctx, current_round, api_key)
    results["stock"] = _run_stock(margins, stock_heatmap, sales_ctx, cash, current_round, api_key)
    return results


# ================================================================
# HELPERS — construire le contexte
# ================================================================

def _build_market_context(data: GameData) -> str:
    if len(data.market) == 0:
        return "Pas de donnees marche disponibles."
    max_rnd = data.market["round"].max()
    latest = data.market[data.market["round"] == max_rnd]
    our = latest[latest["company"] == "LL"]
    others = latest[latest["company"] != "LL"]

    if len(others) == 0:
        return "Pas de donnees concurrents (Round 1 ou test solo)."

    lines = []
    for prod in PRODUCTS:
        our_prod = our[our["product"] == prod]
        oth_prod = others[others["product"] == prod]
        our_price = our_prod["avg_price"].mean() if len(our_prod) > 0 else 0
        our_qty = int(our_prod["qty"].sum()) if len(our_prod) > 0 else 0
        mkt_price = oth_prod["avg_price"].mean() if len(oth_prod) > 0 else 0
        mkt_qty = int(oth_prod["qty"].sum()) if len(oth_prod) > 0 else 0
        total = our_qty + mkt_qty
        share = (our_qty / total * 100) if total > 0 else 0
        lines.append(
            f"- {prod}: nous prix={our_price:.2f} qty={our_qty} | "
            f"concurrents prix={mkt_price:.2f} qty={mkt_qty} | "
            f"part de marche={share:.0f}%"
        )
    return "\n".join(lines)


def _build_sales_context(data: GameData, margins: pd.DataFrame) -> str:
    lines = []
    for _, m in margins.iterrows():
        lines.append(
            f"- {m['product']}: prix={m['price']}, cout_achat={m['cost']}, "
            f"marge={m['margin']} EUR/u ({m['margin_pct']}%), "
            f"vendu={int(m['qty_sold'])}, commande={int(m['qty_ordered'])}, "
            f"restant={int(m['qty_remaining'])}, ecoulement={m['turnover_pct']}%, "
            f"contribution={int(m['contribution'])} EUR"
        )

    # Evolution volumes R-1 vs R
    if len(data.sales) > 0:
        rounds = sorted(data.sales["round"].unique())
        if len(rounds) >= 2:
            lines.append("\nEvolution volumes (dernier round vs precedent):")
            for prod in PRODUCTS:
                by_rnd = data.sales[data.sales["product"] == prod].groupby("round")["qty"].sum()
                if len(by_rnd) >= 2:
                    prev = by_rnd.iloc[-2]
                    curr = by_rnd.iloc[-1]
                    change = ((curr - prev) / prev * 100) if prev > 0 else 0
                    lines.append(f"  {prod}: {int(prev)} -> {int(curr)} ({change:+.0f}%)")

    return "\n".join(lines)


# ================================================================
# AGENT FINANCE
# ================================================================

def _run_finance(cash, loan, credit, profit, current_round, api_key) -> dict:
    prompt = f"""{STRATEGY_CONTEXT}

Tu es l'Agent Finance. Round actuel: {current_round}.

ETAT:
- Cash: {cash:.0f} EUR
- Loan: {abs(loan):.0f} EUR
- Credit: {credit}
- Profit cumule: {profit:.0f} EUR

QUESTIONS:
1. Quel est le status cash (sain/attention/critique) ?
2. Combien peut-on investir max dans une commande sans risquer le cash negatif ?
   Rappel: le paiement fournisseur tombe 5 jours apres livraison. Pendant ces 5 jours on encaisse des ventes.
   Estimation prudente: on peut depenser max = cash - 60000 (garder 60K de marge).
3. Y a-t-il un veto a poser ?

Reponds en JSON:
{{"cash_status": "sain|attention|critique", "assessment": "1-2 phrases max", "vetoes": [], "max_investment": 0}}
"""
    try:
        if api_key:
            return _call_llm(prompt, api_key)
    except Exception:
        pass
    status = "critique" if cash < 50000 else "attention" if cash < 100000 else "sain"
    return {
        "cash_status": status,
        "assessment": f"Cash {cash:.0f} EUR, loan {abs(loan):.0f} EUR, credit {credit}.",
        "vetoes": ["Cash critique — pas de commande"] if cash < 50000 else [],
        "max_investment": max(0, cash - 60000),
    }


# ================================================================
# AGENT PRIX
# ================================================================

def _run_pricing(margins, market_ctx, sales_ctx, current_round, api_key) -> list[dict]:
    prompt = f"""{STRATEGY_CONTEXT}

Tu es l'Agent Prix. Round actuel: {current_round}.

METRIQUES PRODUITS:
{sales_ctx}

DONNEES MARCHE (concurrents):
{market_ctx}

TA MISSION: Recommander les 6 prix pour le prochain round.

STRATEGIE DE PRICING (OBLIGATOIRE):
1. On NE CONNAIT PAS l'elasticite-prix exacte. Chaque changement de prix est une EXPERIENCE.
2. Variation max par round: 2-3%. Jamais plus de 5% sauf donnees marche claires.
3. Si nos prix sont SUPERIEURS aux concurrents et nos volumes baissent → BAISSER.
4. Si nos prix sont INFERIEURS aux concurrents et nos volumes montent → MONTER doucement.
5. Si pas de donnees concurrents: bouger de 1-2% max, observer au round suivant.
6. Produits a bon ecoulement (>75%): on peut tenter +2-3% pour capturer de la marge.
7. Produits a mauvais ecoulement (<45%): baisser de 2-4% pour destocker.
8. Le profit vient du VOLUME — ne jamais sacrifier le volume pour la marge.
9. Round 1-2: NE PAS bouger les prix, on manque de donnees. Petits ajustements seulement.

Reponds en JSON (EXACTEMENT 6 objets, un par produit):
[{{"product": "...", "current_price": 0.0, "recommended_price": 0.0, "change_pct": 0.0, "confidence": "haute|moyenne|basse", "reasoning": "1 phrase"}}]
"""
    try:
        if api_key:
            result = _call_llm(prompt, api_key)
            # Normaliser: s'assurer que chaque item a toutes les cles
            for item in result:
                item.setdefault("confidence", "moyenne")
                item.setdefault("reasoning", "")
            return result
    except Exception:
        pass
    # Fallback
    recs = []
    for _, m in margins.iterrows():
        if current_round <= 2:
            change = 0.0
            conf = "basse"
            reason = f"Round {current_round} — pas assez de data, on maintient"
        elif m["turnover_pct"] > 75:
            change = 0.02
            conf = "moyenne"
            reason = f"Ecoulement {m['turnover_pct']:.0f}%, hausse prudente +2%"
        elif m["turnover_pct"] < 45:
            change = -0.03
            conf = "moyenne"
            reason = f"Ecoulement {m['turnover_pct']:.0f}%, baisse -3% pour destocker"
        else:
            change = 0.0
            conf = "basse"
            reason = f"Ecoulement {m['turnover_pct']:.0f}%, on maintient et on observe"
        new_price = round(m["price"] * (1 + change), 2)
        recs.append({
            "product": m["product"],
            "current_price": m["price"],
            "recommended_price": new_price,
            "change_pct": round(change * 100, 1),
            "confidence": conf,
            "reasoning": reason,
        })
    return recs


# ================================================================
# AGENT STOCK & DISTRIBUTION
# ================================================================

def _run_stock(margins, stock_heatmap, sales_ctx, cash, current_round, api_key) -> dict:
    stock_info = ""
    if len(stock_heatmap) > 0:
        for prod in PRODUCTS:
            if prod in stock_heatmap.index:
                row = stock_heatmap.loc[prod]
                central = int(row.get("Central", 0))
                nord = int(row.get("Nord", 0))
                sud = int(row.get("Sud", 0))
                ouest = int(row.get("Ouest", 0))
                total = int(row.get("Total", 0))
                stock_info += f"- {prod}: Central={central} Nord={nord} Sud={sud} Ouest={ouest} Total={total}\n"

    # Ventes moyennes par round
    sales_avg_info = ""
    for _, m in margins.iterrows():
        avg = int(m["qty_sold"]) / max(1, current_round)
        stock_left = int(m["qty_remaining"])
        rounds_left = (stock_left / avg) if avg > 0 else 999
        sales_avg_info += f"- {m['product']}: ~{avg:.0f} units/round, stock restant={stock_left}, duree stock={rounds_left:.1f} rounds\n"

    total_stock = int(stock_heatmap["Total"].sum()) if len(stock_heatmap) > 0 else 0
    central_stock = int(stock_heatmap["Central"].sum()) if "Central" in stock_heatmap.columns else 0

    prompt = f"""{STRATEGY_CONTEXT}

Tu es l'Agent Stock & Distribution. Round actuel: {current_round}.

STOCK ACTUEL:
{stock_info}
Stock total: {total_stock} | Central: {central_stock}

VENTES MOYENNES ET DUREE DE STOCK:
{sales_avg_info}

CASH DISPONIBLE: {cash:.0f} EUR (max investissement = {max(0, cash - 60000):.0f} EUR)

TA MISSION:
1. COMMANDE: Faut-il commander maintenant? Si oui, combien de chaque produit?
   - Commander quand stock total < 3000 ou quand un produit a forte rotation < 1 round de stock
   - MIX OPTIMAL base sur l'ecoulement: surponderer Milk/Yoghurt, sous-ponderer Cream/Cheese
   - Ne JAMAIS commander plus que le cash le permet (garder 60K de marge)
   - Ne JAMAIS commander au point de depasser 4000 au central apres livraison

2. TRANSFERTS: Quels transferts du Central vers les regions?
   - Transferer IMMEDIATEMENT si stock central > 1000 (eviter les penalites)
   - Priorite aux regions avec stock < 100 sur un produit a forte preference
   - Preferences: Nord=Milk/IceCream, Sud=Yoghurt/IceCream, Ouest=Cheese
   - Cout: 100 EUR par transfert

Reponds en JSON:
{{"order_now": true/false, "order_quantity": 0, "order_detail": [{{"product": "...", "quantity": 0}}], "order_reasoning": "1-2 phrases", "transfers": [{{"from": "Central", "to": "...", "product": "...", "quantity": 0, "reason": "..."}}]}}
"""
    try:
        if api_key:
            return _call_llm(prompt, api_key)
    except Exception:
        pass
    # Fallback
    from src.config import REGIONAL_PREFERENCES

    order_now = total_stock < 3000
    max_invest = max(0, cash - 60000)
    order_detail = []
    if order_now:
        # Mix optimal base sur ecoulement
        budget_left = max_invest - 1000  # fee PO
        for _, m in margins.iterrows():
            if budget_left <= 0:
                break
            cost = m["cost"]
            if m["turnover_pct"] > 70:
                qty = 600
            elif m["turnover_pct"] > 45:
                qty = 300
            else:
                qty = 100
            item_cost = qty * cost
            if item_cost > budget_left:
                qty = int(budget_left / cost)
            if qty > 0:
                order_detail.append({"product": m["product"], "quantity": qty})
                budget_left -= qty * cost

    transfers = []
    if len(stock_heatmap) > 0 and "Central" in stock_heatmap.columns:
        for region in REGIONS:
            if region not in stock_heatmap.columns:
                continue
            for prod in PRODUCTS:
                if prod not in stock_heatmap.index:
                    continue
                reg_stock = int(stock_heatmap.loc[prod, region])
                central = int(stock_heatmap.loc[prod, "Central"])
                pref = REGIONAL_PREFERENCES.get(region, {}).get(prod, 1.0)
                if reg_stock < 80 and central > 100:
                    qty = min(int(central * 0.4), 200)
                    if pref >= 1.5:
                        qty = min(int(central * 0.5), 250)
                    transfers.append({
                        "from": "Central",
                        "to": region,
                        "product": prod,
                        "quantity": qty,
                        "reason": f"Stock region={reg_stock}, central={central}, pref={'forte' if pref >= 1.5 else 'standard'}",
                    })

    total_order = sum(d["quantity"] for d in order_detail)
    return {
        "order_now": order_now,
        "order_quantity": total_order,
        "order_detail": order_detail,
        "order_reasoning": f"Stock total {total_stock}. " + (
            f"< 3000, commande {total_order} units (budget max {max_invest:.0f} EUR)."
            if order_now else "Suffisant pour le moment."
        ),
        "transfers": transfers,
    }
