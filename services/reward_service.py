# ============================================================
# services/reward_service.py — Task completion & reward logic
# ============================================================

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.user import User
from models.task import UserTask
from models.task_definition import TaskDefinition

logger = logging.getLogger(__name__)


def get_active_tasks(db: Session) -> list[dict]:
    """
    Load active task definitions from the database and return them in the
    same dict format as the legacy config.TASKS list:
      {id, name, description, reward, type, url, required_count}
    """
    rows = (
        db.query(TaskDefinition)
        .filter(TaskDefinition.is_active == True)  # noqa: E712
        .order_by(TaskDefinition.id)
        .all()
    )
    return [
        {
            "id":             row.task_key,
            "name":           row.name,
            "description":    row.description,
            "reward":         row.reward_points,
            "type":           row.task_type,
            "url":            row.url,
            "required_count": row.required_count,
        }
        for row in rows
    ]


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
    # Find task definition from DB (active only)
    task_obj = (
        db.query(TaskDefinition)
        .filter(TaskDefinition.task_key == task_id, TaskDefinition.is_active == True)  # noqa: E712
        .first()
    )
    if not task_obj:
        return False, 0

    task_def = {
        "id":             task_obj.task_key,
        "type":           task_obj.task_type,
        "required_count": task_obj.required_count,
        "reward":         task_obj.reward_points,
    }

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
        if user.streak < required or user.total_checkin < required:
            return False, 0

    reward = task_def["reward"]

    # Create or update UserTask record
    if existing:
        existing.completed = True
        existing.points_awarded = reward
        existing.completed_at = datetime.now(timezone.utc)
    else:
        record = UserTask(
            user_id=user.id,
            task_id=task_id,
            completed=True,
            points_awarded=reward,
            completed_at=datetime.now(timezone.utc),
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


def add_points(db: Session, user: User, points: int, reason: str = "admin", admin_id: int | None = None) -> int:
    """
    Directly add (or subtract) points to a user. Used by admin commands.
    Writes an audit row to user_events for full traceability.
    Returns new total.
    """
    old_total = user.points
    user.points = max(0, user.points + points)
    db.flush()

    # Persist audit record via event system
    from services.event_service import log_event, EVT_ADMIN_POINTS
    log_event(db, user.telegram_id, EVT_ADMIN_POINTS, {
        "delta": points,
        "old_total": old_total,
        "new_total": user.points,
        "reason": reason,
        "admin_id": admin_id,
    })

    logger.info(
        "Points adjusted: uid=%s delta=%+d old=%d new=%d reason=%s",
        user.telegram_id, points, old_total, user.points, reason,
    )
    return user.points
