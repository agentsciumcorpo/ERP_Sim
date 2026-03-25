"""Agents IA v2 — Recommandations via OpenRouter, adaptes aux donnees reelles."""

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
        max_tokens=MAX_AGENT_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content.strip()
    # Extraire JSON si dans un bloc code
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


def run_all_agents(
    data: GameData,
    margins: pd.DataFrame,
    stock_heatmap: pd.DataFrame,
    sales_region: pd.DataFrame,
    api_key: str,
) -> dict:
    """Lance les 3 agents et retourne un dict avec les resultats."""
    results = {}

    # Contexte commun
    last_fin = data.financials.iloc[-1]
    cash = last_fin["cash"]
    loan = last_fin["loan"]
    credit = last_fin["credit"]
    profit = last_fin["profit"]

    # --- Agent Finance ---
    results["finance"] = _run_finance(data, cash, loan, credit, profit, api_key)

    # --- Agent Prix ---
    results["pricing"] = _run_pricing(data, margins, cash, api_key)

    # --- Agent Stock ---
    results["stock"] = _run_stock(data, margins, stock_heatmap, sales_region, cash, api_key)

    return results


def _run_finance(data, cash, loan, credit, profit, api_key) -> dict:
    prompt = f"""Tu es l'Agent Finance d'une equipe ERPsim (produits laitiers).
Evalue la sante financiere et dis si on peut investir.

Cash: {cash:.0f} EUR
Loan: {abs(loan):.0f} EUR
Credit: {credit}
Profit cumule: {profit:.0f} EUR

Regles:
- Cash JAMAIS negatif (pret auto + degradation cote irreversible)
- Seuil minimum: 50 000 EUR
- Proteger la cote de credit a tout prix

Reponds en JSON:
{{"cash_status": "sain|attention|critique", "assessment": "1 phrase", "vetoes": ["...si besoin"], "max_investment": 0}}
"""
    try:
        if api_key:
            return _call_llm(prompt, api_key)
    except Exception as e:
        pass
    # Fallback
    status = "critique" if cash < 50000 else "attention" if cash < 100000 else "sain"
    return {
        "cash_status": status,
        "assessment": f"Cash {cash:.0f} EUR, loan {abs(loan):.0f} EUR",
        "vetoes": ["Cash critique, pas de commande" ] if cash < 50000 else [],
        "max_investment": max(0, cash - 60000),
    }


def _run_pricing(data, margins, cash, api_key) -> list[dict]:
    margin_info = ""
    for _, m in margins.iterrows():
        margin_info += (
            f"- {m['product']}: prix={m['price']}, cout={m['cost']}, "
            f"marge={m['margin']} ({m['margin_pct']}%), "
            f"vendu={m['qty_sold']}, ecoulement={m['turnover_pct']}%, "
            f"contribution={m['contribution']}\n"
        )

    # Donnees de prix du marche si disponibles
    market_info = ""
    if len(data.market) > 0:
        max_rnd = data.market["round"].max()
        latest = data.market[data.market["round"] == max_rnd]
        for prod in PRODUCTS:
            prod_mkt = latest[latest["product"] == prod]
            others = prod_mkt[prod_mkt["company"] != "LL"]
            if len(others) > 0:
                avg = others["avg_price"].mean()
                market_info += f"- {prod}: prix moyen concurrents = {avg:.2f}\n"
        if not market_info:
            market_info = "Pas de donnees concurrents disponibles (test solo ou Round 1).\n"

    # Variation prix entre rounds
    price_history = ""
    if len(data.sales) > 0:
        rounds = sorted(data.sales["round"].unique())
        if len(rounds) >= 2:
            for prod in PRODUCTS:
                prices_by_round = []
                for rnd in rounds:
                    rnd_sales = data.sales[(data.sales["round"] == rnd) & (data.sales["product"] == prod)]
                    if len(rnd_sales) > 0:
                        prices_by_round.append((rnd, rnd_sales["price"].mean()))
                if len(prices_by_round) >= 2:
                    p0 = prices_by_round[-2][1]
                    p1 = prices_by_round[-1][1]
                    q_by_rnd = data.sales[data.sales["product"] == prod].groupby("round")["qty"].sum()
                    if len(q_by_rnd) >= 2:
                        q0 = q_by_rnd.iloc[-2]
                        q1 = q_by_rnd.iloc[-1]
                        price_history += f"- {prod}: R{int(prices_by_round[-2][0])} prix={p0:.2f} qty={q0} → R{int(prices_by_round[-1][0])} prix={p1:.2f} qty={q1}\n"

    prompt = f"""Tu es l'Agent Prix d'une equipe ERPsim (6 produits laitiers, 3 regions, 5 equipes en competition).
Recommande les 6 prix pour le prochain round.

METRIQUES PRODUITS:
{margin_info}

PRIX DU MARCHE (concurrents):
{market_info}

HISTORIQUE PRIX/VOLUMES:
{price_history if price_history else "Pas assez d'historique pour calculer l'elasticite."}

REGLES STRICTES DE PRICING:
1. PRUDENCE: On ne connait PAS l'elasticite-prix reelle. On n'a pas assez de data pour savoir comment les clients reagissent.
2. VARIATION MAX 2-3% par round. JAMAIS plus de 5% sauf situation extreme. Le 15% est une limite technique, PAS un objectif.
3. En competition, si on monte trop les concurrents prennent nos clients.
4. Observer l'impact avant de continuer — hausse progressive, pas agressive.
5. Produits a bon ecoulement (>75%): hausse de +1 a +3% pour tester l'elasticite.
6. Produits a mauvais ecoulement (<45%): baisse de -2 a -4% pour stimuler la demande.
7. Produits intermediaires (45-75%): stable ou +/-1%.

Pour chaque produit, donne: prix recommande, variation %, confiance (haute/moyenne/basse), raisonnement (1 phrase).

Reponds en JSON (liste de 6 objets):
[{{"product": "...", "current_price": 0, "recommended_price": 0, "change_pct": 0, "confidence": "haute|moyenne|basse", "reasoning": "..."}}]
"""
    try:
        if api_key:
            return _call_llm(prompt, api_key)
    except Exception:
        pass
    # Fallback
    recs = []
    for _, m in margins.iterrows():
        change = 0.0
        conf = "basse"
        reason = "Pas de cle API — calcul automatique"
        if m["turnover_pct"] > 80:
            change = 0.03
            conf = "moyenne"
            reason = f"Ecoulement {m['turnover_pct']:.0f}% — hausse prudente"
        elif m["turnover_pct"] < 40:
            change = -0.03
            conf = "moyenne"
            reason = f"Ecoulement {m['turnover_pct']:.0f}% — baisse pour destocker"
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


