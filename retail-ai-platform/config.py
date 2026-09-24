"""Central configuration. Override with environment variables in the cloud."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("RETAIL_DB_PATH", os.path.join(BASE_DIR, "data", "retail.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

PORT = int(os.environ.get("PORT", 5000))
DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
CURRENCY = os.environ.get("CURRENCY_SYMBOL", "₹")
