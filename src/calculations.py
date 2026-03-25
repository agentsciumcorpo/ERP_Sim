"""Calculs derives : elasticite-prix, marges, projections, detection plateau."""

from __future__ import annotations

from dataclasses import dataclass
from src.config import (
    PRODUCTS, REGIONS, MIN_CYCLES_FOR_ELASTICITY, MANUAL_ROUNDS,
)
from src.odata_client import ERPSimData, SalesRecord


@dataclass
class ProductMetrics:
    product: str
    current_price: float
    total_quantity: int
    total_revenue: float
    cost_per_unit: float
    net_margin: float  # prix - cout
    margin_pct: float
    elasticity: float | None  # None si pas assez de data
    contribution: float  # marge * quantite


@dataclass
class CashProjection:
    current_cash: float
    projected_next_cycle: float
    projected_5_cycles: float
    trend: str  # "up", "down", "stable"


@dataclass
class PlateauDetection:
    is_plateau: bool
    confidence: float  # 0-1
    message: str


@dataclass
class GamePhase:
    phase: str  # "demarrage", "croissance", "plateau", "fin"
    description: str
    recommendation: str


@dataclass
class CalculationResults:
    product_metrics: list[ProductMetrics]
    cash_projection: CashProjection
    plateau: PlateauDetection
    game_phase: GamePhase
    total_central_stock: int
    regional_stock: dict[str, dict[str, int]]  # region -> product -> qty


# --- Couts de base (a terme, vient du OData) ---
BASE_COSTS = {
    "Milk": 15.00, "Cream": 50.00, "Yoghurt": 18.00,
    "Cheese": 55.00, "Butter": 40.00, "Ice Cream": 28.00,
}
STORAGE_COST_PER_UNIT = 0.02
TRANSPORT_COST_PER_UNIT = 0.05


def compute_metrics(
    current_data: ERPSimData,
    history: list[ERPSimData],
) -> CalculationResults:
    """Calcule toutes les metriques derivees a partir des donnees courantes et de l'historique."""

    product_metrics = _compute_product_metrics(current_data, history)
    cash_proj = _compute_cash_projection(current_data, history)
    plateau = _detect_plateau(history)
    phase = _identify_game_phase(current_data, history, plateau)
    central_stock, regional_stock = _parse_inventory(current_data)

    return CalculationResults(
        product_metrics=product_metrics,
        cash_projection=cash_proj,
        plateau=plateau,
        game_phase=phase,
        total_central_stock=central_stock,
        regional_stock=regional_stock,
    )


def _compute_product_metrics(
    current: ERPSimData, history: list[ERPSimData]
) -> list[ProductMetrics]:
    metrics = []
    elasticities = _compute_elasticities(history)

    for product in PRODUCTS:
        sales = [s for s in current.sales if s.product == product]
        total_qty = sum(s.quantity_sold for s in sales)
        total_rev = sum(s.revenue for s in sales)
        price = sales[0].price if sales else 0.0
        cost = BASE_COSTS.get(product, 1.0) + STORAGE_COST_PER_UNIT + TRANSPORT_COST_PER_UNIT
        margin = price - cost
        margin_pct = (margin / price * 100) if price > 0 else 0.0
        contribution = margin * total_qty

        metrics.append(ProductMetrics(
            product=product,
            current_price=price,
            total_quantity=total_qty,
            total_revenue=total_rev,
            cost_per_unit=cost,
            net_margin=round(margin, 2),
            margin_pct=round(margin_pct, 1),
            elasticity=elasticities.get(product),
            contribution=round(contribution, 2),
        ))

    # Trier par contribution decroissante
    metrics.sort(key=lambda m: m.contribution, reverse=True)
    return metrics


def _compute_elasticities(history: list[ERPSimData]) -> dict[str, float | None]:
    """Calcule l'elasticite-prix pour chaque produit.
    E = (dQ/Q) / (dP/P)
    """
    if len(history) < MIN_CYCLES_FOR_ELASTICITY:
        return {p: None for p in PRODUCTS}

    elasticities = {}
    for product in PRODUCTS:
        price_qty_pairs = []
        for snapshot in history:
            sales = [s for s in snapshot.sales if s.product == product]
            if sales:
                avg_price = sum(s.price for s in sales) / len(sales)
                total_qty = sum(s.quantity_sold for s in sales)
                price_qty_pairs.append((avg_price, total_qty))

        if len(price_qty_pairs) < 2:
            elasticities[product] = None
            continue

        # Calculer elasticite moyenne sur les paires consecutives
        e_values = []
        for i in range(1, len(price_qty_pairs)):
            p0, q0 = price_qty_pairs[i - 1]
            p1, q1 = price_qty_pairs[i]
            if p0 == p1 or q0 == 0 or p0 == 0:
                continue
            dq_q = (q1 - q0) / q0
            dp_p = (p1 - p0) / p0
            if abs(dp_p) > 0.001:
                e_values.append(dq_q / dp_p)

        elasticities[product] = round(sum(e_values) / len(e_values), 2) if e_values else None

    return elasticities


