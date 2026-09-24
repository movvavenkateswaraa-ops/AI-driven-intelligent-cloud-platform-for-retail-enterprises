"""Demand-driven inventory optimisation: forecasts per-product demand and flags stock-out risk."""
import math

import pandas as pd

from database import query_df


def inventory_report(lookback_days: int = 60) -> list[dict]:
    products = query_df("SELECT * FROM products")
    sales = query_df(
        """SELECT o.order_date AS date, oi.product_id, SUM(oi.qty) AS qty
           FROM orders o JOIN order_items oi ON oi.order_id = o.id GROUP BY 1, 2"""
    )
    sales["date"] = pd.to_datetime(sales["date"])
    end = sales["date"].max()
    window = sales[sales["date"] > end - pd.Timedelta(days=lookback_days)]
    daily = window.pivot_table(index="date", columns="product_id", values="qty", aggfunc="sum")
    daily = daily.reindex(pd.date_range(end - pd.Timedelta(days=lookback_days - 1), end)).fillna(0)
    # Exponentially weighted mean gives recent days more influence than old ones.
    demand = daily.ewm(span=14).mean().iloc[-1]

    rows = []
    for p in products.itertuples():
        rate = float(demand.get(p.id, 0.0))
        cover = p.stock / rate if rate > 0.01 else 999.0
        if cover < p.lead_time_days:
            status = "critical"
        elif cover < p.lead_time_days + 7 or p.stock <= p.reorder_level:
            status = "low"
        else:
            status = "healthy"
        target = rate * (p.lead_time_days + 14)  # lead-time demand + 14 days safety stock
        rows.append({
            "id": int(p.id), "name": p.name, "category": p.category, "stock": int(p.stock),
            "daily_demand": round(rate, 2), "days_of_cover": round(min(cover, 999.0), 1),
            "lead_time_days": int(p.lead_time_days), "status": status,
            "suggested_order_qty": int(max(0, math.ceil(target - p.stock))),
        })
    order = {"critical": 0, "low": 1, "healthy": 2}
    rows.sort(key=lambda r: (order[r["status"]], r["days_of_cover"]))
    return rows
