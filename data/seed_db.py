"""
Creates a realistic e-commerce SQLite database for demo purposes.
Run once: python seed_db.py
"""
import sqlite3, random, os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "ecommerce.db"

random.seed(42)

CATEGORIES = ["Electronics", "Clothing", "Books", "Home & Kitchen", "Sports", "Beauty"]
PRODUCTS = [
    ("iPhone 15", "Electronics", 999), ("Samsung TV 55\"", "Electronics", 799),
    ("AirPods Pro", "Electronics", 249), ("Kindle Paperwhite", "Electronics", 139),
    ("Nike Air Max", "Clothing", 120),   ("Levi's Jeans", "Clothing", 60),
    ("Winter Jacket", "Clothing", 180),  ("Python Crash Course", "Books", 35),
    ("Atomic Habits", "Books", 18),      ("Deep Work", "Books", 22),
    ("Coffee Maker", "Home & Kitchen", 89), ("Air Fryer", "Home & Kitchen", 120),
    ("Yoga Mat", "Sports", 45),          ("Resistance Bands", "Sports", 25),
    ("Face Serum", "Beauty", 55),        ("Moisturizer SPF50", "Beauty", 38),
]
CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
          "Philadelphia", "San Antonio", "San Diego", "Dallas", "Mumbai",
          "Delhi", "Bangalore", "London", "Berlin", "Toronto"]

def seed():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE customers (
        id INTEGER PRIMARY KEY,
        name TEXT,
        email TEXT UNIQUE,
        city TEXT,
        signup_date TEXT,
        tier TEXT
    );
    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT,
        category TEXT,
        price REAL,
        stock INTEGER
    );
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER REFERENCES customers(id),
        order_date TEXT,
        status TEXT,
        total REAL
    );
    CREATE TABLE order_items (
        id INTEGER PRIMARY KEY,
        order_id INTEGER REFERENCES orders(id),
        product_id INTEGER REFERENCES products(id),
        quantity INTEGER,
        unit_price REAL
    );
    CREATE TABLE reviews (
        id INTEGER PRIMARY KEY,
        product_id INTEGER REFERENCES products(id),
        customer_id INTEGER REFERENCES customers(id),
        rating INTEGER,
        review_date TEXT
    );
    """)

    # Customers
    first = ["Alice","Bob","Carol","David","Eve","Frank","Grace","Henry",
             "Iris","Jack","Karen","Leo","Mia","Noah","Olivia","Paul",
             "Quinn","Rachel","Sam","Tina","Uma","Victor","Wendy","Xavier"]
    last  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller",
             "Davis","Wilson","Martinez","Anderson","Taylor","Thomas","Jackson"]
    tiers = ["bronze","silver","gold","platinum"]

    customers = []
    for i in range(1, 201):
        fn = random.choice(first)
        ln = random.choice(last)
        city = random.choice(CITIES)
        days_ago = random.randint(30, 730)
        signup = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        tier = random.choices(tiers, weights=[50,30,15,5])[0]
        customers.append((i, f"{fn} {ln}", f"{fn.lower()}.{ln.lower()}{i}@email.com",
                          city, signup, tier))
    cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", customers)

    # Products
    for i, (name, cat, price) in enumerate(PRODUCTS, 1):
        cur.execute("INSERT INTO products VALUES (?,?,?,?,?)",
                    (i, name, cat, price, random.randint(10, 500)))

    # Orders + items
    statuses = ["completed","completed","completed","pending","cancelled"]
    order_id = 1
    item_id  = 1
    orders, items = [], []

    for cust_id in range(1, 201):
        n_orders = random.randint(0, 8)
        for _ in range(n_orders):
            days_ago = random.randint(1, 365)
            order_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            status = random.choice(statuses)
            n_items = random.randint(1, 4)
            total = 0
            for _ in range(n_items):
                prod = random.choice(PRODUCTS)
                prod_id = PRODUCTS.index(prod) + 1
                qty = random.randint(1, 3)
                price = prod[2] * random.uniform(0.85, 1.05)
                total += qty * price
                items.append((item_id, order_id, prod_id, qty, round(price, 2)))
                item_id += 1
            orders.append((order_id, cust_id, order_date, status, round(total, 2)))
            order_id += 1

    cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)
    cur.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", items)

    # Reviews
    rev_id = 1
    reviews = []
    for prod_id in range(1, len(PRODUCTS)+1):
        for _ in range(random.randint(5, 30)):
            cust_id = random.randint(1, 200)
            rating = random.choices([1,2,3,4,5], weights=[5,8,15,40,32])[0]
            days_ago = random.randint(1, 300)
            rev_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            reviews.append((rev_id, prod_id, cust_id, rating, rev_date))
            rev_id += 1
    cur.executemany("INSERT INTO reviews VALUES (?,?,?,?,?)", reviews)

    conn.commit()
    conn.close()
    print(f"✅ Database seeded at {DB_PATH}")
    print(f"   Customers: 200 | Products: {len(PRODUCTS)} | Orders: {order_id-1} | Reviews: {rev_id-1}")

if __name__ == "__main__":
    seed()
