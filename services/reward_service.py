# ============================================================
# services/reward_service.py — Task completion & reward logic
# ============================================================

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from models.user import User
from models.task import UserTask
import config

logger = logging.getLogger(__name__)


def get_user_task_status(db: Session, user: User) -> list[str]:
    """Return list of task_ids that the user has already completed."""
    records = (
        db.query(UserTask)
        .filter(UserTask.user_id == user.id, UserTask.completed == True)  # noqa: E712
        .all()
    )
    return [r.task_id for r in records]


def complete_task(db: Session, user: User, task_id: str) -> tuple[bool, int]:
    """
    Mark a task as complete and award points.

    Returns:
        (success: bool, points_awarded: int)
    """
    # Find task definition
    task_def = next((t for t in config.TASKS if t["id"] == task_id), None)
    if not task_def:
        return False, 0

    # Check if already completed
    existing = (
        db.query(UserTask)
        .filter(UserTask.user_id == user.id, UserTask.task_id == task_id)
        .first()
    )
    if existing and existing.completed:
        return False, 0  # already done

    # Validate prerequisite for type=referral
    if task_def.get("type") == "referral":
        required = task_def.get("required_count", 1)
        referral_count = len(user.referrals_made)
        if referral_count < required:
            return False, 0

    # Validate prerequisite for type=streak
    if task_def.get("type") == "streak":
        required = task_def.get("required_count", 1)
        if user.streak < required and user.total_checkin < required:
            return False, 0

    reward = task_def["reward"]

    # Create or update UserTask record
    if existing:
        existing.completed = True
        existing.points_awarded = reward
        existing.completed_at = datetime.utcnow()
    else:
        record = UserTask(
            user_id=user.id,
            task_id=task_id,
            completed=True,
            points_awarded=reward,
            completed_at=datetime.utcnow(),
        )
        db.add(record)

    # Award points
    user.points += reward
    db.flush()

    logger.info(
        "Task completed: uid=%s task=%s pts=+%d",
        user.telegram_id, task_id, reward,
    )
    return True, reward


def add_points(db: Session, user: User, points: int, reason: str = "admin") -> int:
    """
    Directly add (or subtract) points to a user. Used by admin commands.
    Returns new total.
    """
    user.points = max(0, user.points + points)
    db.flush()
    logger.info("Points adjusted: uid=%s delta=%+d reason=%s", user.telegram_id, points, reason)
    return user.points
