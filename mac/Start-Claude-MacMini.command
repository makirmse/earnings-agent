#!/bin/zsh
# Double-click me on the Mac laptop: connects to the Mac Mini over Tailscale
# and starts a Claude Remote Control session in ~/research-engine.
# Leave the Terminal window open while you work; closing it ends the session.

# Open claude.ai/code directly into the Mac Mini's environment so new
# sessions run on the Mini, not in an Anthropic cloud sandbox.
( sleep 8; open "https://claude.ai/code?environment=env_01VXLXC3ke9RL4pfpacUiNcv" ) &

# -t gives us a real interactive screen; zsh -ic loads the Mini's normal
# shell setup (so `claude` is on PATH), then we drop the API key so
# Remote Control uses the claude.ai subscription login.
exec ssh -t projectx@100.99.13.95 'exec zsh -ic "unset ANTHROPIC_API_KEY; cd ~/research-engine; claude remote-control"'
