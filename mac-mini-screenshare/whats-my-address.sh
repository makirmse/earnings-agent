#!/bin/bash
#
# whats-my-address.sh
# -------------------
# Forgot the address to type on Windows? Run this ON THE MAC MINI:
#
#   bash whats-my-address.sh
#
# It just prints the Tailscale address. It changes nothing.

TS_BIN="$(command -v tailscale 2>/dev/null || true)"
if [ -z "$TS_BIN" ] && [ -x "/Applications/Tailscale.app/Contents/MacOS/Tailscale" ]; then
  TS_BIN="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
fi

if [ -z "$TS_BIN" ]; then
  echo "Tailscale not found. Open the Tailscale app and log in first."
  exit 1
fi

TS_IP="$("$TS_BIN" ip -4 2>/dev/null | head -n 1)"
TS_NAME="$(
  "$TS_BIN" status --json 2>/dev/null \
    | python3 -c "import sys,json;
d=json.load(sys.stdin)
print(d.get('Self',{}).get('DNSName','').rstrip('.'))" 2>/dev/null
)"

if [ -z "$TS_IP" ]; then
  echo "Tailscale does not look connected. Open the app and click Connect."
  exit 1
fi

echo
echo "Type this address on your Windows PC:"
echo
printf "    \033[0;32m%s\033[0m\n" "$TS_IP"
if [ -n "$TS_NAME" ]; then
  echo "    (or the name: ${TS_NAME})"
fi
echo
