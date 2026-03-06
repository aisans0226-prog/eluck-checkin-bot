# ============================================================
# models/audit_log.py — Admin activity tracking
# ============================================================

from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Who performed the action
    admin_username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # What happened  (e.g. "login", "update_game_id", "add_task", "broadcast", …)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # What was affected  (e.g. "user:123456789", "task:5", "reward:POINTS_PER_CHECKIN")
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Human-readable detail string  (e.g. "points +200 → 750", "streak 3 → 0")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Request metadata
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AuditLog [{self.admin_username}] {self.action} @ {self.created_at}>"
