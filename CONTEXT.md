# Unraid Dashboard - Projektkontext

## Ziel
Modernes Web-Dashboard für Unraid Server, läuft als Docker Container auf dem Server selbst.

## Server
- IP: 192.168.178.112
- SSH: root@192.168.178.112 (Key-Auth, kein Passwort)
- Dashboard Port: 8888 -> http://192.168.178.112:8888
- Dateien auf Server: /boot/config/plugins/dockerMan/unraid-dashboard/

## Unraid GraphQL API
- Endpoint: http://192.168.178.112/graphql
- Auth Header: x-api-key: 1976740970e7dcf51c8ff2863232bad9b52f732c8b730a9d0ab622e664a8c833

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

# Netzwerk (Status: noch nicht verifiziert, wird mit Fallback abgefragt)
query { network { interfaces { name rxBytes txBytes } } }
# Fallback:
query { metrics { network { interfaces { name rxBytes txBytes } } } }
```

## Bekannte Eigenheiten / wichtige Hinweise
- **Disk-Größen** werden in KB geliefert -> `fmtKB()` verwenden
- **Memory-Werte** werden in Bytes geliefert -> `fmtBytes()` verwenden
- **memory.free** = wirklich freier RAM (sehr klein, da Linux Speicher als Cache nutzt)
  - "Verfügbar" korrekt berechnen als `total - used` (= free + buffcache)
  - Gauge-Prozent: `used / total * 100` (nicht `percentTotal`, der ggf. Cache einrechnet)
- **Netzwerk-Query** ist noch nicht gegen die API verifiziert; Fehler werden still abgefangen
- **VMs**: Kein `type`-Feld im Schema vorhanden (wurde entfernt)
- **Server Info**: `server { name version uptime }` existiert nicht; korrekte Felder: `vars { name }` und `info { ... }`

## Gelöste Probleme (Changelog)
| Datum      | Problem / Feature                          | Lösung                                                    |
|------------|--------------------------------------------|-----------------------------------------------------------|
| 2026-02-25 | RAM-Anzeige zeigte falschen "freien" Wert  | Verfügbar = `total - used`, Gauge auf `used/total*100`    |
| 2026-02-25 | CPU nur als Gauge, kein Verlauf            | Sparkline (SVG Area-Chart, 30 Punkte History)             |
| 2026-02-25 | Netzwerk nicht dargestellt                 | Neues Netzwerk-Card mit RX/TX Graphen (delta/s)           |
| 2026-02-25 | Schrift schlecht lesbar (zu klein/dunkel)  | --muted auf #94a3b8, Mindest-Fontgröße 11-12px            |
| 2026-02-25 | Speedtest ohne Historie                    | Modal mit localStorage-Historie, Trend-Sparklines, Tabelle |
| 2026-02-25 | Array zeigte nur `disks`, nicht Parities   | Query auf parities + disks + caches erweitert             |

## Offene TODOs
- Netzwerk-Query gegen API verifizieren (rxBytes/txBytes Feldnamen prüfen)
- Speedtest: Server-seitige Historie (aktuell nur localStorage = browserseitig)
- GitHub Remote: https://github.com/simonex3/unraid-dashboard (privat, verbunden)

## GitHub Workflow

**Datei-Struktur:**
- `index.html`        → Sanitized (Placeholder-Key) — in Git, öffentlich teilbar
- `index.html.local`  → Echte Credentials — NIEMALS committen, in `.gitignore`

**Zum GitHub pushen:**
```bash
bash publish.sh "Beschreibung der Änderung"
```
Das Skript ersetzt automatisch den echten API Key mit `YOUR_UNRAID_API_KEY` bevor es pusht.

**Für lokale Entwicklung und Deployments immer `index.html.local` bearbeiten!**

**GitHub Repo einrichten (einmalig, falls noch nicht gemacht):**
```bash
# 1. Repo auf github.com erstellen (privat)
# 2. Remote verbinden:
git remote add origin https://github.com/DEIN_USERNAME/unraid-dashboard.git
git push -u origin master
```

## Deploy-Workflow
```bash
# Alle Dateien auf Server kopieren
scp index.html Dockerfile nginx.conf speedtest_server.py start.sh \
    root@192.168.178.112:/boot/config/plugins/dockerMan/unraid-dashboard/

# Container neu bauen und starten
ssh root@192.168.178.112 "cd /boot/config/plugins/dockerMan/unraid-dashboard && \
    docker build -t unraid-dashboard:latest . && \
    docker stop unraid-dashboard && \
    docker rm unraid-dashboard && \
    docker run -d --name unraid-dashboard --restart=unless-stopped \
    --network host unraid-dashboard:latest"
```

## Architektur / Design-Entscheidungen
- **Kein Framework** - reines HTML/CSS/JS, eine einzige index.html
- **Polling** alle 15 Sekunden via `setInterval(loadAll, 15000)`
- **Netzwerk-Graph**: Delta zwischen zwei Messungen / verstrichene Zeit = Bytes/s
- **CPU-Sparkline**: `cpuHistory[]` Array (max 30), wird bei jedem `renderMetrics()` befüllt
- **Speedtest-Historie**: `localStorage` Key `unraid_speedtest_history`, max 50 Einträge (JSON)
- **Fehlerbehandlung**: Jede GQL-Query hat `.catch()` - ein Fehler blockiert nicht die anderen
- **Gauge-Circumference**: C = 226.19 (Kreis r=36, 2π×36 ≈ 226.19)

## Tech Stack
- Reines HTML/CSS/JS (kein Framework)
- nginx:alpine Docker Container
- Python 3 (speedtest_server.py, Port 8889 intern, via nginx auf 8888 proxied)
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
- `index.html`           -> Das Dashboard (alle UI + JS)
- `Dockerfile`           -> Docker Build (nginx:alpine + python3)
- `nginx.conf`           -> nginx auf Port 8888, proxied /api/speedtest -> 8889
- `speedtest_server.py`  -> Python HTTP Server Port 8889, misst gegen speed.cloudflare.com
- `start.sh`             -> Startet Python-Backend + nginx
- `CONTEXT.md`           -> Diese Datei
