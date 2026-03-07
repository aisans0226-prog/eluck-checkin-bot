# ============================================================
# models/user.py — User ORM model
# ============================================================

from datetime import datetime, date, timezone
from sqlalchemy import BigInteger, String, Integer, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

# Supported language codes for the Telegram bot
SUPPORTED_LANGS = ("en", "pt", "zh", "es", "mx")


class User(Base):
    __tablename__ = "users"

    # Primary key (internal auto-increment ID)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Telegram identifiers
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Game account
    game_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Timestamps
    register_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_checkin: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Check-in stats
    streak: Mapped[int] = mapped_column(Integer, default=0)
    total_checkin: Mapped[int] = mapped_column(Integer, default=0)

    # Reward points
    points: Mapped[int] = mapped_column(Integer, default=0)

    # Preferred language ('en', 'pt', 'zh', 'es')
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False, server_default="en")

    # Referral — FK to self
    referrer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id", ondelete="SET NULL"), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────
    checkin_logs = relationship("CheckinLog", back_populates="user", cascade="all, delete-orphan")
    referrals_made = relationship(
        "Referral",
        foreign_keys="Referral.referrer_id",
        back_populates="referrer",
        cascade="all, delete-orphan",
    )
    referrals_received = relationship(
        "Referral",
        foreign_keys="Referral.referred_id",
        back_populates="referred",
    )
    tasks = relationship("UserTask", back_populates="user", cascade="all, delete-orphan")

    # ── Display helpers ───────────────────────────────────────
    @property
    def display_name(self) -> str:
        """Return @username if available, else first name or 'User'."""
        if self.username:
            return f"@{self.username}"
        return self.first_name or f"User{self.telegram_id}"

    @property
    def referral_count(self) -> int:
        return len(self.referrals_made)

    def __repr__(self) -> str:
        return f"<User tid={self.telegram_id} streak={self.streak} pts={self.points}>"
