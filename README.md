# HackRange

A self-hosted, platform for practicing web application vulnerabilities hands-on. Every visitor gets their own isolated, disposable lab container — built from scratch to understand how a real lab platform is architected, not just to use one.

> Built as a hands-on learning project. Includes intentionally vulnerable
> applications for practicing security concepts. For educational use only —
> do not deploy these vulnerable apps anywhere they'd be reachable by
> anyone you don't trust to use them responsibly.

## What this is

- A **catalog page** listing available labs, with progress tracking.
- A **backend** that spins up a fresh, isolated Docker container per
  visitor per lab, and tears it down automatically when you stop the lab.
- **Deliberately vulnerable lab apps**, each teaching one vulnerability
  class, with the underlying bug and its fix documented in code comments.

## Labs included

| Lab | Vulnerability class | Difficulty |
|---|---|---|
| Broken Login | SQL Injection | Beginner |

*(more labs in progress — see commit history)*

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌────────────────────┐
│  Frontend   │─────▶│   Backend    │─────▶│   Docker Engine     │
│ (catalog UI)│      │ (Flask API)  │      │ (per-user isolated  │
└─────────────┘      └──────────────┘      │  lab containers)    │
                                            └────────────────────┘
```

- Each lab container gets its own memory/CPU/process limits
- Idle containers are automatically cleaned up after a timeout
- Lab containers run on an isolated Docker network, separate from the
  backend and from each other

See [`README_SETUP.md`](./README_SETUP.md) for full local setup
instructions, [`DEPLOYMENT.md`](./DEPLOYMENT.md) for deploying it
live on a free-tier cloud VM, and [`SOLUTIONS.md`](./SOLUTIONS.md) for
payloads/answers to every lab (spoilers — try the labs first!).

## Tech stack

- **Backend:** Python, Flask, Docker SDK for Python
- **Frontend:** Vanilla HTML/CSS/JS (no framework — kept simple on purpose)
- **Orchestration:** Docker, Docker Compose
- **Lab apps:** Python/Flask, SQLite

## Quick start

```bash
git clone https://github.com/Cy5ec-rhythm/hackrange.git
cd hackrange
```

**Windows:**
```powershell
.\hackrange.bat
```

**Mac/Linux:**
```bash
chmod +x hackrange.sh
./hackrange.sh
```

That builds everything, starts it, and opens `http://localhost:8080` in
your browser automatically. To stop everything: `docker compose down`.

Full manual setup and troubleshooting in
[`README_SETUP.md`](./README_SETUP.md).

## Why I built this

I wanted to understand how platforms like PortSwigger Academy actually
work under the hood — session isolation, on-demand container
orchestration, and safely hosting intentionally vulnerable code — rather
than only ever being a user of a tool like it. This project is that,
built one real bug and one real fix at a time.

## License

MIT — see [`LICENSE`](./LICENSE).
