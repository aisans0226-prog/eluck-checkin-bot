# ============================================================
# services/event_service.py — User Behavior Event Logging
#
# Usage (in any handler):
#   from services.event_service import log_event, EVT_BTN_CHECKIN
#   log_event(db, telegram_id, EVT_BTN_CHECKIN)
#
# All log_event() calls are fire-and-forget — errors are
# silenced so the bot flow is never disrupted.
# ============================================================

import json
import logging
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
EVT_CHECKIN_ABANDON  = "checkin_abandoned"   # entered flow, didn't finish
EVT_GAME_ID_REGISTER = "game_id_register"
EVT_TASK_COMPLETED   = "task_completed"
EVT_TASK_FAILED      = "task_failed"
EVT_LANG_CHANGED     = "language_changed"
EVT_REFERRAL_USED    = "referral_used"
EVT_PROFILE_VIEW     = "profile_view"
EVT_REFERRAL_VIEW    = "referral_view"


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
        session_id  : optional session identifier
    """
    try:
        ev = UserEvent(
            telegram_id=telegram_id,
            event_type=event_type,
            event_data=json.dumps(meta, ensure_ascii=False) if meta else None,
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(ev)
        db.flush()
    except Exception as exc:
        logger.debug("event_service.log_event silenced: %s", exc)
