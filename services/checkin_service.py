# ============================================================
# services/checkin_service.py — Check-in business logic
# ============================================================

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from models.user import User
from models.checkin import CheckinLog
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
    ):
        self.success = success
        self.already_checked_in = already_checked_in
        self.new_user = new_user
        self.streak = streak
        self.total_checkins = total_checkins
        self.points_earned = points_earned
        self.streak_bonus = streak_bonus
        self.milestone_reached = milestone_reached  # e.g. 7, 30, 100, 365


def get_or_create_user(db: Session, telegram_id: int, username: str | None, first_name: str | None) -> User:
    """
    Fetch existing user or create a new skeleton user.
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
        db.flush()  # get the auto-generated id
        logger.info("New user created: %s", telegram_id)
    else:
        # Keep username/name fresh
        user.username = username
        user.first_name = first_name
    return user


def perform_checkin(db: Session, user: User) -> CheckinResult:
    """
    Core check-in logic:
    1. Check already checked-in today → return early
    2. Calculate streak (reset if missed a day)
    3. Award base points + streak milestone bonus
    4. Log to checkin_logs
    5. Flush (NOT commit) — caller commits

    Returns a CheckinResult value object.
    """
    today = date.today()

    # ── Guard: already checked in today ──────────────────────
    if user.last_checkin == today:
        return CheckinResult(success=False, already_checked_in=True)

    yesterday = today - timedelta(days=1)

    # ── Streak calculation ────────────────────────────────────
    if user.last_checkin == yesterday:
        # Consecutive day — increment streak
        new_streak = user.streak + 1
    else:
        # Missed one or more days — reset
        new_streak = 1

    # ── Points ────────────────────────────────────────────────
    base_points = config.POINTS_PER_CHECKIN
    milestone_bonus = config.STREAK_REWARDS.get(new_streak, 0)
    total_earned = base_points + milestone_bonus

    # ── Update user record ────────────────────────────────────
    user.streak = new_streak
    user.total_checkin += 1
    user.points += total_earned
    user.last_checkin = today

    # ── Write log ─────────────────────────────────────────────
    log = CheckinLog(
        user_id=user.id,
        checkin_date=today,
        points_earned=total_earned,
        streak_at_checkin=new_streak,
    )
    db.add(log)
    db.flush()

    logger.info(
        "Check-in: uid=%s streak=%d points=+%d",
        user.telegram_id, new_streak, total_earned,
    )

    return CheckinResult(
        success=True,
        streak=new_streak,
        total_checkins=user.total_checkin,
        points_earned=total_earned,
        streak_bonus=milestone_bonus,
        milestone_reached=new_streak if milestone_bonus > 0 else None,
    )


def get_leaderboard(db: Session, limit: int = 10) -> list[User]:
    """Return top N users sorted by total_checkin descending."""
    return (
        db.query(User)
        .filter(User.game_id.isnot(None))
        .order_by(User.total_checkin.desc(), User.streak.desc())
        .limit(limit)
        .all()
    )


def get_checkins_today(db: Session) -> int:
    """Count how many check-ins happened today."""
    today = date.today()
    return db.query(CheckinLog).filter(CheckinLog.checkin_date == today).count()
