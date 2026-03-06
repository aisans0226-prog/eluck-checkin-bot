# ============================================================
# models/dashboard_user.py — Dashboard admin account
# ============================================================

from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class DashboardUser(Base):
    __tablename__ = "dashboard_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Credentials
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)

    # Role: super_admin | admin
    role: Mapped[str] = mapped_column(String(20), default="admin", nullable=False)

    # Fine-grained permissions (ignored for super_admin)
    permissions: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {
            "users": True,
            "tasks": True,
            "rewards": True,
            "broadcast": True,
            "export": True,
        },
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Audit fields
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── Helpers ───────────────────────────────────────────────
    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"

    def has_permission(self, perm: str) -> bool:
        if self.role == "super_admin":
            return True
        return bool((self.permissions or {}).get(perm, False))

    def __repr__(self) -> str:
        return f"<DashboardUser {self.username!r} role={self.role}>"
