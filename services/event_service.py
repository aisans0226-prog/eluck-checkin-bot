# ============================================================
# services/event_service.py — User Behavior Event Logging
#
# Usage (in any handler):
#   from services.event_service import log_event, EVT_BTN_CHECKIN
#   log_event(db, telegram_id, EVT_BTN_CHECKIN)
#
# All log_event() calls are fire-and-forget — errors are
# silenced so the bot flow is never disrupted.
#
# Session logic: each user gets a rolling 30-minute session ID.
# If the user is inactive for >30 min, a new UUID is generated.
# ============================================================

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from models.user_event import UserEvent

logger = logging.getLogger(__name__)

# ── Event type constants ─────────────────────────────────────
# Commands
EVT_CMD_START       = "cmd_start"
EVT_CMD_CHECKIN     = "cmd_checkin"
EVT_CMD_PROFILE     = "cmd_profile"
EVT_CMD_REFERRAL    = "cmd_referral"
EVT_CMD_LEADERBOARD = "cmd_leaderboard"

# Button clicks (inline keyboard)
EVT_BTN_HOME        = "btn_home"
EVT_BTN_CHECKIN     = "btn_checkin"
EVT_BTN_PROFILE     = "btn_profile"
EVT_BTN_TASKS       = "btn_tasks"
EVT_BTN_REFERRAL    = "btn_referral"
EVT_BTN_LEADERBOARD = "btn_leaderboard"
EVT_BTN_LANGUAGE    = "btn_language_menu"
EVT_BTN_TASK_VIEW   = "btn_task_view"
EVT_BTN_TASK_DONE   = "btn_task_complete"

# Functional outcomes
EVT_CHECKIN_SUCCESS  = "checkin_success"
EVT_CHECKIN_ALREADY  = "checkin_already"
EVT_CHECKIN_ABANDON  = "checkin_abandoned"
EVT_GAME_ID_REGISTER = "game_id_register"
EVT_TASK_COMPLETED   = "task_completed"
EVT_TASK_FAILED      = "task_failed"
EVT_LANG_CHANGED     = "language_changed"
EVT_REFERRAL_USED    = "referral_used"
EVT_PROFILE_VIEW     = "profile_view"
EVT_REFERRAL_VIEW    = "referral_view"

# Admin-triggered events
EVT_ADMIN_BAN        = "admin_ban"
EVT_ADMIN_UNBAN      = "admin_unban"
EVT_ADMIN_POINTS     = "admin_points_adjusted"
EVT_ADMIN_STREAK     = "admin_streak_reset"
EVT_ADMIN_BROADCAST  = "admin_broadcast_sent"
EVT_ADMIN_DELETE     = "admin_user_deleted"

# Streak freeze
EVT_STREAK_FREEZE    = "streak_freeze_used"


# ── Session tracker ──────────────────────────────────────────
# {telegram_id: (session_id: str, last_seen: float)}
_SESSION_WINDOW_SECONDS = 30 * 60  # 30 minutes
_session_cache: dict[int, tuple[str, float]] = {}
_SESSION_CACHE_MAX = 20_000


def _get_or_create_session(telegram_id: int) -> str:
    """
    Return the current session UUID for a user.
    Creates a new UUID if the user has been inactive for >30 minutes
    or has no session yet.
    """
    now = time.monotonic()

    # Evict oldest entries when cache is full
    if len(_session_cache) >= _SESSION_CACHE_MAX:
        cutoff = now - _SESSION_WINDOW_SECONDS * 2
        stale = [uid for uid, (_, ts) in _session_cache.items() if ts < cutoff]
        for uid in stale:
            del _session_cache[uid]

    entry = _session_cache.get(telegram_id)
    if entry:
        session_id, last_seen = entry
        if now - last_seen <= _SESSION_WINDOW_SECONDS:
            # Still within the same session window — update timestamp
            _session_cache[telegram_id] = (session_id, now)
            return session_id

    # New session
    new_id = str(uuid.uuid4())
    _session_cache[telegram_id] = (new_id, now)
    return new_id


# ─────────────────────────────────────────────────────────────
# Core logging function
# ─────────────────────────────────────────────────────────────
def log_event(
    db,
    telegram_id: int,
    event_type: str,
    meta: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> None:
    """
    Write one event row to user_events.
    Silently swallows all exceptions — bot logic must not be disrupted.

    Args:
        db          : SQLAlchemy session (already open)
        telegram_id : Telegram user ID
        event_type  : string constant (use EVT_* above)
        meta        : optional dict with extra context (serialised as JSON)
        session_id  : override session ID (auto-assigned if None)
    """
    try:
        sid = session_id or _get_or_create_session(telegram_id)
        ev = UserEvent(
            telegram_id=telegram_id,
            event_type=event_type,
            event_data=json.dumps(meta, ensure_ascii=False, default=str) if meta else None,
            session_id=sid,
            created_at=datetime.now(timezone.utc),
        )
        db.add(ev)
        db.flush()
    except Exception as exc:
        logger.debug("event_service.log_event silenced: %s", exc)
