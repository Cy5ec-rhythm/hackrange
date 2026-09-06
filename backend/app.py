"""
Backend for the mini lab platform.

What this file does, in plain terms:
1. Keeps a small list of "labs" (metadata only — name, description, difficulty).
2. Exposes that list over an API so the frontend page can display it.
3. On request, asks the orchestrator to launch a PRIVATE container for the
   requesting visitor's session (see orchestrator.py) instead of pointing
   everyone at one shared lab instance.
4. Accepts flag submissions and checks them against the correct answer.
5. Remembers (in memory, for now) which labs each browser session has solved.

This is intentionally simple — no database, no user accounts yet.
Everything resets when you restart the backend. That's fine for v1.
"""

import os
from flask import Flask, jsonify, request, session
from flask_cors import CORS
import secrets
import orchestrator

app = Flask(__name__)

# The hostname or IP address visitors' browsers should use to reach lab
# containers. On your own machine this is "localhost". Once you deploy to
# a real server, set the PUBLIC_HOST environment variable to your domain
# or server IP so the URLs the backend hands out are actually reachable.
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "localhost")

# Flask needs a secret key to sign session cookies (so it knows which
# browser is which). In a real deployment you'd load this from an
# environment variable instead of generating a new one every restart.
app.secret_key = secrets.token_hex(16)

# CORS = "Cross-Origin Resource Sharing". Our frontend (e.g. served from
# port 8080) and backend (port 5000) are technically different "origins"
# in the browser's eyes, even on localhost. CORS tells the browser
# "it's fine for the frontend to talk to this backend."
CORS(app, supports_credentials=True)

# ---------------------------------------------------------------------------
# LAB CATALOG
# ---------------------------------------------------------------------------
# Each lab is just a dictionary. `flag` is the correct answer the user must
# find by exploiting the lab. In a bigger version you'd store this in a
# database and generate a unique flag per user session — for now, one
# shared flag per lab is enough to prove the whole flow works.

LABS = [
    {
        "id": "sqli-login",
        "title": "SQL Injection: Broken Login",
        "category": "Injection",
        "difficulty": "Beginner",
        "description": (
            "A login form checks credentials with a raw SQL query. "
            "Can you log in as 'admin' without knowing the password?"
        ),
        "hints": [
            "Try entering a single quote (') in the username field and see what happens.",
            "SQL uses -- to comment out the rest of a line. Can you make the WHERE clause always true, then comment out the rest?",
            "Try entering admin' -- as the username, with any password.",
        ],
        "flag": "FLAG{sql1_1nj3ct10n_byp4ss3d}",
    },
    {
        "id": "sqli-union",
        "title": "SQL Injection: Product Search",
        "category": "Injection",
        "difficulty": "Beginner",
        "description": (
            "A product search box filters by category using a raw SQL query. "
            "There's a secret hidden in a completely different table — "
            "can you pull it out using a UNION-based injection?"
        ),
        "hints": [
            "Break the query with a single quote first — read the error message carefully, it tells you a lot.",
            "Figure out how many columns the query returns using ORDER BY 1--, ORDER BY 2--, etc. until one errors.",
            "Once you know the column count, sqlite_master lists every table in the database — try UNIONing against it before going straight for 'secrets'.",
        ],
        "flag": "FLAG{un10n_s3l3ct_f7w}",
    },
        {
        "id": "sqli-numeric",
        "title": "SQL Injection: Product Details",
        "category": "Injection",
        "difficulty": "Beginner",
        "description": (
            "A product lookup page takes a numeric ID with no quotes around it. "
            "Single quotes won't get you anywhere here — can you find another "
            "way to break out of the query?"
        ),
        "hints": [
            "A single quote won't do anything useful here — this input isn't wrapped in quotes in the query.",
            "Try basic arithmetic in the id parameter, like ?id=1+1 — if the result changes accordingly, your input is being evaluated, not just matched.",
            "The same UNION technique from the Product Search lab applies here too — just without needing quotes to break out first.",
        ],
        "flag": "FLAG{numer1c_c0ntext_1nj3ct10n}",
    },
]

# Tracks which flags each session has already solved.
# Structure: { session_id: set_of_lab_ids_solved }
# This is in-memory only — it's here so the UI can show a checkmark.
progress_store = {}


def get_session_id():
    """
    Make sure every browser gets a stable, unique ID stored in a cookie,
    so we can track their progress across requests.
    """
    if "sid" not in session:
        session["sid"] = secrets.token_hex(8)
    return session["sid"]


@app.route("/api/labs", methods=["GET"])
def list_labs():
    """
    Returns the lab catalog to the frontend, WITHOUT the flag field
    (never send the answer to the browser!). Also includes whether
    the current session has solved each lab.
    """
    sid = get_session_id()
    solved = progress_store.get(sid, set())

    public_labs = []
    for lab in LABS:
        public_labs.append({
            "id": lab["id"],
            "title": lab["title"],
            "category": lab["category"],
            "difficulty": lab["difficulty"],
            "description": lab["description"],
            "solved": lab["id"] in solved,
        })

    return jsonify(public_labs)


@app.route("/api/labs/<lab_id>/launch", methods=["POST"])
def launch_lab(lab_id):
    """
    Starts (or reuses) a private container for THIS visitor's session and
    returns the URL their browser should open. Every visitor gets their
    own isolated instance — nobody shares state with anyone else.
    """
    lab = next((l for l in LABS if l["id"] == lab_id), None)
    if lab is None:
        return jsonify({"error": "Unknown lab id"}), 404

    sid = get_session_id()

    try:
        host_port = orchestrator.launch_lab(sid, lab_id)
    except Exception as e:
        return jsonify({"error": f"Could not launch lab: {e}"}), 500

    return jsonify({"url": f"http://{PUBLIC_HOST}:{host_port}"})


@app.route("/api/labs/<lab_id>/stop", methods=["POST"])
def stop_lab(lab_id):
    """
    Immediately stops and removes THIS visitor's container for this lab,
    instead of waiting for the idle timeout. Keeps the container list
    tidy and frees resources as soon as someone is done.
    """
    sid = get_session_id()
    stopped = orchestrator.stop_lab(sid, lab_id)
    return jsonify({"stopped": stopped})


@app.route("/api/check-flag", methods=["POST"])
def check_flag():
    """
    Receives { "lab_id": "...", "flag": "..." } from the frontend
    and checks it against the correct flag for that lab.
    """
    data = request.get_json(silent=True) or {}
    lab_id = data.get("lab_id")
    submitted_flag = (data.get("flag") or "").strip()

    lab = next((l for l in LABS if l["id"] == lab_id), None)
    if lab is None:
        return jsonify({"correct": False, "error": "Unknown lab id"}), 404

    is_correct = submitted_flag == lab["flag"]

    if is_correct:
        sid = get_session_id()
        progress_store.setdefault(sid, set()).add(lab_id)

    return jsonify({"correct": is_correct})


@app.route("/api/health", methods=["GET"])
def health():
    """Simple endpoint to check the backend is alive."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    orchestrator.ensure_network()
    orchestrator.start_cleanup_thread()
    # host="0.0.0.0" so it's reachable from other containers / your browser,
    # not just from inside the container itself.
    app.run(host="0.0.0.0", port=5000, debug=True)
