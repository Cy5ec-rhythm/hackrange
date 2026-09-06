"""
LAB: SQL Injection - Product Details (Numeric Context)
========================================================
This app is DELIBERATELY vulnerable. Do not copy this pattern into
real projects. It exists so you can practice exploiting it.

The scenario: a "view product" page takes a numeric product ID and
looks it up. The bug is the same root cause as the other two labs —
raw string concatenation into a SQL query — but this time the input
is NOT wrapped in quotes in the original query, because it's expected
to be a plain number.

Why this matters: a lot of people are taught to test for SQL injection
by throwing a single quote (') at every input. That works great against
string parameters, but it does nothing useful here — there's no quote
to break out of. The injection point is just as real, it just needs a
different first move.

How to solve it (no spoilers beyond this comment — try first!):
1. Try a normal numeric ID first (e.g. ?id=1) to see what a valid
   response looks like.
2. Try some basic arithmetic in the id parameter (e.g. ?id=1+1... or
   ?id=2-1) — if the result changes accordingly, your input is being
   evaluated as part of the query, not just matched literally.
3. From there, think about what you did in the "Product Search" lab
   to enumerate tables and columns via UNION — the same idea applies
   here, just without needing quotes.
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
            price TEXT NOT NULL
        )
    """)
    products = [
        (1, "Wireless Mouse", "19.99"),
        (2, "Mechanical Keyboard", "89.99"),
        (3, "Standing Desk", "249.00"),
    ]
    cur.executemany(
        "INSERT INTO products (id, name, price) VALUES (?, ?, ?)",
        products,
    )

    # A separate table the product lookup was never meant to reach.
    cur.execute("""
        CREATE TABLE secrets (
            id INTEGER PRIMARY KEY,
            secret_value TEXT NOT NULL
        )
    """)
    cur.execute(
        "INSERT INTO secrets (secret_value) VALUES (?)",
        ("FLAG{numer1c_c0ntext_1nj3ct10n}",),
    )

    conn.commit()
    conn.close()


@app.route("/", methods=["GET"])
def product_details():
    product_id = request.args.get("id", "")
    result = None
    error = None

    if product_id:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # !!! VULNERABLE LINE !!!
        # Note there are no quotes around {product_id} — it's inserted
        # as if it were always a plain number. A parameterized query
        # ("?" placeholder) would prevent this entirely, regardless of
        # whether the value is expected to be numeric or text.
        query = f"SELECT id, name, price FROM products WHERE id = {product_id}"

        try:
            cur.execute(query)
            result = cur.fetchone()
        except sqlite3.Error as e:
            error = str(e)

        conn.close()

    return render_template("index.html", product_id=product_id, result=result, error=error)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5003, debug=True)
