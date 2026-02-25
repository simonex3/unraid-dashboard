#!/bin/sh
# Optional scheduler tuning:
#   SPEEDTEST_CRON_MINUTES=240 (default, set 0 to disable)
#   SPEEDTEST_HISTORY_LIMIT=500
export SPEEDTEST_CRON_MINUTES="${SPEEDTEST_CRON_MINUTES:-240}"
export SPEEDTEST_HISTORY_LIMIT="${SPEEDTEST_HISTORY_LIMIT:-500}"

# Start Python speedtest backend in background
python3 /speedtest_server.py &
# Start nginx in foreground (keeps container alive)
exec nginx -g 'daemon off;'
