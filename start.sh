#!/bin/sh
# Start Python speedtest backend in background
python3 /speedtest_server.py &
# Start nginx in foreground (keeps container alive)
exec nginx -g 'daemon off;'
