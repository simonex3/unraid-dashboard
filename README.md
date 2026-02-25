# Unraid Dashboard

A modern, single-page web dashboard for Unraid servers. Runs as a Docker container directly on the Unraid host.

## Features

- **System Overview** — hostname, Unraid version, uptime
- **CPU** — live gauge, per-core usage, and persisted 14-day history
- **RAM** — real usage gauge (excluding buffer/cache), available memory display
- **Network** — live RX/TX graphs updated every 15 seconds
- **Array & Disks** — all drives including parities and cache pools
- **Docker Containers** — status, image, sorted by running state
- **VMs** — virtual machine list with state
- **Shares** — all user shares with free space
- **Speedtest** — on-demand test plus automatic cron runs on the server, with persisted history, trend charts and CSV export

## Screenshots

> Dark theme, orange accent color, monospace + Syne fonts

## Requirements

- Unraid 6.12+ with GraphQL API enabled
- Docker available on the Unraid host

## Getting your Unraid API Key

The dashboard connects to Unraid's built-in GraphQL API, which requires an API key for authentication. Here's how to get one:

1. Open your Unraid WebUI in the browser (e.g. `http://192.168.1.100`)
2. Go to **Settings** (top menu bar)
3. Click **Management Access** in the left sidebar
4. Scroll down to the **API Keys** section
5. Click **Add key** (or use the existing key if one already exists)
6. Give it a name (e.g. `dashboard`) and click **Create**
7. Copy the generated key — it looks like a long string of letters and numbers

> **Note:** The API key only works from within your local network. The dashboard itself runs on your Unraid server, so this is fine by default.

> **Unraid version:** API Keys require Unraid **6.12 or newer**. If you don't see the API Keys section, update Unraid first.

## Configuration

Open `index.html` in any text editor and replace the placeholder on **line ~615**:

```js
// ── KONFIGURATION ─────────────────────────────────────────────────
// API Key: Unraid → Einstellungen → Management Access → API Key
const UNRAID_API_KEY = 'YOUR_UNRAID_API_KEY';  // ← paste your key here
```

That's the only change needed. The server IP is detected automatically from the browser URL.

> **Tip:** Use a simple text editor like Notepad (Windows), TextEdit (Mac) or nano (Linux). Avoid Word or other rich-text editors as they may corrupt the file.

## Installation

### Option A — Deploy directly on your Unraid server (recommended)

This runs the build on the Unraid server itself. You need SSH access (enabled by default on Unraid).

**Step 1 — Download the files onto your Unraid server:**
```bash
# Run this in an SSH session on your Unraid server (or via the Unraid terminal)
mkdir -p /boot/config/plugins/dockerMan/unraid-dashboard
cd /boot/config/plugins/dockerMan/unraid-dashboard

# Download all required files
curl -LO https://github.com/simonex3/unraid-dashboard/raw/master/index.html
curl -LO https://github.com/simonex3/unraid-dashboard/raw/master/Dockerfile
curl -LO https://github.com/simonex3/unraid-dashboard/raw/master/nginx.conf
curl -LO https://github.com/simonex3/unraid-dashboard/raw/master/speedtest_server.py
curl -LO https://github.com/simonex3/unraid-dashboard/raw/master/start.sh
```

**Step 2 — Add your API key:**
```bash
# Open index.html and replace YOUR_UNRAID_API_KEY with your real key
nano index.html
# Search for: const UNRAID_API_KEY = 'YOUR_UNRAID_API_KEY';
# Replace:    const UNRAID_API_KEY = 'abc123...your-real-key...';
# Save with Ctrl+O, exit with Ctrl+X
```

**Step 3 — Build and start the container:**
```bash
docker build -t unraid-dashboard:latest . && \
docker run -d --name unraid-dashboard --restart=unless-stopped \
  --network host unraid-dashboard:latest
```

Dashboard is now available at: **`http://YOUR_UNRAID_IP:8888`**

---

### Option B — Clone & deploy from your PC

Requires Git and SSH access to your Unraid server.

```bash
# 1. Clone the repo on your PC
git clone https://github.com/simonex3/unraid-dashboard.git
cd unraid-dashboard

# 2. Add your API key (edit line ~615 in index.html)

# 3. Copy files to Unraid and build
scp index.html Dockerfile nginx.conf speedtest_server.py start.sh \
    root@YOUR_UNRAID_IP:/boot/config/plugins/dockerMan/unraid-dashboard/

ssh root@YOUR_UNRAID_IP "cd /boot/config/plugins/dockerMan/unraid-dashboard && \
    docker build -t unraid-dashboard:latest . && \
    docker stop unraid-dashboard 2>/dev/null; docker rm unraid-dashboard 2>/dev/null; \
    docker run -d --name unraid-dashboard --restart=unless-stopped \
    --network host unraid-dashboard:latest"
```

> **Why `--network host`?**
> The network graph reads live RX/TX data directly from the host system. Without this flag, the container would only see its own isolated network traffic instead of the real server traffic.

---

### Updating to a newer version

```bash
# On your Unraid server (SSH):
cd /boot/config/plugins/dockerMan/unraid-dashboard

# Re-download changed files (keep your index.html with your API key!)
curl -LO https://github.com/simonex3/unraid-dashboard/raw/master/Dockerfile
curl -LO https://github.com/simonex3/unraid-dashboard/raw/master/nginx.conf
curl -LO https://github.com/simonex3/unraid-dashboard/raw/master/speedtest_server.py
curl -LO https://github.com/simonex3/unraid-dashboard/raw/master/start.sh

# Rebuild
docker build -t unraid-dashboard:latest . && \
docker stop unraid-dashboard && docker rm unraid-dashboard && \
docker run -d --name unraid-dashboard --restart=unless-stopped \
  --network host unraid-dashboard:latest
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

Results are persisted server-side via the Python backend and exposed via `/api/speedtest/history`.
Default cron interval is every 240 minutes (configurable via `SPEEDTEST_CRON_MINUTES`, set `0` to disable).
Click **DETAILS** on the speedtest card to view:
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
