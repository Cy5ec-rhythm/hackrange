"""
LAB: SQL Injection - Product Search (UNION-based)
==================================================
This app is DELIBERATELY vulnerable. Do not copy this pattern into
real projects. It exists so you can practice exploiting it.

The scenario: a product search box filters by category. The bug: your
input is pasted directly into the SQL query, same root cause as the
login lab — but this time exploiting it takes one more step.

The bug:
    SELECT name, price FROM products WHERE category = '<your input>'

How to solve it (no spoilers beyond this comment — try first!):
1. This query returns TWO columns (name, price). A UNION-based attack
   only works if your injected SELECT returns the exact same number of
   columns as the original query.
2. There's a completely separate table in this database holding a
   secret. You won't find it by searching normally — you'll need to
   pull data OUT of that other table using a UNION SELECT appended to
   your input.
3. Try breaking the query with a single quote first and see what the
   error message tells you — error messages are often the biggest clue
   in this kind of bug.
"""

from flask import Flask, request, render_template
import sqlite3
import os

app = Flask(__name__)

DB_PATH = "/tmp/lab.db"


def init_db():
    """Create a fresh database every time the container starts, so the
    lab is always in a known, resettable state."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price TEXT NOT NULL
        )
    """)
    products = [
        ("Wireless Mouse", "electronics", "19.99"),
        ("Mechanical Keyboard", "electronics", "89.99"),
        ("Standing Desk", "furniture", "249.00"),
        ("Office Chair", "furniture", "129.50"),
        ("Notebook Set", "stationery", "6.99"),
    ]
    cur.executemany(
        "INSERT INTO products (name, category, price) VALUES (?, ?, ?)",
        products,
    )

    # A completely separate table, unrelated to products, holding the
    # thing you're actually after. Nothing on the page links to this —
    # you can only reach it via the injection itself.
    cur.execute("""
        CREATE TABLE secrets (
            id INTEGER PRIMARY KEY,
            secret_value TEXT NOT NULL
        )
    """)
    cur.execute(
        "INSERT INTO secrets (secret_value) VALUES (?)",
        ("FLAG{un10n_s3l3ct_f7w}",),
    )

    conn.commit()
    conn.close()


@app.route("/", methods=["GET"])
def search():
    category = request.args.get("category", "")
    results = []
    error = None

    if category:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # !!! VULNERABLE LINE !!!
        # Same root cause as the login lab: user input pasted directly
        # into the query string. A parameterized query ("?" placeholder)
        # would prevent this entirely.
        query = f"SELECT name, price FROM products WHERE category = '{category}'"

        try:
            cur.execute(query)
            results = cur.fetchall()
        except sqlite3.Error as e:
            error = str(e)

        conn.close()

    return render_template("index.html", category=category, results=results, error=error)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5002, debug=True)
