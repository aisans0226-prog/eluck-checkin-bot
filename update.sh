#!/bin/bash
set -e
PROJECT=/opt/eluck-checkin-bot
VENV=$PROJECT/venv
BOT=eluck-checkin-bot
DASH=eluck-dashboard
echo "[1/5] git pull..."
cd $PROJECT && git pull origin master
echo "[2/5] pip install..."
$VENV/bin/pip install -q --upgrade pip
$VENV/bin/pip install -q -r $PROJECT/requirements.txt
echo "[3/5] restart bot..."
systemctl restart $BOT
echo "[4/5] restart dashboard..."
systemctl restart $DASH
echo "[5/5] checking status..."
sleep 3
systemctl is-active $BOT && echo "  bot: OK" || echo "  bot: FAILED"
systemctl is-active $DASH && echo "  dashboard: OK" || echo "  dashboard: FAILED"
echo "Update complete."
