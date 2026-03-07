# ============================================================
# handlers/profile.py — User profile & referral display
# ============================================================

import logging

from telegram import Update
from telegram.ext import ContextTypes

from models.user import User
from services.referral_service import get_referral_stats
from services.event_service import log_event, EVT_PROFILE_VIEW, EVT_REFERRAL_VIEW
from utils.keyboard import profile_keyboard, back_to_menu_keyboard
from utils.helpers import (
    format_points,
    format_streak_bar,
    build_referral_link,
    safe_edit_or_reply,
    rate_limited,
)
from utils.i18n import t
import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Internal implementation — no rate limiting, no answer()
# Called directly by menu_callback_handler (which already
# answers the query and is itself rate-limited).
# ─────────────────────────────────────────────────────────────
async def _profile_impl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Core profile display logic (no rate limiting, no answer())."""
    tg_user = update.effective_user
    if not tg_user:
        return

    db = context.bot_data["db_session"]()
    try:
        user: User | None = db.query(User).filter(User.telegram_id == tg_user.id).first()

        if not user:
            await safe_edit_or_reply(
                update,
                t("profile_not_found", "en"),
                reply_markup=back_to_menu_keyboard("en"),
            )
            return

        lang = user.language or "en"
        log_event(db, tg_user.id, EVT_PROFILE_VIEW)
        ref_stats = get_referral_stats(db, tg_user.id)
        streak_bar = format_streak_bar(user.streak)
        day_word = t("day", lang) if user.streak == 1 else t("days", lang)

        game_id_line = (
            f"{t('game_id_label', lang)}: <code>{user.game_id}</code>"
            if user.game_id
            else f"{t('game_id_label', lang)}: {t('game_id_notset', lang)}"
        )

        text = (
            f"{t('profile_header', lang)}\n"
            f"{'─' * 28}\n"
            f"{t('telegram_label', lang)}:  {user.display_name}\n"
            f"{game_id_line}\n\n"
            f"{t('streak_label', lang)}:   <b>{user.streak} {day_word}</b>  {streak_bar}\n"
            f"{t('total_checkins_label', lang)}:  <b>{user.total_checkin}</b>\n"
            f"{t('points_label', lang)}:           <b>{format_points(user.points)}</b>\n\n"
            f"{t('referrals_label', lang)}:        <b>{ref_stats['count']}</b>\n"
            f"{t('referral_points_label', lang)}:  <b>{format_points(ref_stats['total_points_earned'])}</b>"
        )

        await safe_edit_or_reply(update, text, reply_markup=profile_keyboard(lang))

    finally:
        db.close()


async def _referral_impl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Core referral display logic (no rate limiting, no answer())."""
    tg_user = update.effective_user
    if not tg_user:
        return

    db = context.bot_data["db_session"]()
    try:
        user: User | None = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if not user:
            await safe_edit_or_reply(update, t("start_first", "en"))
            return

        lang = user.language or "en"
        log_event(db, tg_user.id, EVT_REFERRAL_VIEW)
        ref_stats = get_referral_stats(db, tg_user.id)
        link = build_referral_link(tg_user.id)
        reward = context.bot_data.get("referral_reward", config.REFERRAL_REWARD)

        text = (
            f"{t('referral_header', lang)}\n"
            f"{'─' * 28}\n\n"
            f"<code>{link}</code>\n\n"
            f"{t('total_referrals_label', lang)}: <b>{ref_stats['count']}</b>\n"
            f"{t('points_earned_label', lang)}:   <b>{format_points(ref_stats['total_points_earned'])}</b>\n\n"
            f"{t('referral_tip', lang, reward=reward)}"
        )

        await safe_edit_or_reply(update, text, reply_markup=back_to_menu_keyboard(lang))

    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# Public handlers — rate-limited, answer the callback query.
# Registered as CommandHandlers (/profile, /referral) in bot.py
# ─────────────────────────────────────────────────────────────
@rate_limited
async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the user's profile card. Entry point for /profile command."""
    if update.callback_query:
        await update.callback_query.answer()
    await _profile_impl(update, context)


@rate_limited
async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user's referral link and stats. Entry point for /referral command."""
    if update.callback_query:
        await update.callback_query.answer()
    await _referral_impl(update, context)
