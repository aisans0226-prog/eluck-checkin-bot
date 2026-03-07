# ============================================================
# utils/helpers.py — Utility / helper functions
# ============================================================

import logging
import time
from datetime import date, datetime, timedelta
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


# ── Per-user timezone helpers ─────────────────────────────────

# Common timezone options shown in the selection menu.
# Each entry: (display_label, iana_zone)
TIMEZONE_OPTIONS: list[tuple[str, str]] = [
    ("🇺🇸 UTC-8  (Los Angeles)",    "America/Los_Angeles"),
    ("🇲🇽 UTC-6  (Mexico City)",    "America/Mexico_City"),
    ("🇺🇸 UTC-5  (New York)",       "America/New_York"),
    ("🇧🇷 UTC-3  (São Paulo)",      "America/Sao_Paulo"),
    ("🇬🇧 UTC+0  (London)",         "Europe/London"),
    ("🇪🇺 UTC+1  (Paris/Berlin)",   "Europe/Paris"),
    ("🇷🇺 UTC+3  (Moscow)",         "Europe/Moscow"),
    ("🇮🇳 UTC+5:30 (India)",        "Asia/Kolkata"),
    ("🌏 UTC+7  (Bangkok/Hanoi)",   "Asia/Bangkok"),
    ("🇨🇳 UTC+8  (Beijing/SG)",     "Asia/Shanghai"),
    ("🇯🇵 UTC+9  (Tokyo/Seoul)",    "Asia/Tokyo"),
    ("🇦🇺 UTC+10 (Sydney)",         "Australia/Sydney"),
]

# Map iana_zone → display_label for fast lookup
_TZ_LABEL: dict[str, str] = {iana: label for label, iana in TIMEZONE_OPTIONS}


def tz_label(iana_zone: str) -> str:
    """Return the short display label for a timezone, e.g. 'UTC+7 (Bangkok/Hanoi)'."""
    label = _TZ_LABEL.get(iana_zone)
    if label:
        # Strip the flag emoji, keep the rest
        parts = label.split(" ", 1)
        return parts[1] if len(parts) == 2 else label
    return iana_zone


def now_in_tz(iana_zone: str) -> datetime:
    """Return the current datetime in the given IANA timezone."""
    try:
        tz = pytz.timezone(iana_zone)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = MEXICO_TZ
    return datetime.now(tz)


def next_checkin_countdown(iana_zone: str) -> str:
    """
    Return a human-readable countdown string to midnight (next check-in window)
    in the user's timezone.  E.g. '14h 32m' or '45m'.
    """
    now = now_in_tz(iana_zone)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    delta = midnight - now
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def build_weekly_grid(checkin_dates: set[date], iana_zone: str) -> str:
    """
    Build a 7-day check-in grid ending today (user timezone).
    Returns two rows: day-of-week labels and check/empty markers.
    Example:
        Mo Tu We Th Fr Sa Su
        ✅ ✅ ✅ ✅ ✅ ⬜ ⬜
    """
    try:
        tz = pytz.timezone(iana_zone)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = MEXICO_TZ
    today = datetime.now(tz).date()

    day_labels = []
    markers = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day_labels.append(d.strftime("%a")[:2])   # Mo, Tu …
        markers.append("✅" if d in checkin_dates else "⬜")

    header = " ".join(day_labels)
    row = " ".join(markers)
    return f"<code>{header}</code>\n{row}"

logger = logging.getLogger(__name__)

# ── Rate-limit tracker: {telegram_id: last_call_timestamp} ───
_rate_limit_cache: dict[int, float] = {}
_RATE_CACHE_MAX_SIZE = 10_000
_RATE_CACHE_TTL = 300  # evict entries older than 5 minutes


def _cleanup_rate_cache(now: float) -> None:
    """Remove stale entries to prevent unbounded memory growth."""
    if len(_rate_limit_cache) < _RATE_CACHE_MAX_SIZE:
        return
    cutoff = now - _RATE_CACHE_TTL
    stale = [uid for uid, ts in _rate_limit_cache.items() if ts < cutoff]
    for uid in stale:
        del _rate_limit_cache[uid]


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
        _cleanup_rate_cache(now)
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
# Language helper — single source, replaces _get_lang in handlers
# ─────────────────────────────────────────────────────────────
def get_user_lang(db, telegram_id: int) -> str:
    """
    Fetch stored language preference for a user.
    Falls back to 'en' if user not found.
    Import this instead of duplicating _get_lang in each handler.
    """
    from models.user import User
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    return (user.language if user else None) or "en"


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
