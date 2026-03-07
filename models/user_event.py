# ============================================================
# models/user_event.py — User Behavior Event ORM model
# ============================================================

import json
from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, Integer, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class UserEvent(Base):
    __tablename__ = "user_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Telegram user ID — not FK so events survive user deletion
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # Event type string (see event_service.py for constants)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # JSON metadata: button name, task_id, language, points, etc.
    event_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Simple session ID — same value for events within a 30-min window
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # UTC timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        # Speed up per-user event history queries
        Index("ix_user_events_tid_created", "telegram_id", "created_at"),
        # Speed up funnel/count queries per event type + time range
        Index("ix_user_events_type_created", "event_type", "created_at"),
    )

    @property
    def meta(self) -> dict:
        """Parse event_data JSON safely."""
        if not self.event_data:
            return {}
        try:
            return json.loads(self.event_data)
        except Exception:
            return {}

    def __repr__(self) -> str:
        return f"<UserEvent tid={self.telegram_id} type={self.event_type} at={self.created_at}>"
