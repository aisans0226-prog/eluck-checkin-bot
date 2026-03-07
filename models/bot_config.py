# ============================================================
# models/bot_config.py — Dynamic key/value config stored in DB
# Overrides .env defaults; editable from the admin dashboard
# ============================================================

from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class BotConfig(Base):
    __tablename__ = "bot_config"

    # Config key  (e.g. "POINTS_PER_CHECKIN")
    key: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Stored as string — cast to int/float in application code
    value: Mapped[str] = mapped_column(Text, nullable=False)

    description: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<BotConfig {self.key}={self.value}>"


# ── Helpers ───────────────────────────────────────────────────

def get_config(db, key: str, default=None):
    """Get a single config value from DB, returning default if not found."""
    row = db.query(BotConfig).filter(BotConfig.key == key).first()
    return row.value if row else default


def set_config(db, key: str, value, description: str = ""):
    """Upsert a config value. Caller must commit."""
    row = db.query(BotConfig).filter(BotConfig.key == key).first()
    if row:
        row.value = str(value)
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = BotConfig(key=key, value=str(value), description=description)
        db.add(row)
    db.flush()


# Default reward keys seeded on first dashboard start
DEFAULT_CONFIGS = {
    "POINTS_PER_CHECKIN": ("10", "Points awarded per daily check-in"),
    "REFERRAL_REWARD": ("20", "Points awarded to referrer when new user joins"),
    "STREAK_7_REWARD": ("100", "Bonus points at 7-day streak milestone"),
    "STREAK_30_REWARD": ("500", "Bonus points at 30-day streak milestone"),
    "STREAK_100_REWARD": ("2000", "Bonus points at 100-day streak milestone"),
    "STREAK_365_REWARD": ("10000", "Bonus points at 365-day streak milestone"),
    "LEADERBOARD_SIZE": ("10", "Number of entries shown in leaderboard"),
    "STREAK_REMINDER_HOUR": ("18", "Hour (UTC) to send streak reminder notifications"),
}

# Link & Mini App config keys
DEFAULT_LINK_CONFIGS = {
    "PLAY_URL":       ("", "Play button URL"),
    "GAME_URL":       ("", "Games button URL"),
    "EVENT_URL":      ("", "Events button URL"),
    "DOWNLOAD_URL":   ("", "Download button URL"),
    "CHANNEL_URL":    ("", "Official channel URL"),
    "COMMUNITY_URL":  ("", "Community group URL"),
    "PLAY_AS_WEBAPP": ("true",  "Open Play as Telegram Mini App (true/false)"),
    "GAME_AS_WEBAPP": ("false", "Open Games as Telegram Mini App (true/false)"),
}
