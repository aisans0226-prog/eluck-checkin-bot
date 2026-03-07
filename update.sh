#!/bin/bash
# ─────────────────────────────────────────────────────────────
# update.sh — Deploy script for ELUCK Check-in Bot
# VPS path : /opt/eluck-checkin-bot
# Services : eluck-checkin-bot   (bot)
#            eluck-dashboard     (Flask dashboard)
# ─────────────────────────────────────────────────────────────
set -e
source "$(dirname "$0")/deploy.conf"

echo "[1/4] Pulling latest code..."
cd "$PROJECT" && git pull origin master
echo "[2/4] Installing dependencies..."
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$PROJECT/requirements.txt"
echo "[3/4] Restarting services..."
systemctl restart "$BOT" "$DASH"
sleep 3
echo "[4/4] Status..."
systemctl is-active "$BOT"
systemctl is-active "$DASH"
echo "Done."
