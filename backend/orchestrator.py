"""
Orchestrator: spins up a fresh, isolated Docker container per (session, lab)
pair, instead of everyone sharing one always-on container.

Why this exists:
When this platform is only running on your own machine for yourself, one
shared container per lab is fine. Once strangers use it at the same time,
sharing a container means one person's login state, database rows, or
crashes affect everyone else. Each visitor needs their own sandboxed copy.

Security note on Docker socket access:
This backend is given access to the host's Docker socket so it can create
containers on demand. That access is powerful — effectively root-level
control of the host. For a small personal project this is a known,
accepted tradeoff, but if you later expose this backend more broadly,
look into a restricted proxy in front of the socket (e.g. Tecnativa's
docker-socket-proxy) so the backend can only do exactly what it needs
(create/stop containers) and nothing else.
"""

import docker
import time
import threading
import urllib.request

client = docker.from_env()

# Maps lab id -> the Docker image tag that lab was built as.
LAB_IMAGES = {
    "sqli-login": "lab-sqli-login:latest",
    "sqli-union": "lab-sqli-union:latest",
    "sqli-numeric": "lab-sqli-numeric:latest",
}

# Maps lab id -> the port the app listens on INSIDE its container.
LAB_INTERNAL_PORT = {
    "sqli-login": 5001,
    "sqli-union": 5002,
    "sqli-numeric": 5003,
}

# Must match the network name defined in docker-compose.yml.
NETWORK_NAME = "labs-internal"

# How long a container can sit unused before we destroy it.
IDLE_TIMEOUT_SECONDS = 15 * 60  # 15 minutes

# In-memory tracking of active containers.
# Key: (session_id, lab_id)  Value: {"container_id", "host_port", "last_used"}
_active_containers = {}
_lock = threading.Lock()


def ensure_network():
    """Create the isolated lab network if it doesn't already exist."""
    try:
        client.networks.get(NETWORK_NAME)
    except docker.errors.NotFound:
        client.networks.create(NETWORK_NAME, driver="bridge", internal=True)


def reconcile_existing_containers():
    """
    Rebuilds the in-memory tracking dict from what's actually running in
    Docker. Needed because this dict is lost every time the backend
    process restarts, even though lab containers keep running
    independently. Without this, "Stop lab" fails to find containers
    that were launched before the most recent backend restart.
    """
    with _lock:
        containers = client.containers.list(filters={"label": "lab_id"})
        for c in containers:
            session_id = c.labels.get("lab_session")
            lab_id = c.labels.get("lab_id")
            if not session_id or not lab_id:
                continue
            try:
                c.reload()
                port_key = f"{LAB_INTERNAL_PORT.get(lab_id)}/tcp"
                ports = c.attrs["NetworkSettings"]["Ports"]
                if port_key not in ports or not ports[port_key]:
                    continue
                host_port = ports[port_key][0]["HostPort"]
            except Exception:
                continue
            _active_containers[(session_id, lab_id)] = {
                "container_id": c.id,
                "host_port": host_port,
                "last_used": time.time(),
            }


def launch_lab(session_id, lab_id):
    """
    Returns the host port for a running container serving this lab for
    this session — reusing an existing one if it's still alive, or
    creating a new one if not. Waits until the app inside is actually
    responding before returning, so the browser never opens a tab too
    early.
    """
    if lab_id not in LAB_IMAGES:
        raise ValueError(f"Unknown lab id: {lab_id}")

    key = (session_id, lab_id)

    with _lock:
        existing = _active_containers.get(key)
        if existing:
            try:
                c = client.containers.get(existing["container_id"])
                if c.status == "running":
                    existing["last_used"] = time.time()
                    return existing["host_port"]
            except docker.errors.NotFound:
                pass  # container's gone — fall through and make a new one

        image = LAB_IMAGES[lab_id]
        internal_port = LAB_INTERNAL_PORT[lab_id]
        container_name = f"lab-{lab_id}-{session_id}"[:63]

        # Clean up any stale container with this exact name before making
        # a new one (can happen if the backend restarted).
        try:
            old = client.containers.get(container_name)
            old.remove(force=True)
        except docker.errors.NotFound:
            pass

        container = client.containers.run(
            image,
            detach=True,
            name=container_name,
            network=NETWORK_NAME,
            ports={f"{internal_port}/tcp": None},  # None = random free host port
            mem_limit="128m",           # cap memory so one lab can't eat the server
            nano_cpus=int(0.5 * 1e9),   # cap at 0.5 CPU core
            pids_limit=100,             # cap process count (fork-bomb protection)
            labels={"lab_session": session_id, "lab_id": lab_id},
        )
        container.reload()
        host_port = container.ports[f"{internal_port}/tcp"][0]["HostPort"]

        # The container's port is published by Docker immediately, but the
        # Flask app inside it takes a little longer to actually start
        # listening and be ready to serve a full response. A raw TCP
        # connection can succeed a moment before the WSGI app is truly
        # ready, so we do a real HTTP request here instead — only return
        # once the app genuinely answers.
        internal_ip = container.attrs["NetworkSettings"]["Networks"][NETWORK_NAME]["IPAddress"]
        _wait_until_http_ready(internal_ip, internal_port, timeout_seconds=15)

        _active_containers[key] = {
            "container_id": container.id,
            "host_port": host_port,
            "last_used": time.time(),
        }
        return host_port


def _wait_until_http_ready(host, port, timeout_seconds=15):
    """Polls the lab app with a real HTTP GET until it responds, or times out."""
    deadline = time.time() + timeout_seconds
    url = f"http://{host}:{port}/"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def stop_lab(session_id, lab_id):
    """
    Stops and removes the container for this (session, lab) pair, if one
    exists. Returns True if a container was found and stopped, False
    otherwise.
    """
    key = (session_id, lab_id)
    with _lock:
        info = _active_containers.pop(key, None)
        if info is None:
            return False
        try:
            c = client.containers.get(info["container_id"])
            c.stop(timeout=3)
            c.remove(force=True)
        except docker.errors.NotFound:
            pass
        return True


def _cleanup_idle_containers():
    now = time.time()
    with _lock:
        stale_keys = [
            k for k, v in _active_containers.items()
            if now - v["last_used"] > IDLE_TIMEOUT_SECONDS
        ]
        for k in stale_keys:
            info = _active_containers.pop(k)
            try:
                c = client.containers.get(info["container_id"])
                c.stop(timeout=3)
                c.remove(force=True)
            except docker.errors.NotFound:
                pass


def _cleanup_loop():
    while True:
        time.sleep(60)
        try:
            _cleanup_idle_containers()
        except Exception as e:
            # Never let the background thread die silently.
            print(f"[orchestrator] cleanup error: {e}")


def start_cleanup_thread():
    """Call once at backend startup — runs the idle-container reaper forever."""
    thread = threading.Thread(target=_cleanup_loop, daemon=True)
    thread.start()
