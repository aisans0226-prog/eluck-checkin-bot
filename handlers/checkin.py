# ============================================================
# handlers/checkin.py — Daily check-in handler
# Manages the two-phase flow:
#   Phase 1: No game_id → ask for Game ID
#   Phase 2: Has game_id → process check-in
# ============================================================

import logging
import re

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from models.user import User
from services.checkin_service import get_or_create_user, perform_checkin
from utils.keyboard import checkin_success_keyboard, back_to_menu_keyboard
from utils.helpers import format_points, format_streak_bar, rate_limited, safe_edit_or_reply
import config

logger = logging.getLogger(__name__)

# ConversationHandler states
WAITING_GAME_ID = 1

# ─────────────────────────────────────────────────────────────
# Entry point — triggered when user clicks ✅ Daily Check-in
# ─────────────────────────────────────────────────────────────
@rate_limited
async def checkin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """
    Called from callback_data='menu:checkin'
    or via /checkin command.
    """
    tg_user = update.effective_user
    if not tg_user:
        return

    db = context.bot_data["db_session"]()

    try:
        user = get_or_create_user(db, tg_user.id, tg_user.username, tg_user.first_name)
        db.commit()

        if update.callback_query:
            await update.callback_query.answer()

        # ── No game ID yet — enter conversation ───────────────
        if not user.game_id:
            await safe_edit_or_reply(
                update,
                text=(
                    "🎮 <b>Game ID Required</b>\n\n"
                    "Please enter your <b>Game ID</b> to activate check-in.\n"
                    "<i>Example: <code>12345678</code></i>\n\n"
                    "⚠️ You only need to do this once!"
                ),
                reply_markup=None,
                parse_mode="HTML",
            )
            return WAITING_GAME_ID

        # ── Already has game ID — process check-in ────────────
        result = perform_checkin(db, user)
        db.commit()

        if result.already_checked_in:
            await safe_edit_or_reply(
                update,
                text=(
                    "⚠️ <b>Already Checked In</b>\n\n"
                    "You already checked in today!\n"
                    "Come back tomorrow 😊\n\n"
                    f"🔥 Current Streak: <b>{user.streak} days</b>"
                ),
                reply_markup=back_to_menu_keyboard(),
                parse_mode="HTML",
            )
        else:
            await _send_checkin_success(update, user, result)

    except Exception as exc:
        db.rollback()
        logger.error("checkin_entry error: %s", exc, exc_info=True)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# Phase 2 — Receive Game ID from user
# ─────────────────────────────────────────────────────────────
async def receive_game_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Receive and validate the Game ID entered by the user.
    Called in ConversationHandler state WAITING_GAME_ID.
    """
    tg_user = update.effective_user
    text = (update.message.text or "").strip()

    # Validate: numeric, 4–20 chars
    if not re.match(r"^\d{4,20}$", text):
        await update.message.reply_text(
            "❌ <b>Invalid Game ID</b>\n\n"
            "Please enter a valid numeric Game ID (4–20 digits).\n"
            "<i>Example: <code>12345678</code></i>",
            parse_mode="HTML",
        )
        return WAITING_GAME_ID  # stay in state

    db = context.bot_data["db_session"]()

    try:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if not user:
            await update.message.reply_text("⚠️ Please send /start first.")
            return ConversationHandler.END

        # Save the game ID
        user.game_id = text
        db.flush()

        # Immediately perform check-in after registering game ID
        result = perform_checkin(db, user)
        db.commit()

        await _send_checkin_success(update, user, result, new_registration=True)

    except Exception as exc:
        db.rollback()
        logger.error("receive_game_id error: %s", exc, exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again.")
    finally:
        db.close()

    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────
# /leaderboard command
# ─────────────────────────────────────────────────────────────
async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display top users by total check-ins."""
    from services.checkin_service import get_leaderboard
    from utils.helpers import rank_emoji

    db = context.bot_data["db_session"]()
    try:
        if update.callback_query:
            await update.callback_query.answer()

        top_users = get_leaderboard(db, limit=config.LEADERBOARD_SIZE)

        if not top_users:
            await safe_edit_or_reply(
                update,
                "🏆 No leaderboard data yet. Be the first to check in!",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        lines = ["🏆 <b>TOP CHECK-IN USERS</b>\n"]
        for i, u in enumerate(top_users, start=1):
            name = u.display_name
            lines.append(
                f"{rank_emoji(i)} {name} — "
                f"<b>{u.total_checkin}</b> days | "
                f"🔥{u.streak} | "
                f"💰{format_points(u.points)}"
            )

        text = "\n".join(lines)
        await safe_edit_or_reply(update, text, reply_markup=back_to_menu_keyboard())

    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# Internal helper — build and send success message
# ─────────────────────────────────────────────────────────────
async def _send_checkin_success(update, user, result, new_registration: bool = False) -> None:
    streak_bar = format_streak_bar(result.streak)

    bonus_line = ""
    if result.streak_bonus > 0:
        bonus_line = (
            f"\n🎉 <b>Milestone Bonus!</b> You reached a "
            f"<b>{result.milestone_reached}-day streak!</b>\n"
            f"   💰 Bonus: <b>+{format_points(result.streak_bonus)} pts</b>"
        )

    reg_line = "\n✨ <i>Game ID registered successfully!</i>" if new_registration else ""

    text = (
        f"✅ <b>Check-in Successful!</b>{reg_line}\n\n"
        f"🔥 Streak: <b>{result.streak} day{'s' if result.streak != 1 else ''}</b>  {streak_bar}\n"
        f"📅 Total check-ins: <b>{result.total_checkins}</b>\n"
        f"💰 Points earned: <b>+{result.points_earned} pts</b>"
        f"{bonus_line}\n\n"
        f"🎮 Game ID: <code>{user.game_id}</code>"
    )

    await safe_edit_or_reply(update, text, reply_markup=checkin_success_keyboard())
