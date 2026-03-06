# Eluck Check-in Bot — Changelog & Session Notes

## Session: 2026-03-06 — Full Build + Dashboard

### Summary
Built a production-ready Telegram Community Check-in Bot (`@Eluck_checkin_bot`) with a Flask admin dashboard from scratch in a single Claude Code session.

---

## Features Implemented

### Telegram Bot (`bot.py`, `handlers/`, `services/`)
- **Daily Check-in system** — Users check in once per day; requires Game ID registration on first check-in
- **Streak system** — Tracks consecutive daily check-ins; milestone bonuses at 7, 30, 100 days
- **Leaderboard** — Top 10 users ranked by total check-ins with streak display
- **Referral system** — Unique referral links (`/start ref<id>`); rewards for referrer on first check-in
- **Task system** — Completable tasks (follow social, retweet, join group) with one-time point rewards
- **Inline keyboard navigation** — Full menu-driven UX without needing commands
- **Admin commands** — `/stats`, `/export` (CSV), `/broadcast`, `/addpoints`, `/resetstreak`, `/userinfo`

### Flask Admin Dashboard (`dashboard/app.py`, `dashboard/templates/`)
- **Overview page** — Stat cards (total users, check-ins today, active users, total points); Chart.js line/bar charts (daily check-ins and new users, last 30 days); Top-5 leaderboard; Recent check-in feed
- **User management** — Full list with search/filter; user detail view with edit forms (game_id, points, streak reset); check-in history; referral table
- **Task management** — Full CRUD for task definitions stored in DB (add, edit, toggle active, delete)
- **Reward configuration** — Range sliders to adjust all point values live, stored in `bot_config` table
- **Broadcast** — Compose and send messages to all users or active-only via Telegram Bot API
- **CSV export** — One-click user export via pandas
- **Authentication** — Session-based login with credentials from `.env`

---

## Database Models

| Model | Table | Purpose |
|-------|-------|---------|
| `User` | `users` | Telegram user profile, stats, points |
| `CheckinLog` | `checkin_logs` | Daily check-in records |
| `Referral` | `referrals` | Referral relationships |
| `UserTask` | `user_tasks` | Per-user task completion state |
| `TaskDefinition` | `task_definitions` | Admin-managed task definitions |
| `BotConfig` | `bot_config` | Key/value reward config (editable from dashboard) |

---

## Python 3.14 Compatibility Fixes

| Package | Problem | Fix |
|---------|---------|-----|
| `pandas==2.1.4` | No `cp314` wheel | Upgraded to `pandas>=2.2.3` |
| `SQLAlchemy==2.0.25` | `AssertionError` — `__static_attributes__` conflict | Upgraded to `SQLAlchemy>=2.0.36` |
| `python-telegram-bot==20.7` | `AttributeError: 'Updater' object has no attribute '_Updater__polling_cleanup_cb'` — `__slots__` name mangling | Upgraded to `>=21.0` (installed 22.6) |
| APScheduler | `RuntimeError: no current event loop` when calling `.start()` at module level | Moved `.start()` into PTB `post_init` async hook |

---

## Bug Fixes

### Dashboard `/dashboard` HTTP 500 — SQLAlchemy Cython `str_to_date` threading bug

**Root cause:** SQLAlchemy's Cython extension (`processors.pyx`) processes `Date`/`DateTime` column values using `datetime.fromisoformat()`. In Flask's multi-threaded mode (`threaded=True`), the type processor is called from a different thread than the one that executed the query, causing `TypeError: fromisoformat: argument must be str` (receives a non-string due to thread-local state corruption).

**Fix:** Replaced the three ORM queries in the `dashboard()` route that return `Date` columns with raw SQL using `db.execute(text("SELECT ..."))`. Raw SQL returns plain Python tuples — no Cython processor is invoked.

Affected queries:
1. Recent check-ins JOIN (`CheckinLog` × `User`)
2. Daily check-in chart (`CheckinLog.checkin_date GROUP BY`)
3. New-users-per-day chart (`DATE(User.register_date) GROUP BY`)

**Architecture fixes also applied (defence-in-depth):**
- `NullPool` instead of `StaticPool` for Flask's SQLAlchemy engine
- `scoped_session` for thread-local session isolation
- `@app.teardown_appcontext` calls `_SessionLocal.remove()` to clean up

---

## Project Structure

```
telegram-checkin-bot/
├── bot.py                  # Entry point
├── config.py               # Central config from .env
├── database.py             # SQLAlchemy engine + Base
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── models/
│   ├── user.py
│   ├── checkin.py
│   ├── referral.py
│   ├── task.py
│   ├── task_definition.py  # NEW — DB-managed tasks
│   └── bot_config.py       # NEW — dynamic reward config
├── handlers/
│   ├── start.py
│   ├── checkin.py
│   ├── profile.py
│   └── menu.py
├── services/
│   ├── checkin_service.py
│   ├── referral_service.py
│   └── reward_service.py
├── admin/
│   └── admin_commands.py
├── utils/
│   ├── keyboard.py
│   └── helpers.py
└── dashboard/
    ├── app.py
    └── templates/
        ├── base.html
        ├── login.html
        ├── index.html
        ├── users.html
        ├── user_detail.html
        ├── tasks.html
        ├── rewards.html
        ├── broadcast.html
        └── _task_form.html
```

---

## Running the Project

### Bot
```bash
python bot.py
```

### Dashboard
```bash
python dashboard/app.py
# Access: http://127.0.0.1:5000
# Login: admin / admin123 (configurable in .env)
```

### Environment variables (`.env`)
```
BOT_TOKEN=<your-telegram-bot-token>
ADMIN_IDS=<comma-separated-telegram-ids>
DATABASE_URL=sqlite:///data/database.db
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=admin123
DASHBOARD_SECRET_KEY=<random-secret>
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=5000
```
