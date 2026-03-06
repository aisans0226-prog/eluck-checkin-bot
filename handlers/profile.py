# ============================================================
# handlers/profile.py — User profile & referral display
# ============================================================

import logging

from telegram import Update
from telegram.ext import ContextTypes

from models.user import User
from services.referral_service import get_referral_stats
from utils.keyboard import profile_keyboard, back_to_menu_keyboard
from utils.helpers import (
    format_points,
    format_streak_bar,
    build_referral_link,
    safe_edit_or_reply,
    rate_limited,
)

logger = logging.getLogger(__name__)


@rate_limited
async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the user's profile card."""
    tg_user = update.effective_user
    if not tg_user:
        return

    if update.callback_query:
        await update.callback_query.answer()

    db = context.bot_data["db_session"]()
    try:
        user: User | None = db.query(User).filter(User.telegram_id == tg_user.id).first()

        if not user:
            await safe_edit_or_reply(
                update,
                "⚠️ Profile not found. Please send /start first.",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        ref_stats = get_referral_stats(db, tg_user.id)
        streak_bar = format_streak_bar(user.streak)

        game_id_line = (
            f"🎮 Game ID: <code>{user.game_id}</code>"
            if user.game_id
            else "🎮 Game ID: <i>Not set — click Check-in to register</i>"
        )

        text = (
            f"👤 <b>USER PROFILE</b>\n"
            f"{'─' * 28}\n"
            f"Telegram:  {user.display_name}\n"
            f"{game_id_line}\n\n"
            f"🔥 Current Streak:   <b>{user.streak} day{'s' if user.streak != 1 else ''}</b>  {streak_bar}\n"
            f"📅 Total Check-ins:  <b>{user.total_checkin}</b>\n"
            f"💰 Points:           <b>{format_points(user.points)}</b>\n\n"
            f"👥 Referrals:        <b>{ref_stats['count']}</b>\n"
            f"🎁 Referral Points:  <b>{format_points(ref_stats['total_points_earned'])}</b>"
        )

        await safe_edit_or_reply(update, text, reply_markup=profile_keyboard())

    finally:
        db.close()


@rate_limited
async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user's referral link and stats."""
    tg_user = update.effective_user
    if not tg_user:
        return

    if update.callback_query:
        await update.callback_query.answer()

    db = context.bot_data["db_session"]()
    try:
        user: User | None = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if not user:
            await safe_edit_or_reply(update, "Please send /start first.")
            return

        ref_stats = get_referral_stats(db, tg_user.id)
        link = build_referral_link(tg_user.id)

        text = (
            f"🔗 <b>Your Referral Link</b>\n"
            f"{'─' * 28}\n\n"
            f"<code>{link}</code>\n\n"
            f"👥 Total Referrals: <b>{ref_stats['count']}</b>\n"
            f"💰 Points Earned:   <b>{format_points(ref_stats['total_points_earned'])}</b>\n\n"
            f"📌 <i>Share this link and earn "
            f"<b>{context.bot_data.get('referral_reward', 20)} points</b> "
            f"for every friend who joins!</i>"
        )

        await safe_edit_or_reply(update, text, reply_markup=back_to_menu_keyboard())

    finally:
        db.close()