def _compute_cash_projection(
    current: ERPSimData, history: list[ERPSimData]
) -> CashProjection:
    if not current.financials:
        return CashProjection(0, 0, 0, "stable")

    cash = current.financials.cash

    # Calculer le delta cash moyen sur les derniers cycles
    cash_deltas = []
    for i in range(1, len(history)):
        if history[i].financials and history[i - 1].financials:
            delta = history[i].financials.cash - history[i - 1].financials.cash
            cash_deltas.append(delta)

    avg_delta = sum(cash_deltas) / len(cash_deltas) if cash_deltas else 0
    projected_1 = cash + avg_delta
    projected_5 = cash + avg_delta * 5

    if avg_delta > 500:
        trend = "up"
    elif avg_delta < -500:
        trend = "down"
    else:
        trend = "stable"

    return CashProjection(
        current_cash=round(cash, 2),
        projected_next_cycle=round(projected_1, 2),
        projected_5_cycles=round(projected_5, 2),
        trend=trend,
    )


def _detect_plateau(history: list[ERPSimData]) -> PlateauDetection:
    """Detecte un plateau de croissance sur les ventes globales."""
    if len(history) < 5:
        return PlateauDetection(False, 0.0, "Pas assez de donnees pour detecter un plateau")

    # Ventes totales par cycle (derniers 5 cycles)
    recent = history[-5:]
    totals = []
    for snapshot in recent:
        totals.append(sum(s.revenue for s in snapshot.sales))

    if not totals or totals[0] == 0:
        return PlateauDetection(False, 0.0, "Donnees insuffisantes")

    # Calculer le taux de croissance moyen
    growth_rates = []
    for i in range(1, len(totals)):
        if totals[i - 1] > 0:
            rate = (totals[i] - totals[i - 1]) / totals[i - 1]
            growth_rates.append(rate)

    avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0

    if avg_growth < 0.01:  # Moins de 1% de croissance
        confidence = min(1.0, (0.01 - avg_growth) * 50)
        return PlateauDetection(
            True, round(confidence, 2),
            f"Plateau detecte : croissance moyenne {avg_growth:.1%} sur 5 cycles"
        )

    return PlateauDetection(
        False, 0.0,
        f"Croissance saine : {avg_growth:.1%} par cycle"
    )


def _identify_game_phase(
    current: ERPSimData,
    history: list[ERPSimData],
    plateau: PlateauDetection,
) -> GamePhase:
    rnd = current.round_number

    if rnd <= MANUAL_ROUNDS:
        return GamePhase(
            "demarrage",
            f"Phase manuelle (round {rnd}/{MANUAL_ROUNDS})",
            "Distribuer le stock initial vers les regions. Pas de recommandation IA.",
        )

    if plateau.is_plateau:
        return GamePhase(
            "plateau",
            "Plateau de croissance detecte",
            "Transition Phase 2 : ajuster les prix agressivement sur les produits a forte marge.",
        )

    if len(history) > 25:
        return GamePhase(
            "fin",
            "Phase finale — maximiser la valorisation",
            "Consolider les marges, eviter les risques, maintenir la cote de credit.",
        )

    return GamePhase(
        "croissance",
        "Phase de croissance active",
        "Optimiser les prix par elasticite, pousser les volumes sur les produits rentables.",
    )


def _parse_inventory(data: ERPSimData) -> tuple[int, dict[str, dict[str, int]]]:
    central_total = 0
    regional: dict[str, dict[str, int]] = {r: {} for r in REGIONS}

    for inv in data.inventory:
        if inv.location == "Central":
            central_total += inv.quantity
        elif inv.location in regional:
            regional[inv.location][inv.product] = inv.quantity

    return central_total, regional
