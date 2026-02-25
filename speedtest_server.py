#!/usr/bin/env python3
"""Minimal HTTP server on port 8889: speedtest + network stats + history."""
import http.server
import json
import time
import ssl
import http.client
import subprocess
import re
import os
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

PORT = 8889
HOST = "127.0.0.1"
STATE_FILE = os.environ.get("DASHBOARD_STATE_FILE", "/tmp/unraid_dashboard_state.json")
DEFAULT_SPEEDTEST_CRON_MINUTES = max(0, int(os.environ.get("SPEEDTEST_CRON_MINUTES", "240")))
MAX_SPEEDTEST_CRON_MINUTES = 14 * 24 * 60
SPEEDTEST_HISTORY_LIMIT = max(10, int(os.environ.get("SPEEDTEST_HISTORY_LIMIT", "500")))

# Interfaces to prefer for network stats (in order)
_NET_PREFER = ["bond0", "eth0", "eth1", "ens3", "ens0", "enp3s0", "enp0s3"]
# Interfaces / prefixes to always ignore
_NET_IGNORE = {"lo", "tunl0", "virbr0", "docker0", "tailscale1"}
_NET_IGNORE_PFX = ("veth", "br-", "vnet", "tun", "tap")

_state_lock = threading.Lock()
_speedtest_lock = threading.Lock()
_state = {"speedtest_history": [], "speedtest_config": {"cron_minutes": DEFAULT_SPEEDTEST_CRON_MINUTES}}


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso_to_epoch(ts):
    try:
        if not ts:
            return None
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _load_state():
    global _state
    try:
        if not os.path.exists(STATE_FILE):
            return
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        history = raw.get("speedtest_history", []) if isinstance(raw, dict) else []
        config_raw = raw.get("speedtest_config", {}) if isinstance(raw, dict) else {}
        cron_minutes = int(config_raw.get("cron_minutes", DEFAULT_SPEEDTEST_CRON_MINUTES))
        cron_minutes = max(0, min(MAX_SPEEDTEST_CRON_MINUTES, cron_minutes))
        if not isinstance(history, list):
            history = []
        cleaned = []
        for entry in history:
            if not isinstance(entry, dict) or not entry.get("ts"):
                continue
            cleaned.append(
                {
                    "ts": entry["ts"],
                    "source": entry.get("source", "manual"),
                    "ping": entry.get("ping"),
                    "download": entry.get("download"),
                    "upload": entry.get("upload"),
                }
            )
        _state = {
            "speedtest_history": cleaned[:SPEEDTEST_HISTORY_LIMIT],
            "speedtest_config": {"cron_minutes": cron_minutes},
        }
    except Exception:
        _state = {"speedtest_history": [], "speedtest_config": {"cron_minutes": DEFAULT_SPEEDTEST_CRON_MINUTES}}


def _save_state_locked():
    tmp_file = f"{STATE_FILE}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(_state, f, separators=(",", ":"))
    os.replace(tmp_file, STATE_FILE)


def _append_speedtest_result_locked(result, source):
    entry = {
        "ts": now_iso(),
        "source": source,
        "ping": result.get("ping"),
        "download": result.get("download"),
        "upload": result.get("upload"),
    }
    _state["speedtest_history"].insert(0, entry)
    if len(_state["speedtest_history"]) > SPEEDTEST_HISTORY_LIMIT:
        del _state["speedtest_history"][SPEEDTEST_HISTORY_LIMIT:]
    _save_state_locked()


def get_speedtest_history():
    with _state_lock:
        return list(_state["speedtest_history"])


def clear_speedtest_history():
    with _state_lock:
        _state["speedtest_history"] = []
        _save_state_locked()


def get_cron_minutes():
    with _state_lock:
        return int(_state.get("speedtest_config", {}).get("cron_minutes", DEFAULT_SPEEDTEST_CRON_MINUTES))


def set_cron_minutes(value):
    minutes = max(0, min(MAX_SPEEDTEST_CRON_MINUTES, int(value)))
    with _state_lock:
        _state.setdefault("speedtest_config", {})
        _state["speedtest_config"]["cron_minutes"] = minutes
        _save_state_locked()
    return minutes


def read_net_dev():
    """Parse /proc/net/dev and return {iface: {rxBytes, txBytes}}.
    Prefers /host-proc-net-dev (host-mounted) over the container's own /proc/net/dev."""
    result = {}
    try:
        path = "/host-proc-net-dev" if os.path.exists("/host-proc-net-dev") else "/proc/net/dev"
        with open(path, "r", encoding="utf-8") as f:
            for line in f.readlines()[2:]:  # skip 2-line header
                if ":" not in line:
                    continue
                name, data = line.split(":", 1)
                name = name.strip()
                fields = data.split()
                if len(fields) < 9:
                    continue
                result[name] = {
                    "rxBytes": int(fields[0]),
                    "txBytes": int(fields[8]),
                }
    except Exception:
        pass
    return result


