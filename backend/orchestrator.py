"""
Orchestrator: spins up a fresh, isolated Docker container per (session, lab)
pair, instead of everyone sharing one always-on container.

Why this exists:
When this platform is only running on your own machine for yourself, one
shared container per lab is fine. Once strangers use it at the same time,
sharing a container means one person's login state, database rows, or
crashes affect everyone else. Each visitor needs their own sandboxed copy.

How it works, in plain terms:
1. When someone clicks "Launch lab", the backend asks Docker to start a
   brand new container from that lab's pre-built image.
2. That container is given a random free port on the host and placed on an
   isolated Docker network with no outbound internet access (so it can't be
   used to attack anything else, even if someone breaks out of the app).
3. We remember which container belongs to which (session, lab) pair, so if
   the same person clicks "Launch" again, they get their existing container
   back rather than a new one every time.
4. A background thread checks every 60 seconds for containers nobody has
   used in a while, and destroys them, so abandoned containers don't pile
   up and eat server resources.

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
import socket

client = docker.from_env()

# Maps lab id -> the Docker image tag that lab was built as.
LAB_IMAGES = {
    "sqli-login": "lab-sqli-login:latest",
}

# Maps lab id -> the port the app listens on INSIDE its container.
LAB_INTERNAL_PORT = {
    "sqli-login": 5001,
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


def launch_lab(session_id, lab_id):
    """
    Returns the host port for a running container serving this lab for
    this session — reusing an existing one if it's still alive, or
    creating a new one if not.
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
        # listening. Without waiting here, the browser can open the lab
        # tab a moment too early and get a blank/failed connection. We
        # wait (briefly) until something is genuinely listening before
        # handing the URL back. Since the backend itself runs inside a
        # container, we check via the lab container's internal IP on our
        # shared network, not via the host-published port.
        internal_ip = container.attrs["NetworkSettings"]["Networks"][NETWORK_NAME]["IPAddress"]
        _wait_until_port_open(internal_ip, internal_port, timeout_seconds=10)

        _active_containers[key] = {
            "container_id": container.id,
            "host_port": host_port,
            "last_used": time.time(),
        }
        return host_port


def _wait_until_port_open(host, port, timeout_seconds=10):
    """Polls a TCP port until something is listening, or times out."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def stop_lab(session_id, lab_id):
    """
    Stops and removes the container for this (session, lab) pair, if one
    exists. Called when a user explicitly clicks "Stop lab" instead of
    waiting for the idle timeout to clean it up automatically.
    Returns True if a container was found and stopped, False otherwise.
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
