# ============================================================
# config.py — Central configuration for the bot
# All environment variables are loaded here via python-dotenv
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
# BOT CORE
# ─────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "CheckinBot")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set. Check your .env file.")

# ─────────────────────────────────────────────────────────────
# ADMIN IDs — list of Telegram user IDs with admin privileges
# ─────────────────────────────────────────────────────────────
_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()
]

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/database.db")

# ─────────────────────────────────────────────────────────────
# EXTERNAL LINKS — used in inline keyboard URL buttons
# ─────────────────────────────────────────────────────────────
GAME_URL: str = os.getenv("GAME_URL", "https://example.com/game")
EVENT_URL: str = os.getenv("EVENT_URL", "https://example.com/events")
DOWNLOAD_URL: str = os.getenv("DOWNLOAD_URL", "https://example.com/download")
PLAY_URL: str = os.getenv("PLAY_URL", "https://example.com/play")
CHANNEL_URL: str = os.getenv("CHANNEL_URL", "https://t.me/your_channel")
COMMUNITY_URL: str = os.getenv("COMMUNITY_URL", "https://t.me/your_community")

# Mini App mode — set to "true" to open as Telegram Mini App instead of browser
PLAY_AS_WEBAPP: bool = os.getenv("PLAY_AS_WEBAPP", "true").lower() == "true"
GAME_AS_WEBAPP: bool = os.getenv("GAME_AS_WEBAPP", "false").lower() == "true"

# ─────────────────────────────────────────────────────────────
# REWARD SETTINGS
# ─────────────────────────────────────────────────────────────
POINTS_PER_CHECKIN: int = int(os.getenv("POINTS_PER_CHECKIN", "10"))
REFERRAL_REWARD: int = int(os.getenv("REFERRAL_REWARD", "20"))

# Streak milestone rewards: {streak_days: bonus_points}
STREAK_REWARDS: dict[int, int] = {
    7:   int(os.getenv("STREAK_7_REWARD",   "100")),
    30:  int(os.getenv("STREAK_30_REWARD",  "500")),
    100: int(os.getenv("STREAK_100_REWARD", "2000")),
    365: int(os.getenv("STREAK_365_REWARD", "10000")),
}

# ─────────────────────────────────────────────────────────────
# WEBHOOK (leave WEBHOOK_URL empty to use polling)
# ─────────────────────────────────────────────────────────────
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8443"))

# ─────────────────────────────────────────────────────────────
# RATE LIMIT — minimum seconds between requests per user
# ─────────────────────────────────────────────────────────────
RATE_LIMIT_SECONDS: int = int(os.getenv("RATE_LIMIT_SECONDS", "1"))

# ─────────────────────────────────────────────────────────────
# TASK SYSTEM — task definitions
# Each task: {id, name, description, reward_points, task_type}
# ─────────────────────────────────────────────────────────────
TASKS: list[dict] = [
    {
        "id": "join_channel",
        "name": "Join Official Channel",
        "description": "Join our official Telegram channel",
        "reward": 50,
        "type": "join_channel",
        "url": CHANNEL_URL,
    },
    {
        "id": "invite_friends",
        "name": "Invite 3 Friends",
        "description": "Refer 3 friends using your referral link",
        "reward": 150,
        "type": "referral",
        "required_count": 3,
    },
    {
        "id": "daily_checkin",
        "name": "Daily Check-in",
        "description": "Check in for 7 consecutive days",
        "reward": 100,
        "type": "streak",
        "required_count": 7,
    },
    {
        "id": "play_game",
        "name": "Play The Game",
        "description": "Visit and play the game",
        "reward": 30,
        "type": "visit_url",
        "url": PLAY_URL,
    },
]

# ─────────────────────────────────────────────────────────────
# LEADERBOARD
# ─────────────────────────────────────────────────────────────
LEADERBOARD_SIZE: int = 10   # number of entries to show

# ─────────────────────────────────────────────────────────────
# MESSAGES — centralised text strings (i18n-ready)
# ─────────────────────────────────────────────────────────────
MSG_WELCOME = (
    "🎰 <b>Welcome to Community Check-in Bot!</b>\n\n"
    "Check in every day to earn rewards and keep your streak alive 💎\n\n"
    "Use the menu below to get started:"
)

MSG_ALREADY_CHECKEDIN = (
    "⚠️ <b>You already checked in today.</b>\n"
    "Come back tomorrow!"
)

MSG_NEED_GAME_ID = (
    "🎮 <b>Game ID Required</b>\n\n"
    "Please enter your <b>Game ID</b> to activate check-in.\n"
    "<i>Example: 12345678</i>"
)

MSG_INVALID_GAME_ID = (
    "❌ Invalid Game ID format.\n"
    "Please enter a numeric Game ID (e.g. <code>12345678</code>)."
)
