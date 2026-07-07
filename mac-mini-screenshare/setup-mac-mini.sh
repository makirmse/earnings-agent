#!/bin/bash
#
# setup-mac-mini.sh
# -----------------
# Run this ON YOUR MAC MINI, one time, to turn on Screen Sharing and find out
# the exact address you'll type on your Windows PC.
#
# How to run it:
#   1. On the Mac Mini, open the Terminal app.
#   2. Go to this folder, e.g.:   cd ~/projects/earnings-agent/mac-mini-screenshare
#   3. Run:                       bash setup-mac-mini.sh
#   4. Type your Mac password if it asks (it needs admin rights to flip switches).
#
# It will NOT change anything on your Windows PC. It only sets up the Mac Mini
# and prints the address for you. Nothing here is destructive.

# Pretty printing helpers ----------------------------------------------------
bold() { printf "\033[1m%s\033[0m\n" "$1"; }
green() { printf "\033[0;32m%s\033[0m\n" "$1"; }
yellow() { printf "\033[0;33m%s\033[0m\n" "$1"; }
red() { printf "\033[0;31m%s\033[0m\n" "$1"; }
line() { printf "%s\n" "------------------------------------------------------------"; }

echo
bold "Mac Mini Screen Sharing setup"
line

# 0. Sanity check: are we actually on a Mac? -------------------------------
if [ "$(uname -s)" != "Darwin" ]; then
  red "This script is meant to run on your Mac Mini (macOS), not on this machine."
  echo "Copy this folder to the Mac Mini and run it there."
  exit 1
fi

# 1. Find the Tailscale command --------------------------------------------
# Tailscale can be installed a few different ways; check the common spots.
TS_BIN="$(command -v tailscale 2>/dev/null || true)"
if [ -z "$TS_BIN" ] && [ -x "/Applications/Tailscale.app/Contents/MacOS/Tailscale" ]; then
  TS_BIN="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
fi

if [ -z "$TS_BIN" ]; then
  red "Could not find Tailscale on this Mac."
  echo "Open the Tailscale app once and make sure you are logged in, then run this again."
  echo "If you installed the app from the Mac App Store, just opening it is enough."
  exit 1
fi

# Make sure Tailscale is actually connected.
if ! "$TS_BIN" status >/dev/null 2>&1; then
  yellow "Tailscale is installed but does not look connected."
  echo "Open the Tailscale app (menu bar icon) and click 'Connect' / log in, then run this again."
  exit 1
fi

# 2. Get this Mac's Tailscale address --------------------------------------
TS_IP="$("$TS_BIN" ip -4 2>/dev/null | head -n 1)"

# The friendly MagicDNS name (if MagicDNS is turned on for your tailnet).
TS_NAME="$(
  "$TS_BIN" status --json 2>/dev/null \
    | python3 -c "import sys,json;
d=json.load(sys.stdin)
print(d.get('Self',{}).get('DNSName','').rstrip('.'))" 2>/dev/null
)"

if [ -z "$TS_IP" ]; then
  red "Tailscale is connected but did not return an IP address."
  echo "Try opening the Tailscale app and reconnecting, then run this again."
  exit 1
fi

# 3. Turn on Screen Sharing (best effort) ----------------------------------
bold "Turning on Screen Sharing..."
echo "(You may be asked for your Mac password.)"

# Try the modern command first, then the older one. Errors are fine to ignore
# here because we verify below whether it actually came on.
sudo launchctl enable system/com.apple.screensharing >/dev/null 2>&1 || true
sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.screensharing.plist >/dev/null 2>&1 || true

# 4. Verify Screen Sharing is really listening -----------------------------
# macOS Screen Sharing (VNC) listens on port 5900 when it is on.
SHARING_ON="no"
if lsof -nP -iTCP:5900 -sTCP:LISTEN >/dev/null 2>&1; then
  SHARING_ON="yes"
fi

echo
line
if [ "$SHARING_ON" = "yes" ]; then
  green "Screen Sharing is ON. You're ready to connect from Windows."
else
  yellow "I could not confirm Screen Sharing turned on automatically."
  echo "Please turn it on by hand (takes 10 seconds):"
  echo
  echo "  System Settings  ->  General  ->  Sharing"
  echo "  Turn ON the 'Screen Sharing' switch."
  echo
  echo "Tip: click the (i) info button next to Screen Sharing, and if you see"
  echo "'VNC viewers may control screen with password', turn it on and set a"
  echo "password. That makes Windows VNC apps connect most reliably."
fi
line

# 5. Print the address to use on Windows -----------------------------------
echo
bold "USE THIS ADDRESS ON YOUR WINDOWS PC:"
echo
green "    ${TS_IP}"
if [ -n "$TS_NAME" ]; then
  echo "    (or the name: ${TS_NAME})"
fi
echo
echo "In your Windows VNC viewer, connect to the address above."
echo "It works from anywhere as long as BOTH computers are signed in to"
echo "Tailscale with the same account."
echo
bold "Next: open the README in this folder for the Windows steps."
echo
