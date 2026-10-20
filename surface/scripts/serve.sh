#!/usr/bin/env bash
# serve.sh: publica site/ en la tailnet.
#
# http.server via launchd escuchando SOLO en la IP tailscale del host:
# el trafico tailnet ya va cifrado (WireGuard), TLS no agrega nada, y
# evita depender de que HTTPS certs esten habilitados en la tailnet.
# URL: http://<host>.<tailnet>.ts.net:8787
#
#   serve.sh          levanta el daemon (idempotente)
#   serve.sh off      apaga
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE="${SURFACE_SITE:-$ROOT/site}"
PORT="${SURFACE_PORT:-8787}"
LABEL="com.positronica.learning-surface"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${1:-}" = "off" ]; then
  launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "serve off"
  exit 0
fi

[ -f "$SITE/index.html" ] || { echo "corre scripts/bundle.sh primero" >&2; exit 1; }

TS_IP=$(tailscale ip -4 | head -1)
[ -n "$TS_IP" ] || { echo "tailscale sin IPv4" >&2; exit 1; }

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>-m</string><string>http.server</string>
    <string>$PORT</string>
    <string>--bind</string><string>$TS_IP</string>
    <string>--directory</string><string>$SITE</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
sleep 1

curl -sf "http://$TS_IP:$PORT/" -o /dev/null && echo "ok: http://$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || echo "$TS_IP"):$PORT/"
