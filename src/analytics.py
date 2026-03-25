"""Calculs analytiques enrichis a partir des donnees historiques."""

from __future__ import annotations

import pandas as pd
import numpy as np
from src.data_loader import GameData, PRODUCTS, REGIONS


def compute_real_margins(data: GameData) -> pd.DataFrame:
    """Marge reelle par produit avec les vrais couts d'achat PO."""
    rows = []
    for prod in PRODUCTS:
        cost = data.purchase_costs.get(prod, 0)
        price = data.current_prices.get(prod, 0)
        margin = price - cost if cost > 0 else 0
        margin_pct = (margin / price * 100) if price > 0 else 0

        # Volumes vendus
        prod_sales = data.sales[data.sales["product"] == prod] if len(data.sales) > 0 else pd.DataFrame()
        total_qty = int(prod_sales["qty"].sum()) if len(prod_sales) > 0 else 0
        total_rev = prod_sales["revenue"].sum() if len(prod_sales) > 0 else 0

        # Stock total commande
        total_ordered = sum(po.quantity for po in data.purchase_orders if po.product == prod)
        # Stock restant
        prod_stock = data.current_stock[data.current_stock["product"] == prod] if len(data.current_stock) > 0 else pd.DataFrame()
        remaining = int(prod_stock["stock"].sum()) if len(prod_stock) > 0 else 0
        turnover_pct = (total_qty / total_ordered * 100) if total_ordered > 0 else 0

        contribution = margin * total_qty

        rows.append({
            "product": prod,
            "price": price,
            "cost": round(cost, 2),
            "margin": round(margin, 2),
            "margin_pct": round(margin_pct, 1),
            "qty_sold": total_qty,
            "revenue": round(total_rev, 0),
            "qty_ordered": total_ordered,
            "qty_remaining": remaining,
            "turnover_pct": round(turnover_pct, 1),
            "contribution": round(contribution, 0),
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("contribution", ascending=False).reset_index(drop=True)
    return df


def compute_sales_by_round(data: GameData) -> pd.DataFrame:
    """Ventes agregees par round et produit."""
    if len(data.sales) == 0:
        return pd.DataFrame()
    grouped = data.sales.groupby(["round", "product"]).agg(
        qty=("qty", "sum"),
        revenue=("revenue", "sum"),
        avg_price=("price", "mean"),
    ).reset_index()
    return grouped


def compute_sales_by_region(data: GameData) -> pd.DataFrame:
    """Ventes agregees par region et produit."""
    if len(data.sales) == 0:
        return pd.DataFrame()
    grouped = data.sales.groupby(["region", "product"]).agg(
        qty=("qty", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()
    return grouped


def compute_stock_timeline(data: GameData) -> pd.DataFrame:
    """Stock total par step (pour graphe d'evolution)."""
    if len(data.inventory) == 0:
        return pd.DataFrame()

    # Stock total par step
    total = data.inventory.groupby("elapsed").agg(
        total=("balance", "sum"),
    ).reset_index()

    # Stock central par step
    central = data.inventory[data.inventory["location"] == "Central"].groupby("elapsed").agg(
        central=("balance", "sum"),
    ).reset_index()

    # Stock regions par step
    regions = data.inventory[data.inventory["location"] != "Central"].groupby("elapsed").agg(
        regions=("balance", "sum"),
    ).reset_index()

    df = total.merge(central, on="elapsed", how="left").merge(regions, on="elapsed", how="left")
    df = df.fillna(0)
    return df


def compute_stock_heatmap(data: GameData) -> pd.DataFrame:
    """Stock actuel par produit x location pour heatmap."""
    if len(data.current_stock) == 0:
        return pd.DataFrame()
    pivot = data.current_stock.pivot_table(
        index="product", columns="location", values="stock", fill_value=0, aggfunc="sum"
    )
    # Reorder columns
    cols = ["Central"] + [r for r in REGIONS if r in pivot.columns]
    pivot = pivot.reindex(columns=cols, fill_value=0)
    pivot["Total"] = pivot.sum(axis=1)
    return pivot


def compute_penalty_steps(data: GameData) -> pd.DataFrame:
    """Identifie les steps ou une penalite de stockage s'applique."""
    if len(data.inventory) == 0:
        return pd.DataFrame()

    stock_per_step = data.inventory[data.inventory["location"] == "Central"].groupby("elapsed").agg(
        central_stock=("balance", "sum"),
    ).reset_index()

    penalties = stock_per_step[stock_per_step["central_stock"] > 4000].copy()
    penalties["penalty_eur"] = 300
    return penalties


def compute_po_summary(data: GameData) -> pd.DataFrame:
    """Resume des POs avec cout et timing."""
    if not data.purchase_orders:
        return pd.DataFrame()

    rows = []
    # Group by PO number
    po_groups: dict[str, list] = {}
    for po in data.purchase_orders:
        if po.po_number not in po_groups:
            po_groups[po.po_number] = []
        po_groups[po.po_number].append(po)

    for po_num, items in po_groups.items():
        total_qty = sum(p.quantity for p in items)
        total_cost = sum(p.total_cost for p in items)
        delivery = f"R{items[0].delivery_round:02d}S{items[0].delivery_step:02d}"
        products = ", ".join(f"{p.product} x{p.quantity}" for p in items)
        rows.append({
            "po_number": po_num,
            "delivery": delivery,
            "delivery_elapsed": items[0].delivery_elapsed,
            "total_qty": total_qty,
            "goods_cost": round(total_cost, 0),
            "po_fee": 1000,
            "total_cost": round(total_cost + 1000, 0),
            "products": products,
        })

    return pd.DataFrame(rows)


def compute_market_comparison(data: GameData, our_company: str = "LL") -> pd.DataFrame:
    """Compare nos prix et volumes avec le marche."""
    if len(data.market) == 0:
        return pd.DataFrame()

    # Dernier round du marche
    max_round = data.market["round"].max()
    latest = data.market[data.market["round"] == max_round].copy()

    # Agreger par produit: nous vs les autres
    rows = []
    for prod in PRODUCTS:
        prod_data = latest[latest["product"] == prod]
        ours = prod_data[prod_data["company"] == our_company]
        others = prod_data[prod_data["company"] != our_company]

        our_qty = int(ours["qty"].sum()) if len(ours) > 0 else 0
        our_rev = ours["revenue"].sum() if len(ours) > 0 else 0
        our_avg_price = (our_rev / our_qty) if our_qty > 0 else 0

        market_qty = int(others["qty"].sum()) if len(others) > 0 else 0
        market_rev = others["revenue"].sum() if len(others) > 0 else 0
        market_avg_price = (market_rev / market_qty) if market_qty > 0 else 0

        total_qty = our_qty + market_qty
        market_share = (our_qty / total_qty * 100) if total_qty > 0 else 0
        price_diff_pct = ((our_avg_price - market_avg_price) / market_avg_price * 100) if market_avg_price > 0 else 0

        rows.append({
            "product": prod,
            "our_qty": our_qty,
            "our_price": round(our_avg_price, 2),
            "our_revenue": round(our_rev, 0),
            "market_qty": market_qty,
            "market_price": round(market_avg_price, 2),
            "market_share_pct": round(market_share, 1),
            "price_vs_market_pct": round(price_diff_pct, 1),
        })

    return pd.DataFrame(rows)


def compute_volume_evolution(data: GameData) -> pd.DataFrame:
    """Evolution des volumes par produit et par round."""
    if len(data.sales) == 0:
        return pd.DataFrame()

    pivot = data.sales.groupby(["round", "product"]).agg(
        qty=("qty", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()

    return pivot


def compute_cash_flow_events(data: GameData) -> pd.DataFrame:
    """Timeline des evenements financiers (PO livrees, paiements, penalites)."""
    events = []

    # PO deliveries
    for po in data.purchase_orders:
        events.append({
            "elapsed": po.delivery_elapsed,
            "type": "PO Livraison",
            "description": f"{po.product} x{po.quantity}",
            "amount": 0,
        })

    # PO payments (5 days after delivery)
    po_groups: dict[str, list] = {}
    for po in data.purchase_orders:
        if po.po_number not in po_groups:
            po_groups[po.po_number] = []
        po_groups[po.po_number].append(po)

    for po_num, items in po_groups.items():
        total_cost = sum(p.total_cost for p in items) + 1000
        payment_step = items[0].delivery_elapsed + 5
        events.append({
            "elapsed": payment_step,
            "type": "PO Paiement",
            "description": f"PO {po_num}",
            "amount": -total_cost,
        })

    # Penalties
    penalties = compute_penalty_steps(data)
    if len(penalties) > 0:
        for _, row in penalties.iterrows():
            events.append({
                "elapsed": int(row["elapsed"]),
                "type": "Penalite stock",
                "description": f"Central > 4000 ({int(row['central_stock'])})",
                "amount": -300,
            })

    df = pd.DataFrame(events)
    if len(df) > 0:
        df = df.sort_values("elapsed").reset_index(drop=True)
    return df