def pick_main_iface(stats):
    """Return the name of the primary network interface."""
    for pref in _NET_PREFER:
        if pref in stats:
            return pref
    candidates = [
        (k, v["rxBytes"] + v["txBytes"])
        for k, v in stats.items()
        if k not in _NET_IGNORE and not k.startswith(_NET_IGNORE_PFX)
    ]
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0] if candidates else None


def measure_ping(host="1.1.1.1", count=5):
    """ICMP ping via system ping command: accurate latency without TLS overhead."""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", "2", host],
            capture_output=True,
            text=True,
            timeout=20,
        )
        match = re.search(r"(?:rtt|round-trip) min/avg/max(?:/mdev)? = [\d.]+/([\d.]+)/", result.stdout)
        if match:
            return round(float(match.group(1)))
    except Exception:
        pass
    return None


def measure_download():
    size = 50 * 1024 * 1024  # 50 MB
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("speed.cloudflare.com", context=ctx, timeout=60)
    conn.request("GET", f"/__down?bytes={size}")
    resp = conn.getresponse()
    received = 0
    t0 = time.perf_counter()
    while True:
        chunk = resp.read(65536)
        if not chunk:
            break
        received += len(chunk)
    elapsed = time.perf_counter() - t0
    conn.close()
    return round(received * 8 / elapsed / 1e6, 1)


def measure_upload():
    size = 10 * 1024 * 1024  # 10 MB
    data = bytes(size)
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("speed.cloudflare.com", context=ctx, timeout=60)
    conn.putrequest("POST", "/__up")
    conn.putheader("Content-Type", "application/octet-stream")
    conn.putheader("Content-Length", str(size))
    conn.endheaders()
    t0 = time.perf_counter()
    conn.send(data)
    resp = conn.getresponse()
    resp.read()
    elapsed = time.perf_counter() - t0
    conn.close()
    return round(size * 8 / elapsed / 1e6, 1)


def run_speedtest_measurements():
    result = {"ping": None, "download": None, "upload": None}
    try:
        result["ping"] = measure_ping()
    except Exception:
        pass
    try:
        result["download"] = measure_download()
    except Exception:
        pass
    try:
        result["upload"] = measure_upload()
    except Exception:
        pass
    return result


def perform_speedtest(source="manual"):
    if not _speedtest_lock.acquire(blocking=False):
        return None
    try:
        result = run_speedtest_measurements()
        with _state_lock:
            _append_speedtest_result_locked(result, source)
        return result
    finally:
        _speedtest_lock.release()


def should_run_cron():
    cron_minutes = get_cron_minutes()
    if cron_minutes <= 0:
        return False
    history = get_speedtest_history()
    if not history:
        return True
    last_epoch = _parse_iso_to_epoch(history[0].get("ts"))
    if not last_epoch:
        return True
    return (time.time() - last_epoch) >= cron_minutes * 60


def cron_worker():
    while True:
        try:
            if should_run_cron():
                perform_speedtest("cron")
        except Exception:
            pass
        time.sleep(30)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/speedtest":
            self.run_speedtest()
        elif path == "/api/speedtest/history":
            self.serve_speedtest_history()
        elif path == "/api/speedtest/config":
            self.serve_speedtest_config()
        elif path == "/api/network":
            self.serve_network()
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/speedtest/config":
            self.update_speedtest_config()
        else:
            self.send_error(404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path == "/api/speedtest/history":
            clear_speedtest_history()
            self._json({"ok": True})
        else:
            self.send_error(404)

    def serve_speedtest_history(self):
        self._json({"history": get_speedtest_history(), "cronMinutes": get_cron_minutes()})

    def serve_speedtest_config(self):
        self._json({"cronMinutes": get_cron_minutes(), "maxCronMinutes": MAX_SPEEDTEST_CRON_MINUTES})

    def update_speedtest_config(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query or "")
        if "cronMinutes" in query:
            raw_value = query.get("cronMinutes", [None])[0]
        else:
            body = self._read_json_body()
            raw_value = body.get("cronMinutes") if isinstance(body, dict) else None
        if raw_value is None:
            self._json({"error": "invalid payload"}, status=400)
            return
        try:
            cron_minutes = set_cron_minutes(raw_value)
        except Exception:
            self._json({"error": "invalid cronMinutes"}, status=400)
            return
        self._json({"ok": True, "cronMinutes": cron_minutes})

    def serve_network(self):
        stats = read_net_dev()
        iface = pick_main_iface(stats)
        if iface:
            payload = {
                "interface": iface,
                "rxBytes": stats[iface]["rxBytes"],
                "txBytes": stats[iface]["txBytes"],
                "ts": time.time(),
            }
        else:
            payload = {"error": "no interface found"}
        self._json(payload)

    def run_speedtest(self):
        result = perform_speedtest("manual")
        if result is None:
            self._json({"error": "speedtest already running"}, status=429)
            return
        self._json(result)

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    _load_state()
    threading.Thread(target=cron_worker, daemon=True).start()
    server = http.server.HTTPServer((HOST, PORT), Handler)
    server.serve_forever()
