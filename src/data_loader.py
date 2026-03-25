"""Chargement complet des donnees historiques SAP ERPsim."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from collections import defaultdict

import requests
from requests.auth import HTTPBasicAuth
import urllib3
import pandas as pd

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STORAGE_TO_REGION = {"03": "Central", "03N": "Nord", "03S": "Sud", "03W": "Ouest"}
AREA_TO_REGION = {"North": "Nord", "South": "Sud", "West": "Ouest"}
PRODUCTS = ["Milk", "Cream", "Yoghurt", "Cheese", "Butter", "Ice Cream"]
REGIONS = ["Nord", "Sud", "Ouest"]


@dataclass
class PurchaseOrder:
    po_number: str
    product: str
    material_number: str
    quantity: int
    unit_price: float
    total_cost: float
    status: str
    delivery_round: int
    delivery_step: int
    delivery_elapsed: int


@dataclass
class GameData:
    """Toutes les donnees historiques du jeu."""
    # DataFrames pandas pour faciliter le plotting
    financials: pd.DataFrame  # step, cash, profit, loan, credit, valuation, risk_rate
    sales: pd.DataFrame  # step, round, product, region, qty, revenue, price
    inventory: pd.DataFrame  # step, round, product, location, balance
    purchase_orders: list[PurchaseOrder]
    market: pd.DataFrame  # round, company, product, region, qty, avg_price, revenue
    current_prices: dict[str, float]
    current_stock: pd.DataFrame  # product, location, stock
    game_rules: dict[str, str]
    # Derived
    purchase_costs: dict[str, float]  # cout moyen par produit
    max_elapsed_step: int = 0
    current_round: int = 0


class SAPDataLoader:
    """Charge toutes les donnees historiques depuis SAP OData."""

    def __init__(self, base_url: str = "", username: str = "", password: str = ""):
        self._base_url = (base_url or os.getenv("SAP_BASE_URL", "")).rstrip("/")
        self._session = requests.Session()
        self._session.auth = HTTPBasicAuth(
            username or os.getenv("SAP_USERNAME", ""),
            password or os.getenv("SAP_PASSWORD", ""),
        )
        self._session.headers.update({"Accept": "application/json"})
        self._session.verify = False
        self._connected = False

        try:
            r = self._session.get(
                f"{self._base_url}/Current_Game_Rules?$top=1&$format=json", timeout=10
            )
            self._connected = r.status_code == 200
        except Exception:
            pass

    @property
    def connected(self) -> bool:
        return self._connected

    def _get(self, entity: str, params: str = "") -> list[dict]:
        url = f"{self._base_url}/{entity}?$format=json{params}"
        r = self._session.get(url, timeout=20)
        r.raise_for_status()
        return r.json().get("d", {}).get("results", [])

    def load_all(self) -> GameData:
        """Charge toutes les donnees en une fois."""
        financials = self._load_financials()
        sales = self._load_sales()
        inventory = self._load_inventory()
        pos = self._load_purchase_orders()
        market = self._load_market()
        prices = self._load_current_prices()
        stock = self._load_current_stock()
        rules = self._load_game_rules()

        # Cout moyen d'achat par produit (depuis les POs)
        purchase_costs = {}
        cost_totals = defaultdict(lambda: {"cost": 0.0, "qty": 0})
        for po in pos:
            cost_totals[po.product]["cost"] += po.total_cost
            cost_totals[po.product]["qty"] += po.quantity
        for prod, v in cost_totals.items():
            purchase_costs[prod] = v["cost"] / v["qty"] if v["qty"] > 0 else 0

        max_step = int(financials["elapsed"].max()) if len(financials) > 0 else 0
        current_round = int(financials["round"].max()) if len(financials) > 0 else 0

        return GameData(
            financials=financials,
            sales=sales,
            inventory=inventory,
            purchase_orders=pos,
            market=market,
            current_prices=prices,
            current_stock=stock,
            game_rules=rules,
            purchase_costs=purchase_costs,
            max_elapsed_step=max_step,
            current_round=current_round,
        )

    def _load_financials(self) -> pd.DataFrame:
        rows = self._get("Company_Valuation", "&$orderby=SIM_ELAPSED_STEPS asc")
        records = []
        for r in rows:
            records.append({
                "elapsed": int(r["SIM_ELAPSED_STEPS"]),
                "round": int(r["SIM_ROUND"]),
                "step": int(r["SIM_STEP"]),
                "label": f"R{r['SIM_ROUND']}S{r['SIM_STEP']}",
                "cash": float(r["BANK_CASH_ACCOUNT"]),
                "profit": float(r["PROFIT"]),
                "loan": float(r["BANK_LOAN"]),
                "credit": r["CREDIT_RATING"],
                "valuation": float(r["COMPANY_VALUATION"]),
                "risk_company": float(r["COMPANY_RISK_RATE_PCT"]),
                "risk_market": float(r["MARKET_RISK_RATE_PCT"]),
                "receivables": float(r.get("ACCOUNTS_RECEIVABLE", 0)),
                "payables": float(r.get("ACCOUNTS_PAYABLE", 0)),
            })
        return pd.DataFrame(records)

    def _load_sales(self) -> pd.DataFrame:
        rows = self._get("Sales", "&$orderby=SIM_ELAPSED_STEPS asc")
        records = []
        for r in rows:
            records.append({
                "elapsed": int(r["SIM_ELAPSED_STEPS"]),
                "round": int(r["SIM_ROUND"]),
                "step": int(r["SIM_STEP"]),
                "product": r["MATERIAL_DESCRIPTION"],
                "material": r["MATERIAL_NUMBER"],
                "region": AREA_TO_REGION.get(r.get("AREA", ""), r.get("AREA", "")),
                "area_raw": r.get("AREA", ""),
                "qty": int(r["QUANTITY"]),
                "revenue": float(r["NET_VALUE"]),
                "price": float(r["NET_PRICE"]),
                "cost": float(r.get("COST", 0)),
            })
        return pd.DataFrame(records)

    def _load_inventory(self) -> pd.DataFrame:
        rows = self._get("Inventory", "&$orderby=SIM_ELAPSED_STEPS asc")
        records = []
        for r in rows:
            loc = STORAGE_TO_REGION.get(r["STORAGE_LOCATION"], r["STORAGE_LOCATION"])
            records.append({
                "elapsed": int(r["SIM_ELAPSED_STEPS"]),
                "round": int(r["SIM_ROUND"]),
                "step": int(r["SIM_STEP"]),
                "product": r["MATERIAL_DESCRIPTION"],
                "location": loc,
                "balance": int(r["INVENTORY_OPENING_BALANCE"]),
            })
        return pd.DataFrame(records)

    def _load_purchase_orders(self) -> list[PurchaseOrder]:
        rows = self._get("Purchase_Orders")
        pos = []
        for r in rows:
            qty = int(r["QUANTITY"])
            price = float(r["UNIT_PRICE"])
            gr_round = int(r.get("GOODS_RECEIPT_ROUND", 0))
            gr_step = int(r.get("GOODS_RECEIPT_STEP", 0))
            pos.append(PurchaseOrder(
                po_number=r["PURCHASING_ORDER"],
                product=r["MATERIAL_DESCRIPTION"],
                material_number=r["MATERIAL_NUMBER"],
                quantity=qty,
                unit_price=price,
                total_cost=qty * price,
                status=r["STATUS"],
                delivery_round=gr_round,
                delivery_step=gr_step,
                delivery_elapsed=(gr_round - 1) * 10 + gr_step if gr_round > 0 else 0,
            ))
        return pos

    def _load_market(self) -> pd.DataFrame:
        rows = self._get("Market", "&$orderby=SIM_ROUND desc")
        records = []
        for r in rows:
            records.append({
                "round": int(r["SIM_ROUND"]),
                "company": r["COMPANY_CODE"],
                "product": r["MATERIAL_DESCRIPTION"],
                "region": AREA_TO_REGION.get(r.get("AREA", ""), r.get("AREA", "")),
                "area_raw": r.get("AREA", ""),
                "qty": int(r["QUANTITY"]),
                "avg_price": float(r["AVERAGE_PRICE"]),
                "revenue": float(r["NET_VALUE"]),
                "channel": r.get("DISTRIBUTION_CHANNEL", ""),
            })
        return pd.DataFrame(records)

    def _load_current_prices(self) -> dict[str, float]:
        rows = self._get("Current_Pricing_Conditions")
        return {r["MATERIAL_DESCRIPTION"]: float(r["PRICE"]) for r in rows}

    def _load_current_stock(self) -> pd.DataFrame:
        rows = self._get("Current_Inventory")
        records = []
        for r in rows:
            loc = STORAGE_TO_REGION.get(r["STORAGE_LOCATION"], r["STORAGE_LOCATION"])
            records.append({
                "product": r["MATERIAL_DESCRIPTION"],
                "location": loc,
                "stock": int(r["STOCK"]),
            })
        return pd.DataFrame(records)

    def _load_game_rules(self) -> dict[str, str]:
        rows = self._get("Current_Game_Rules")
        rules = {}
        for r in rows:
            key = f"{r['CATEGORY']}.{r['ELEMENT']}.{r['DETAIL']}"
            rules[key] = r["VALUE"]
        return rules
