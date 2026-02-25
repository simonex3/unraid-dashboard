# Unraid Dashboard

A modern, single-page web dashboard for Unraid servers. Runs as a Docker container directly on the Unraid host.

## Features

- **System Overview** — hostname, Unraid version, uptime
- **CPU** — live gauge, per-core usage, 30-point sparkline history
- **RAM** — real usage gauge (excluding buffer/cache), available memory display
- **Network** — live RX/TX graphs updated every 15 seconds
- **Array & Disks** — all drives including parities and cache pools
- **Docker Containers** — status, image, sorted by running state
- **VMs** — virtual machine list with state
- **Shares** — all user shares with free space
- **Speedtest** — on-demand test from the server itself (against Cloudflare), with history modal, trend charts and CSV export

## Screenshots

> Dark theme, orange accent color, monospace + Syne fonts

## Requirements

- Unraid 6.12+ with GraphQL API enabled
- Docker available on the Unraid host

## Configuration

Before building, edit **two lines** in `index.html`:

```js
// Line ~615 in index.html
const UNRAID_API_KEY = 'YOUR_UNRAID_API_KEY';
```

**Where to find your API key:**
Unraid WebUI → Settings → Management Access → API Key

The server IP is detected automatically from the browser URL — no need to configure it.

## Quick Start (docker-compose)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/unraid-dashboard.git
cd unraid-dashboard

# 2. Set your API key in index.html (see Configuration above)

# 3. Build and start
docker compose up -d
```

Dashboard is available at: `http://YOUR_UNRAID_IP:8888`

## Manual Deploy

```bash
# Copy files to Unraid
scp index.html Dockerfile nginx.conf speedtest_server.py start.sh \
    root@YOUR_UNRAID_IP:/boot/config/plugins/dockerMan/unraid-dashboard/

# Build and run on Unraid
ssh root@YOUR_UNRAID_IP "cd /boot/config/plugins/dockerMan/unraid-dashboard && \
    docker build -t unraid-dashboard:latest . && \
    docker stop unraid-dashboard 2>/dev/null; docker rm unraid-dashboard 2>/dev/null; \
    docker run -d --name unraid-dashboard --restart=unless-stopped \
    -p 8888:8888 unraid-dashboard:latest"
```

## How it Works

| Component | Description |
|---|---|
| `index.html` | Complete UI — HTML, CSS, JS in one file |
| `Dockerfile` | nginx:alpine + Python 3 |
| `nginx.conf` | Serves dashboard on port 8888, proxies `/api/speedtest` |
| `speedtest_server.py` | Python HTTP server (port 8889), measures against Cloudflare |
| `start.sh` | Starts Python backend + nginx |

The dashboard polls the Unraid GraphQL API every 15 seconds. All queries use individual `.catch()` handlers so a failing endpoint doesn't break the rest of the UI.

## Speedtest History

Results are stored in the browser's `localStorage` (up to 50 entries). Click **DETAILS** on the speedtest card to view:
- Average download / upload / ping
- Trend sparklines
- Full history table with CSV export

## Tech Stack

- Pure HTML / CSS / JavaScript — no build step, no framework
- nginx:alpine Docker image
- Google Fonts: [Syne](https://fonts.google.com/specimen/Syne) + [Space Mono](https://fonts.google.com/specimen/Space+Mono)
- Dark theme, `#f97316` orange accent

## License

MIT
