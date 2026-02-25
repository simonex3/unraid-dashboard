#!/usr/bin/env python3
"""Minimal HTTP server on port 8889 that runs a speedtest from the server side."""
import http.server
import json
import time
import ssl
import http.client

PORT = 8889
HOST = '127.0.0.1'


def measure_ping():
    ctx = ssl.create_default_context()
    t0 = time.perf_counter()
    conn = http.client.HTTPSConnection('speed.cloudflare.com', context=ctx, timeout=10)
    conn.request('GET', '/__down?bytes=1024')
    resp = conn.getresponse()
    resp.read()
    conn.close()
    return round((time.perf_counter() - t0) * 1000)


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
        else:
            self.send_error(404)

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

        body = json.dumps(result).encode()
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
