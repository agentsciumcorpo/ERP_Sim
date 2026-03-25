"""Garde-fous codes en dur pour proteger l'equipe."""

from __future__ import annotations

from dataclasses import dataclass
from src.config import (
    CASH_MINIMUM,
    MAX_PRICE_CHANGE_PCT,
    WAREHOUSE_CAPACITY,
    WAREHOUSE_WARNING_THRESHOLD,
)


@dataclass
class GuardrailResult:
    allowed: bool
    original_value: float
    adjusted_value: float
    reason: str


@dataclass
class GuardrailReport:
    price_checks: dict[str, GuardrailResult]
    stock_alert: str | None
    cash_alert: str | None
    vetoes: list[str]


def check_price_change(
    product: str, current_price: float, proposed_price: float
) -> GuardrailResult:
    """Verifie que le changement de prix ne depasse pas 15%."""
    if current_price <= 0:
        return GuardrailResult(True, current_price, proposed_price, "Prix initial")

    change_pct = abs(proposed_price - current_price) / current_price

    if change_pct > MAX_PRICE_CHANGE_PCT:
        # Plafonner a 15%
        direction = 1 if proposed_price > current_price else -1
        adjusted = current_price * (1 + direction * MAX_PRICE_CHANGE_PCT)
        adjusted = round(adjusted, 2)
        return GuardrailResult(
            allowed=False,
            original_value=proposed_price,
            adjusted_value=adjusted,
            reason=f"{product}: variation {change_pct:.0%} > {MAX_PRICE_CHANGE_PCT:.0%} max — plafonne a {adjusted}",
        )

    return GuardrailResult(True, proposed_price, proposed_price, "OK")


def check_stock_level(central_stock: int) -> str | None:
    """Alerte si le stock central approche la capacite max."""
    if central_stock >= WAREHOUSE_CAPACITY:
        return f"CRITIQUE: Stock central {central_stock} >= {WAREHOUSE_CAPACITY} — penalite {300}$/jour active!"
    if central_stock >= WAREHOUSE_WARNING_THRESHOLD:
        return f"ATTENTION: Stock central {central_stock} — seuil d'alerte {WAREHOUSE_WARNING_THRESHOLD} depasse"
    return None


def check_cash_level(current_cash: float, proposed_expense: float = 0) -> str | None:
    """Alerte si le cash risque de passer sous le minimum."""
    remaining = current_cash - proposed_expense
    if remaining < 0:
        return f"VETO: Operation refusee — cash deviendrait negatif ({remaining:.0f} EUR)"
    if remaining < CASH_MINIMUM:
        return f"ATTENTION: Cash apres operation {remaining:.0f} EUR < seuil minimum {CASH_MINIMUM:.0f} EUR"
    return None


def apply_guardrails(
    proposed_prices: dict[str, float],
    current_prices: dict[str, float],
    central_stock: int,
    current_cash: float,
) -> GuardrailReport:
    """Applique tous les garde-fous et retourne un rapport."""
    price_checks = {}
    vetoes = []

    for product, proposed in proposed_prices.items():
        current = current_prices.get(product, proposed)
        result = check_price_change(product, current, proposed)
        price_checks[product] = result
        if not result.allowed:
            vetoes.append(result.reason)

    stock_alert = check_stock_level(central_stock)
    cash_alert = check_cash_level(current_cash)

    if cash_alert and cash_alert.startswith("VETO"):
        vetoes.append(cash_alert)

    return GuardrailReport(
        price_checks=price_checks,
        stock_alert=stock_alert,
        cash_alert=cash_alert,
        vetoes=vetoes,
    )
