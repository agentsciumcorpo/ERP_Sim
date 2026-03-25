"""3 Agents IA specialises via OpenRouter (API compatible OpenAI)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.config import PRODUCTS, REGIONS, OPENROUTER_BASE_URL, DEFAULT_MODEL, MAX_AGENT_TOKENS
from src.calculations import CalculationResults, ProductMetrics
from src.memory import get_memory_context


# --- Modeles de reponse des agents ---

@dataclass
class PriceRecommendation:
    product: str
    current_price: float
    recommended_price: float
    change_pct: float
    confidence: str  # "haute", "moyenne", "basse"
    reasoning: str


@dataclass
class PricingAgentResponse:
    recommendations: list[PriceRecommendation]
    global_strategy: str


@dataclass
class RegionAllocation:
    region: str
    product: str
    quantity: int
    reasoning: str


@dataclass
class StockAgentResponse:
    order_quantity: int
    order_reasoning: str
    allocations: list[RegionAllocation]
    alerts: list[str]


@dataclass
class FinanceAgentResponse:
    cash_status: str  # "sain", "attention", "critique"
    credit_assessment: str
    vetoes: list[str]
    recommendations: list[str]
    approved: bool


# --- Construction des prompts ---

def _build_pricing_prompt(
    metrics: CalculationResults,
    memories: dict[str, str],
) -> str:
    product_info = ""
    for m in metrics.product_metrics:
        elasticity_str = f"{m.elasticity}" if m.elasticity is not None else "insuffisante"
        product_info += (
            f"- {m.product}: prix={m.current_price}, marge_nette={m.net_margin} ({m.margin_pct}%), "
            f"qty_vendue={m.total_quantity}, contribution={m.contribution}, elasticite={elasticity_str}\n"
        )

    memory_ctx = get_memory_context(memories, "prix")
    phase = metrics.game_phase

    return f"""Tu es l'Agent Prix d'une equipe ERPsim (produits laitiers, 6 produits, 3 regions).
Ton role : recommander les 6 prix pour le prochain cycle.

PHASE ACTUELLE: {phase.phase} — {phase.description}
RECOMMANDATION PHASE: {phase.recommendation}

METRIQUES PRODUITS:
{product_info}

STOCK CENTRAL: {metrics.total_central_stock} / 4000
CASH: {metrics.cash_projection.current_cash} EUR (tendance: {metrics.cash_projection.trend})
PLATEAU: {"OUI — " + metrics.plateau.message if metrics.plateau.is_plateau else "Non"}

MEMOIRE CUMULATIVE:
{memory_ctx}

REGLES:
- Variation max 15% par cycle
- Favoriser les produits a forte marge de contribution
- Si plateau detecte, ajuster agressivement
- Prix minimum = cout + 10% de marge

Reponds en JSON strict avec cette structure:
{{
  "recommendations": [
    {{"product": "...", "current_price": 0.0, "recommended_price": 0.0, "change_pct": 0.0, "confidence": "haute|moyenne|basse", "reasoning": "..."}}
  ],
  "global_strategy": "..."
}}
Inclus les 6 produits. Raisonnement en francais, court (1 phrase par produit)."""


def _build_stock_prompt(
    metrics: CalculationResults,
    memories: dict[str, str],
) -> str:
    stock_info = f"Stock central total: {metrics.total_central_stock} / 4000\n"
    stock_info += "\nStocks regionaux:\n"
    for region in REGIONS:
        stocks = metrics.regional_stock.get(region, {})
        items = ", ".join(f"{p}={stocks.get(p, 0)}" for p in PRODUCTS)
        stock_info += f"- {region}: {items}\n"

    # Ventes par region
    sales_info = "Ventes du cycle:\n"
    for m in metrics.product_metrics:
        sales_info += f"- {m.product}: {m.total_quantity} unites, contribution={m.contribution}\n"

    memory_ctx = get_memory_context(memories, "stock")

    return f"""Tu es l'Agent Stock d'une equipe ERPsim (produits laitiers, 6 produits, 3 regions: Nord, Sud, Ouest).
Ton role : recommander la quantite a commander ET les transferts du central vers les regions.

{stock_info}

{sales_info}

CASH: {metrics.cash_projection.current_cash} EUR
PHASE: {metrics.game_phase.phase} — {metrics.game_phase.description}

MEMOIRE CUMULATIVE:
{memory_ctx}