def _run_stock(data, margins, stock_heatmap, sales_region, cash, api_key) -> dict:
    stock_info = ""
    if len(stock_heatmap) > 0:
        for prod in PRODUCTS:
            if prod in stock_heatmap.index:
                row = stock_heatmap.loc[prod]
                stock_info += f"- {prod}: Central={row.get('Central', 0)}"
                for r in REGIONS:
                    stock_info += f" {r}={row.get(r, 0)}"
                stock_info += f" Total={row.get('Total', 0)}\n"

    ecoulement_info = ""
    for _, m in margins.iterrows():
        ecoulement_info += f"- {m['product']}: ecoulement={m['turnover_pct']}%, restant={m['qty_remaining']}\n"

    # Ventes moyennes par round par produit
    sales_avg = ""
    if len(data.sales) > 0:
        avg = data.sales.groupby("product")["qty"].sum() / max(1, data.current_round)
        for prod in PRODUCTS:
            v = avg.get(prod, 0)
            sales_avg += f"- {prod}: ~{v:.0f} units/round\n"

    prompt = f"""Tu es l'Agent Stock d'une equipe ERPsim (6 produits, 3 regions: Nord, Sud, Ouest).
Dis quand commander, combien, et quels transferts faire.

STOCK ACTUEL:
{stock_info}

ECOULEMENT:
{ecoulement_info}

VENTES MOYENNES PAR ROUND:
{sales_avg}

CASH: {cash:.0f} EUR
COUT PO: 1000 EUR fixe par commande
LEAD TIME: 1-2 jours (steps)
CAPACITE ENTREPOT: 4000 (penalite 300/jour au-dela)

REGLES:
- Surponderer Milk et Yoghurt (s'ecoulent vite)
- Reduire Cream et Cheese (s'ecoulent mal)
- Commander quand stock total < 2500
- Distribuer pour que chaque region ait au moins 1 round de stock

Reponds en JSON:
{{"order_now": true/false, "order_quantity": 0, "order_detail": [{{"product": "...", "quantity": 0}}], "order_reasoning": "...", "transfers": [{{"from": "Central", "to": "...", "product": "...", "quantity": 0, "reason": "..."}}]}}
"""
    try:
        if api_key:
            return _call_llm(prompt, api_key)
    except Exception:
        pass
    # Fallback
    total_stock = int(stock_heatmap["Total"].sum()) if len(stock_heatmap) > 0 else 0
    order_now = total_stock < 2500

    order_detail = []
    transfers = []
    if order_now:
        for _, m in margins.iterrows():
            if m["turnover_pct"] > 70:
                order_detail.append({"product": m["product"], "quantity": 600})
            elif m["turnover_pct"] > 45:
                order_detail.append({"product": m["product"], "quantity": 300})

    # Transferts: regions avec stock < 50 et preference forte
    from src.config import REGIONAL_PREFERENCES
    if len(stock_heatmap) > 0:
        for region in REGIONS:
            if region not in stock_heatmap.columns:
                continue
            for prod in PRODUCTS:
                if prod not in stock_heatmap.index:
                    continue
                reg_stock = int(stock_heatmap.loc[prod, region])
                central = int(stock_heatmap.loc[prod].get("Central", 0))
                pref = REGIONAL_PREFERENCES.get(region, {}).get(prod, 1.0)
                if reg_stock < 60 and central > 100 and pref >= 1.0:
                    qty = min(150, central // 2)
                    transfers.append({
                        "from": "Central",
                        "to": region,
                        "product": prod,
                        "quantity": qty,
                        "reason": f"Stock {reg_stock}, central {central}",
                    })

    total_order = sum(d["quantity"] for d in order_detail)
    return {
        "order_now": order_now,
        "order_quantity": total_order,
        "order_detail": order_detail,
        "order_reasoning": f"Stock total {total_stock}" + (" < 2500, reapprovisionner" if order_now else ", suffisant"),
        "transfers": transfers,
    }
