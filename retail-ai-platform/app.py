"""Flask API + dashboard for the AI-Driven Intelligent Cloud Platform for Retail Enterprises."""
import pandas as pd
from flask import Flask, jsonify, render_template, request

import seed_data
from ai import forecasting, inventory, recommender, segmentation, sentiment
from config import CURRENCY, DEBUG, PORT
from database import db_is_empty, init_db, query_df


def create_app() -> Flask:
    app = Flask(__name__)
    init_db()
    if db_is_empty():
        seed_data.seed()

    @app.get("/")
    def index():
        return render_template("index.html", currency=CURRENCY)

    @app.get("/health")
    def health():  # used by load balancers / container orchestrators
        return jsonify(status="ok")

    @app.get("/api/summary")
    def summary():
        daily = forecasting.daily_revenue()
        end = daily.index[-1]
        last30 = float(daily[daily.index > end - pd.Timedelta(days=30)].sum())
        prev30 = float(daily[(daily.index <= end - pd.Timedelta(days=30)) &
                             (daily.index > end - pd.Timedelta(days=60))].sum())
        totals = query_df(
            """SELECT COUNT(DISTINCT o.id) AS orders, COUNT(DISTINCT o.customer_id) AS customers,
                      SUM(oi.qty * oi.unit_price) AS revenue
               FROM orders o JOIN order_items oi ON oi.order_id = o.id"""
        ).iloc[0]
        cats = query_df(
            """SELECT p.category, ROUND(SUM(oi.qty * oi.unit_price)) AS revenue
               FROM order_items oi JOIN products p ON p.id = oi.product_id
               GROUP BY p.category ORDER BY revenue DESC"""
        )
        top = query_df(
            """SELECT p.name, SUM(oi.qty) AS units FROM order_items oi
               JOIN products p ON p.id = oi.product_id GROUP BY p.id ORDER BY units DESC LIMIT 5"""
        )
        stock_alerts = sum(1 for r in inventory.inventory_report() if r["status"] != "healthy")
        return jsonify(
            revenue=round(float(totals["revenue"])), orders=int(totals["orders"]), customers=int(totals["customers"]),
            avg_order_value=round(float(totals["revenue"]) / int(totals["orders"])),
            last30_revenue=round(last30), growth_pct=round((last30 / prev30 - 1) * 100, 1) if prev30 else None,
            stock_alerts=stock_alerts, categories=cats.to_dict("records"), top_products=top.to_dict("records"),
        )

    @app.get("/api/forecast")
    def forecast():
        days = max(1, min(int(request.args.get("days", 14)), 90))
        return jsonify(forecasting.forecast_revenue(horizon=days))

    @app.get("/api/segments")
    def segments():
        return jsonify(segmentation.customer_segments())

    @app.get("/api/inventory")
    def inventory_api():
        rows = inventory.inventory_report()
        status = request.args.get("status")
        if status:
            rows = [r for r in rows if r["status"] == status]
        return jsonify(rows)

    @app.get("/api/products")
    def products():
        return jsonify(query_df("SELECT id, name, category, price FROM products ORDER BY category, name").to_dict("records"))

    @app.get("/api/recommendations/product/<int:product_id>")
    def rec_product(product_id):
        return jsonify(recommender.similar_products(product_id, int(request.args.get("n", 5))))

    @app.get("/api/recommendations/customer/<int:customer_id>")
    def rec_customer(customer_id):
        return jsonify(recommender.recommend_for_customer(customer_id, int(request.args.get("n", 5))))

    @app.get("/api/sentiment")
    def sentiment_api():
        return jsonify(sentiment.sentiment_report())

    @app.post("/api/sentiment/analyze")
    def analyze():
        text = (request.get_json(silent=True) or {}).get("text", "").strip()
        if not text:
            return jsonify(error="Send JSON like {\"text\": \"your review\"}"), 400
        s = sentiment.score_text(text)
        return jsonify(score=round(s, 2), label=sentiment.label(s))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
