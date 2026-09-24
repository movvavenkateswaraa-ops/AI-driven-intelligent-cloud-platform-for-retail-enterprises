import os
import sys
import tempfile

import pytest

# Use an isolated database for tests (must be set before importing the app).
os.environ["RETAIL_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from ai.sentiment import score_text, label  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return create_app().test_client()


def test_health(client):
    assert client.get("/health").json == {"status": "ok"}


def test_dashboard_page(client):
    assert b"Retail Intelligence Platform" in client.get("/").data


def test_summary(client):
    d = client.get("/api/summary").json
    assert d["orders"] > 0 and d["revenue"] > 0 and len(d["categories"]) > 0


def test_forecast_length_and_bounds(client):
    d = client.get("/api/forecast?days=10").json
    assert len(d["forecast"]) == 10
    assert all(r["lower"] <= r["revenue"] <= r["upper"] for r in d["forecast"])


def test_segments_cover_all_customers(client):
    d = client.get("/api/segments").json
    assert {s["segment"] for s in d["segments"]} == {"Champions", "Loyal customers", "Needs attention", "Dormant"}


def test_inventory_status_filter(client):
    rows = client.get("/api/inventory?status=healthy").json
    assert all(r["status"] == "healthy" for r in rows)


def test_recommendations(client):
    recs = client.get("/api/recommendations/product/1?n=3").json
    assert len(recs) == 3 and all(r["product_id"] != 1 for r in recs)
    assert len(client.get("/api/recommendations/customer/5").json) == 5


def test_sentiment_scoring():
    assert label(score_text("Excellent quality, totally worth the price")) == "positive"
    assert label(score_text("Poor quality, very disappointed")) == "negative"
    assert label(score_text("Not fresh and the packaging was damaged")) == "negative"


def test_sentiment_endpoint_validation(client):
    assert client.post("/api/sentiment/analyze", json={}).status_code == 400
    assert client.post("/api/sentiment/analyze", json={"text": "love it"}).json["label"] == "positive"
