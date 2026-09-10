# HackRange — Setup Guide

A tiny, self-hosted version platform:
a catalog page listing labs, and one real, working vulnerable lab
(SQL injection login bypass) to prove the whole flow end-to-end.

This version supports multiple visitors at once — each person who clicks
"Launch lab" gets their own private, isolated container, automatically
cleaned up when they're done or after a period of inactivity. Still no
accounts yet (progress is tracked per-browser via a generated session ID)
— see "Where to go next" at the bottom for what's still ahead.

## What's inside

```
hackrange/
├── docker-compose.yml        <- starts backend + lab together
├── backend/                  <- Flask API: lab list + flag checking
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── labs/
│   └── lab-sqli-login/       <- the vulnerable app itself
│       ├── app.py
│       ├── templates/index.html
│       ├── requirements.txt
│       └── Dockerfile
└── frontend/                 <- the catalog page you browse
    ├── index.html
    ├── style.css
    └── app.js
```

## Prerequisites

You need **Docker** and **Docker Compose** installed.

- Windows/Mac: install Docker Desktop → https://www.docker.com/products/docker-desktop/
- Linux: install `docker` and the `docker compose` plugin via your package manager

Check it worked:
```bash
docker --version
docker compose version
```

## How to run it

**Easiest way — one command:**

Windows: `.\hackrange.bat`
Mac/Linux: `chmod +x hackrange.sh && ./hackrange.sh`

This builds and starts everything, then opens `http://localhost:8080`
in your browser automatically. Skip to step 4 below.

**Manual way, if you want to see each step:**

1. Open a terminal in the `hackrange` folder.

2. Start the backend and the frontend:
   ```bash
   docker compose up --build -d
   ```
   First run will take a minute or two while Docker downloads images
   and installs Python packages.

3. Open your browser to:
   ```
   http://localhost:8080
   ```

4. You should see one lab card: "SQL Injection: Broken Login".
   Click **Launch lab** — it opens the vulnerable login page in a new
   tab, on a randomly-assigned port.

5. Solve it. (Hint: think about what happens to the SQL query if your
   username input contains a piece of SQL that's always true, and
   comments out the rest of the query. No further spoilers here —
   open `labs/lab-sqli-login/app.py` afterward to see exactly how the
   bug works and why the fix is parameterized queries.)

6. Copy the flag it gives you, paste it into the input box on the
   catalog page next to that lab, and click **Submit**. The card
   should flip to "Solved".

7. When you're done, stop everything with `Ctrl+C` in the terminal,
   then:
   ```bash
   docker compose down
   ```

## How the pieces talk to each other

- **frontend/app.js** calls `http://localhost:5000/api/labs` to get
  the list of labs, and `http://localhost:5000/api/check-flag` when
  you submit a flag.
- **backend/app.py** is that API. It never sends the actual flag to
  the browser — only a yes/no answer when you submit a guess.
- **labs/lab-sqli-login/app.py** is a totally separate, deliberately
  broken app. It doesn't know or care about the backend at all — it
  just serves a vulnerable login page on its own port.

This separation is the same pattern real platforms use: the "catalog
and progress tracking" system is completely different code from the
"vulnerable target" code, so you can add new labs without touching
the backend at all (just add a new folder under `labs/` and one new
entry in `LABS` inside `backend/app.py`).

## Where to go next

Once this is comfortable:

1. **Add a second lab.** Copy the `lab-sqli-login` folder, change the
   vulnerability (e.g. an IDOR, a broken JWT check, an SSRF endpoint
   like the one you exploited against Grafana), add a new service to
   `docker-compose.yml`, and a new entry to `LABS` in `backend/app.py`.

2. **Give each user their own container.** Right now everyone hits
   the same lab container. The real next step is having the backend
   use the Docker SDK (`docker-py`) to spin up a fresh container per
   session and tear it down after a timeout — this is the part that
   makes it feel like a "real" platform.

3. **Persist progress.** Swap the in-memory `progress_store` dict in
   `backend/app.py` for a real database (SQLite to start, Postgres
   later) so progress survives a backend restart.

4. **Add accounts.** Simple username/password auth (Flask-Login) so
   progress is tied to a person, not just a browser session.

5. **Add hints and write-ups**, PortSwigger-style: a "show hint"
   button that reveals progressively more specific guidance, and a
   "solution" write-up unlocked after solving.

Ask me for help with any of these when you're ready — happy to build
the next one with you the same way.
