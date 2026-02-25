# Unraid Dashboard - Projektkontext

## Ziel
Modernes Web-Dashboard für Unraid Server, läuft als Docker Container auf dem Server selbst.

## Server
- IP: 192.168.178.112
- SSH: root@192.168.178.112 (Key-Auth, kein Passwort)
- Dashboard Port: 8888 → http://192.168.178.112:8888
- Dateien auf Server: /boot/config/plugins/dockerMan/unraid-dashboard/

## Unraid GraphQL API
- Endpoint: http://192.168.178.112/graphql
- Auth Header: `x-api-key: YOUR_UNRAID_API_KEY`
- Key-Ablage lokal: nur in `index.html.local` (nie committen!)

## Funktionierende GraphQL Queries (verifiziert)
```graphql
# CPU + RAM Metriken
query { metrics { cpu { percentTotal cpus { percentTotal } } memory { total used free buffcache percentTotal swapTotal swapUsed swapFree percentSwapTotal } } }

# Array + Disks (inkl. Parities und Caches)
query { array { state parities { name size status temp } disks { name size status temp } caches { name size status temp } } }

# Docker Container
query { docker { containers { id names image state status } } }

# Shares
query { shares { name size free comment } }

# VMs (kein "type"-Feld verfügbar)
query { vms { domain { name state } } }

# Server Info
query { vars { name } info { os { uptime hostname } versions { core { unraid } } } }
```

## Nicht verfügbare GraphQL Felder (verifiziert per Introspection)
- `network { ... }` → existiert NICHT im Schema
- `metrics { network { ... } }` → existiert NICHT im Schema
- Netzwerk-Daten kommen stattdessen via Python-Backend aus `/proc/net/dev`

## Bekannte Eigenheiten / wichtige Hinweise

### RAM
- `memory.used` = `total - free` (enthält buffcache!) → NICHT direkt für Prozent verwenden
- `memory.percentTotal` = korrekte Metrik (API berechnet intern aus `MemAvailable`) → diese verwenden
- Echte App-Nutzung in Bytes: `used - buffcache`
- Beispiel-Werte: total=31.1GB, used=30.9GB, free=230MB, buffcache=25.1GB, percentTotal=77.67%

### Disk / Shares
- Disk-Größen und Share-Größen werden in **KB** geliefert → `fmtKB()` verwenden
- Memory-Werte in **Bytes** → `fmtBytes()` verwenden

### Netzwerk
- Kein GraphQL-Feld → Python-Backend liest `/proc/net/dev` des Hosts
- Endpoint: `GET /api/network` → `{interface, rxBytes, txBytes, ts}`
- Container muss mit `--network host` laufen, sonst sieht er nur Container-Interfaces
- Interface-Präferenz: bond0 > eth0 > eth1 > ..., ignoriert lo/veth*/br-*/docker0/virbr0

### Speedtest Ping
- Früher: HTTPS-Roundtrip gemessen (DNS + TCP + TLS + HTTP) → ~300ms (falsch!)
- Jetzt: echter ICMP-Ping via `ping -c 5 1.1.1.1` (Cloudflare Anycast) → ~19ms
- Alpine/Busybox ping-Format: `round-trip min/avg/max = X/Y/Z ms` (kein mdev, kein "rtt")

### Sonstiges
- VMs: Kein `type`-Feld im Schema vorhanden
- Server Info: `server { ... }` existiert nicht → `vars { name }` und `info { ... }` verwenden

## Changelog
| Datum      | Problem / Feature                            | Lösung                                                          |
|------------|----------------------------------------------|-----------------------------------------------------------------|
| 2026-02-25 | RAM zeigte falschen "freien" Wert            | Verfügbar = `free + buffcache`, Gauge = `memory.percentTotal`   |
| 2026-02-25 | CPU nur als Gauge, kein Verlauf              | SVG Sparkline, 30 Punkte History in `cpuHistory[]`              |
| 2026-02-25 | Netzwerk fehlte komplett                     | Python-Backend liest `/proc/net/dev`, `--network host` nötig    |
| 2026-02-25 | Schrift schlecht lesbar                      | `--muted` auf #94a3b8, Mindest-Fontgröße 11-12px               |
| 2026-02-25 | Speedtest ohne Historie                      | Modal mit localStorage (50 Einträge), Sparklines, CSV-Export    |
| 2026-02-25 | Array zeigte nur `disks`                     | Query auf parities + disks + caches erweitert                   |
| 2026-02-25 | RAM-Gauge zeigte 99% (falscher Algorithmus)  | Zurück zu `memory.percentTotal` (API-Wert ist korrekt)          |
| 2026-02-25 | RAM-Gauge zeigte 19% (zu aggressiver Fix)    | `used - buffcache` war falsch, da `used` schon buffcache enthält|
| 2026-02-25 | Netzwerk-Graph leer (kein GraphQL-Feld)      | `/api/network` Endpoint im Python-Backend, liest /proc/net/dev  |
| 2026-02-25 | Netzwerk zeigte Container-IFs statt Host-IFs | Container auf `--network host` umgestellt                       |
| 2026-02-25 | Speedtest Ping viel zu hoch (~300ms)         | ICMP-Ping via `subprocess ping 1.1.1.1`, Busybox-Regex fix      |
| 2026-02-25 | Harte Host-IP im Dashboard                   | Host/API-Adresse wird dynamisch aus `location.hostname` ermittelt |
| 2026-02-25 | CPU-Verlauf zu kurz                          | 14-Tage-Historie (1-Min-Sampling) in `localStorage` eingeführt   |
| 2026-02-25 | Speedtest nur manuell/local                  | Server-Cron + persistente History API (`/api/speedtest/history`) |
| 2026-02-25 | CPU/Netzwerk ohne Detailansicht              | Klickbare Detail-Modals mit Zeitraumfilter (1h/6h/24h/7d/14d)    |
| 2026-02-25 | Speedtest-Cron nicht im UI einstellbar       | Cron-Input + Save-Button, neue Config-API (`/api/speedtest/config`) |

