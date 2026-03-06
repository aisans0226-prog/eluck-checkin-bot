# 🎰 Telegram Community Check-in Bot

Production-ready Telegram bot for community engagement — daily check-ins, streak tracking, leaderboard, referral system, task system, and full admin tooling.

---

## Features

| Feature | Details |
|---|---|
| ✅ Daily Check-in | One check-in per day, anti-spam guard |
| 🔥 Streak System | Auto-reset if user misses a day |
| 🎁 Milestone Rewards | Bonus points at 7 / 30 / 100 / 365 days |
| 👤 Profile Card | Streak, total check-ins, points, referrals |
| 🏆 Leaderboard | Top 10 users by check-in count |
| 🔗 Referral System | Unique links, auto-point awards |
| 🎯 Task System | Join channel, invite friends, play game, etc. |
| 📢 Admin Broadcast | Message all users at once |
| 📊 Admin Stats | User count, daily activity, streak averages |
| 📥 Export CSV | pandas-powered user export |
| ⏰ Scheduler | Daily reset, streak reminders, DB backup |

---

## Project Structure

```
telegram-checkin-bot/
├── bot.py                    # Entry point
├── config.py                 # All env vars & constants
├── database.py               # SQLAlchemy engine + SessionLocal
│
├── models/
│   ├── user.py               # User ORM model
│   ├── checkin.py            # CheckinLog ORM model
│   ├── referral.py           # Referral ORM model
│   └── task.py               # UserTask ORM model
│
├── handlers/
│   ├── start.py              # /start + referral parsing
│   ├── checkin.py            # Daily check-in conversation
│   ├── profile.py            # /profile + referral link
│   └── menu.py               # Inline keyboard dispatcher
│
├── services/
│   ├── checkin_service.py    # Check-in business logic
│   ├── referral_service.py   # Referral business logic
│   └── reward_service.py     # Task & points management
│
├── admin/
│   └── admin_commands.py     # /stats /export /broadcast etc.
│
├── utils/
│   ├── keyboard.py           # InlineKeyboard builders
│   └── helpers.py            # Decorators, formatters, guards
│
├── data/                     # SQLite DB + logs (auto-created)
├── requirements.txt
├── .env.example
├── Dockerfile
└── README.md
```

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/yourname/telegram-checkin-bot.git
cd telegram-checkin-bot
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env   # fill in BOT_TOKEN, ADMIN_IDS, links
```

Minimum required `.env`:

```env
BOT_TOKEN=123456:ABCdef...
BOT_USERNAME=YourBotUsername
ADMIN_IDS=123456789
```

### 3. Run

```bash
python bot.py
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | **required** | BotFather token |
| `BOT_USERNAME` | `CheckinBot` | Bot username (no @) |
| `ADMIN_IDS` | — | Comma-separated admin Telegram IDs |
| `DATABASE_URL` | `sqlite:///data/database.db` | SQLAlchemy URL |
| `GAME_URL` | — | Game website link |
| `EVENT_URL` | — | Events page link |
| `DOWNLOAD_URL` | — | App download link |
| `PLAY_URL` | — | Play now link |
| `POINTS_PER_CHECKIN` | `10` | Points per daily check-in |
| `REFERRAL_REWARD` | `20` | Points awarded per referral |
| `STREAK_7_REWARD` | `100` | Bonus at 7-day streak |
| `STREAK_30_REWARD` | `500` | Bonus at 30-day streak |
| `STREAK_100_REWARD` | `2000` | Bonus at 100-day streak |
| `STREAK_365_REWARD` | `10000` | Bonus at 365-day streak |
| `WEBHOOK_URL` | *(empty — uses polling)* | Public HTTPS URL for webhook |
| `WEBHOOK_PORT` | `8443` | Port for webhook listener |

---

## Admin Commands

| Command | Description |
|---|---|
| `/stats` | Bot statistics (users, activity, streaks) |
| `/export` | Download CSV of all users |
| `/broadcast` | Broadcast message to all users |
| `/addpoints <id> <pts>` | Add/subtract points for a user |
| `/resetstreak <id>` | Reset user's streak to 0 |
| `/userinfo <id>` | Full profile lookup |

---

## Bot Commands (Public)

| Command | Description |
|---|---|
| `/start` | Welcome message + main menu |
| `/checkin` | Daily check-in |
| `/profile` | View your profile |
| `/leaderboard` | Top 10 check-in users |
| `/referral` | Your referral link & stats |

---

## Deploy on VPS (Ubuntu)

```bash
# 1. Install Python 3.11+
sudo apt update && sudo apt install python3.11 python3.11-venv python3-pip -y

# 2. Create venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure env
cp .env.example .env && nano .env

# 4. Run with systemd
sudo tee /etc/systemd/system/checkin-bot.service > /dev/null <<EOF
[Unit]
Description=Telegram Check-in Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable checkin-bot
sudo systemctl start checkin-bot
sudo systemctl status checkin-bot
```

---

## Deploy with Docker

```bash
# Build & run
docker build -t checkin-bot .
docker run -d \
  --name checkin-bot \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  checkin-bot

# View logs
docker logs -f checkin-bot
```

---

## Deploy on Railway / Render

1. Push code to GitHub.
2. Create new project on Railway or Render.
3. Set all environment variables from `.env.example`.
4. Set **start command**: `python bot.py`
5. For webhook mode, set `WEBHOOK_URL` to your app's public URL.

---

## Database

Default: **SQLite** (`data/database.db`) — zero config, great for < 50k users.

Switch to **PostgreSQL** for production scale:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/checkinbot
```

---

## Referral Link Format

```
https://t.me/YourBotUsername?start=ref123456789
```

When a new user clicks this link:
1. They get registered in the DB
2. `referrer_id` is set on their account
3. The referrer receives `REFERRAL_REWARD` points immediately

---

## Scheduler Jobs

| Job | Schedule | Action |
|---|---|---|
| `daily_reset` | 00:00 UTC | Hook for daily stat resets |
| `streak_reminder` | 18:00 UTC | Nudge users with streak ≥ 3 who haven't checked in |
| `db_backup` | 03:00 UTC | Copy `database.db` to `data/backup_YYYY-MM-DD.db` |

---

## License

MIT — free to use, fork, and extend.
