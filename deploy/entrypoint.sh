#!/bin/sh
set -e
# Host sets PORT (e.g. 10000 on Render). App must stay on 8000 internally.
HOST_PORT="${PORT:-8080}"
PORT=8000 python server.py &
sleep 3
export PORT="$HOST_PORT"
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
