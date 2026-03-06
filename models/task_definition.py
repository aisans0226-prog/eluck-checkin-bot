# ============================================================
# models/task_definition.py — DB-stored task definitions
# Editable from the admin dashboard
# ============================================================

from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class TaskDefinition(Base):
    __tablename__ = "task_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Unique slug used as task_id in UserTask
    task_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(512), default="")
    reward_points: Mapped[int] = mapped_column(Integer, default=10)

    # Type: join_channel | referral | streak | visit_url | manual
    task_type: Mapped[str] = mapped_column(String(32), default="manual")

    # Optional URL for visit_url / join_channel tasks
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Required count for referral / streak tasks
    required_count: Mapped[int] = mapped_column(Integer, default=1)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_key": self.task_key,
            "name": self.name,
            "description": self.description,
            "reward_points": self.reward_points,
            "task_type": self.task_type,
            "url": self.url,
            "required_count": self.required_count,
            "is_active": self.is_active,
        }

    def __repr__(self) -> str:
        return f"<TaskDef {self.task_key} pts={self.reward_points}>"
