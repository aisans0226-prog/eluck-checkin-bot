# ============================================================
# models/checkin.py — Daily check-in log ORM model
# ============================================================

from datetime import date, datetime
from sqlalchemy import Integer, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class CheckinLog(Base):
    __tablename__ = "checkin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK → users.id  (internal PK, not telegram_id)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    streak_at_checkin: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # ── Relationship ──────────────────────────────────────────
    user = relationship("User", back_populates="checkin_logs")

    def __repr__(self) -> str:
        return f"<CheckinLog uid={self.user_id} date={self.checkin_date} pts={self.points_earned}>"
