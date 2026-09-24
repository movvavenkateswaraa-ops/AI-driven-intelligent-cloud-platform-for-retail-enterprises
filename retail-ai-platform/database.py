"""SQLite data layer. Swap the connection for PostgreSQL / Cloud SQL in production."""
import sqlite3
from contextlib import closing

import pandas as pd

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    price         REAL NOT NULL,
    stock         INTEGER NOT NULL,
    reorder_level INTEGER NOT NULL,
    lead_time_days INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_date  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty        INTEGER NOT NULL,
    unit_price REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    text       TEXT NOT NULL,
    rating     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_items_product ON order_items(product_id);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_conn()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def db_is_empty() -> bool:
    with closing(get_conn()) as conn:
        return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with closing(get_conn()) as conn:
        return pd.read_sql_query(sql, conn, params=params)
