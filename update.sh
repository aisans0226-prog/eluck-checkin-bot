#!/bin/bash
# ============================================================
# update.sh — Pull latest code and restart Eluck bot services
# Usage: bash /opt/eluck-checkin-bot/update.sh
# ============================================================
set -e

PROJECT=/opt/eluck-checkin-bot
VENV=$PROJECT/venv
BOT_SERVICE=eluck-checkin-bot
DASH_SERVICE=eluck-dashboard

echo "[1/5] Pulling latest code from GitHub..."
cd $PROJECT
git pull origin master

echo "[2/5] Installing / upgrading Python packages..."
$VENV/bin/pip install -q --upgrade pip
$VENV/bin/pip install -q -r requirements.txt

echo "[3/5] Restarting bot service..."
systemctl restart $BOT_SERVICE

echo "[4/5] Restarting dashboard service..."
systemctl restart $DASH_SERVICE

echo "[5/5] Status:"
sleep 3
systemctl is-active $BOT_SERVICE && echo "  bot      : OK" || echo "  bot      : FAILED"
systemctl is-active $DASH_SERVICE && echo "  dashboard: OK" || echo "  dashboard: FAILED"

echo ""
echo "Done. Logs:"
echo "  journalctl -u $BOT_SERVICE -n 20 --no-pager"
echo "  journalctl -u $DASH_SERVICE -n 20 --no-pager"
