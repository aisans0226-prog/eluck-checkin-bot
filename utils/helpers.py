# ============================================================
# utils/helpers.py — Utility / helper functions
# ============================================================

import logging
import time
from datetime import date, datetime
from functools import wraps
from typing import Callable

import pytz
from telegram import Update
from telegram.ext import ContextTypes

import config

# ── Mexico City timezone (UTC-6 / UTC-5 DST) ─────────────────
MEXICO_TZ = pytz.timezone("America/Mexico_City")


def today_mexico() -> date:
    """Return the current date in Mexico City timezone."""
    return datetime.now(MEXICO_TZ).date()

logger = logging.getLogger(__name__)

# ── Rate-limit tracker: {telegram_id: last_call_timestamp} ───
_rate_limit_cache: dict[int, float] = {}


# ─────────────────────────────────────────────────────────────
# Rate-limit decorator
# Prevents users from spamming commands / callbacks
# ─────────────────────────────────────────────────────────────
def rate_limited(func: Callable) -> Callable:
    """Decorator — enforce RATE_LIMIT_SECONDS between calls per user."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else 0
        now = time.monotonic()
        last = _rate_limit_cache.get(user_id, 0)
        if now - last < config.RATE_LIMIT_SECONDS:
            # Silently ignore — do NOT answer to avoid flooding answers
            if update.callback_query:
                await update.callback_query.answer("Please slow down!", show_alert=False)
            return
        _rate_limit_cache[user_id] = now
        return await func(update, context, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────
# Admin-only guard decorator
# ─────────────────────────────────────────────────────────────
def admin_only(func: Callable) -> Callable:
    """Decorator — restrict handler to ADMIN_IDS only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else 0
        if user_id not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ You don't have permission to use this command.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────
def format_streak_bar(streak: int) -> str:
    """Return a visual fire progress bar for the streak."""
    filled = min(streak, 30)
    bar = "🔥" * (filled // 5) + "▓" * (filled % 5)
    return bar or "▒▒▒▒▒"


def format_points(points: int) -> str:
    """Add comma separator for large numbers."""
    return f"{points:,}"


def ordinal(n: int) -> str:
    """Return ordinal string: 1→1st, 2→2nd, 3→3rd, 4→4th…"""
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10 if n % 100 not in (11, 12, 13) else 0, "th")
    return f"{n}{suffix}"


def rank_emoji(rank: int) -> str:
    """Return medal emoji for top 3, number emoji otherwise."""
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    if rank in medals:
        return medals[rank]
    return f"{rank}."


def is_today(d: date | None) -> bool:
    """Check whether a date is today (Mexico City time)."""
    if d is None:
        return False
    return d == today_mexico()


# ─────────────────────────────────────────────────────────────
# Text sanitiser (prevent Telegram HTML injection)
# ─────────────────────────────────────────────────────────────
def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


# ─────────────────────────────────────────────────────────────
# Referral link builder
# ─────────────────────────────────────────────────────────────
def build_referral_link(telegram_id: int) -> str:
    return f"https://t.me/{config.BOT_USERNAME}?start=ref{telegram_id}"


# ─────────────────────────────────────────────────────────────
# Safe send — edit OR send new message (for callback handlers)
# ─────────────────────────────────────────────────────────────
async def safe_edit_or_reply(update: Update, text: str, reply_markup=None, parse_mode="HTML"):
    """
    If called from a callback query, edit the existing message.
    If called from a regular message, send a new reply.
    """
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        elif update.message:
            await update.message.reply_text(
                text=text, reply_markup=reply_markup, parse_mode=parse_mode
            )
    except Exception as exc:
        logger.warning("safe_edit_or_reply error: %s", exc)
        if update.message:
            await update.message.reply_text(
                text=text, reply_markup=reply_markup, parse_mode=parse_mode
            )
