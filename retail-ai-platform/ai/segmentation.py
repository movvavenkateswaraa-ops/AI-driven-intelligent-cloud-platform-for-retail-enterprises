"""Customer segmentation with RFM features + K-Means clustering."""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from database import query_df

NAMES = ["Champions", "Loyal customers", "Needs attention", "Dormant"]


def customer_segments(k: int = 4) -> dict:
    df = query_df(
        """SELECT c.id, c.name, c.city, MAX(o.order_date) AS last_order,
                  COUNT(DISTINCT o.id) AS frequency, SUM(oi.qty * oi.unit_price) AS monetary
           FROM customers c
           JOIN orders o ON o.customer_id = c.id
           JOIN order_items oi ON oi.order_id = o.id
           GROUP BY c.id"""
    )
    snapshot = pd.to_datetime(df["last_order"]).max() + pd.Timedelta(days=1)
    df["recency"] = (snapshot - pd.to_datetime(df["last_order"])).dt.days

    X = np.column_stack([df["recency"], np.log1p(df["frequency"]), np.log1p(df["monetary"])])
    Xs = StandardScaler().fit_transform(X)
    df["cluster"] = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(Xs)

    # Rank clusters by value score so labels are meaningful and stable.
    score = pd.DataFrame(Xs, columns=["r", "f", "m"]).assign(cluster=df["cluster"])
    score = score.groupby("cluster").mean()
    score["value"] = score["f"] + score["m"] - score["r"]
    rank = score["value"].sort_values(ascending=False).index.tolist()
    label = {c: NAMES[i] for i, c in enumerate(rank)}
    df["segment"] = df["cluster"].map(label)

    summary = (
        df.groupby("segment")
        .agg(customers=("id", "count"), avg_recency_days=("recency", "mean"),
             avg_orders=("frequency", "mean"), avg_spend=("monetary", "mean"), total_spend=("monetary", "sum"))
        .round(1).reset_index()
    )
    summary["order"] = summary["segment"].map({n: i for i, n in enumerate(NAMES)})
    summary = summary.sort_values("order").drop(columns="order")
    actions = {
        "Champions": "Reward with early access and loyalty perks.",
        "Loyal customers": "Upsell bundles and ask for reviews.",
        "Needs attention": "Send a time-limited offer on favourite categories.",
        "Dormant": "Run a win-back campaign with a discount code.",
    }
    summary["recommended_action"] = summary["segment"].map(actions)
    top = df.sort_values("monetary", ascending=False).head(10)[["id", "name", "city", "segment", "monetary"]]
    return {"segments": summary.to_dict("records"), "top_customers": top.round(0).to_dict("records")}
