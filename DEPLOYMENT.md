# Deploying HackRange live — free tier (Oracle Cloud)

This walks through taking the platform from "runs on my laptop" to "runs on
a real server anyone can visit," using Oracle Cloud's Always Free tier
(genuinely free forever, not a trial — a real VM you fully control).

Read the security note at the top of `backend/orchestrator.py` before doing
this. In short: the backend needs access to the Docker socket to launch lab
containers on demand, which is powerful access. That's an accepted tradeoff
for a small project, but don't casually extend this backend's permissions
further without thinking it through.

## 1. Create the free VM

1. Sign up at https://www.oracle.com/cloud/free/
2. Once in the console, create a new **Compute Instance**:
   - Shape: choose an "Always Free eligible" shape (Ampere A1 ARM, or the
     free x86 micro shape — either works)
   - Image: Ubuntu (latest LTS)
   - Add your SSH key during creation (or let Oracle generate one for you
     to download) — you'll need it to log in
3. Note the instance's **public IP address** once it's running.
4. In the instance's networking settings, open a **Security List** or
   **Network Security Group** rule to allow inbound traffic on ports
   **22** (SSH), **80** (HTTP), **443** (HTTPS), and a range like
   **30000-31000** (for the randomly-assigned lab container ports —
   adjust the orchestrator's port range later if you want to narrow this).

## 2. Log in and install Docker

```bash
ssh -i /path/to/your/key ubuntu@YOUR_SERVER_IP

sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Log out and back in for the group change to apply, then confirm:

```bash
docker --version
docker compose version
```

## 3. Get the project onto the server

Easiest path: push the project to a GitHub repo from your own machine,
then clone it on the server.

```bash
git clone https://github.com/YOUR_USERNAME/hackrange.git
cd hackrange
```

(If you'd rather not use GitHub, you can `scp` the folder directly:
`scp -r -i /path/to/key ./hackrange ubuntu@YOUR_SERVER_IP:~`)

## 4. Build the lab images and set your public host

```bash
docker compose build
export PUBLIC_HOST=YOUR_SERVER_IP
docker compose up -d
```

`PUBLIC_HOST` is what the backend uses when it tells a visitor's browser
where to find their freshly-launched lab container — it has to be your
server's real address, not "localhost", once you're not the one browsing
from the same machine.

To make `PUBLIC_HOST` persist across reboots, add the export line to
`~/.bashrc`, or better, create a `.env` file next to `docker-compose.yml`
containing:

```
PUBLIC_HOST=YOUR_SERVER_IP
```

Docker Compose reads `.env` automatically.

## 5. Confirm it's reachable

From your own machine (not the server):

```bash
curl http://YOUR_SERVER_IP:5000/api/health
```

Should return `{"status":"ok"}`. If it hangs, double check the security
list/firewall rule from step 1 actually allows port 5000 inbound, or move
straight to step 6 and put everything behind the reverse proxy instead of
exposing 5000 directly.

## 6. Put a domain + HTTPS in front of it (recommended before sharing widely)

Right now everything is plain HTTP on raw ports — fine for testing, not
great for something you'll share publicly. Caddy makes HTTPS nearly
effortless.

1. Point a domain (or subdomain) at your server's IP via an A record.
2. Install Caddy:
   ```bash
   sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
   curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
   curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
   sudo apt update && sudo apt install caddy
   ```
3. Edit `/etc/caddy/Caddyfile`:
   ```
   yourdomain.com {
       reverse_proxy /api/* localhost:5000
       reverse_proxy /* localhost:8080
   }
   ```
   (This assumes you're also serving the frontend folder over HTTP — see
   step 7 below — rather than opening `index.html` as a local file, since
   visitors on the internet obviously can't open a file on your machine.)
4. Restart Caddy: `sudo systemctl restart caddy`. It automatically gets a
   free TLS certificate from Let's Encrypt — no manual cert setup needed.
5. Update `PUBLIC_HOST` and `BACKEND_URL` (in `frontend/app.js`) to use
   `https://yourdomain.com` instead of raw IPs and ports.

## 7. Actually serve the frontend (not just open it locally)

The frontend is static files, so any simple web server works. Easiest:
add one more tiny service to `docker-compose.yml`:

```yaml
  frontend:
    image: nginx:alpine
    volumes:
      - ./frontend:/usr/share/nginx/html:ro
    ports:
      - "8080:80"
    networks:
      - labnet
```

Then `docker compose up -d --build` again. Your frontend is now served at
`http://YOUR_SERVER_IP:8080`, which is what Caddy proxies to in step 6.

## 8. Ongoing maintenance

- `docker compose logs -f backend` — watch backend logs live
- `docker ps` — see all currently-running lab containers (one per active
  visitor)
- `sudo apt update && sudo apt upgrade` periodically — keep the host OS
  patched, since it's now internet-facing
- Consider setting up basic `ufw` firewall rules on the VM itself in
  addition to Oracle's cloud-level security list, as defense in depth:
  ```bash
  sudo ufw allow 22
  sudo ufw allow 80
  sudo ufw allow 443
  sudo ufw enable
  ```

## What's still worth doing before wide sharing

- Swap the in-memory `progress_store` for real SQLite/Postgres storage
  (see the note in `README.md`) so a backend restart doesn't wipe
  everyone's progress
- Add a short on-page notice that these labs are for educational practice
  only
- Watch server resource usage for the first few days after sharing it —
  scanners and bots will find any public IP eventually, and the memory/CPU
  limits already baked into `orchestrator.py` are your safety net against
  that
