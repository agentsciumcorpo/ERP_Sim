"""Orchestrateur du cycle decisionnel complet."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.odata_client import ODataClient, ERPSimData
from src.calculations import compute_metrics, CalculationResults
from src.agents import (
    PricingAgentResponse, StockAgentResponse, FinanceAgentResponse,
    run_pricing_agent, run_stock_agent, run_finance_agent,
    run_pricing_agent_fallback, run_stock_agent_fallback, run_finance_agent_fallback,
)
from src.guardrails import apply_guardrails, GuardrailReport
from src.memory import append_memory
from src.config import MANUAL_ROUNDS


@dataclass
class CycleResult:
    """Resultat complet d'un cycle decisionnel."""
    round_number: int
    metrics: CalculationResults
    finance_eval: FinanceAgentResponse | None = None
    pricing: PricingAgentResponse | None = None
    stock: StockAgentResponse | None = None
    finance_veto: FinanceAgentResponse | None = None
    guardrails: GuardrailReport | None = None
    is_manual_mode: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class GameState:
    """Etat global du jeu, persiste entre les cycles."""
    client: ODataClient
    history: list[ERPSimData] = field(default_factory=list)
    cycle_results: list[CycleResult] = field(default_factory=list)
    memories: dict[str, str] = field(default_factory=dict)
    current_prices: dict[str, float] = field(default_factory=dict)
    use_ai: bool = True
    api_key: str = ""

    def __post_init__(self):
        if not self.memories:
            from src.memory import init_memory
            self.memories = init_memory()
        if not self.current_prices:
            from src.config import PRODUCTS
            self.current_prices = {
                "Lait": 2.50, "Creme": 3.80, "Yaourt": 2.40,
                "Fromage": 5.20, "Beurre": 4.10, "Glace": 3.50,
            }


def run_cycle(state: GameState) -> CycleResult:
    """Execute un cycle decisionnel complet:
    OData → Calculs → Finance eval → Prix → Stock → Finance veto → Garde-fous → Affichage
    """
    errors = []

    # 1. Recuperer les donnees
    data = state.client.fetch_data()
    state.history.append(data)

    # 2. Calculer les metriques
    metrics = compute_metrics(data, state.history)

    # 3. Mode manuel ?
    if data.round_number <= MANUAL_ROUNDS:
        result = CycleResult(
            round_number=data.round_number,
            metrics=metrics,
            is_manual_mode=True,
        )
        state.cycle_results.append(result)
        return result

    # 4. Finance eval
    finance_eval = _run_finance_eval(state, metrics, errors)

    # 5. Agent Prix
    pricing = _run_pricing(state, metrics, errors)

    # 6. Agent Stock
    stock = _run_stock(state, metrics, errors)

    # 7. Finance veto
    finance_veto = _run_finance_veto(state, metrics, pricing, stock, errors)

    # 8. Appliquer garde-fous sur les prix
    guardrails = None
    if pricing:
        proposed = {r.product: r.recommended_price for r in pricing.recommendations}
        guardrails = apply_guardrails(
            proposed, state.current_prices,
            metrics.total_central_stock,
            metrics.cash_projection.current_cash,
        )
        # Mettre a jour les prix avec les valeurs ajustees
        for product, check in guardrails.price_checks.items():
            state.current_prices[product] = check.adjusted_value

    # 9. Enregistrer en memoire
    _record_memories(state, data.round_number, pricing, stock, finance_eval, finance_veto)

    result = CycleResult(
        round_number=data.round_number,
        metrics=metrics,
        finance_eval=finance_eval,
        pricing=pricing,
        stock=stock,
        finance_veto=finance_veto,
        guardrails=guardrails,
        errors=errors,
    )
    state.cycle_results.append(result)
    return result


def _run_finance_eval(
    state: GameState, metrics: CalculationResults, errors: list[str]
) -> FinanceAgentResponse | None:
    try:
        if state.use_ai and state.api_key:
            return run_finance_agent(metrics, state.memories, state.api_key)
        return run_finance_agent_fallback(metrics)
    except Exception as e:
        errors.append(f"Agent Finance (eval): {e}")
        return run_finance_agent_fallback(metrics)


def _run_pricing(
    state: GameState, metrics: CalculationResults, errors: list[str]
) -> PricingAgentResponse | None:
    try:
        if state.use_ai and state.api_key:
            return run_pricing_agent(metrics, state.memories, state.api_key)
        return run_pricing_agent_fallback(metrics)
    except Exception as e:
        errors.append(f"Agent Prix: {e}")
        return run_pricing_agent_fallback(metrics)


def _run_stock(
    state: GameState, metrics: CalculationResults, errors: list[str]
) -> StockAgentResponse | None:
    try:
        if state.use_ai and state.api_key:
            return run_stock_agent(metrics, state.memories, state.api_key)
        return run_stock_agent_fallback(metrics)
    except Exception as e:
        errors.append(f"Agent Stock: {e}")
        return run_stock_agent_fallback(metrics)


def _run_finance_veto(
    state: GameState,
    metrics: CalculationResults,
    pricing: PricingAgentResponse | None,
    stock: StockAgentResponse | None,
    errors: list[str],
) -> FinanceAgentResponse | None:
    try:
        if state.use_ai and state.api_key:
            return run_finance_agent(
                metrics, state.memories, state.api_key, pricing, stock
            )
        return run_finance_agent_fallback(metrics, pricing, stock)
    except Exception as e:
        errors.append(f"Agent Finance (veto): {e}")
        return run_finance_agent_fallback(metrics, pricing, stock)


def _record_memories(
    state: GameState,
    round_number: int,
    pricing: PricingAgentResponse | None,
    stock: StockAgentResponse | None,
    finance_eval: FinanceAgentResponse | None,
    finance_veto: FinanceAgentResponse | None,
):
    if pricing:
        changes = [
            f"{r.product}: {r.current_price} -> {r.recommended_price} ({r.confidence})"
            for r in pricing.recommendations
        ]
        append_memory(
            state.memories, "prix", round_number,
            decision="\n".join(changes),
            reasoning=pricing.global_strategy,
        )

    if stock:
        alloc_summary = [
            f"{a.region}/{a.product}: +{a.quantity}" for a in stock.allocations
        ]
        append_memory(
            state.memories, "stock", round_number,
            decision=f"Commande: {stock.order_quantity} | Transferts: {len(stock.allocations)}",
            reasoning=stock.order_reasoning + "\n" + "\n".join(alloc_summary),
        )

    if finance_veto:
        vetoes_str = ", ".join(finance_veto.vetoes) if finance_veto.vetoes else "Aucun veto"
        append_memory(
            state.memories, "finance", round_number,
            decision=f"Status: {finance_veto.cash_status} | Approuve: {finance_veto.approved}",
            reasoning=finance_veto.credit_assessment + f" | Vetos: {vetoes_str}",
        )