REGLES:
- Stock central ne doit PAS depasser 3800 (penalite a 4000)
- Distribuer en priorite vers les regions a forte demande
- Preferences: Nord=Lait/Glace, Sud=Yaourt/Glace, Ouest=Fromage
- Commander pour maintenir 2-3 cycles de stock

Reponds en JSON strict:
{{
  "order_quantity": 0,
  "order_reasoning": "...",
  "allocations": [
    {{"region": "...", "product": "...", "quantity": 0, "reasoning": "..."}}
  ],
  "alerts": ["..."]
}}
Inclus uniquement les transferts necessaires. Raisonnement en francais, court."""


def _build_finance_prompt(
    metrics: CalculationResults,
    memories: dict[str, str],
    pricing_response: PricingAgentResponse | None = None,
    stock_response: StockAgentResponse | None = None,
) -> str:
    fin = metrics.cash_projection
    financials_info = (
        f"Cash: {fin.current_cash} EUR\n"
        f"Projection +1 cycle: {fin.projected_next_cycle} EUR\n"
        f"Projection +5 cycles: {fin.projected_5_cycles} EUR\n"
        f"Tendance: {fin.trend}\n"
    )

    pending_decisions = ""
    if pricing_response:
        changes = [
            f"{r.product}: {r.current_price} -> {r.recommended_price}"
            for r in pricing_response.recommendations
        ]
        pending_decisions += "Changements prix proposes:\n" + "\n".join(f"- {c}" for c in changes) + "\n"
    if stock_response:
        pending_decisions += f"Commande proposee: {stock_response.order_quantity} unites\n"
        if stock_response.allocations:
            pending_decisions += f"Transferts: {len(stock_response.allocations)} operations\n"

    memory_ctx = get_memory_context(memories, "finance")

    return f"""Tu es l'Agent Finance d'une equipe ERPsim. Ton role : evaluer la sante financiere et VETOIR les decisions dangereuses.

ETAT FINANCIER:
{financials_info}
Cote de credit: {metrics.cash_projection.current_cash > 200000 and "AAA+" or metrics.cash_projection.current_cash > 100000 and "AA" or "A"}
Valorisation = Profit / Taux de risque — la cote de credit est CRITIQUE

DECISIONS EN ATTENTE DE VALIDATION:
{pending_decisions if pending_decisions else "Aucune decision a valider (evaluation initiale)"}

MEMOIRE CUMULATIVE:
{memory_ctx}

REGLES:
- Cash JAMAIS negatif — c'est irreversible (pret auto + degradation cote)
- Seuil minimum cash: 50 000 EUR
- Si cash < 50 000: VETO sur les commandes non essentielles
- Proteger la cote de credit a tout prix

