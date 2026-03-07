# ============================================================
# models/scheduled_broadcast.py — Scheduled Broadcast ORM
# ============================================================

from datetime import datetime, timezone
from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class ScheduledBroadcast(Base):
    __tablename__ = "scheduled_broadcasts"

    id:             Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_text:   Mapped[str]           = mapped_column(Text, default="")
    target:         Mapped[str]           = mapped_column(String(16), default="all")
    # comma-separated Game IDs when target == "specific_ids"
    target_game_ids: Mapped[str | None]  = mapped_column(Text, nullable=True)
    # filename inside data/broadcast_images/ (None = no image)
    image_filename: Mapped[str | None]    = mapped_column(String(256), nullable=True)
    # scheduled_at stored as UTC naive datetime
    scheduled_at:   Mapped[datetime]      = mapped_column(DateTime)
    # human-readable timezone the admin chose (display only)
    timezone_name:  Mapped[str]           = mapped_column(String(64), default="UTC")
    # pending / sending / sent / failed / cancelled
    status:         Mapped[str]           = mapped_column(String(16), default="pending")
    created_at:     Mapped[datetime]      = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
    created_by:     Mapped[str]           = mapped_column(String(64), default="")
    sent_count:     Mapped[int]           = mapped_column(Integer, default=0)
    failed_count:   Mapped[int]           = mapped_column(Integer, default=0)
    sent_at:        Mapped[datetime|None] = mapped_column(DateTime, nullable=True)
    error_message:  Mapped[str|None]      = mapped_column(Text, nullable=True)

    # ── Convenience properties used in templates ──────────────
    @property
    def target_label(self) -> str:
        if self.target == "specific_ids":
            ids = self.target_game_ids or ""
            count = len([x for x in ids.split(",") if x.strip()])
            return f"Specific IDs ({count})"
        return {
            "all":     "All Users",
            "active":  "Active (7d)",
            "game_id": "With Game ID",
        }.get(self.target, self.target)

    @property
    def status_badge(self) -> str:
        return {
            "pending":   "warning",
            "sending":   "info",
            "sent":      "success",
            "failed":    "danger",
            "cancelled": "secondary",
        }.get(self.status, "secondary")
