"""
LAB: SQL Injection - User Lookup (Blind, Boolean-based)
=========================================================
This app is DELIBERATELY vulnerable. Do not copy this pattern into
real projects. It exists so you can practice exploiting it.

The scenario: a username lookup page tells you whether a user exists
or not. That's it — no data is ever returned to your browser, and
errors are silently suppressed. This is blind SQL injection: the only
signal you have is "user exists" vs "user doesn't exist."

Why this is harder than the previous labs:
- You can't see any query output — no rows, no error messages
- You can't use UNION SELECT to dump data (there's nowhere to dump
  it to — the page only shows "exists" or "doesn't exist")
- You have to extract data one character at a time by asking
  true/false questions through the injection point

How blind SQLi actually works:
You inject a condition that changes the boolean outcome of the query.
For example, if you can make the WHERE clause check something like
"does the first character of the flag equal 'F'?" — and the page
says "exists" when true and "not found" when false — you can extract
the entire flag one character at a time.

How to solve it (try first before reading hints in the app!):
1. Confirm the injection: does injecting a true condition (like 1=1)
   change the response vs a false one (like 1=2)?
2. Confirm you can query another table from inside the injection.
3. Extract the flag character by character using SUBSTR() and
   asking yes/no questions about each character.
"""

from flask import Flask, request, render_template
import sqlite3
import os

app = Flask(__name__)

DB_PATH = "/tmp/lab.db"


def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL
        )
    """)
    users = ["alice", "bob", "charlie", "admin"]
    for u in users:
        cur.execute("INSERT INTO users (username) VALUES (?)", (u,))

    cur.execute("""
        CREATE TABLE secrets (
            id INTEGER PRIMARY KEY,
            secret_value TEXT NOT NULL
        )
    """)
    cur.execute(
        "INSERT INTO secrets (secret_value) VALUES (?)",
        ("FLAG{bl1nd_sqli_0ne_b1t_4t_4_t1me}",),
    )

    conn.commit()
    conn.close()


@app.route("/", methods=["GET"])
def lookup():
    username = request.args.get("username", "")
    result = None

    if username:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # !!! VULNERABLE LINE !!!
        # Errors are silently suppressed and only a boolean signal is
        # returned — "exists" or "not found". This is what makes it blind.
        query = f"SELECT id FROM users WHERE username = '{username}'"

        try:
            cur.execute(query)
            row = cur.fetchone()
            result = "exists" if row else "not_found"
        except sqlite3.Error:
            result = "not_found"

        conn.close()

    return render_template("index.html", username=username, result=result)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5004, debug=True)
