"""Item-based collaborative filtering (cosine similarity on the order x product matrix)."""
import os

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from config import DB_PATH
from database import query_df

_cache: dict = {}


def _model():
    key = os.path.getmtime(DB_PATH)
    if _cache.get("key") != key:
        items = query_df("SELECT order_id, product_id FROM order_items")
        basket = pd.crosstab(items["order_id"], items["product_id"]).clip(upper=1)
        sim = cosine_similarity(basket.T.values)
        names = query_df("SELECT id, name, category, price FROM products").set_index("id")
        _cache.update(key=key, ids=list(basket.columns), sim=sim, names=names)
    return _cache


def _format(m, idx_scores, n):
    out = []
    for i, s in idx_scores[:n]:
        pid = m["ids"][i]
        row = m["names"].loc[pid]
        out.append({"product_id": int(pid), "name": row["name"], "category": row["category"],
                    "price": float(row["price"]), "score": round(float(s), 3)})
    return out


def similar_products(product_id: int, n: int = 5) -> list[dict]:
    m = _model()
    if product_id not in m["ids"]:
        return []
    row = m["sim"][m["ids"].index(product_id)].copy()
    row[m["ids"].index(product_id)] = -1
    top = sorted(enumerate(row), key=lambda x: x[1], reverse=True)
    return _format(m, top, n)


def recommend_for_customer(customer_id: int, n: int = 5) -> list[dict]:
    m = _model()
    hist = query_df(
        """SELECT oi.product_id, SUM(oi.qty) AS qty FROM orders o
           JOIN order_items oi ON oi.order_id = o.id WHERE o.customer_id = ? GROUP BY oi.product_id""",
        (customer_id,),
    )
    if hist.empty:  # cold start: fall back to global best-sellers
        top = query_df("SELECT product_id FROM order_items GROUP BY product_id ORDER BY SUM(qty) DESC LIMIT ?", (n,))
        return [{"product_id": int(p), "name": m["names"].loc[p, "name"], "category": m["names"].loc[p, "category"],
                 "price": float(m["names"].loc[p, "price"]), "score": 0.0} for p in top["product_id"]]
    scores = np.zeros(len(m["ids"]))
    bought = set()
    for pid, qty in zip(hist["product_id"], hist["qty"]):
        if pid in m["ids"]:
            scores += m["sim"][m["ids"].index(pid)] * np.log1p(qty)
            bought.add(m["ids"].index(pid))
    ranked = [(i, s) for i, s in sorted(enumerate(scores), key=lambda x: x[1], reverse=True) if i not in bought]
    return _format(m, ranked, n)
