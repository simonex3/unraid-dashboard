#!/usr/bin/env python3
"""Minimal HTTP server on port 8889 — speedtest + network stats."""
import http.server
import json
import time
import ssl
import http.client
import subprocess
import re

PORT = 8889
HOST = '127.0.0.1'

# Interfaces to prefer for network stats (in order)
_NET_PREFER = ['bond0', 'eth0', 'eth1', 'ens3', 'ens0', 'enp3s0', 'enp0s3']
# Interfaces / prefixes to always ignore
_NET_IGNORE  = {'lo', 'tunl0', 'virbr0', 'docker0', 'tailscale1'}
_NET_IGNORE_PFX = ('veth', 'br-', 'vnet', 'tun', 'tap')


def read_net_dev():
    """Parse /proc/net/dev and return {iface: {rxBytes, txBytes}}.
    Prefers /host-proc-net-dev (host-mounted) over the container's own /proc/net/dev."""
    result = {}
    try:
        path = '/host-proc-net-dev' if __import__('os').path.exists('/host-proc-net-dev') else '/proc/net/dev'
        with open(path) as f:
            for line in f.readlines()[2:]:  # skip 2-line header
                if ':' not in line:
                    continue
                name, data = line.split(':', 1)
                name = name.strip()
                fields = data.split()
                if len(fields) < 9:
                    continue
                result[name] = {
                    'rxBytes': int(fields[0]),
                    'txBytes': int(fields[8]),
                }
    except Exception:
        pass
    return result


def pick_main_iface(stats):
    """Return the name of the primary network interface."""
    # 1. preferred list
    for pref in _NET_PREFER:
        if pref in stats:
            return pref
    # 2. first non-ignored interface with traffic, sorted by rx+tx desc
    candidates = [
        (k, v['rxBytes'] + v['txBytes'])
        for k, v in stats.items()
        if k not in _NET_IGNORE and not k.startswith(_NET_IGNORE_PFX)
    ]
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0] if candidates else None


def measure_ping(host='1.1.1.1', count=5):
    """ICMP ping via system ping command — accurate latency without TLS overhead.
    Uses 1.1.1.1 (Cloudflare anycast) which routes to the nearest datacenter."""
    try:
        result = subprocess.run(
            ['ping', '-c', str(count), '-W', '2', host],
            capture_output=True, text=True, timeout=20
        )
        # Supports both formats:
        #   iputils:  "rtt min/avg/max/mdev = 5.1/6.4/7.8/0.3 ms"
        #   busybox:  "round-trip min/avg/max = 18.7/18.9/19.0 ms"
        match = re.search(r'(?:rtt|round-trip) min/avg/max(?:/mdev)? = [\d.]+/([\d.]+)/', result.stdout)
        if match:
            return round(float(match.group(1)))
    except Exception:
        pass
    return None


def measure_download():
    size = 50 * 1024 * 1024  # 50 MB
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection('speed.cloudflare.com', context=ctx, timeout=60)
    conn.request('GET', f'/__down?bytes={size}')
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
    conn = http.client.HTTPSConnection('speed.cloudflare.com', context=ctx, timeout=60)
    conn.putrequest('POST', '/__up')
    conn.putheader('Content-Type', 'application/octet-stream')
    conn.putheader('Content-Length', str(size))
    conn.endheaders()
    t0 = time.perf_counter()
    conn.send(data)
    resp = conn.getresponse()
    resp.read()
    elapsed = time.perf_counter() - t0
    conn.close()
    return round(size * 8 / elapsed / 1e6, 1)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/speedtest':
            self.run_speedtest()
        elif self.path == '/api/network':
            self.serve_network()
        else:
            self.send_error(404)

    def serve_network(self):
        stats = read_net_dev()
        iface = pick_main_iface(stats)
        if iface:
            payload = {
                'interface': iface,
                'rxBytes':   stats[iface]['rxBytes'],
                'txBytes':   stats[iface]['txBytes'],
                'ts':        time.time(),
            }
        else:
            payload = {'error': 'no interface found'}
        self._json(payload)

    def run_speedtest(self):
        result = {'ping': None, 'download': None, 'upload': None}
        try:
            result['ping'] = measure_ping()
        except Exception:
            pass
        try:
            result['download'] = measure_download()
        except Exception:
            pass
        try:
            result['upload'] = measure_upload()
        except Exception:
            pass
        self._json(result)

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # Silence access logs


if __name__ == '__main__':
    server = http.server.HTTPServer((HOST, PORT), Handler)
    server.serve_forever()
