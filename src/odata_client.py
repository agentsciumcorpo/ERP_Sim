"""Client OData pour SAP ERPsim avec mode mock."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol

from src.config import PRODUCTS, REGIONS, STARTING_CASH


# --- Data models ---

@dataclass
class SalesRecord:
    product: str
    region: str
    quantity_sold: int
    revenue: float
    price: float
    round_number: int


@dataclass
class InventoryRecord:
    product: str
    location: str  # "Central" ou region
    quantity: int


@dataclass
class FinancialData:
    cash: float
    debt: float
    credit_rating: str  # "AAA+", "AA", etc.
    valuation: float
    profit: float
    risk_rate: float


@dataclass
class ERPSimData:
    """Snapshot complet d'un cycle ERPsim."""
    sales: list[SalesRecord] = field(default_factory=list)
    inventory: list[InventoryRecord] = field(default_factory=list)
    financials: FinancialData | None = None
    round_number: int = 0


# --- Interface client ---

class ODataClient(ABC):
    @abstractmethod
    def fetch_data(self) -> ERPSimData:
        """Recupere toutes les donnees d'un cycle."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...


# --- Client Mock ---

class MockODataClient(ODataClient):
    """Client mock pour developper sans SAP."""

    def __init__(self):
        self._round = 0
        self._prices: dict[str, float] = {
            "Lait": 2.50, "Creme": 3.80, "Yaourt": 2.40,
            "Fromage": 5.20, "Beurre": 4.10, "Glace": 3.50,
        }
        self._base_costs: dict[str, float] = {
            "Lait": 1.20, "Creme": 2.00, "Yaourt": 1.30,
            "Fromage": 2.80, "Beurre": 2.20, "Glace": 1.80,
        }
        self._cash = float(STARTING_CASH)
        self._central_stock = 3500
        self._regional_stock = {r: {p: 150 for p in PRODUCTS} for r in REGIONS}
        self._cumulative_profit = 0.0

    def set_prices(self, prices: dict[str, float]):
        """Permet a l'orchestrateur de mettre a jour les prix pour simuler l'impact."""
        self._prices.update(prices)

    def fetch_data(self) -> ERPSimData:
        self._round += 1
        sales = self._generate_sales()
        inventory = self._generate_inventory()
        financials = self._generate_financials(sales)
        return ERPSimData(
            sales=sales,
            inventory=inventory,
            financials=financials,
            round_number=self._round,
        )

    def is_connected(self) -> bool:
        return True

    def _generate_sales(self) -> list[SalesRecord]:
        records = []
        from src.config import REGIONAL_PREFERENCES
        for region in REGIONS:
            for product in PRODUCTS:
                pref = REGIONAL_PREFERENCES[region][product]
                base_demand = int(30 * pref)
                # Simuler elasticite: prix plus haut → moins de ventes
                price = self._prices[product]
                price_factor = max(0.3, 1.0 - (price - 2.5) * 0.15)
                # Ajouter du bruit
                noise = random.uniform(0.8, 1.2)
                # Croissance legere avec les rounds
                growth = 1.0 + self._round * 0.02
                qty = max(1, int(base_demand * price_factor * noise * growth))
                revenue = qty * price
                records.append(SalesRecord(
                    product=product,
                    region=region,
                    quantity_sold=qty,
                    revenue=revenue,
                    price=price,
                    round_number=self._round,
                ))
        return records

    def _generate_inventory(self) -> list[InventoryRecord]:
        records = []
        # Stock central fluctue
        self._central_stock += random.randint(-200, 300)
        self._central_stock = max(500, min(4200, self._central_stock))
        for product in PRODUCTS:
            share = self._central_stock // len(PRODUCTS)
            records.append(InventoryRecord(
                product=product,
                location="Central",
                quantity=share + random.randint(-50, 50),
            ))
        # Stocks regionaux
        for region in REGIONS:
            for product in PRODUCTS:
                self._regional_stock[region][product] += random.randint(-30, 40)
                self._regional_stock[region][product] = max(
                    0, self._regional_stock[region][product]
                )
                records.append(InventoryRecord(
                    product=product,
                    location=region,
                    quantity=self._regional_stock[region][product],
                ))
        return records

    def _generate_financials(self, sales: list[SalesRecord]) -> FinancialData:
        total_revenue = sum(s.revenue for s in sales)
        total_cost = sum(
            s.quantity_sold * self._base_costs[s.product] for s in sales
        )
        cycle_profit = total_revenue - total_cost
        self._cumulative_profit += cycle_profit
        self._cash += cycle_profit * 0.7  # 70% en cash
        # Credit rating basé sur le cash
        if self._cash > 200_000:
            rating = "AAA+"
        elif self._cash > 100_000:
            rating = "AA"
        elif self._cash > 50_000:
            rating = "A"
        elif self._cash > 0:
            rating = "BBB"
        else:
            rating = "D"
        # Risk rate selon rating
        risk_rates = {"AAA+": 0.05, "AA": 0.08, "A": 0.12, "BBB": 0.18, "D": 0.35}
        risk_rate = risk_rates.get(rating, 0.20)
        valuation = self._cumulative_profit / risk_rate if risk_rate > 0 else 0
        return FinancialData(
            cash=round(self._cash, 2),
            debt=0.0,
            credit_rating=rating,
            valuation=round(valuation, 2),
            profit=round(self._cumulative_profit, 2),
            risk_rate=risk_rate,
        )


# --- Client OData reel (placeholder) ---

class RealODataClient(ODataClient):
    """Client OData reel via PyOData. A completer avec les vrais endpoints."""

    def __init__(self, base_url: str, username: str, password: str):
        self._base_url = base_url
        self._username = username
        self._password = password
        self._connected = False

    def fetch_data(self) -> ERPSimData:
        # TODO: Implementer avec PyOData quand on aura acces au $metadata SAP
        raise NotImplementedError("Connecter PyOData apres acces au $metadata SAP")

    def is_connected(self) -> bool:
        return self._connected


def get_client(use_mock: bool = True, **kwargs) -> ODataClient:
    """Factory pour obtenir le bon client."""
    if use_mock:
        return MockODataClient()
    return RealODataClient(**kwargs)
