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
            "Milk": 24.52, "Cream": 77.60, "Yoghurt": 28.52,
            "Cheese": 89.15, "Butter": 65.79, "Ice Cream": 47.55,
        }
        self._base_costs: dict[str, float] = {
            "Milk": 15.00, "Cream": 50.00, "Yoghurt": 18.00,
            "Cheese": 55.00, "Butter": 40.00, "Ice Cream": 28.00,
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


# --- Mapping SAP ---

STORAGE_TO_REGION = {
    "03": "Central",
    "03N": "Nord",
    "03S": "Sud",
    "03W": "Ouest",
}

AREA_TO_REGION = {
    "North": "Nord",
    "South": "Sud",
    "West": "Ouest",
}

MATERIAL_TO_PRODUCT = {
    "LL-T01": "Milk",
    "LL-T02": "Cream",
    "LL-T03": "Yoghurt",
    "LL-T04": "Cheese",
    "LL-T05": "Butter",
    "LL-T06": "Ice Cream",
}


# --- Client OData reel ---

class RealODataClient(ODataClient):
    """Client OData reel connecte a SAP ERPsim."""

    def __init__(self, base_url: str, username: str, password: str):
        import requests as _requests
        from requests.auth import HTTPBasicAuth
        self._base_url = base_url.rstrip("/")
        self._auth = HTTPBasicAuth(username, password)
        self._headers = {"Accept": "application/json"}
        self._session = _requests.Session()
        self._session.auth = self._auth
        self._session.headers.update(self._headers)
        self._session.verify = False
        self._connected = False
        self._last_error: str | None = None
        # Disable SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # Test connection
        try:
            r = self._session.get(f"{self._base_url}/Current_Game_Rules?$top=1&$format=json", timeout=10)
            self._connected = r.status_code == 200
        except Exception as e:
            self._last_error = str(e)

    def _get(self, entity: str, params: str = "") -> list[dict]:
        """GET sur une entite OData, retourne la liste de resultats."""
        url = f"{self._base_url}/{entity}?$format=json{params}"
        try:
            r = self._session.get(url, timeout=15)
            r.raise_for_status()
            return r.json().get("d", {}).get("results", [])
        except Exception as e:
            self._last_error = str(e)
            return []

    def fetch_data(self) -> ERPSimData:
        sales = self._fetch_sales()
        inventory = self._fetch_inventory()
        financials = self._fetch_financials()

        # Determiner le round courant
        round_number = 0
        if financials:
            round_number = int(financials.risk_rate)  # placeholder, on le calcule mieux
        # Prendre le max round des ventes
        if sales:
            round_number = max(s.round_number for s in sales)

        return ERPSimData(
            sales=sales,
            inventory=inventory,
            financials=financials,
            round_number=round_number,
        )

    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _fetch_sales(self) -> list[SalesRecord]:
        """Recupere les ventes du dernier round."""
        # Prendre les ventes les plus recentes
        rows = self._get("Sales", "&$orderby=SIM_ELAPSED_STEPS desc&$top=500")
        if not rows:
            return []

        # Trouver le dernier round
        max_round = max(row["SIM_ROUND"] for row in rows)
        latest = [r for r in rows if r["SIM_ROUND"] == max_round]

        records = []
        for row in latest:
            region = AREA_TO_REGION.get(row.get("AREA", ""), row.get("AREA", ""))
            product = row.get("MATERIAL_DESCRIPTION", "")
            records.append(SalesRecord(
                product=product,
                region=region,
                quantity_sold=int(row.get("QUANTITY", 0)),
                revenue=float(row.get("NET_VALUE", 0)),
                price=float(row.get("NET_PRICE", 0)),
                round_number=int(row.get("SIM_ROUND", "0")),
            ))
        return records

    def _fetch_inventory(self) -> list[InventoryRecord]:
        """Recupere le stock actuel via Current_Inventory."""
        rows = self._get("Current_Inventory")
        records = []
        for row in rows:
            location = STORAGE_TO_REGION.get(
                row.get("STORAGE_LOCATION", ""), row.get("STORAGE_LOCATION", "")
            )
            records.append(InventoryRecord(
                product=row.get("MATERIAL_DESCRIPTION", ""),
                location=location,
                quantity=int(row.get("STOCK", 0)),
            ))
        return records

    def _fetch_financials(self) -> FinancialData | None:
        """Recupere la derniere valorisation."""
        rows = self._get("Company_Valuation", "&$orderby=SIM_ELAPSED_STEPS desc&$top=1")
        if not rows:
            return None
        row = rows[0]
        cash = float(row.get("BANK_CASH_ACCOUNT", 0))
        debt = float(row.get("BANK_LOAN", 0))
        profit = float(row.get("PROFIT", 0))
        company_risk = float(row.get("COMPANY_RISK_RATE_PCT", 10))
        market_risk = float(row.get("MARKET_RISK_RATE_PCT", 7))
        total_risk = (company_risk + market_risk) / 100.0
        return FinancialData(
            cash=cash,
            debt=debt,
            credit_rating=row.get("CREDIT_RATING", "?"),
            valuation=float(row.get("COMPANY_VALUATION", 0)),
            profit=profit,
            risk_rate=total_risk,
        )

    def fetch_current_prices(self) -> dict[str, float]:
        """Recupere les prix actuels."""
        rows = self._get("Current_Pricing_Conditions")
        prices = {}
        for row in rows:
            product = row.get("MATERIAL_DESCRIPTION", "")
            price = float(row.get("PRICE", 0))
            prices[product] = price
        return prices

    def fetch_market_data(self) -> list[dict]:
        """Recupere les donnees du marche (toutes les equipes)."""
        rows = self._get("Market", "&$orderby=SIM_ROUND desc&$top=200")
        return rows


def get_client(use_mock: bool = True, **kwargs) -> ODataClient:
    """Factory pour obtenir le bon client."""
    if use_mock:
        return MockODataClient()
    return RealODataClient(**kwargs)