## Offene TODOs
- RAM: kein `MemAvailable`-Feld in der API — Bytes-Anzeige weicht vom Gauge-% ab

## GitHub Workflow

**Datei-Struktur:**
- `index.html`        → Sanitized (API Key = Placeholder) — in Git
- `index.html.local`  → Echte Credentials — NIEMALS committen, in `.gitignore`
- `CONTEXT.md`        → Wird ebenfalls sanitized (API Key ersetzt)

**Zum GitHub pushen:**
```bash
bash publish.sh "Beschreibung der Änderung"
```
Das Skript ersetzt automatisch den echten API Key in `index.html` und `CONTEXT.md`.

**Für lokale Entwicklung und Deployments immer `index.html.local` bearbeiten!**

## Deploy-Workflow
```bash
# Alle Dateien auf Server kopieren
scp index.html.local root@192.168.178.112:/boot/config/plugins/dockerMan/unraid-dashboard/index.html
scp Dockerfile nginx.conf speedtest_server.py start.sh \
    root@192.168.178.112:/boot/config/plugins/dockerMan/unraid-dashboard/

# Container neu bauen und starten (--network host für Netzwerk-Stats!)
ssh root@192.168.178.112 "cd /boot/config/plugins/dockerMan/unraid-dashboard && \
    docker build -t unraid-dashboard:latest . && \
    docker stop unraid-dashboard && \
    docker rm unraid-dashboard && \
    docker run -d --name unraid-dashboard --restart=unless-stopped \
    --network host unraid-dashboard:latest"
```

## Architektur / Design-Entscheidungen
- **Kein Framework** — reines HTML/CSS/JS, eine einzige `index.html`
- **Polling** alle 15 Sekunden via `setInterval(loadAll, 15000)`
- **Netzwerk-Graph**: `/api/network` alle 15s pollen, Delta rxBytes/txBytes / Δt = Bytes/s
- **CPU-Sparkline**: 14-Tage-Historie in `localStorage` (`unraid_cpu_history_v1`, 1-Min-Sampling), fürs Rendering auf max. 300 Punkte gesampelt
- **CPU-Detailmodal**: Zeitraumfilter (1h/6h/24h/7d/14d), Trendchart + Tabelle
- **Netzwerk-Detailmodal**: 14-Tage-Historie in `localStorage` (`unraid_net_history_v1`, 1-Min-Sampling), Zeitraumfilter + Trends
- **Speedtest-Historie**: serverseitig im Python-Backend persistiert (`/tmp/unraid_dashboard_state.json`), Modal lädt via `/api/speedtest/history`
- **Speedtest-Cron-Konfiguration**: Backend-konfigurierbar via `/api/speedtest/config` (GET/POST), UI setzt Minutenintervall
- **Fehlerbehandlung**: Jede GQL-Query hat `.catch()` — ein Fehler blockiert nicht die anderen
- **Gauge-Circumference**: C = 226.19 (Kreis r=36, 2π×36 ≈ 226.19)
- **Sparkline-Formel**: `y = height - (value / max) * (height - 4) - 2` (2px Padding)

## Backend API (Python)
- `GET /api/network` → Host-Netzwerkbytes (`rxBytes`, `txBytes`, `interface`)
- `GET /api/speedtest` → Führt sofortigen Speedtest aus
- `GET /api/speedtest/history` → Persistente Speedtest-Historie + aktuelles Cron-Intervall
- `DELETE /api/speedtest/history` → Löscht Speedtest-Historie
- `GET /api/speedtest/config` → Liefert Cron-Konfiguration (`cronMinutes`)
- `POST /api/speedtest/config?cronMinutes=N` → Setzt Cron-Intervall (0 = deaktiviert)

## Tech Stack
- Reines HTML/CSS/JS (kein Framework)
- nginx:alpine Docker Container, läuft mit `--network host`
- Python 3 (`speedtest_server.py`, Port 8889 intern, nginx proxied /api/speedtest + /api/network)
- Font: Syne (Überschriften) + Space Mono (Monospace/Daten) via Google Fonts
- Design: Dark Theme, Orange Akzentfarbe (#f97316)

## CSS Design-Variablen
```css
--bg:       #0a0c10
--surface:  #10141c
--surface2: #161b26
--border:   #1e2535
--accent:   #f97316  (Orange)
--blue:     #38bdf8
--green:    #4ade80
--red:      #f87171
--yellow:   #facc15
--text:     #e2e8f0
--muted:    #94a3b8  (aufgehellt von #64748b für bessere Lesbarkeit)
```

## Projektdateien
- `index.html`           → Das Dashboard (alle UI + JS), sanitized für Git
- `index.html.local`     → Wie index.html, aber mit echten Credentials (nur lokal)
- `Dockerfile`           → Docker Build (nginx:alpine + python3)
- `nginx.conf`           → nginx Port 8888, proxied /api/speedtest + /api/network → 8889
- `speedtest_server.py`  → Python HTTP Server Port 8889: Speedtest, Cron, History + Config API, `/proc/net/dev`
- `start.sh`             → Startet Python-Backend + nginx
- `publish.sh`           → Sanitized index.html + CONTEXT.md und pusht zu GitHub
- `CONTEXT.md`           → Diese Datei
