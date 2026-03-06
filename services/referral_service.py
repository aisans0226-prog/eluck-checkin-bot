# ============================================================
# services/referral_service.py — Referral business logic
# ============================================================

import logging

from sqlalchemy.orm import Session

from models.user import User
from models.referral import Referral
import config

logger = logging.getLogger(__name__)


def process_referral(db: Session, referrer_id: int, referred_user: User) -> bool:
    """
    Link referred_user to referrer and award points to referrer.

    Returns True if referral was successfully recorded, False if:
    - referrer not found
    - user is referring themselves
    - user was already referred
    """
    # Self-referral guard
    if referred_user.telegram_id == referrer_id:
        logger.warning("Self-referral attempt: uid=%s", referrer_id)
        return False

    # Check referrer exists
    referrer = db.query(User).filter(User.telegram_id == referrer_id).first()
    if not referrer:
        logger.warning("Referrer not found: %s", referrer_id)
        return False

    # Check not already referred
    existing = (
        db.query(Referral)
        .filter(Referral.referred_id == referred_user.telegram_id)
        .first()
    )
    if existing:
        logger.info("User %s already referred", referred_user.telegram_id)
        return False

    # ── Record referral ───────────────────────────────────────
    referral = Referral(
        referrer_id=referrer_id,
        referred_id=referred_user.telegram_id,
        points_awarded=config.REFERRAL_REWARD,
    )
    db.add(referral)

    # Award points to referrer
    referrer.points += config.REFERRAL_REWARD
    referred_user.referrer_id = referrer_id

    db.flush()
    logger.info(
        "Referral recorded: referrer=%s referred=%s pts=+%d",
        referrer_id, referred_user.telegram_id, config.REFERRAL_REWARD,
    )
    return True


def get_referral_stats(db: Session, telegram_id: int) -> dict:
    """Return referral stats for a given user."""
    referrals = (
        db.query(Referral)
        .filter(Referral.referrer_id == telegram_id)
        .all()
    )
    total_points = sum(r.points_awarded for r in referrals)
    return {
        "count": len(referrals),
        "total_points_earned": total_points,
    }
