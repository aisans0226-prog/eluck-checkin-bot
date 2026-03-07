# ============================================================
# services/checkin_service.py — Check-in business logic
# ============================================================

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from models.user import User
from models.checkin import CheckinLog
from utils.helpers import today_mexico
import config

logger = logging.getLogger(__name__)


class CheckinResult:
    """Value object returned by perform_checkin()."""
    def __init__(
        self,
        success: bool,
        already_checked_in: bool = False,
        new_user: bool = False,
        streak: int = 0,
        total_checkins: int = 0,
        points_earned: int = 0,
        streak_bonus: int = 0,
        milestone_reached: int | None = None,
        freeze_used: bool = False,
    ):
        self.success = success
        self.already_checked_in = already_checked_in
        self.new_user = new_user
        self.streak = streak
        self.total_checkins = total_checkins
        self.points_earned = points_earned
        self.streak_bonus = streak_bonus
        self.milestone_reached = milestone_reached
        self.freeze_used = freeze_used  # True if a streak freeze was consumed today


def get_or_create_user(
    db: Session, telegram_id: int, username: str | None, first_name: str | None
) -> tuple["User", bool]:
    """
    Fetch existing user or create a new skeleton user.
    Returns (user, is_new) — is_new is True only on first creation.
    Does NOT commit — caller is responsible.
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )
        db.add(user)
        db.flush()
        logger.info("New user created: %s", telegram_id)
        return user, True
    else:
        # Keep username/name fresh
        user.username = username
        user.first_name = first_name
        return user, False


def _reset_freeze_if_new_month(user: User, month_str: str) -> None:
    """Reset the monthly streak freeze counter when a new calendar month starts."""
    if user.streak_freeze_month != month_str:
        user.streak_freeze_used = 0
        user.streak_freeze_month = month_str


def can_use_streak_freeze(user: User) -> bool:
    """Return True if the user still has a freeze available this calendar month."""
    today = today_mexico()
    month_str = today.strftime("%Y-%m")
    _reset_freeze_if_new_month(user, month_str)
    return user.streak_freeze_used < config.STREAK_FREEZE_PER_MONTH


def perform_checkin(db: Session, user: User) -> CheckinResult:
    """
    Core check-in logic:
    1. Block if already done today
    2. Streak freeze: if user missed exactly 1 day and has freeze credits,
       consume one credit and keep the streak alive
    3. Otherwise reset streak on any missed day
    4. Award base points + milestone bonus
    5. Log to checkin_logs; flush (caller commits)

    Returns a CheckinResult value object.
    """
    today = today_mexico()
    if user.last_checkin == today:
        return CheckinResult(success=False, already_checked_in=True)

    yesterday = today - timedelta(days=1)
    month_str = today.strftime("%Y-%m")

    # Reset monthly freeze counter at start of new month
    _reset_freeze_if_new_month(user, month_str)

    freeze_used = False

    # Streak calculation
    if user.last_checkin == yesterday:
        # Consecutive day — increment streak
        new_streak = user.streak + 1
    else:
        # Missed one or more days
        missed_exactly_one = (
            user.last_checkin is not None
            and user.last_checkin == today - timedelta(days=2)
        )
        if missed_exactly_one and user.streak_freeze_used < config.STREAK_FREEZE_PER_MONTH:
            # Use streak freeze: preserve current streak
            new_streak = user.streak + 1
            user.streak_freeze_used += 1
            freeze_used = True
            logger.info(
                "Streak freeze used: uid=%s streak=%d freeze_remaining=%d",
                user.telegram_id, new_streak,
                config.STREAK_FREEZE_PER_MONTH - user.streak_freeze_used,
            )
        else:
            # Reset streak
            new_streak = 1

    # Points
    base_points = config.POINTS_PER_CHECKIN
    milestone_bonus = config.STREAK_REWARDS.get(new_streak, 0)
    total_earned = base_points + milestone_bonus

    # Update user record
    user.streak = new_streak
    user.total_checkin += 1
    user.points += total_earned
    user.last_checkin = today

    # Write log
    log = CheckinLog(
        user_id=user.id,
        checkin_date=today,
        points_earned=total_earned,
        streak_at_checkin=new_streak,
    )
    db.add(log)
    db.flush()

    logger.info(
        "Check-in: uid=%s streak=%d points=+%d freeze=%s",
        user.telegram_id, new_streak, total_earned, freeze_used,
    )

    return CheckinResult(
        success=True,
        streak=new_streak,
        total_checkins=user.total_checkin,
        points_earned=total_earned,
        streak_bonus=milestone_bonus,
        milestone_reached=new_streak if milestone_bonus > 0 else None,
        freeze_used=freeze_used,
    )


def get_leaderboard(db: Session, limit: int = 10) -> list[User]:
    """Return top N users sorted by total_checkin desc, then streak desc."""
    return (
        db.query(User)
        .filter(User.game_id.isnot(None), User.is_banned == False)  # noqa: E712
        .order_by(User.total_checkin.desc(), User.streak.desc())
        .limit(limit)
        .all()
    )


def get_checkins_today(db: Session) -> int:
    """Count how many check-ins happened today (Mexico City time)."""
    today = today_mexico()
    return db.query(CheckinLog).filter(CheckinLog.checkin_date == today).count()