Reponds en JSON strict:
{{
  "cash_status": "sain|attention|critique",
  "credit_assessment": "...",
  "vetoes": ["..."],
  "recommendations": ["..."],
  "approved": true/false
}}
Raisonnement en francais, court."""


# --- Appels OpenRouter API ---

def _call_llm(prompt: str, api_key: str, model: str | None = None) -> dict:
    """Appelle OpenRouter (compatible OpenAI) et parse la reponse JSON."""
    import openai

    client = openai.OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
    )
    response = client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        max_tokens=MAX_AGENT_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content.strip()
    # Extraire le JSON si entoure de ```json
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                json_lines.append(line)
        text = "\n".join(json_lines)
    return json.loads(text)


def _parse_pricing_response(data: dict) -> PricingAgentResponse:
    recs = []
    for r in data.get("recommendations", []):
        recs.append(PriceRecommendation(
            product=r["product"],
            current_price=r.get("current_price", 0),
            recommended_price=r["recommended_price"],
            change_pct=r.get("change_pct", 0),
            confidence=r.get("confidence", "moyenne"),
            reasoning=r.get("reasoning", ""),
        ))
    return PricingAgentResponse(
        recommendations=recs,
        global_strategy=data.get("global_strategy", ""),
    )


def _parse_stock_response(data: dict) -> StockAgentResponse:
    allocs = []
    for a in data.get("allocations", []):
        allocs.append(RegionAllocation(
            region=a["region"],
            product=a["product"],
            quantity=a["quantity"],
            reasoning=a.get("reasoning", ""),
        ))
    return StockAgentResponse(
        order_quantity=data.get("order_quantity", 0),
        order_reasoning=data.get("order_reasoning", ""),
        allocations=allocs,
        alerts=data.get("alerts", []),
    )


def _parse_finance_response(data: dict) -> FinanceAgentResponse:
    return FinanceAgentResponse(
        cash_status=data.get("cash_status", "sain"),
        credit_assessment=data.get("credit_assessment", ""),
        vetoes=data.get("vetoes", []),
        recommendations=data.get("recommendations", []),
        approved=data.get("approved", True),
    )


# --- Fonctions publiques ---

def run_pricing_agent(
    metrics: CalculationResults,
    memories: dict[str, str],
    api_key: str,
) -> PricingAgentResponse:
    prompt = _build_pricing_prompt(metrics, memories)
    data = _call_llm(prompt, api_key)
    return _parse_pricing_response(data)


def run_stock_agent(
    metrics: CalculationResults,
    memories: dict[str, str],
    api_key: str,
) -> StockAgentResponse:
    prompt = _build_stock_prompt(metrics, memories)
    data = _call_llm(prompt, api_key)
    return _parse_stock_response(data)


def run_finance_agent(
    metrics: CalculationResults,
    memories: dict[str, str],
    api_key: str,
    pricing_response: PricingAgentResponse | None = None,
    stock_response: StockAgentResponse | None = None,
) -> FinanceAgentResponse:
    prompt = _build_finance_prompt(metrics, memories, pricing_response, stock_response)
    data = _call_llm(prompt, api_key)
    return _parse_finance_response(data)


# --- Mode fallback sans API ---

def run_pricing_agent_fallback(metrics: CalculationResults) -> PricingAgentResponse:
    """Recommandations basees uniquement sur les calculs, sans IA."""
    recs = []
    for m in metrics.product_metrics:
        # Logique simple: si marge faible, monter le prix; si elasticite forte, baisser
        change = 0.0
        confidence = "basse"
        reasoning = "Fallback sans IA"

        if m.elasticity is not None and m.elasticity < -1.5:
            change = -0.05  # Baisser legerement
            reasoning = f"Elasticite forte ({m.elasticity}), baisse prudente"
        elif m.margin_pct < 30:
            change = 0.05
            reasoning = f"Marge faible ({m.margin_pct}%), hausse pour rentabilite"

        new_price = round(m.current_price * (1 + change), 2)
        recs.append(PriceRecommendation(
            product=m.product,
            current_price=m.current_price,
            recommended_price=new_price,
            change_pct=round(change * 100, 1),
            confidence=confidence,
            reasoning=reasoning,
        ))
    return PricingAgentResponse(recs, "Mode fallback — recommandations calculees sans IA")


def run_stock_agent_fallback(metrics: CalculationResults) -> StockAgentResponse:
    """Allocations basees sur les preferences regionales, sans IA."""
    from src.config import REGIONAL_PREFERENCES
    allocs = []
    for region in REGIONS:
        for product in PRODUCTS:
            pref = REGIONAL_PREFERENCES[region][product]
            regional_qty = metrics.regional_stock.get(region, {}).get(product, 0)
            if regional_qty < 100 and pref >= 1.5:
                allocs.append(RegionAllocation(
                    region=region,
                    product=product,
                    quantity=int(80 * pref),
                    reasoning=f"Stock bas ({regional_qty}) + preference regionale",
                ))

    order = 1000 if metrics.total_central_stock < 2500 else 0
    return StockAgentResponse(
        order_quantity=order,
        order_reasoning="Reapprovisionnement standard" if order else "Stock suffisant",
        allocations=allocs,
        alerts=[],
    )


def run_finance_agent_fallback(
    metrics: CalculationResults,
    pricing: PricingAgentResponse | None = None,
    stock: StockAgentResponse | None = None,
) -> FinanceAgentResponse:
    """Evaluation financiere basee sur les seuils, sans IA."""
    cash = metrics.cash_projection.current_cash
    vetoes = []

    if cash < 50_000:
        status = "critique"
        if stock and stock.order_quantity > 0:
            vetoes.append("VETO: Cash critique, commande bloquee")
    elif cash < 100_000:
        status = "attention"
    else:
        status = "sain"

    return FinanceAgentResponse(
        cash_status=status,
        credit_assessment=f"Cash {cash:.0f} EUR — status {status}",
        vetoes=vetoes,
        recommendations=[],
        approved=len(vetoes) == 0,
    )
