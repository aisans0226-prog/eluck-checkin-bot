#!/bin/bash
set -e
PROJECT=/opt/vpoker-checkin-bot
VENV=$PROJECT/venv
BOT=vpoker-bot
DASH=vpoker-dashboard
echo "[1/4] Pulling latest code..."
cd $PROJECT && git pull origin master
echo "[2/4] Installing dependencies..."
$VENV/bin/pip install -q --upgrade pip
$VENV/bin/pip install -q -r $PROJECT/requirements.txt
echo "[3/4] Restarting services..."
systemctl restart $BOT
systemctl restart $DASH
sleep 3
echo "[4/4] Status..."
systemctl is-active $BOT
systemctl is-active $DASH
echo "Done."
