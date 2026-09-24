"""Generates a realistic synthetic retail dataset (12 months) so the platform works out of the box."""
import random
from datetime import date, timedelta
from contextlib import closing

import numpy as np

from database import get_conn, init_db

CATALOG = {
    "Grocery": [("Basmati Rice 5kg", 480), ("Whole Wheat Flour 5kg", 250), ("Sunflower Oil 1L", 165),
                ("Toor Dal 1kg", 150), ("Tea Leaves 500g", 260), ("Sugar 1kg", 48), ("Salted Butter 500g", 285)],
    "Dairy & Bakery": [("Full Cream Milk 1L", 68), ("Sandwich Bread", 45), ("Paneer 200g", 95),
                       ("Curd 400g", 40), ("Eggs (12)", 84), ("Cheese Slices", 130)],
    "Personal Care": [("Herbal Shampoo 340ml", 320), ("Toothpaste 200g", 110), ("Body Lotion 400ml", 355),
                      ("Face Wash 100ml", 240), ("Hand Wash 500ml", 125), ("Deodorant", 210)],
    "Home & Kitchen": [("Non-stick Pan", 899), ("Storage Container Set", 650), ("Dish Wash Liquid 1L", 190),
                       ("Cotton Bath Towel", 420), ("LED Bulb 9W (2)", 180), ("Water Bottle 1L", 299)],
    "Electronics": [("Wireless Earbuds", 1799), ("Power Bank 10000mAh", 1299), ("USB-C Cable", 349),
                    ("Bluetooth Speaker", 2299), ("Smartwatch", 3499), ("Phone Stand", 399)],
    "Snacks & Drinks": [("Potato Chips 150g", 50), ("Chocolate Bar", 60), ("Cola 2L", 95),
                        ("Instant Noodles (5)", 75), ("Mixed Nuts 250g", 320), ("Orange Juice 1L", 110)],
}

FIRST = ["Aarav", "Vivaan", "Aditi", "Diya", "Rohan", "Ishaan", "Ananya", "Kavya", "Arjun", "Meera",
         "Sneha", "Karthik", "Priya", "Rahul", "Neha", "Sanjay", "Lakshmi", "Varun", "Pooja", "Manoj"]
LAST = ["Reddy", "Sharma", "Patel", "Rao", "Iyer", "Nair", "Gupta", "Singh", "Kumar", "Das"]
CITIES = ["Hyderabad", "Bengaluru", "Chennai", "Mumbai", "Pune", "Delhi"]

POSITIVE = ["Excellent quality, totally worth the price", "Love it, works great and arrived fast",
            "Very good product, would buy again", "Amazing value, highly recommend",
            "Fresh and perfect, my family enjoyed it", "Great quality and good packaging"]
NEUTRAL = ["It is okay, does the job", "Average product, nothing special", "Decent for the price"]
NEGATIVE = ["Poor quality, very disappointed", "Terrible, stopped working within a week",
            "Not fresh and the packaging was damaged", "Bad experience, would not recommend",
            "Overpriced and not worth it", "Late delivery and the item was broken"]


def seed(days: int = 365, seed_value: int = 42) -> None:
    rng = np.random.default_rng(seed_value)
    random.seed(seed_value)
    init_db()

    with closing(get_conn()) as conn:
        cur = conn.cursor()

        # --- products
        products = []
        pid = 1
        for category, items in CATALOG.items():
            for name, price in items:
                stock = int(rng.integers(15, 320))
                lead = int(rng.integers(3, 12))
                products.append((pid, name, category, float(price), stock, int(rng.integers(20, 60)), lead))
                pid += 1
        cur.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?)", products)
        n_products = len(products)
        cat_of = {p[0]: p[2] for p in products}
        price_of = {p[0]: p[3] for p in products}
        by_cat = {}
        for p in products:
            by_cat.setdefault(p[2], []).append(p[0])
        pop = rng.pareto(2.0, n_products) + 1  # a few best-sellers, long tail
        pop = pop / pop.sum()

        # --- customers (each has an activity window so some customers churn)
        n_customers = 400
        customers = [(i, f"{random.choice(FIRST)} {random.choice(LAST)}", random.choice(CITIES))
                     for i in range(1, n_customers + 1)]
        cur.executemany("INSERT INTO customers VALUES (?,?,?)", customers)
        weight = rng.pareto(1.5, n_customers) + 1
        churn_day = np.where(rng.random(n_customers) < 0.3, rng.integers(60, days - 20, n_customers), days + 1)
        join_day = np.where(rng.random(n_customers) < 0.35, rng.integers(0, days - 60, n_customers), 0)
        fav_cat = rng.choice(list(CATALOG), n_customers)

        # --- orders with trend + weekly seasonality
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=days - 1)
        order_id, item_id = 1, 1
        orders, items = [], []
        for d in range(days):
            day = start + timedelta(days=d)
            dow_factor = [0.85, 0.85, 0.9, 0.95, 1.1, 1.35, 1.3][day.weekday()]
            festive = 1.4 if day.month in (10, 11) else 1.0
            n_orders = max(3, int(rng.poisson(18 * (1 + 0.5 * d / days) * dow_factor * festive)))
            active = (join_day <= d) & (churn_day > d)
            w = weight * active
            probs = w / w.sum()
            for cust in rng.choice(n_customers, n_orders, p=probs):
                orders.append((order_id, int(cust) + 1, day.isoformat()))
                anchor = fav_cat[cust] if rng.random() < 0.6 else random.choice(list(CATALOG))
                basket = set(random.sample(by_cat[anchor], k=min(len(by_cat[anchor]), random.randint(1, 3))))
                if rng.random() < 0.3:
                    basket.add(int(rng.choice(n_products, p=pop)) + 1)
                for prod in basket:
                    qty = int(rng.integers(1, 4))
                    items.append((item_id, order_id, prod, qty, price_of[prod]))
                    item_id += 1
                order_id += 1
        cur.executemany("INSERT INTO orders VALUES (?,?,?)", orders)
        cur.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", items)

        # --- reviews (each product has a hidden 'quality' that biases sentiment)
        reviews = []
        for p in products:
            quality = rng.uniform(0.15, 0.95)
            for _ in range(int(rng.integers(6, 15))):
                r = rng.random()
                if r < quality:
                    reviews.append((p[0], random.choice(POSITIVE), int(rng.integers(4, 6))))
                elif r < quality + 0.15:
                    reviews.append((p[0], random.choice(NEUTRAL), 3))
                else:
                    reviews.append((p[0], random.choice(NEGATIVE), int(rng.integers(1, 3))))
        cur.executemany("INSERT INTO reviews (product_id, text, rating) VALUES (?,?,?)", reviews)
        conn.commit()
    print(f"Seeded {n_products} products, {n_customers} customers, {len(orders)} orders, {len(items)} line items.")


if __name__ == "__main__":
    seed()
