"""
LAB: SQL Injection - Broken Login
==================================
This app is DELIBERATELY vulnerable. Do not copy this pattern into
real projects. It exists so you can practice exploiting it.

The bug: the login query is built by directly pasting the username
and password into a SQL string (string concatenation / f-string),
instead of using parameterized queries. This lets an attacker inject
their own SQL logic into the query.

How to solve it (no spoilers beyond this comment - try first!):
Think about what happens to the query if your "username" input
contains a piece of SQL that always evaluates to true, and also
comments out the rest of the query.
"""

from flask import Flask, request, render_template
import sqlite3
import os

app = Flask(__name__)

DB_PATH = "/tmp/lab.db"


def init_db():
    """Create a fresh database with one admin user, every time the
    container starts. This keeps the lab in a known, resettable state."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
    """)
    # The real password is long and random - you are NOT meant to guess it.
    # You're meant to bypass the check entirely.
    cur.execute(
        "INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
        ("admin", "x7Kd93!qLpZmN2vR", 1),
    )
    conn.commit()
    conn.close()


@app.route("/", methods=["GET", "POST"])
def login():
    message = None
    logged_in_as = None

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # !!! VULNERABLE LINE !!!
        # User input is pasted directly into the SQL string. This is
        # the bug you're here to exploit. A parameterized query
        # (using "?" placeholders, like in init_db above) would prevent
        # this attack entirely.
        query = f"SELECT id, username, is_admin FROM users WHERE username = '{username}' AND password = '{password}'"

        try:
            cur.execute(query)
            row = cur.fetchone()
        except sqlite3.Error as e:
            row = None
            message = f"Database error: {e}"

        conn.close()

        if row:
            user_id, uname, is_admin = row
            logged_in_as = uname
            if is_admin:
                message = "flag_reveal"
            else:
                message = f"Logged in as {uname}, but this account has no special access."
        elif message is None:
            message = "Invalid username or password."

    return render_template(
        "index.html",
        message=message,
        logged_in_as=logged_in_as,
        flag="FLAG{sql1_1nj3ct10n_byp4ss3d}",
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
